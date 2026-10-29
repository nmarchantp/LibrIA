"""Stable library responses, independent of discovery cache and feed aliases."""
from sqlalchemy import select

from app.modules.books.canonical import resolve_canonical_work
from app.modules.books.models import CatalogSource, Edition, Work, WorkAuthor, Author
from app.modules.books.catalog_models import WorkReference
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent
from app.modules.library.schemas import ReadingState


def reading_state(db, reading):
    from app.core.config import get_settings
    from app.modules.books.router import source_payload
    edition = db.get(Edition, reading.edition_id) if reading.edition_id else None
    work = db.get(Work, reading.work_id)
    sources = db.scalars(select(CatalogSource).where(CatalogSource.edition_id == edition.id).order_by(CatalogSource.provider)).all() if edition else []
    source = next((s for s in sources if s.payload and s.provider in {"google-books", "open-library"}), None)
    aliases = [("openlibrary:" if s.provider == "open-library" else "") + s.external_id for s in sources]
    aliases.extend(("openlibrary:" if ref.provider == "open-library" else "") + ref.external_id
        for ref in db.scalars(select(WorkReference).where(WorkReference.work_id == reading.work_id,
            WorkReference.reference_type.in_(["volume", "edition"]), WorkReference.verification_status.in_(["provisional", "confirmed"]))))
    root = resolve_canonical_work(db, reading.work_id).canonical_work_id
    volume = {**(source_payload(db, source) if source else {"volumeInfo": {"title": edition.title if edition else work.title,
              "description": work.description, "categories": work.categories,
              "authors": db.scalars(select(Author.name).join(WorkAuthor, WorkAuthor.author_id == Author.id).where(WorkAuthor.work_id == work.id)).all()}}),
              "id": str(reading.work_id), "libria": {
                  "workId": str(reading.work_id), "canonicalWorkId": str(root), "editionId": str(edition.id) if edition else None,
                  "editionOptional": get_settings().catalog_editionless_enabled,
                  "externalId": ("openlibrary:" if source and source.provider == "open-library" else "") + source.external_id if source else str(reading.work_id),
                  "catalogOrigin": "libria", "sourceProvider": source.provider if source else "libria",
                  "catalogFlow": "discovery-v1", "externalAliases": aliases + [str(root)]}}
    return ReadingState(reading_id=reading.id, work_id=reading.work_id, edition_id=reading.edition_id,
        book_ref=str(reading.work_id), book_title=edition.title if edition else work.title, status=reading.status, current_page=reading.current_page,
        edition_optional=get_settings().catalog_editionless_enabled,
        total_pages=reading.total_pages, progress_percent=round(reading.current_page*100/reading.total_pages) if reading.total_pages else None if get_settings().catalog_editionless_enabled else 0,
        started_at=reading.started_at, finished_at=reading.finished_at, notebook=reading.notebook or {}, catalog_volume=volume,
        reflection=db.scalar(select(ReadingEvent.reflection).where(ReadingEvent.reading_id == reading.id, ReadingEvent.kind == "finish")))


def library_states(db, actor_id):
    rows = db.scalars(select(Reading).join(LibraryEntry, LibraryEntry.id == Reading.library_entry_id).where(
        LibraryEntry.user_id == actor_id, LibraryEntry.archived_at.is_(None)).order_by(Reading.created_at.desc(), Reading.id.desc())).all()
    latest = {}
    from app.modules.books.canonical import enabled, identity_snapshot
    snapshot = identity_snapshot(db) if enabled() else None
    for reading in rows:
        root = snapshot.root(reading.work_id) if snapshot else resolve_canonical_work(db, reading.work_id).canonical_work_id
        if root not in latest:
            latest[root] = reading_state(db, reading)
    return list(latest.values())
