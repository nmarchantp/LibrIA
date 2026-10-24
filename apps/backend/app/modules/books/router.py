"""Local-first, lossless mirror of public Google Books volume resources."""
from datetime import datetime, timezone
import logging
import re
import uuid
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.books.community import public_rating, reading_statistics
from app.modules.books.identity import canonical_book_title, canonical_title_variants, canonical_work_key
from app.modules.books.models import AlternateTitle, Author, CatalogQuery, CatalogSource, Edition, Work, WorkAuthor
from app.modules.books.service import consolidate_equivalent_works, equivalent_work_ids

router = APIRouter(prefix="/books", tags=["books"])
logger = logging.getLogger(__name__)


def publication_sort_key(value):
    """Sort partial Google dates (YYYY, YYYY-MM or YYYY-MM-DD), unknown last."""
    match = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", str(value or ""))
    if not match:
        return (9999, 12, 31)
    parts = match.groups()
    year = int(parts[0])
    month = int(parts[1]) if parts[1] else 1
    day = int(parts[2]) if parts[2] else 1
    if year < 1000 or year > 2100 or not 1 <= month <= 12 or not 1 <= day <= 31:
        return (9999, 12, 31)
    return (year, month, day)


def google_request(path="", query=None):
    params = {"projection": "full"}
    if query is not None:
        params.update(q=query, maxResults=40, langRestrict="es")
    key = get_settings().google_books_api_key
    if key:
        params["key"] = key
    try:
        with httpx.Client(timeout=20) as client:
            pages = []
            starts = (0, 40, 80) if query is not None else (0,)
            for start in starts:
                page_params = {**params, "startIndex": start} if query is not None else params
                for attempt in range(2):
                    response = client.get("https://www.googleapis.com/books/v1/volumes" + path, params=page_params)
                    if response.status_code not in {500, 502, 503, 504} or attempt == 1:
                        break
                if response.status_code == 404:
                    raise HTTPException(404, "Libro no encontrado")
                response.raise_for_status()
                page = response.json()
                if not isinstance(page, dict):
                    raise ValueError("Invalid volume response")
                pages.append(page)
                if query is None or len(page.get("items", [])) < 40:
                    break
        if query is None:
            return pages[0]
        unique = {}
        for page in pages:
            for item in page.get("items", []):
                if item.get("id"):
                    unique[item["id"]] = item
        return {**pages[0], "totalItems": len(unique), "items": list(unique.values())}
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Google Books unavailable: %s, HTTP %s", type(error).__name__,
                       error.response.status_code if isinstance(error, httpx.HTTPStatusError) else "unavailable")
        raise HTTPException(502, "No se pudo consultar Google Books. Inténtalo nuevamente.") from None


