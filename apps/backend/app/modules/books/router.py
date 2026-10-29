"""Local-first, lossless mirror of public Google Books volume resources."""
from datetime import datetime, timezone
import re
import uuid
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.database import get_db
from app.core.config import get_settings
from app.modules.books.google_books import google_request, safe_volume_info, valid_volume
from app.modules.books import open_library
from app.modules.books.open_library_catalog import ensure_edition, present as present_open_library
from app.modules.books.community import public_rating, reading_statistics
from app.modules.books.identity import bibliographic_title, canonical_book_title, canonical_title_variants, canonical_work_key
from app.modules.books.models import AlternateTitle, Author, CatalogQuery, CatalogSource, Edition, Work, WorkAuthor
from app.modules.books.service import equivalent_work_ids, verified_original_publication, verified_work_for_import

router = APIRouter(prefix="/books", tags=["books"])


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


def store_volume(db, item, complete=False):
    from app.modules.books.policy import reject_legacy_writer
    reject_legacy_writer()
    external_id = item.get("id")
    info = safe_volume_info(item)
    if not external_id or not isinstance(info, dict):
        raise HTTPException(502, "Google Books devolvió un libro sin identificación válida")
    title_variants = canonical_title_variants(bibliographic_title(info)) or {canonical_book_title(info.get("title"))}
    identity_keys = [key for title in sorted(title_variants)
                     if (key := canonical_work_key(title, info.get("authors")))]
    identity_key = identity_keys[0] if identity_keys else None
    identifiers = {value.get("type"): str(value.get("identifier", "")).replace("-", "")
                   for value in info.get("industryIdentifiers", []) if isinstance(value, dict)}
    isbn10 = identifiers.get("ISBN_10") if len(identifiers.get("ISBN_10", "")) == 10 else None
    isbn13 = identifiers.get("ISBN_13") if len(identifiers.get("ISBN_13", "")) == 13 else None
    isbn_conflict = False
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:libria-feed:" + external_id))))
    from app.modules.books.open_library_catalog import identifiers
    valid_ten, valid_thirteen = identifiers(item)
    if valid_ten or valid_thirteen:
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext('catalog:isbn:' + (valid_thirteen or valid_ten)))))
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
        from app.modules.books.open_library_catalog import find_existing
        verified = find_existing(db, item)
        if verified and db.scalar(select(CatalogSource.id).where(CatalogSource.edition_id == verified.id, CatalogSource.provider == 'open-library').limit(1)):
            edition = verified
    if edition is None:
        work = verified_work_for_import(db, bibliographic_title(info), info.get("authors"))
        isbn_edition = db.scalar(select(Edition).where(
            (Edition.isbn13 == isbn13) if isbn13 else (Edition.isbn10 == isbn10))) if isbn13 or isbn10 else None
        if isbn_edition and work and isbn_edition.work_id == work.id:
            edition = isbn_edition
        elif isbn_edition:
            isbn_conflict = True
        if work is None:
            if identity_key and db.scalar(select(Work.id).where(Work.identity_key == identity_key)):
                identity_key = None  # Existing incompatible evidence: preserve both records.
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
    edition.description = info.get("description") or edition.description
    work.description = work.description or edition.description
    edition.language = info.get("language") or edition.language or "und"
    edition.publication_date = info.get("publishedDate") or edition.publication_date
    try:
        edition.publication_year = int(str(edition.publication_date or "")[:4]) or edition.publication_year
    except ValueError:
        pass
    edition.format = info.get("printType") or edition.format
    conflicting_edition = db.scalar(select(Edition).where(Edition.id != edition.id,
        ((Edition.isbn13 == isbn13) if isbn13 else (Edition.isbn10 == isbn10)))) if isbn13 or isbn10 else None
    isbn_conflict = isbn_conflict or conflicting_edition is not None
    if not isbn_conflict:
        edition.isbn10, edition.isbn13 = isbn10 or edition.isbn10, isbn13 or edition.isbn13
    pages = info.get("pageCount")
    edition.page_count = pages if isinstance(pages, int) and pages > 0 else edition.page_count
    edition.publisher_name = info.get("publisher") or edition.publisher_name
    edition.cover_url = info.get("imageLinks", {}).get("thumbnail") or edition.cover_url
    work.categories = work.categories or info.get("categories")
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
    editorial = db.scalar(select(CatalogSource).where(CatalogSource.edition_id == source.edition_id,
        CatalogSource.provider == 'libria-editorial'))
    if editorial:
        return {**(source.payload or {}), "id": source.external_id,
                "volumeInfo": {**((source.payload or {}).get('volumeInfo') or {}), **editorial.payload['volumeInfo']}}
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


