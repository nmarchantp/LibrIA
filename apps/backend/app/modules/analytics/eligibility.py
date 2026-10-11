"""Shared minimum library size for personal AI features."""
from fastapi import HTTPException
from sqlalchemy import func, select
from app.modules.library.models import LibraryEntry

MIN_READER_BOOKS = 10


def reader_eligibility(db, user_id):
    count = db.scalar(select(func.count(func.distinct(LibraryEntry.work_id))).where(
        LibraryEntry.user_id == user_id, LibraryEntry.archived_at.is_(None)))
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
