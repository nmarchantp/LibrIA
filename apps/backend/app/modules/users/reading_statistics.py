"""Current library genre assignments, separate from declared preferences and ETL."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import unicodedata

from sqlalchemy import select

from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry, Reading

MISSING_CATEGORIES = {"sin categoría", "sin categoria", "sin género informado", "sin genero informado",
                      "sin género", "sin genero", "unknown", "uncategorized"}


def genre_distribution(category_lists):
    counts = Counter()
    names = {}
    classified = 0
    for categories in category_lists:
        unique = {}
        if isinstance(categories, list):
            for value in categories:
                if not isinstance(value, str):
                    continue
                name = unicodedata.normalize("NFC", " ".join(value.split()))
                key = name.casefold()
                if key and key not in MISSING_CATEGORIES:
                    unique.setdefault(key, name)
        if unique:
            classified += 1
        for key, name in unique.items():
            counts[key] += 1
            # Deterministic label even when different works vary capitalization.
            names[key] = min(names.get(key, name), name)
    total = sum(counts.values())
    genres = [{"name": names[key], "assignments": count,
               "percentage": float((Decimal(count) * 100 / total).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))}
              for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]
    return {"status": "no_finished_books" if not category_lists else "ready" if total else "insufficient_metadata",
            "finished_books": len(category_lists), "classified_books": classified,
            "unclassified_books": len(category_lists) - classified, "total_assignments": total, "genres": genres}


def most_read_genres(db, user_id):
    from app.modules.books.canonical import enabled, identity_snapshot
    if enabled():
        snapshot = identity_snapshot(db)
        rows = db.scalars(select(Reading).join(LibraryEntry, Reading.library_entry_id == LibraryEntry.id)
            .where(LibraryEntry.user_id == user_id, LibraryEntry.archived_at.is_(None))
            .order_by(Reading.created_at.desc(), Reading.id.desc())).all()
        latest = {}
        for reading in rows:
            latest.setdefault(snapshot.root(reading.work_id), reading)
        return genre_distribution([db.get(Work, key).categories for key, reading in latest.items() if reading.status == "finished"])
    # Select the current attempt BEFORE filtering finished; a past completion must
    # not count when the current library state is pending/reading/abandoned.
    latest = (select(Reading.work_id, Reading.status)
              .join(LibraryEntry, Reading.library_entry_id == LibraryEntry.id)
              .where(LibraryEntry.user_id == user_id, LibraryEntry.archived_at.is_(None))
              .distinct(Reading.library_entry_id)
              .order_by(Reading.library_entry_id, Reading.created_at.desc(), Reading.id.desc()).subquery())
    rows = db.scalars(select(Work.categories).join(latest, latest.c.work_id == Work.id)
                      .where(latest.c.status == "finished")).all()
    return genre_distribution(rows)
