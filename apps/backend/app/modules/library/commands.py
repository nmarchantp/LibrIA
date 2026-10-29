"""Phase-4 reading commands. Caller owns transaction; never mutate catalog data."""
from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.books.models import Work, Edition
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent, ReadingProgress, ReadingEditionSelection
from app.modules.library.schemas import ReadingEventResponse
from app.modules.users.models import User


def owned_reading(db, actor_id, reading_id):
    # Same actor-first order as incorporation, avoiding row-lock inversion.
    actor = db.scalar(select(User).where(User.id == actor_id).with_for_update())
    if actor is None or actor.role == "libreria":
        raise HTTPException(403, "Se requiere una biblioteca personal")
    reading = db.scalar(select(Reading).join(LibraryEntry, Reading.library_entry_id == LibraryEntry.id).where(
        Reading.id == reading_id, LibraryEntry.user_id == actor_id).with_for_update(of=Reading))
    if reading is None:
        raise HTTPException(404, "Lectura no encontrada")
    return actor, reading


def snapshot(reading):
    return {key: str(value) if isinstance(value, (uuid.UUID, datetime)) else value for key in
        ("work_id", "edition_id", "status", "current_page", "total_pages", "started_at", "finished_at")
        for value in [getattr(reading, key)]}


def select_edition(db, actor_id, reading_id, edition_id):
    _, reading = owned_reading(db, actor_id, reading_id)
    edition = db.get(Edition, edition_id)
    # Physical correspondence is required by the composite FK, even for redirects.
    if edition is None or edition.work_id != reading.work_id:
        raise HTTPException(422, "La edición no pertenece a la obra de esta lectura")
    if reading.edition_id == edition.id:
        return reading
    if reading.edition_id is not None:
        raise HTTPException(409, "La edición elegida anteriormente se conserva")
    before = snapshot(reading)
    reading.edition_id = edition.id
    db.add(ReadingEditionSelection(reading_id=reading.id, actor_user_id=actor_id, work_id=reading.work_id,
        edition_id=edition.id, before_state=before, after_state=snapshot(reading)))
    db.flush()
    return reading


def set_total(db, actor_id, reading_id, total):
    _, reading = owned_reading(db, actor_id, reading_id)
    if reading.status in {"finished", "abandoned"}:
        raise HTTPException(409, "El intento cerrado conserva sus páginas registradas")
    if total < reading.current_page:
        raise HTTPException(422, "El total no puede ser menor que la página registrada")
    reading.total_pages = total
    db.flush()
    return {"reading_id": reading.id, "total_pages": reading.total_pages, "current_page": reading.current_page,
        "progress_percent": round(reading.current_page * 100 / total)}