def work_payload(db, work_id, preferred_source=None, include_reading_stats=False, preferred_edition_id=None):
    canonical_mode = get_settings().catalog_discovery_enabled
    if canonical_mode:
        from app.modules.books.canonical import canonical_members, resolve_canonical_work
        work_id = resolve_canonical_work(db, work_id).canonical_work_id
        work_ids = canonical_members(db, work_id)
    else:
        work_ids = equivalent_work_ids(db, work_id) or {work_id}
    if get_settings().catalog_editionless_enabled and not preferred_source and not preferred_edition_id:
        work = db.get(Work, work_id)
        editions = db.scalars(select(Edition).where(Edition.work_id.in_(work_ids)).order_by(Edition.created_at, Edition.id)).all()
        cover = next((edition.cover_url for edition in editions if edition.cover_url), None)
        if not cover:
            for source in db.scalars(select(CatalogSource).where(CatalogSource.edition_id.in_([e.id for e in editions])).order_by(CatalogSource.id)):
                images = safe_volume_info(source.payload or {}).get("imageLinks") or {}
                cover = images.get("thumbnail") or images.get("smallThumbnail")
                if cover:
                    break
        members = db.scalars(select(Work).where(Work.id.in_(work_ids)).order_by(Work.created_at, Work.id)).all()
        description = work.description or next((member.description for member in members if member.description), None)
        average, count = public_rating(db, work_ids)
        return {"id": str(work_id), "volumeInfo": {"title": work.title, "description": description,
            "imageLinks": {"thumbnail": cover} if cover else {},
            "categories": work.categories or [], "authors": db.scalars(select(Author.name).join(WorkAuthor,
                Author.id == WorkAuthor.author_id).where(WorkAuthor.work_id == work_id)).all()},
            "libria": {"workId": str(work_id), "editionId": None, "editionOptional": True,
                "catalogOrigin": "libria", "catalogFlow": "discovery-v1", "editionCount": len(editions),
                "averageRating": float(average) if average is not None else None, "ratingsCount": count,
                "readingStats": reading_statistics(db, work_ids),
                "editions": [{"id": str(e.id), "title": e.title, "language": e.language,
                    "pageCount": e.page_count, "publisher": e.publisher_name, "coverUrl": e.cover_url,
                    "format": e.format, "isbn10": e.isbn10, "isbn13": e.isbn13} for e in editions]}}
    all_rows = db.execute(select(CatalogSource, Edition).join(Edition, CatalogSource.edition_id == Edition.id)
        .where(Edition.work_id.in_(work_ids))).all()
    priority = {"google-books": 0, "open-library": 1, "libria-feed": 2}
    chosen = {}
    for source, edition in sorted((row for row in all_rows if row[0].provider in priority), key=lambda row: (priority.get(row[0].provider, 3), row[1].language, row[1].title)):
        chosen.setdefault(edition.id, (source, edition))
    rows = list(chosen.values())
    if not rows:
        if canonical_mode:
            work = db.get(Work, work_id)
            editions = db.scalars(select(Edition).where(Edition.work_id.in_(work_ids)).order_by(Edition.created_at, Edition.id)).all()
            edition = next((e for e in editions if e.id == preferred_edition_id), None) or (editions[0] if editions else None)
            return {"id": str(work_id), "volumeInfo": {"title": edition.title if edition else work.title,
                    "description": work.description, "categories": work.categories or [],
                    "authors": db.scalars(select(Author.name).join(WorkAuthor, Author.id == WorkAuthor.author_id).where(WorkAuthor.work_id == work_id)).all()},
                    "libria": {"workId": str(work_id), "editionId": str(edition.id) if edition else None,
                    "catalogOrigin": "libria", "catalogFlow": "discovery-v1", "editionCount": len(editions),
                    "editions": [{"id": str(e.id), "title": e.title, "language": e.language,
                                  "pageCount": e.page_count, "publisher": e.publisher_name} for e in editions]}}
        return None
    localized = next(((source, edition) for source, edition in rows
                      if is_spanish(edition.language)), None)
    preferred = next(((source, edition) for source, edition in rows
                      if source.external_id == preferred_source), None)
    if canonical_mode and preferred_edition_id:
        preferred = next(((source, edition) for source, edition in rows if edition.id == preferred_edition_id), preferred)
    source, edition = (preferred if preferred and (canonical_mode or is_spanish(preferred[1].language)) else None) or localized or preferred or rows[0]
    payload = source_payload(db, source)
    editions = [{"id": str(row_edition.id), "externalId": ('openlibrary:' if row_source.provider == 'open-library' else '') + row_source.external_id,
                 "title": row_edition.title, "language": row_edition.language,
                 "publisher": row_edition.publisher_name, "pageCount": row_edition.page_count,
                 "coverUrl": row_edition.cover_url, "publishedDate": row_edition.publication_date,
                 "format": row_edition.format, "isbn10": row_edition.isbn10,
                 "isbn13": row_edition.isbn13}
                for row_source, row_edition in rows]
    known_dates = [row_edition.publication_date for _, row_edition in rows
                   if publication_sort_key(row_edition.publication_date)[0] != 9999]
    earliest_edition_date = min(known_dates, key=publication_sort_key) if known_dates else None
    first_publication_date = verified_original_publication(db, work_id)
    rating_average, rating_count = public_rating(db, work_ids)
    reading_stats = reading_statistics(db, work_ids) if include_reading_stats else None
    return {**payload, "id": str(work_id), "libria": {**payload.get('libria', {}), "workId": str(work_id),
            "editionId": str(edition.id), "externalId": ('openlibrary:' if source.provider == 'open-library' else '') + source.external_id,
            **({"catalogFlow": "discovery-v1", "editionOptional": get_settings().catalog_editionless_enabled} if canonical_mode else {}),
            "catalogOrigin": "libria", "sourceProvider": source.provider,
            "editionCount": len({row_edition.id for _, row_edition in rows}), "editions": editions,
            "firstPublicationDate": first_publication_date,
            "originalPublicationVerified": first_publication_date is not None,
            "earliestEditionDate": earliest_edition_date,
            "averageRating": round(float(rating_average), 2) if rating_average is not None else None,
            "ratingsCount": rating_count,
            **({"readingStats": reading_stats} if reading_stats is not None else {})}}


