"""Consolidate equivalent catalog works without touching users or profiles."""

from sqlalchemy import func, select, text

from app.core.database import SessionLocal
from app.modules.books.models import Edition, Work
from app.modules.books.service import consolidate_equivalent_works


def main():
    with SessionLocal() as db:
        before = (db.scalar(text("SELECT count(*) FROM app.usuarios")),
                  db.scalar(text("SELECT count(*) FROM app.perfiles")),
                  db.scalar(select(func.count(Work.id))), db.scalar(select(func.count(Edition.id))))
        for work_id in list(db.scalars(select(Work.id).order_by(Work.created_at, Work.id))):
            if db.get(Work, work_id):
                consolidate_equivalent_works(db, work_id)
        db.commit()
        after = (db.scalar(text("SELECT count(*) FROM app.usuarios")),
                 db.scalar(text("SELECT count(*) FROM app.perfiles")),
                 db.scalar(select(func.count(Work.id))), db.scalar(select(func.count(Edition.id))))
        if before[:2] != after[:2]:
            raise RuntimeError("Catalog consolidation changed users or profiles")
        chamber = db.execute(text("""
            SELECT w.id, w.title, w.identity_key, count(DISTINCT e.id) AS editions,
              string_agg(DISTINCT a.name, ', ') AS authors
            FROM app.obras w JOIN app.ediciones e ON e.work_id=w.id
            LEFT JOIN app.obras_autores wa ON wa.work_id=w.id
            LEFT JOIN app.autores a ON a.id=wa.author_id
            WHERE e.title ILIKE '%harry potter%'
              AND (e.title ILIKE '%cámara secreta%' OR e.title ILIKE '%camara secreta%')
            GROUP BY w.id,w.title,w.identity_key ORDER BY w.title
        """)).mappings().all()
        court = db.execute(text("""
            SELECT w.id, w.title, count(DISTINCT e.id) AS editions
            FROM app.obras w JOIN app.ediciones e ON e.work_id=w.id
            WHERE e.title ILIKE '%una corte de rosas y espinas%'
            GROUP BY w.id,w.title ORDER BY w.title
        """)).mappings().all()
        print({"before": dict(zip(("users", "profiles", "works", "editions"), before)),
               "after": dict(zip(("users", "profiles", "works", "editions"), after)),
               "chamber_of_secrets": [dict(row) for row in chamber],
               "court_of_thorns_and_roses": [dict(row) for row in court]})


if __name__ == "__main__":
    main()
