"""Biblioteca e historial de lectura; el feed deriva sus hitos del historial."""

from datetime import datetime, timezone
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.books.identity import canonical_work_key
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.service import equivalent_work_ids
from app.modules.library.models import LibraryEntry, Reading, ReadingProgress, ReadingEvent
from app.modules.library.schemas import LibraryBookCreate, ReadingEventCreate, ReadingEventResponse, ReadingState, ReadingTotalUpdate, ReadingNotebookUpdate
from app.modules.social.router import as_reading_response
from app.modules.users.models import User

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/me", response_model=list[ReadingState])
def my_readings(user: Annotated[User, Depends(get_current_user)],
                db: Annotated[Session, Depends(get_db)]) -> list[ReadingState]:
    rows = db.execute(select(Reading, CatalogSource.external_id, Edition.title)
                      .join(LibraryEntry, Reading.library_entry_id == LibraryEntry.id)
                      .join(Edition, Reading.edition_id == Edition.id)
                      .join(CatalogSource, Reading.edition_id == CatalogSource.edition_id)
                      .where(LibraryEntry.user_id == user.id, CatalogSource.provider == "libria-feed")
                      .order_by(Reading.created_at.desc(), Reading.id.desc())).all()
    latest = {}
    for reading, book_ref, book_title in rows:
        if book_ref not in latest:
            latest[book_ref] = ReadingState(reading_id=reading.id, work_id=reading.work_id, edition_id=reading.edition_id, book_ref=book_ref, book_title=book_title, status=reading.status,
                                            reflection=db.scalar(select(ReadingEvent.reflection).where(ReadingEvent.reading_id == reading.id, ReadingEvent.kind == "finish")),
                                            catalog_volume=db.scalar(select(CatalogSource.payload).where(CatalogSource.edition_id == reading.edition_id, CatalogSource.provider == "google-books")),
                                            current_page=reading.current_page,
                                            total_pages=reading.total_pages or (db.get(Edition, reading.edition_id).page_count if reading.status == "pending" else None),
                                            progress_percent=round(reading.current_page * 100 / reading.total_pages) if reading.total_pages else 0,
                                            started_at=reading.started_at, finished_at=reading.finished_at,
                                            notebook=reading.notebook or {})
    return list(latest.values())


def resolve_book(db: Session, data: LibraryBookCreate) -> tuple[Work, Edition]:
    # Una misma referencia importada simultáneamente no debe duplicar el catálogo.
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:libria-feed:" + data.book_ref))))
    source = db.scalar(select(CatalogSource).where(
        CatalogSource.provider == "libria-feed", CatalogSource.external_id == data.book_ref,
    ))
    if source:
        edition = db.get(Edition, source.edition_id)
        return db.get(Work, edition.work_id), edition
    try:
        internal_work_id = uuid.UUID(data.book_ref)
    except ValueError:
        internal_work_id = None
    if internal_work_id:
        work = db.get(Work, internal_work_id)
        if work:
            edition = db.get(Edition, data.edition_id) if data.edition_id else db.scalar(
                select(Edition).where(Edition.work_id == work.id).order_by(Edition.created_at, Edition.id))
            if edition is None or edition.work_id not in equivalent_work_ids(db, work.id):
                raise HTTPException(status_code=422, detail="Selecciona una edición válida de la obra")
            return db.get(Work, edition.work_id), edition
    # Unknown/manual references have no author metadata. Google-backed books
    # resolve through their source above and retain the author-aware identity.
    identity_key = canonical_work_key(data.book_title)
    if identity_key:
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:work:" + identity_key))))
    work = db.scalar(select(Work).where(Work.identity_key == identity_key)) if identity_key else None
    if work is None:
        work = Work(title=data.book_title, identity_key=identity_key, original_language="es")
        db.add(work)
        db.flush()
    edition = Edition(work_id=work.id, title=data.book_title, language="es", page_count=data.page_count)
    db.add(edition)
    db.flush()
    db.add(CatalogSource(edition_id=edition.id, provider="libria-feed", external_id=data.book_ref,
                         fetched_at=datetime.now(timezone.utc)))
    return work, edition


