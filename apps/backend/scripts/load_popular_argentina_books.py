"""Load current Argentina bestsellers, restricted to Spanish editions.

Source: https://www.planetadelibros.com.ar/libros-mas-vendidos
"""

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.main import app as _application  # noqa: F401
from app.core.database import SessionLocal
from app.modules.books.models import Edition, Work
from app.modules.books.router import google_request, store_volume
from app.modules.books.service import consolidate_equivalent_works
from scripts.load_popular_spanish_books import matching_items


POPULAR_ARGENTINA = [
    ("Maite", "Fernando Aramburu"),
    ("La vida privada", "Valeria Tentoni"),
    ("El último secreto", "Dan Brown"),
    ("El viaje inútil", "Camila Sosa Villada"),
    ("Morir en la arena", "Leonardo Padura"),
    ("Antonia", "Graciela Ramos"),
    ("Llevará tu nombre", "Sonsoles Ónega"),
    ("Murdle: Resuelve el crimen", "G. T. Karber"),
    ("Primer amor", "Banana Yoshimoto"),
    ("Madre mía", "Mercedes Morán"),
    ("Montoneros", "María O'Donnell"),
    ("76", "Felipe Pigna"),
    ("La soledad", "Gabriel Rolón"),
    ("Persistir", "Agostina Bisio"),
    ("La felicidad", "Gabriel Rolón"),
    ("Los relatos bíblicos", "Gonzalo Garcés"),
    ("Operación Argentina", "Andrés Malamud"),
    ("La hora de los depredadores", "Giuliano da Empoli"),
    ("El acto de crear", "Rick Rubin"),
    ("El duelo", "Gabriel Rolón"),
]


def main():
    from app.core.config import get_settings
    if get_settings().catalog_discovery_enabled:
        from scripts.import_catalog import main as authorized_import
        return authorized_import(default_queries=[f'"{title}" {author}' for title, author in POPULAR_ARGENTINA])
    with SessionLocal() as db:
        before = {"users": db.scalar(text("SELECT count(*) FROM app.usuarios")),
                  "profiles": db.scalar(text("SELECT count(*) FROM app.perfiles")),
                  "works": db.scalar(select(func.count(Work.id)))}
        loaded, missing, editions = [], [], 0
        for title, author in POPULAR_ARGENTINA:
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
        print({"before": before, "after": after, "loaded": loaded,
               "missing": missing, "matched_editions": editions})


if __name__ == "__main__":
    main()
