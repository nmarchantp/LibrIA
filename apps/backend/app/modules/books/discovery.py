"""Read catalog / discover providers. The only writable table is CatalogQuery."""
from datetime import datetime, timezone
import uuid
from urllib.parse import quote

from fastapi import HTTPException
from app.core.config import get_settings
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.modules.books import open_library
from app.modules.books.evidence import ExternalReference, BibliographicDataError
from app.modules.books.google_books import google_request, valid_volume
from app.modules.books.models import CatalogQuery, CatalogSource, Edition, Work
from app.modules.books.catalog_models import WorkReference
from app.modules.books.policy import provider_budget


def external_payload(item, provider):
    if not valid_volume(item):
        raise HTTPException(502, "El proveedor devolvió una ficha inválida")
    raw_id = item["id"].removeprefix("openlibrary:") if provider == "open-library" else item["id"]
    try:
        ref = ExternalReference(provider, "edition" if provider == "open-library" else "volume", raw_id)
    except BibliographicDataError as error:
        raise HTTPException(502, str(error)) from None
    external_id = ("openlibrary:" if provider == "open-library" else "") + ref.external_id
    # No provider-supplied workId or cache metadata can impersonate an internal work.
    return {**item, "id": external_id, "libria": {
        "catalogOrigin": "open_library" if provider == "open-library" else "google_books",
        "catalogFlow": "discovery-v1", "discoveryOnly": True, "externalId": external_id,
        "editionOptional": get_settings().catalog_editionless_enabled,
        "selectionReference": ref.as_dict(), "editionCount": 1,
        "averageRating": None, "ratingsCount": 0,
        "readingStats": {"finished": 0, "reading": 0, "abandoned": 0, "readerPreview": []}}}


def _present(db, item, provider):
    from app.modules.books.router import work_payload
    payload = external_payload(item, provider)
    ref = payload["libria"]["selectionReference"]
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == ref["provider"],
                                                  CatalogSource.external_id == ref["external_id"]))
    if source:
        edition = db.get(Edition, source.edition_id)
        return work_payload(db, edition.work_id)
    binding = _publication_binding(db, ref["provider"], ref["external_id"])
    if binding:
        return work_payload(db, binding.work_id)
    from app.modules.books.catalog_identity import matching_work
    from app.modules.books.identity import bibliographic_title
    from app.modules.books.evidence import normalize_isbns
    info = item["volumeInfo"]
    try:
        ten, thirteen = normalize_isbns([value.get("identifier") for value in info.get("industryIdentifiers") or []
            if isinstance(value, dict) and value.get("type") in {"ISBN_10", "ISBN_13"}])
    except BibliographicDataError:
        ten = thirteen = None
    if ten or thirteen:
        from sqlalchemy import or_
        edition = db.scalar(select(Edition).where(or_(
            *([Edition.isbn10 == ten] if ten else []),
            *([Edition.isbn13 == thirteen] if thirteen else []))))
        if edition:
            return work_payload(db, edition.work_id)
    work = matching_work(db, bibliographic_title(info), info.get("authors") or [])
    if work:
        return work_payload(db, work.id)
    return payload


def _publication_binding(db, provider, reference):
    return db.scalar(select(WorkReference).where(WorkReference.provider == provider,
        WorkReference.external_id == reference, WorkReference.reference_type.in_(["volume", "edition"]),
        WorkReference.verification_status.in_(["provisional", "confirmed"])))