def store_volume(db, item, complete=False):
    external_id = item.get("id")
    info = item.get("volumeInfo", {})
    if not external_id or not isinstance(info, dict):
        raise HTTPException(502, "Google Books devolvió un libro sin identificación válida")
    title_variants = canonical_title_variants(info.get("title")) or {canonical_book_title(info.get("title"))}
    identity_keys = [canonical_work_key(title, info.get("authors")) for title in sorted(title_variants)]
    identity_key = identity_keys[0]
    identifiers = {value.get("type"): str(value.get("identifier", "")).replace("-", "")
                   for value in info.get("industryIdentifiers", []) if isinstance(value, dict)}
    isbn10 = identifiers.get("ISBN_10") if len(identifiers.get("ISBN_10", "")) == 10 else None
    isbn13 = identifiers.get("ISBN_13") if len(identifiers.get("ISBN_13", "")) == 13 else None
    isbn_conflict = False
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:libria-feed:" + external_id))))
    if identity_key:
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:work:" + identity_key))))
    sources = db.scalars(select(CatalogSource).where(CatalogSource.external_id == external_id,
        CatalogSource.provider.in_(["google-books", "libria-feed"]))).all()
    source = next((s for s in sources if s.provider == "google-books"), None)
    legacy = next((s for s in sources if s.provider == "libria-feed"), None)
    if source and source.detail_complete and not complete:
        return source
    edition = db.get(Edition, (source or legacy).edition_id) if sources else None
    if edition is None:
        work = db.scalar(select(Work).where(Work.identity_key.in_(identity_keys))) if identity_key else None
        isbn_edition = db.scalar(select(Edition).where(
            (Edition.isbn13 == isbn13) if isbn13 else (Edition.isbn10 == isbn10))) if isbn13 or isbn10 else None
        if isbn_edition and work and isbn_edition.work_id == work.id:
            edition = isbn_edition
        elif isbn_edition:
            isbn_conflict = True
        if work is None:
            work = Work(title=info.get("title") or "Sin título", identity_key=identity_key,
                        original_language=info.get("language"))
            db.add(work)
            db.flush()
        if edition is None:
            edition = Edition(work_id=work.id, title=work.title, language=info.get("language") or "und")
            db.add(edition)
            db.flush()
    work = db.get(Work, edition.work_id)
    edition.title = info.get("title") or edition.title
    if len(edition.title) < len(work.title):
        work.title = edition.title
    edition.description = info.get("description")
    work.description = work.description or edition.description
    edition.language = info.get("language") or "und"
    edition.publication_date = info.get("publishedDate")
    try:
        edition.publication_year = int(str(info.get("publishedDate", ""))[:4]) or None
    except ValueError:
        edition.publication_year = None
    edition.format = info.get("printType")
    conflicting_edition = db.scalar(select(Edition).where(Edition.id != edition.id,
        ((Edition.isbn13 == isbn13) if isbn13 else (Edition.isbn10 == isbn10)))) if isbn13 or isbn10 else None
    isbn_conflict = isbn_conflict or conflicting_edition is not None
    if not isbn_conflict:
        edition.isbn10, edition.isbn13 = isbn10, isbn13
    pages = info.get("pageCount")
    edition.page_count = pages if isinstance(pages, int) and pages > 0 else None
    edition.publisher_name = info.get("publisher")
    edition.cover_url = info.get("imageLinks", {}).get("thumbnail")
    work.categories = work.categories or info.get("categories")
    work.first_publication_date = work.first_publication_date or info.get("publishedDate")
    for normalized_title in title_variants:
        alternate = db.scalar(select(AlternateTitle).where(AlternateTitle.work_id == work.id,
            AlternateTitle.normalized_title == normalized_title,
            AlternateTitle.language == info.get("language")))
        if normalized_title and alternate is None:
            db.add(AlternateTitle(work_id=work.id, title=info.get("title"), normalized_title=normalized_title,
                                  language=info.get("language")))
    for position, author_name in enumerate(info.get("authors") or [], 1):
        author = db.scalar(select(Author).where(func.lower(Author.name) == str(author_name).casefold()))
        if author is None:
            author = Author(name=author_name)
            db.add(author)
            db.flush()
        if db.get(WorkAuthor, (work.id, author.id)) is None:
            db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=position))
    if source is None:
        source = CatalogSource(edition_id=edition.id, provider="google-books", external_id=external_id)
        db.add(source)
    source.payload = item
    source.consolidation_status = "pending_isbn_conflict" if isbn_conflict else "automatic"
    source.detail_complete = complete
    source.fetched_at = source.synced_at = datetime.now(timezone.utc)
    # Keep existing reading references while pointing both providers to one edition.
    if legacy is None:
        db.add(CatalogSource(edition_id=edition.id, provider="libria-feed", external_id=external_id,
                             fetched_at=source.fetched_at))
    db.flush()
    return source


def is_spanish(value):
    aliases = {"es", "spa", "spanish", "español"}
    return (isinstance(value, str)
            and value.casefold().split("-", 1)[0] in aliases)


def source_payload(db, source):
    if source.payload:
        return source.payload
    edition = db.get(Edition, source.edition_id)
    return {"kind": "books#volume", "id": source.external_id, "volumeInfo": {
        "title": edition.title, "language": edition.language, "pageCount": edition.page_count,
        "description": edition.description, "publisher": edition.publisher_name,
        "publishedDate": edition.publication_date, "printType": edition.format,
        "industryIdentifiers": [
            *([{"type": "ISBN_13", "identifier": edition.isbn13}] if edition.isbn13 else []),
            *([{"type": "ISBN_10", "identifier": edition.isbn10}] if edition.isbn10 else []),
        ],
        "imageLinks": {"thumbnail": edition.cover_url} if edition.cover_url else {}}}