def local_works(db, query, search_by, limit=40):
    google_source = aliased(CatalogSource)
    mirrored = select(google_source.id).where(google_source.edition_id == CatalogSource.edition_id,
        google_source.provider == "google-books").exists()
    statement = select(CatalogSource, Edition).join(Edition, CatalogSource.edition_id == Edition.id).where(
        (CatalogSource.provider.in_(["google-books", "open-library"])) | ((CatalogSource.provider == "libria-feed") & ~mirrored))
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
            info = safe_volume_info(source.payload) if source.payload else {}
            titles = [edition.title, info.get("title", ""), info.get("subtitle", "")]
            authors = info.get("authors") or []
            fields = authors if search_by == "author" else titles + (authors if search_by == "all" else [])
            return any(needle in canonical_book_title(value) for value in fields if isinstance(value, str))
        rows = [row for row in rows if matches(row)]
    works = {}
    for source, edition in rows:
        works.setdefault(edition.work_id, source.external_id)
    if get_settings().catalog_editionless_enabled:
        statement = select(Work.id)
        if query:
            pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            author_match = select(WorkAuthor.work_id).join(Author, WorkAuthor.author_id == Author.id).where(Author.name.ilike(pattern, escape="\\"))
            if search_by == "isbn":
                statement = statement.where(Work.id.in_(select(Edition.work_id).where(or_(Edition.isbn10 == query, Edition.isbn13 == query))))
            else:
                statement = statement.where(Work.id.in_(author_match) if search_by == "author" else
                    or_(Work.title.ilike(pattern, escape="\\"), Work.id.in_(author_match)) if search_by == "all" else Work.title.ilike(pattern, escape="\\"))
        for key in db.scalars(statement.order_by(Work.title, Work.id).limit(1000)):
            works[key] = None  # a work result never selects the first edition
    items, seen = [], set()
    for work_id, external_id in works.items():
        if get_settings().catalog_discovery_enabled:
            from app.modules.books.canonical import canonical_members
            group = canonical_members(db, work_id)
        else:
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
        publication = publication_sort_key(item.get("libria", {}).get("earliestEditionDate"))
        return (publication, 0 if exact else 1 if starts else 2, -completeness, title)
    return sorted(items, key=relevance)[:limit]