def search(db, query, search_by, provider, refresh, start_index, page):
    from app.modules.books.router import is_spanish, local_works, search_warning
    key = f"discovery-v1:{search_by}:{query.casefold()}:{provider}:{page if provider == 'open_library' else start_index}"
    local = local_works(db, query, search_by, limit=max(40, start_index + 40))
    if not query:
        return {"items": local, "totalItems": len(local)}
    cached = db.get(CatalogQuery, key)
    stored = dict(cached.payload or {}) if cached else None
    age = (datetime.now(timezone.utc) - cached.fetched_at).total_seconds() if cached else float("inf")
    ttl = 30 if stored and stored.get("partial") else 600 if stored and not stored.get("items") else 86400
    cooldown = max(10, (stored or {}).get("retry_after", 0))
    use_cache = stored is not None and age < max(ttl, (stored or {}).get("retry_after", 0)) and (not refresh or age < cooldown)
    db.rollback()  # never hold PostgreSQL transactions across remote I/O
    if use_cache:
        result = stored
    else:
        result = {"items": [], "active_provider": provider}
        fallback_attempted = False
        try:
            with provider_budget():
                if provider == "google_books":
                    result = {**google_request(query={"author": "inauthor:", "isbn": "isbn:"}.get(search_by, "") + query,
                                               start_index=start_index), "active_provider": "google_books"}
                if provider == "open_library" or result.get("partial") or not result.get("items"):
                    fallback_attempted = True
                    fallback = open_library.search(query, search_by, page if provider == "open_library" else 1)
                    if fallback.get("items") or not result.get("items"):
                        result = {**fallback, "active_provider": "open_library"}
        except HTTPException as error:
            if provider == "google_books" and not result.get("items") and not fallback_attempted:
                try:
                    with provider_budget():
                        result = {**open_library.search(query, search_by, 1), "active_provider": "open_library"}
                except HTTPException:
                    pass
            if not result.get("items"):
                result.update(partial=True, has_more=False, error_code="external_unavailable",
                              warning="La búsqueda externa está temporalmente limitada; mostramos los resultados disponibles.")
        raw = result.get("items") if isinstance(result.get("items"), list) else []
        result["items"] = [item for item in raw if valid_volume(item) and is_spanish(item["volumeInfo"].get("language"))]
        if result.get("partial") and stored:
            result["items"] = list({item["id"]: item for item in stored.get("items", []) + result["items"]}.values())
        # Raw external snapshots only. Re-presentation always reads the current catalog.
        db.execute(insert(CatalogQuery).values(query=key, payload=result, fetched_at=datetime.now(timezone.utc))
                   .on_conflict_do_update(index_elements=[CatalogQuery.query],
                     set_={"payload": result, "fetched_at": datetime.now(timezone.utc)}))
        db.commit()
    local = local_works(db, query, search_by, limit=max(40, start_index + 40))
    external = []
    for item in result.get("items", []):
        provider_name = "open-library" if item["id"].startswith("openlibrary:") else "google-books"
        try:
            external.append(_present(db, item, provider_name))
        except HTTPException:
            continue
    items = list({item["id"]: item for item in local + external}.values())
    payload = {**result, "items": items, "totalItems": len(items)}
    if payload.get("partial"):
        payload["warning"] = search_warning(payload)
    return payload


def detail(db, reference):
    from app.modules.books.router import work_payload
    from app.modules.books.canonical import enabled, reference_work
    if enabled():
        # Validate exact bindings even when presentation preserves a selected edition.
        reference_work(db,reference)
    try:
        internal_id = uuid.UUID(reference)
    except ValueError:
        internal_id = None
    if internal_id:
        work = db.get(Work, internal_id)
        edition = db.get(Edition, internal_id)
        if work or edition:
            return work_payload(db, work.id if work else edition.work_id, include_reading_stats=True,
                                preferred_edition_id=edition.id if edition and not work else None)
    raw_id = reference.removeprefix("openlibrary:").removeprefix("googlebooks:")
    provider = "open-library" if reference.startswith("openlibrary:") else "google-books"
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == provider, CatalogSource.external_id == raw_id))
    if source is None:
        source = db.scalar(select(CatalogSource).where(CatalogSource.provider == "libria-feed", CatalogSource.external_id == reference))
    if source:
        edition = db.get(Edition, source.edition_id)
        return work_payload(db, edition.work_id, preferred_source=raw_id, include_reading_stats=True)
    if get_settings().catalog_editionless_enabled:
        binding = _publication_binding(db, provider, raw_id)
        if binding:
            payload = work_payload(db, binding.work_id, include_reading_stats=True)
            payload["libria"]["selectionReference"] = {"provider": provider,
                "reference_type": "edition" if provider == "open-library" else "volume", "external_id": raw_id}
            return payload
    db.rollback()
    with provider_budget():
        item = open_library.detail(raw_id) if provider == "open-library" else google_request("/" + quote(raw_id, safe=""))
    if provider == "google-books" and item.get("id") != raw_id:
        raise HTTPException(502, "Google Books devolvió un identificador diferente")
    return external_payload(item, provider)