def work_payload(db, work_id, preferred_source=None, include_reading_stats=False):
    work_ids = equivalent_work_ids(db, work_id) or {work_id}
    rows = db.execute(select(CatalogSource, Edition).join(Edition, CatalogSource.edition_id == Edition.id)
                      .where(Edition.work_id.in_(work_ids), CatalogSource.provider == "google-books")
                      .order_by(Edition.language, Edition.title, CatalogSource.external_id)).all()
    if not rows:
        rows = db.execute(select(CatalogSource, Edition).join(Edition, CatalogSource.edition_id == Edition.id)
                          .where(Edition.work_id.in_(work_ids)).order_by(Edition.title)).all()
    if not rows:
        return None
    localized = next(((source, edition) for source, edition in rows
                      if is_spanish(edition.language)), None)
    preferred = next(((source, edition) for source, edition in rows
                      if source.external_id == preferred_source), None)
    source, edition = localized or preferred or rows[0]
    payload = source_payload(db, source)
    editions = [{"id": str(row_edition.id), "externalId": row_source.external_id,
                 "title": row_edition.title, "language": row_edition.language,
                 "publisher": row_edition.publisher_name, "pageCount": row_edition.page_count,
                 "coverUrl": row_edition.cover_url, "publishedDate": row_edition.publication_date,
                 "format": row_edition.format, "isbn10": row_edition.isbn10,
                 "isbn13": row_edition.isbn13}
                for row_source, row_edition in rows]
    known_dates = [row_edition.publication_date for _, row_edition in rows
                   if publication_sort_key(row_edition.publication_date)[0] != 9999]
    first_publication_date = min(known_dates, key=publication_sort_key) if known_dates else None
    rating_average, rating_count = public_rating(db, work_ids)
    reading_stats = reading_statistics(db, work_ids) if include_reading_stats else None
    return {**payload, "id": str(work_id), "libria": {"workId": str(work_id),
            "editionId": str(edition.id), "externalId": source.external_id,
            "catalogOrigin": "google_books" if source.provider == "google-books" else "libria",
            "editionCount": len({row_edition.id for _, row_edition in rows}), "editions": editions,
            "firstPublicationDate": first_publication_date,
            "averageRating": round(float(rating_average), 2) if rating_average is not None else None,
            "ratingsCount": rating_count,
            **({"readingStats": reading_stats} if reading_stats is not None else {})}}


def local_works(db, query, search_by, limit=40):
    google_source = aliased(CatalogSource)
    mirrored = select(google_source.id).where(google_source.edition_id == CatalogSource.edition_id,
        google_source.provider == "google-books").exists()
    statement = select(CatalogSource, Edition).join(Edition, CatalogSource.edition_id == Edition.id).where(
        (CatalogSource.provider == "google-books") | ((CatalogSource.provider == "libria-feed") & ~mirrored))
    if query:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        if search_by == "isbn":
            statement = statement.where(cast(CatalogSource.payload["volumeInfo"]["industryIdentifiers"], Text)
                                        .ilike(pattern, escape="\\"))
    rows = db.execute(statement.order_by(Edition.title, CatalogSource.external_id).limit(1000)).all()
    # Keep the user-facing catalog strictly Spanish even for legacy rows or
    # incorrectly broad cached/provider responses.
    rows = [row for row in rows if is_spanish(row[1].language)]
    if query and search_by != "isbn":
        needle = canonical_book_title(query)
        def matches(row):
            source, edition = row
            info = source.payload.get("volumeInfo", {}) if source.payload else {}
            titles = [edition.title, info.get("title", ""), info.get("subtitle", "")]
            authors = info.get("authors") or []
            fields = authors if search_by == "author" else titles + (authors if search_by == "all" else [])
            return any(needle in canonical_book_title(value) for value in fields)
        rows = [row for row in rows if matches(row)]
    works = {}
    for source, edition in rows:
        works.setdefault(edition.work_id, source.external_id)
    items, seen = [], set()
    for work_id, external_id in works.items():
        group = equivalent_work_ids(db, work_id) or {work_id}
        if group & seen:
            continue
        seen.update(group)
        item = work_payload(db, work_id, external_id)
        if item:
            items.append(item)
    normalized_query = canonical_book_title(query)
    def relevance(item):
        info = item.get("volumeInfo", {})
        title = canonical_book_title(info.get("title"))
        exact = title == normalized_query
        starts = bool(normalized_query and title.startswith(normalized_query))
        completeness = sum(bool(info.get(field)) for field in ("authors", "description", "publishedDate", "imageLinks"))
        publication = publication_sort_key(item.get("libria", {}).get("firstPublicationDate"))
        return (publication, 0 if exact else 1 if starts else 2, -completeness, title)
    return sorted(items, key=relevance)[:limit]


