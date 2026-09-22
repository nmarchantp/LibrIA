"""Registra hitos reales de lectura y crea su publicación automática."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.library.models import LibraryEntry, Reading, ReadingProgress
from app.modules.library.schemas import ReadingEventCreate, ReadingEventResponse, ReadingState
from app.modules.social.models import Post
from app.modules.social.router import as_response
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
            latest[book_ref] = ReadingState(book_ref=book_ref, book_title=book_title, status=reading.status,
                                            current_page=reading.current_page,
                                            total_pages=reading.total_pages,
                                            progress_percent=round(reading.current_page * 100 / reading.total_pages))
    return list(latest.values())


def resolve_book(db: Session, data: ReadingEventCreate) -> tuple[Work, Edition]:
    source = db.scalar(select(CatalogSource).where(
        CatalogSource.provider == "libria-feed", CatalogSource.external_id == data.book_ref,
    ))
    if source:
        edition = db.get(Edition, source.edition_id)
        return db.get(Work, edition.work_id), edition
    work = Work(title=data.book_title)
    db.add(work)
    db.flush()
    edition = Edition(work_id=work.id, title=data.book_title, language="es", page_count=data.page_count)
    db.add(edition)
    db.flush()
    db.add(CatalogSource(edition_id=edition.id, provider="libria-feed", external_id=data.book_ref,
                         fetched_at=datetime.now(timezone.utc)))
    return work, edition


@router.post("/events", response_model=ReadingEventResponse, status_code=status.HTTP_201_CREATED)
def record_reading_event(data: ReadingEventCreate, user: Annotated[User, Depends(get_current_user)],
                         db: Annotated[Session, Depends(get_db)]) -> ReadingEventResponse:
    work, edition = resolve_book(db, data)
    entry = db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == user.id, LibraryEntry.work_id == work.id))
    if entry is None:
        entry = LibraryEntry(user_id=user.id, work_id=work.id)
        db.add(entry)
        db.flush()

    reading = db.scalar(select(Reading).where(Reading.library_entry_id == entry.id)
                        .order_by(Reading.created_at.desc(), Reading.id.desc()))
    now = datetime.now(timezone.utc)
    if data.event == "start":
        if reading and reading.status == "reading":
            raise HTTPException(status_code=409, detail="Este libro ya está en lectura")
        reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id,
                          status="reading", current_page=0, total_pages=data.page_count, started_at=now)
        db.add(reading)
        db.flush()
        percent = 0
        body = f'Comenzó a leer "{work.title}".'
    elif data.event == "progress":
        if reading is None:
            reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id,
                              status="reading", current_page=0, total_pages=data.page_count, started_at=now)
            db.add(reading)
            db.flush()
        if reading.status != "reading":
            raise HTTPException(status_code=409, detail="Esta lectura ya terminó")
        if data.current_page <= reading.current_page or data.current_page >= reading.total_pages:
            raise HTTPException(status_code=422, detail="La página debe avanzar y ser menor que el total")
        reading.current_page = data.current_page
        percent = round(data.current_page * 100 / reading.total_pages)
        body = f'Llegó al {percent} % de "{work.title}".'
        db.add(ReadingProgress(reading_id=reading.id, page=data.current_page, recorded_at=now))
    elif data.event == "finish":
        if reading and reading.status != "reading":
            raise HTTPException(status_code=409, detail="Esta lectura ya terminó")
        if reading is None:
            reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id,
                              status="reading", current_page=0, total_pages=data.page_count, started_at=now)
            db.add(reading)
            db.flush()
        reading.current_page = reading.total_pages
        reading.status = "finished"
        reading.finished_at = now
        db.add(ReadingProgress(reading_id=reading.id, page=reading.current_page, recorded_at=now))
        percent = 100
        body = f'Terminó "{work.title}".'
    else:
        if reading and reading.status != "reading":
            raise HTTPException(status_code=409, detail="Esta lectura ya terminó")
        if reading is None:
            reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id,
                              status="reading", current_page=0, total_pages=data.page_count, started_at=now)
            db.add(reading)
            db.flush()
        reading.status = "abandoned"
        reading.abandoned_at = now
        reading.abandonment_reason = data.abandonment_reason.strip()
        percent = round(reading.current_page * 100 / reading.total_pages)
        body = f'Abandonó "{work.title}".'

    post = Post(user_id=user.id, author_role=user.role, source="reading", kind="progress", body=body,
                book_ref=data.book_ref, book_title=work.title,
                progress_percent=percent, reading_event=data.event)
    db.add(post)
    db.commit()
    db.refresh(post)
    return ReadingEventResponse(reading_id=reading.id, status=reading.status,
                                progress_percent=percent, post=as_response(post, user.display_name, user.role))