def consolidate_catalog_matches(db, query, search_by):
    """Search must never physically consolidate catalog records.

    Kept as a compatibility hook for callers; duplicate review is read-only.
    """
    return None


def search_warning(payload):
    if not payload.get('partial'):
        return payload.get('warning')
    if payload.get('error_code') == 'external_unavailable':
        return 'La búsqueda externa está temporalmente limitada; mostramos los resultados disponibles. Puedes reintentar más tarde.'
    warning = payload.get('warning') or 'La búsqueda externa está temporalmente limitada.'
    return warning.split(' Mostramos los resultados disponibles; pueden faltar libros.')[0]


def cached_search_payload(db, key, items, refresh):
    cached = db.get(CatalogQuery, key, populate_existing=True)
    if cached is None:
        return None
    age = (datetime.now(timezone.utc) - cached.fetched_at).total_seconds()
    payload = cached.payload or {}
    ttl = 30 if payload.get("error_code") and not payload.get("items") else 60 if payload.get("partial") else 600 if not payload.get("items") else 86400
    cooldown = max(30 if payload.get("error_code") else 10, payload.get("retry_after", 0))
    ttl = max(ttl, payload.get("retry_after", 0))
    # Forced refreshes also share a small cooldown, including across web workers.
    if age >= ttl or (refresh and age >= cooldown):
        return None
    extra = [present_open_library(db, item, match_work=not key.startswith('es-only-v4:isbn:')) for item in payload.get("items", []) if str(item.get("id", "")).startswith("openlibrary:")]
    items = list({item["id"]: item for item in items + extra}.values())
    result = {**payload, "items": items, "totalItems": len(items)}
    if result.get('partial'):
        result['warning'] = search_warning(result)
    return result