def record_event(db, actor_id, data):
    actor = db.scalar(select(User).where(User.id == actor_id).with_for_update())
    if actor is None or actor.role == "libreria":
        raise HTTPException(403, "Se requiere una biblioteca personal")
    now = datetime.now(timezone.utc)
    if data.event == "start":
        from app.modules.library.router import resolve_book
        work, edition = resolve_book(db, data)
        from app.modules.books.canonical import enabled, canonical_members
        ids = canonical_members(db, work.id) if enabled() else {work.id}
        entries = db.scalars(select(LibraryEntry).where(LibraryEntry.user_id == actor_id,
            LibraryEntry.work_id.in_(ids), LibraryEntry.archived_at.is_(None)).order_by(LibraryEntry.created_at, LibraryEntry.id)).all()
        entry = next((e for e in entries if edition and e.work_id == edition.work_id), entries[0] if entries else None)
        if entry is None:
            raise HTTPException(409, "Agrega primero la obra a tu biblioteca")
        reading = db.scalar(select(Reading).where(Reading.library_entry_id.in_([e.id for e in entries]))
            .order_by(Reading.created_at.desc(), Reading.id.desc()))
        if reading and reading.status == "reading":
            raise HTTPException(409, "La obra ya tiene una lectura activa")
        if reading and reading.status == "pending":
            entry = db.get(LibraryEntry, reading.library_entry_id)
            if data.edition_id and reading.edition_id != data.edition_id:
                raise HTTPException(409, "Selecciona la edición mediante el comando de selección")
            # Preserve the pending selection even if the request omits it.
        else:
            work = db.get(Work, entry.work_id)
            if edition and edition.work_id != work.id:
                raise HTTPException(409, "La edición elegida requiere su pertenencia física correspondiente")
            reading = Reading(library_entry_id=entry.id, work_id=work.id,
                edition_id=edition.id if edition else None, status="pending", current_page=0)
            db.add(reading)
        work = db.get(Work, reading.work_id)
        reading.status, reading.started_at = "reading", now
        reading.total_pages = data.page_count if data.page_count is not None else reading.total_pages
        db.flush()
    else:
        _, reading = owned_reading(db, actor_id, data.reading_id)
        work = db.get(Work, reading.work_id)
        if reading.status != "reading":
            raise HTTPException(409, "El intento no está activo")
        if data.edition_id and data.edition_id != reading.edition_id:
            raise HTTPException(409, "La edición del intento no coincide")
        if data.page_count is not None and data.page_count != reading.total_pages:
            raise HTTPException(409, "Declara el total con el comando de páginas del intento")
    previous = reading.current_page
    if data.event in {"progress", "correction"}:
        page = data.current_page
        if data.event == "progress" and (page <= previous or (reading.total_pages is not None and page >= reading.total_pages)):
            raise HTTPException(422, "El avance debe superar la página actual y ser menor que el total conocido")
        if data.event == "correction" and page >= previous:
            raise HTTPException(422, "La corrección debe indicar una página anterior")
        reading.current_page = page
    elif data.event == "finish":
        if reading.total_pages is not None:
            if data.current_page is not None and data.current_page != reading.total_pages:
                raise HTTPException(422, "La página final debe coincidir con el total declarado")
            reading.current_page = reading.total_pages
        elif data.current_page is not None:
            if data.current_page < previous:
                raise HTTPException(422, "La página final no puede retroceder")
            reading.current_page = data.current_page
        # Unknown total stays NULL; finishing never fabricates a page count.
        reading.status, reading.finished_at = "finished", now
    elif data.event == "abandon":
        reading.status, reading.abandoned_at = "abandoned", now
        reading.abandonment_reason = (data.abandonment_reason or "").strip() or None
    if data.event in {"progress", "correction", "finish"}:
        db.add(ReadingProgress(reading_id=reading.id, page=reading.current_page, recorded_at=now))
    public = data.event in {"start", "progress", "finish"} or (data.event == "abandon" and data.share)
    event = ReadingEvent(reading_id=reading.id, actor_user_id=actor_id, kind=data.event, previous_page=previous,
        page=reading.current_page, total_pages=reading.total_pages, is_public=public,
        reason=data.correction_reason if data.event == "correction" else data.abandonment_reason if data.event == "abandon" else None,
        reflection=data.reflection.model_dump() if data.reflection else None, created_at=now)
    db.add(event)
    db.flush()
    if data.event in {"finish", "abandon"}:
        from app.modules.analytics.persistence import enqueue_reading_event_analysis
        settings = get_settings()
        enqueue_reading_event_analysis(db, reading_event_id=event.id, provider=settings.ai_provider,
            model=settings.gemini_model, prompt_version=settings.reading_analysis_prompt_version,
            delay_minutes=settings.reading_analysis_delay_minutes)
    from app.modules.social.router import as_reading_response
    percent = round(reading.current_page * 100 / reading.total_pages) if reading.total_pages else None
    return ReadingEventResponse(reading_id=reading.id, work_id=reading.work_id, edition_id=reading.edition_id,
        event_id=event.id, current_page=reading.current_page, total_pages=reading.total_pages, status=reading.status,
        progress_percent=percent, reflection=event.reflection,
        post=as_reading_response(event, work.title, actor, str(work.id)) if public else None)