@router.post("/library", response_model=ReadingState)
def add_to_library(data: LibraryBookCreate, user: Annotated[User, Depends(get_current_user)],
                   db: Annotated[Session, Depends(get_db)]) -> ReadingState:
    db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if user.role == "libreria":
        raise HTTPException(status_code=403, detail="Una librería no tiene biblioteca personal")
    work, edition = resolve_book(db, data)
    entry = db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == user.id,
                      LibraryEntry.work_id.in_(equivalent_work_ids(db, work.id))))
    if entry is not None and entry.work_id != work.id:
        work = db.get(Work, entry.work_id)
        edition = db.scalar(select(Edition).where(Edition.work_id == work.id).order_by(Edition.created_at, Edition.id))
    if entry is None:
        entry = LibraryEntry(user_id=user.id, work_id=work.id)
        db.add(entry)
        db.flush()
    reading = db.scalar(select(Reading).where(Reading.library_entry_id == entry.id)
                        .order_by(Reading.created_at.desc(), Reading.id.desc()))
    if reading is None:
        reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id,
                          status="pending", current_page=0, total_pages=edition.page_count or data.page_count)
        db.add(reading)
    db.commit()
    db.refresh(reading)
    return ReadingState(reading_id=reading.id, work_id=reading.work_id, edition_id=reading.edition_id, book_ref=data.book_ref, book_title=edition.title,
                        status=reading.status, current_page=reading.current_page, total_pages=reading.total_pages,
                        progress_percent=round(reading.current_page * 100 / reading.total_pages) if reading.total_pages else 0,
                        started_at=reading.started_at, finished_at=reading.finished_at, notebook=reading.notebook or {})


@router.post("/events", response_model=ReadingEventResponse, status_code=status.HTTP_201_CREATED)
def record_reading_event(data: ReadingEventCreate, user: Annotated[User, Depends(get_current_user)],
                         db: Annotated[Session, Depends(get_db)]) -> ReadingEventResponse:
    # Serializa comandos del mismo titular, incluso cuando aún no hay biblioteca.
    db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if user.role == "libreria":
        raise HTTPException(status_code=403, detail="Una librería no puede registrar lecturas personales")
    if data.event != "start":
        reading = db.scalar(select(Reading).join(LibraryEntry, Reading.library_entry_id == LibraryEntry.id)
                          .where(Reading.id == data.reading_id, LibraryEntry.user_id == user.id))
        if reading is None:
            raise HTTPException(status_code=404, detail="Lectura no encontrada")
        work, edition = db.get(Work, reading.work_id), db.get(Edition, reading.edition_id)
        if reading.status != "reading":
            raise HTTPException(status_code=409, detail="El intento indicado no está activo para este libro")
        if data.page_count != reading.total_pages:
            raise HTTPException(status_code=409, detail="El total de páginas no puede cambiar durante un intento")
    else:
        work, edition = resolve_book(db, data)
        entry = db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == user.id,
                          LibraryEntry.work_id.in_(equivalent_work_ids(db, work.id))))
        if entry is not None and entry.work_id != work.id:
            work = db.get(Work, entry.work_id)
            edition = db.scalar(select(Edition).where(Edition.work_id == work.id).order_by(Edition.created_at, Edition.id))
        if entry is None:
            entry = LibraryEntry(user_id=user.id, work_id=work.id)
            db.add(entry)
            db.flush()
        reading = db.scalar(select(Reading).where(Reading.library_entry_id == entry.id)
                            .order_by(Reading.created_at.desc(), Reading.id.desc()))
    now = datetime.now(timezone.utc)
    previous_page = reading.current_page if reading and data.event != "start" else 0
    if data.event == "start":
        if reading and reading.status == "reading":
            raise HTTPException(status_code=409, detail="Este libro ya está en lectura")
        if reading and reading.status == "pending":
            reading.status = "reading"
            reading.total_pages = data.page_count
            reading.started_at = now
        else:
            reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id,
                              status="reading", current_page=0, total_pages=data.page_count, started_at=now, created_at=now)
            db.add(reading)
        db.flush()
        percent = 0
        body = f'Comenzó a leer "{work.title}".'
    elif data.event == "progress":
        if reading.status != "reading":
            raise HTTPException(status_code=409, detail="Esta lectura ya terminó")
        if data.current_page <= reading.current_page or data.current_page >= reading.total_pages:
            raise HTTPException(status_code=422, detail="La página debe avanzar y ser menor que el total")
        reading.current_page = data.current_page
        percent = round(data.current_page * 100 / reading.total_pages)
        body = f'Llegó al {percent} % de "{work.title}".'
        db.add(ReadingProgress(reading_id=reading.id, page=data.current_page, recorded_at=now))
    elif data.event == "correction":
        if data.current_page >= reading.current_page:
            raise HTTPException(status_code=422, detail="La corrección debe indicar una página anterior")
        reading.current_page = data.current_page
        percent = round(reading.current_page * 100 / reading.total_pages)
        db.add(ReadingProgress(reading_id=reading.id, page=reading.current_page, recorded_at=now))
    elif data.event == "finish":
        if reading and reading.status != "reading":
            raise HTTPException(status_code=409, detail="Esta lectura ya terminó")
        reading.current_page = reading.total_pages
        reading.status = "finished"
        reading.finished_at = now
        db.add(ReadingProgress(reading_id=reading.id, page=reading.current_page, recorded_at=now))
        percent = 100
        body = f'Terminó "{work.title}".'
    else:
        if reading and reading.status != "reading":
            raise HTTPException(status_code=409, detail="Esta lectura ya terminó")
        reading.status = "abandoned"
        reading.abandoned_at = now
        reading.abandonment_reason = data.abandonment_reason.strip()
        percent = round(reading.current_page * 100 / reading.total_pages)
        body = f'Abandonó "{work.title}".'

    public = data.event in {"start", "progress", "finish"} or (data.event == "abandon" and data.share)
    event = ReadingEvent(reading_id=reading.id, actor_user_id=user.id, kind=data.event,
                          reflection=data.reflection.model_dump() if data.reflection else None,
                          previous_page=previous_page, page=reading.current_page, total_pages=reading.total_pages,
                          is_public=public, reason=data.correction_reason if data.event == "correction" else
                          data.abandonment_reason if data.event == "abandon" else None, created_at=now)
    db.add(event)
    db.commit()
    db.refresh(event)
    return ReadingEventResponse(reading_id=reading.id, work_id=reading.work_id, edition_id=reading.edition_id, event_id=event.id, status=reading.status,
                                reflection=event.reflection,
                                current_page=reading.current_page, total_pages=reading.total_pages,
                                progress_percent=percent, post=as_reading_response(event, work.title, user) if public else None)


