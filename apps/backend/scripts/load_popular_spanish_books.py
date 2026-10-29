"""Load current Spanish bestsellers through Google Books.

Popularity source (2026-09-11):
https://los40.com/2026/09/11/los-30-libros-mas-vendidos-esta-semana-los-titulos-de-ficcion-y-no-ficcion-mas-populares/
"""

from sqlalchemy import func, select, text
from fastapi import HTTPException

from app.main import app as _application  # noqa: F401 - registers every ORM table
from app.core.database import SessionLocal
from app.modules.books.identity import canonical_author_name, canonical_match_title, canonical_title_variants
from app.modules.books.models import Work
from app.modules.books.router import google_request, is_spanish, store_volume
from app.modules.books.service import consolidate_equivalent_works


POPULAR_BOOKS = [
    ("Los huérfanos", "Carmen Mola"),
    ("La inquilina", "Freida McFadden"),
    ("El partido más largo", "Rachel Reid"),
    ("El llanto de los muertos", "Camilla Läckberg"),
    ("Una corona de huesos dorados", "Jennifer L. Armentrout"),
    ("Las gratitudes", "Delphine de Vigan"),
    ("El tren de la medianoche", "Matt Haig"),
    ("Una familia moderna", "Julia Navarro"),
    ("El falsificador", "Rafael Tarradas Bultó"),
    ("Fury Bound. Furia de lobo", "Sable Sorensen"),
    ("La biblioteca de la medianoche", "Matt Haig"),
    ("La paciente silenciosa", "Alex Michaelides"),
    ("El cuarto mono", "J. D. Barker"),
    ("Proyecto Hail Mary", "Andy Weir"),
    ("Verity. La sombra de un engaño", "Colleen Hoover"),
    ("La quinta víctima", "J. D. Barker"),
    ("No mientas", "Arturo del Burgo"),
    ("Al este del Edén", "John Steinbeck"),
    ("La sexta trampa", "J. D. Barker"),
    ("Ángel escarlata", "S. T. Abby"),
]


def matching_items(result, title, author):
    target_title = canonical_match_title(title)
    target_author = canonical_author_name(author)
    surname = target_author[-8:] if len(target_author) > 8 else target_author
    matches = []
    for item in result.get("items", []):
        info = item.get("volumeInfo", {})
        if not is_spanish(info.get("language")):
            continue
        titles = {canonical_match_title(value) for value in canonical_title_variants(info.get("title"))}
        title_match = target_title in titles or any(
            target_title in candidate or candidate in target_title for candidate in titles)
        authors = [canonical_author_name(value) for value in info.get("authors") or []]
        author_match = not authors or any(surname in value for value in authors)
        if title_match and author_match:
            matches.append(item)
    return matches[:5]


def main():
    from app.core.config import get_settings
    if get_settings().catalog_discovery_enabled:
        from scripts.import_catalog import main as authorized_import
        return authorized_import(default_queries=[f'"{title}" {author}' for title, author in POPULAR_BOOKS])
    with SessionLocal() as db:
        before = {
            "users": db.scalar(text("SELECT count(*) FROM app.usuarios")),
            "profiles": db.scalar(text("SELECT count(*) FROM app.perfiles")),
            "works": db.scalar(select(func.count(Work.id))),
        }
        loaded, missing, unavailable, editions = [], [], [], 0
        for title, author in POPULAR_BOOKS:
            try:
                result = google_request(query=f'"{title}" {author}')
            except HTTPException:
                unavailable.append(f"{title} — {author}")
                continue
            candidates = matching_items(result, title, author)
            if not candidates:
                try:
                    candidates = matching_items(google_request(query=title), title, author)
                except HTTPException:
                    unavailable.append(f"{title} — {author}")
                    continue
            if not candidates:
                missing.append(f"{title} — {author}")
                continue
            work_ids = []
            for item in candidates:
                source = store_volume(db, item)
                db.flush()
                from app.modules.books.models import Edition
                work_ids.append(db.get(Edition, source.edition_id).work_id)
                editions += 1
            for work_id in work_ids:
                if db.get(Work, work_id):
                    consolidate_equivalent_works(db, work_id)
            loaded.append(f"{title} — {author}")
            db.commit()
        db.execute(text("DELETE FROM app.consultas_catalogo"))
        after = {
            "users": db.scalar(text("SELECT count(*) FROM app.usuarios")),
            "profiles": db.scalar(text("SELECT count(*) FROM app.perfiles")),
            "works": db.scalar(select(func.count(Work.id))),
        }
        if before["users"] != after["users"] or before["profiles"] != after["profiles"]:
            raise RuntimeError("La carga modificó usuarios o perfiles")
        db.commit()
        print({"before": before, "after": after, "loaded": loaded,
               "missing": missing, "provider_unavailable": unavailable,
               "matched_editions": editions})


if __name__ == "__main__":
    main()
