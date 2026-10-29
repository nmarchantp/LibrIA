"""Load bestsellers in Chile, restricted to verified Spanish Google editions.

Source: El Mercurio/GDA ranking for Chile, based on Antártica, Feria Chilena
del Libro, Trayecto Bookstore, Librerías UC and Lolita.
https://gda.com/detalle-de-la-noticia/?article=6119153
"""

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.main import app as _application  # noqa: F401 - registers every ORM table
from app.core.database import SessionLocal
from app.modules.books.models import Edition, Work
from app.modules.books.router import google_request, store_volume
from app.modules.books.service import consolidate_equivalent_works
from scripts.load_popular_spanish_books import matching_items


POPULAR_CHILE = [
    ("El buzón de las impuras", "Francisca Solar"),
    ("Te receto un gato", "Syou Ishida"),
    ("Mi nombre es Emilia del Valle", "Isabel Allende"),
    ("Si fuéramos eternos", "Emma Gil"),
    ("Murdle resuelve el crimen", "G. T. Karber"),
    ("La paciente silenciosa", "Alex Michaelides"),
    ("El último secreto", "Dan Brown"),
    ("La asistenta", "Freida McFadden"),
    ("Más que rivales", "Rachel Reid"),
    ("1984", "George Orwell"),
    ("Magnifica Humanitas", "León XIV"),
    ("Boric frente a frente", "Marian Basso"),
    ("El hombre en busca de sentido", "Viktor Frankl"),
    ("Sombras de impunidad", "Cristián Vargas"),
    ("Mi psicóloga me dijo", "Khaterine Hoyer"),
    ("Los Luksic", "Sergio Jara"),
    ("Hábitos atómicos", "James Clear"),
    ("Mapocho incaico", "Rubén Stehberg"),
    ("Ikigai", "Francesc Miralles"),
    ("La palabra mágica", "Isabel Allende"),
]


def main():
    from app.core.config import get_settings
    if get_settings().catalog_discovery_enabled:
        from scripts.import_catalog import main as authorized_import
        return authorized_import(default_queries=[f'"{title}" {author}' for title, author in POPULAR_CHILE])
    with SessionLocal() as db:
        before = {"users": db.scalar(text("SELECT count(*) FROM app.usuarios")),
                  "profiles": db.scalar(text("SELECT count(*) FROM app.perfiles")),
                  "works": db.scalar(select(func.count(Work.id)))}
        loaded, missing, unavailable, editions = [], [], [], 0
        for title, author in POPULAR_CHILE:
            candidates = []
            for query in (f'"{title}" {author}', title):
                try:
                    candidates = matching_items(google_request(query=query), title, author)
                except HTTPException:
                    continue
                if candidates:
                    break
            if not candidates:
                missing.append(f"{title} — {author}")
                continue
            work_ids = []
            for item in candidates:
                source = store_volume(db, item)
                db.flush()
                work_ids.append(db.get(Edition, source.edition_id).work_id)
                editions += 1
            for work_id in work_ids:
                if db.get(Work, work_id):
                    consolidate_equivalent_works(db, work_id)
            loaded.append(f"{title} — {author}")
            db.commit()
        db.execute(text("DELETE FROM app.consultas_catalogo"))
        after = {"users": db.scalar(text("SELECT count(*) FROM app.usuarios")),
                 "profiles": db.scalar(text("SELECT count(*) FROM app.perfiles")),
                 "works": db.scalar(select(func.count(Work.id)))}
        if before["users"] != after["users"] or before["profiles"] != after["profiles"]:
            raise RuntimeError("La carga modificó usuarios o perfiles")
        db.commit()
        print({"before": before, "after": after, "loaded": loaded, "missing": missing,
               "provider_unavailable": unavailable, "matched_editions": editions})


if __name__ == "__main__":
    main()