@router.patch("/{reading_id}/total-pages")
def update_total_pages(reading_id: uuid.UUID, data: ReadingTotalUpdate,
                       user: Annotated[User, Depends(get_current_user)],
                       db: Annotated[Session, Depends(get_db)]):
    reading = db.scalar(select(Reading).join(LibraryEntry, LibraryEntry.id == Reading.library_entry_id)
                        .where(Reading.id == reading_id, LibraryEntry.user_id == user.id).with_for_update())
    if reading is None:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    if data.total_pages < reading.current_page:
        raise HTTPException(status_code=422, detail="El total no puede ser menor que la pÃ¡gina actual")
    if reading.status == "finished" and data.total_pages != reading.current_page:
        reading.current_page = data.total_pages
    reading.total_pages = data.total_pages
    db.commit()
    return {"reading_id": reading.id, "total_pages": reading.total_pages,
            "current_page": reading.current_page,
            "progress_percent": round(reading.current_page * 100 / reading.total_pages)}


@router.patch("/{reading_id}/notebook")
def update_notebook(reading_id: uuid.UUID, data: ReadingNotebookUpdate,
                    user: Annotated[User, Depends(get_current_user)],
                    db: Annotated[Session, Depends(get_db)]):
    reading = db.scalar(select(Reading).join(LibraryEntry, LibraryEntry.id == Reading.library_entry_id)
                        .where(Reading.id == reading_id, LibraryEntry.user_id == user.id).with_for_update())
    if reading is None:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    reading.notebook = data.model_dump()
    db.commit()
    return {"reading_id": reading.id, "notebook": reading.notebook}


@router.get("/{reading_id}/history")
def reading_history(reading_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
                    db: Annotated[Session, Depends(get_db)]):
    reading = db.scalar(select(Reading).join(LibraryEntry, LibraryEntry.id == Reading.library_entry_id)
                        .where(Reading.id == reading_id, LibraryEntry.user_id == user.id))
    if reading is None:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    events = db.scalars(select(ReadingEvent).where(ReadingEvent.reading_id == reading_id)
                        .order_by(ReadingEvent.created_at, ReadingEvent.id)).all()
    return [{"id": event.id, "event": event.kind, "previous_page": event.previous_page,
             "page": event.page, "total_pages": event.total_pages, "reason": event.reason,
             "is_public": event.is_public, "created_at": event.created_at} for event in events]