@router.get("")
def search_books(response: Response, db: Annotated[Session, Depends(get_db)], q: str = Query(default="", max_length=200),
                 search_by: Literal["all", "title", "author", "isbn"] = "all",
                 refresh: bool = False, start_index: int = Query(default=0, ge=0, le=1000),
                 provider: Literal["google_books", "open_library"] = "google_books",
                 page: int = Query(default=1, ge=1, le=1000)):
    response.headers["Cache-Control"] = "no-store"
    query = q.strip()
    if get_settings().catalog_discovery_enabled:
        from app.modules.books.discovery import search
        return search(db, query, search_by, provider, refresh, start_index, page)
    google_query = ({"author": "inauthor:", "isbn": "isbn:"}.get(search_by, "") + query)
    key = "es-only-v4:" + search_by + ":" + query.casefold() + ":" + provider + ":" + str(page if provider == "open_library" else start_index)
    consolidate_catalog_matches(db, query, search_by)
    db.commit()
    db.expire_all()
    limit = max(40, start_index + 40)
    items = local_works(db, query, search_by, limit=limit)
    base = {"kind": "books#volumes", "totalItems": len(items), "items": items}
    if not query:
        return base
    cached = cached_search_payload(db, key, items, refresh)
    if cached is not None:
        return cached
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:query:" + key))))
    # A concurrent request may have completed while this one waited for the lock.
    items = local_works(db, query, search_by, limit=limit)
    cached = cached_search_payload(db, key, items, refresh)
    if cached is not None:
        return cached
    previous = db.get(CatalogQuery, key)
    previous_items = list((previous.payload or {}).get('items') or []) if previous else []
    result = {"items": []}
    google_failed = False
    if provider == "google_books":
        try:
            result = google_request(query=google_query, **({"start_index": start_index} if start_index else {}))
        except HTTPException as error:
            if error.status_code != 502:
                raise
            google_failed = True
            detail = error.detail if isinstance(error.detail, dict) else {}
            result = {"items": [], "partial": True, "error_code": detail.get("code", "unavailable"),
                      "warning": detail.get("message", "Búsqueda externa limitada."), **({"retry_after": detail["retry_after"]} if "retry_after" in detail else {})}
    raw = result.get("items") or []
    valid = [item for item in raw if valid_volume(item)] if isinstance(raw, list) else []
    if not isinstance(raw, list) or len(valid) != len(raw):
        result.update(partial=True, error_code="invalid_response", warning="Se omitieron registros inválidos.")
    useful = [item for item in valid if is_spanish(item["volumeInfo"].get("language"))]
    for item in sorted(useful, key=lambda value: value["id"]):
        store_volume(db, item)
    external = []
    selected_provider = provider
    if provider == "open_library" or google_failed or result.get("partial") or not useful:
        try:
            fallback = open_library.search(query, search_by, page if provider == "open_library" else 1)
            external = fallback.get("items") or []
            if external or (not google_failed and not result.get("partial")):
                result = fallback
                selected_provider = "open_library"
            elif google_failed or result.get("partial"):
                result.update(has_more=False, next_start_index=None)
        except HTTPException:
            result.update(partial=True, error_code="external_unavailable", has_more=False, next_start_index=None,
                          warning="La búsqueda externa está temporalmente limitada. Mostramos los libros disponibles; puedes reintentar.")
    # Searches never physically consolidate existing Work records.
    if useful:
        consolidate_catalog_matches(db, query, search_by)
    db.flush()
    db.expire_all()
    items = local_works(db, query, search_by, limit=limit)
    if result.get('partial'):
        # Stale-if-error: keep verified, previously discovered editions when a
        # refresh fails. They may exist only in cache until the user selects one.
        external += [item for item in previous_items if str(item.get('id', '')).startswith('openlibrary:')]
    items += [present_open_library(db, item, match_work=search_by != "isbn") for item in external]
    items = list({item["id"]: item for item in items}.values())
    payload = {"kind": "books#volumes", "totalItems": len(items), "items": items, "active_provider": selected_provider}
    for field in ("has_more", "next_start_index", "next_page", "partial", "error_code", "warning", "retry_after"):
        if field in result:
            payload[field] = result[field]
    if payload.get("partial"):
        payload["has_more"] = False
        payload["warning"] = search_warning(payload)
    cached = db.get(CatalogQuery, key)
    if cached:
        cached.payload, cached.fetched_at = payload, datetime.now(timezone.utc)
    else:
        db.add(CatalogQuery(query=key, payload=payload, fetched_at=datetime.now(timezone.utc)))
    db.commit()
    return payload


@router.get("/{volume_id}")
def get_book(volume_id: str, response: Response, db: Annotated[Session, Depends(get_db)]):
    response.headers["Cache-Control"] = "no-store"
    if get_settings().catalog_discovery_enabled:
        from app.modules.books.discovery import detail
        return detail(db, volume_id)
    if volume_id.startswith("openlibrary:"):
        edition = ensure_edition(db, volume_id)
        db.commit()
        return work_payload(db, edition.work_id, preferred_source=volume_id.removeprefix("openlibrary:"), include_reading_stats=True)
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
