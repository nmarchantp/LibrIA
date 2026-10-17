"""Shared minimum library size for personal AI features."""
from fastapi import HTTPException
from sqlalchemy import func, select, text
from app.modules.library.models import LibraryEntry

MIN_READER_BOOKS = 10


def reader_eligibility(db, user_id):
    demo = set(db.execute(text("SELECT entity_type, entity_id FROM app.procedencia_demo")).all())
    count = db.scalar(select(func.count(func.distinct(LibraryEntry.work_id))).where(
        LibraryEntry.user_id == user_id, LibraryEntry.archived_at.is_(None),
        LibraryEntry.id.not_in([entity_id for kind, entity_id in demo if kind == "library"]),
        LibraryEntry.work_id.not_in([entity_id for kind, entity_id in demo if kind == "obras"])))
    return {"eligible": count >= MIN_READER_BOOKS, "book_count": count,
            "minimum_books": MIN_READER_BOOKS, "missing_books": max(0, MIN_READER_BOOKS - count)}


def locked_reader_access(eligibility):
    return {**eligibility, "status": "locked", "evidence": None, "interpretation": None, "items": []}


def require_reader_eligibility(db, user_id):
    eligibility = reader_eligibility(db, user_id)
    if not eligibility["eligible"]:
        raise HTTPException(403, detail={"code": "minimum_reader_books", **eligibility,
            "message": "Registra al menos 10 libros en tu biblioteca para usar Tu ADN lector y Recomendaciones IA."})
    return eligibility