def consolidate_catalog_matches(db, query, search_by):
    """Physically normalize any duplicate groups reached by this search."""
    matches = local_works(db, query, search_by, limit=1000)
    for item in matches:
        consolidate_equivalent_works(db, uuid.UUID(item["libria"]["workId"]))


@router.get("")
def search_books(db: Annotated[Session, Depends(get_db)], q: str = Query(default="", max_length=200),
                 search_by: Literal["all", "title", "author", "isbn"] = "all"):
    query = q.strip()
    # Google's intitle operator is unexpectedly narrow for multi-word saga names
    # (for example, it only exposes a couple of Spanish Harry Potter records).
    # General relevance gives the title tab the expected discovery behaviour.
    google_query = ({"author": "inauthor:", "isbn": "isbn:"}.get(search_by, "") + query)
    # Version the cache because older entries may contain non-Spanish results.
    key = "es-only-v2:" + search_by + ":" + query.casefold()
    consolidate_catalog_matches(db, query, search_by)
    # Search is also the catalog synchronization boundary; persist physical
    # consolidation even when no Google request is necessary afterwards.
    db.commit()
    db.expire_all()
    items = local_works(db, query, search_by)
    total = len(items)
    if not query:
        return {"kind": "books#volumes", "totalItems": total, "items": items}
    exact = any(canonical_book_title(item.get("volumeInfo", {}).get("title")) == canonical_book_title(query)
                for item in items)
    cached = db.get(CatalogQuery, key)
    if exact or len(items) >= 5 or cached:
        return {"kind": "books#volumes", "totalItems": total, "items": items}
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:query:" + key))))
    try:
        result = google_request(query=google_query)
    except HTTPException as error:
        if error.status_code != 502:
            raise
        return {"totalItems": total, "items": items, "partial": True,
                "warning": "Google Books no está disponible en este momento. Mostramos solo coincidencias guardadas; pueden faltar libros. Vuelve a intentar la búsqueda."}
    external_items = result.get("items", [])
    for item in sorted(external_items, key=lambda value: value["id"]):
        if is_spanish(item.get("volumeInfo", {}).get("language")):
            store_volume(db, item)
    consolidate_catalog_matches(db, query, search_by)
    db.flush()
    db.expire_all()
    items = local_works(db, query, search_by)
    result = {"kind": "books#volumes", "totalItems": len(items), "items": items}
    cached = db.get(CatalogQuery, key)
    if cached:
        cached.payload, cached.fetched_at = result, datetime.now(timezone.utc)
    else:
        db.add(CatalogQuery(query=key, payload=result, fetched_at=datetime.now(timezone.utc)))
    db.commit()
    return result


@router.get("/{volume_id}")
def get_book(volume_id: str, response: Response, db: Annotated[Session, Depends(get_db)]):
    response.headers["Cache-Control"] = "no-store"
    try:
        work_id = uuid.UUID(volume_id)
    except ValueError:
        work_id = None
    if work_id and db.get(Work, work_id):
        return work_payload(db, work_id, include_reading_stats=True)
    if work_id and (edition := db.get(Edition, work_id)):
        return work_payload(db, edition.work_id, include_reading_stats=True)
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == "google-books", CatalogSource.external_id == volume_id))
    if source and source.detail_complete:
        edition = db.get(Edition, source.edition_id)
        return work_payload(db, edition.work_id, preferred_source=volume_id, include_reading_stats=True)
    if source is None and (":" in volume_id or volume_id.isdigit()):
        legacy = db.scalar(select(CatalogSource).where(CatalogSource.provider == "libria-feed", CatalogSource.external_id == volume_id))
        if legacy:
            edition = db.get(Edition, legacy.edition_id)
            return work_payload(db, edition.work_id, preferred_source=volume_id, include_reading_stats=True)
    item = google_request("/" + quote(volume_id, safe=""))
    if item.get("id") != volume_id:
        raise HTTPException(502, "Google Books devolvió un identificador diferente")
    source = store_volume(db, item, complete=True)
    db.commit()
    edition = db.get(Edition, source.edition_id)
    return work_payload(db, edition.work_id, preferred_source=volume_id, include_reading_stats=True)
