"""Local-first, lossless mirror of public Google Books volume resources."""
from datetime import datetime, timezone
import logging
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.books.models import CatalogQuery, CatalogSource, Edition, Work

router = APIRouter(prefix="/books", tags=["books"])
logger = logging.getLogger(__name__)


def google_request(path="", query=None):
    params = {"projection": "full"}
    if query is not None:
        params.update(q=query, maxResults=40)
    key = get_settings().google_books_api_key
    if key:
        params["key"] = key
    try:
        with httpx.Client(timeout=20) as client:
            for attempt in range(2):
                response = client.get("https://www.googleapis.com/books/v1/volumes" + path, params=params)
                if response.status_code not in {500, 502, 503, 504} or attempt == 1:
                    break
        if response.status_code == 404:
            raise HTTPException(404, "Libro no encontrado")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid volume response")
        return data
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Google Books unavailable: %s, HTTP %s", type(error).__name__,
                       error.response.status_code if isinstance(error, httpx.HTTPStatusError) else "unavailable")
        raise HTTPException(502, "No se pudo consultar Google Books. Inténtalo nuevamente.") from None


def store_volume(db, item, complete=False):
    external_id = item.get("id")
    info = item.get("volumeInfo", {})
    if not external_id or not isinstance(info, dict):
        raise HTTPException(502, "Google Books devolvió un libro sin identificación válida")
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:libria-feed:" + external_id))))
    sources = db.scalars(select(CatalogSource).where(CatalogSource.external_id == external_id,
        CatalogSource.provider.in_(["google-books", "libria-feed"]))).all()
    source = next((s for s in sources if s.provider == "google-books"), None)
    legacy = next((s for s in sources if s.provider == "libria-feed"), None)
    if source and source.detail_complete and not complete:
        return source
    edition = db.get(Edition, (source or legacy).edition_id) if sources else None
    if edition is None:
        work = Work(title=info.get("title") or "Sin título")
        db.add(work)
        db.flush()
        edition = Edition(work_id=work.id, title=work.title, language=info.get("language") or "und")
        db.add(edition)
        db.flush()
    work = db.get(Work, edition.work_id)
    edition.title = work.title = info.get("title") or edition.title
    edition.description = work.description = info.get("description")
    edition.language = info.get("language") or "und"
    pages = info.get("pageCount")
    edition.page_count = pages if isinstance(pages, int) and pages > 0 else None
    edition.publisher_name = info.get("publisher")
    edition.cover_url = info.get("imageLinks", {}).get("thumbnail")
    if source is None:
        source = CatalogSource(edition_id=edition.id, provider="google-books", external_id=external_id)
        db.add(source)
    source.payload = item
    source.detail_complete = complete
    source.fetched_at = datetime.now(timezone.utc)
    # Keep existing reading references while pointing both providers to one edition.
    if legacy is None:
        db.add(CatalogSource(edition_id=edition.id, provider="libria-feed", external_id=external_id,
                             fetched_at=source.fetched_at))
    db.flush()
    return source


@router.get("")
def search_books(db: Annotated[Session, Depends(get_db)], q: str = Query(default="", max_length=200)):
    query = q.strip()
    key = query.casefold()
    if query:
        cached = db.get(CatalogQuery, key)
        if cached:
            return cached.payload
    google_source = aliased(CatalogSource)
    mirrored = select(google_source.id).where(google_source.edition_id == CatalogSource.edition_id,
        google_source.provider == "google-books").exists()
    statement = select(CatalogSource).join(Edition, CatalogSource.edition_id == Edition.id).where(
        (CatalogSource.provider == "google-books") | ((CatalogSource.provider == "libria-feed") & ~mirrored))
    if query:
        # Search all bibliographic fields, including authors, categories and ISBNs.
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        statement = statement.where(cast(CatalogSource.payload["volumeInfo"], Text).ilike(pattern, escape="\\") | Edition.title.ilike(pattern, escape="\\"))
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    local = db.scalars(statement.order_by(CatalogSource.external_id).limit(12)).all()
    # Local matches are only a browse view, never a complete search result.
    if not query:
        items = []
        for source in local:
            if source.payload:
                items.append(source.payload)
            else:
                edition = db.get(Edition, source.edition_id)
                items.append({"kind": "books#volume", "id": source.external_id, "volumeInfo": {
                    "title": edition.title, "language": edition.language, "pageCount": edition.page_count,
                    "description": edition.description, "publisher": edition.publisher_name,
                    "imageLinks": {"thumbnail": edition.cover_url} if edition.cover_url else {}}})
        return {"kind": "books#volumes", "totalItems": total, "items": items}
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:query:" + key))))
    cached = db.get(CatalogQuery, key)
    if cached:
        return cached.payload
    try:
        result = google_request(query=query)
    except HTTPException as error:
        if error.status_code != 502:
            raise
        items = []
        for source in local:
            if source.payload:
                items.append(source.payload)
            else:
                edition = db.get(Edition, source.edition_id)
                items.append({"id": source.external_id, "volumeInfo": {
                    "title": edition.title, "pageCount": edition.page_count,
                    "imageLinks": {"thumbnail": edition.cover_url} if edition.cover_url else {}}})
        return {"totalItems": total, "items": items, "partial": True,
                "warning": "Google Books no está disponible en este momento. Mostramos solo coincidencias guardadas; pueden faltar libros. Vuelve a intentar la búsqueda."}
    for item in sorted(result.get("items", []), key=lambda value: value["id"]):
        store_volume(db, item)
    db.add(CatalogQuery(query=key, payload=result, fetched_at=datetime.now(timezone.utc)))
    db.commit()
    return result


@router.get("/{volume_id}")
def get_book(volume_id: str, db: Annotated[Session, Depends(get_db)]):
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == "google-books", CatalogSource.external_id == volume_id))
    if source and source.detail_complete:
        return source.payload
    if source is None and (":" in volume_id or volume_id.isdigit()):
        legacy = db.scalar(select(CatalogSource).where(CatalogSource.provider == "libria-feed", CatalogSource.external_id == volume_id))
        if legacy:
            edition = db.get(Edition, legacy.edition_id)
            return {"id": volume_id, "kind": "books#volume", "volumeInfo": {"title": edition.title,
                "language": edition.language, "pageCount": edition.page_count, "description": edition.description}}
    item = google_request("/" + quote(volume_id, safe=""))
    if item.get("id") != volume_id:
        raise HTTPException(502, "Google Books devolvió un identificador diferente")
    source = store_volume(db, item, complete=True)
    db.commit()
    return source.payload
