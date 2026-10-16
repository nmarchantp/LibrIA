"""Keep only editions whose language is exactly ``es`` without deleting identities."""

import argparse

from sqlalchemy import text

from app.core.database import SessionLocal


COUNTS_SQL = text("""
    SELECT
      (SELECT count(*) FROM app.usuarios) AS users,
      (SELECT count(*) FROM app.perfiles) AS profiles,
      (SELECT count(*) FROM app.obras) AS works,
      (SELECT count(*) FROM app.ediciones) AS editions,
      (SELECT count(*) FROM app.ediciones WHERE language IS DISTINCT FROM 'es') AS editions_to_remove,
      (SELECT count(*) FROM app.lecturas l JOIN app.ediciones e ON e.id=l.edition_id
        WHERE e.language IS DISTINCT FROM 'es') AS readings_to_reassign,
      (SELECT count(*) FROM app.resenas r JOIN app.ediciones e ON e.id=r.edition_id
        WHERE e.language IS DISTINCT FROM 'es') AS reviews_to_unlink,
      (SELECT count(*) FROM app.obras w WHERE NOT EXISTS (
        SELECT 1 FROM app.ediciones e WHERE e.work_id=w.id AND e.language='es')) AS works_without_spanish_edition
""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        before = dict(db.execute(COUNTS_SQL).mappings().one())
        print({"mode": "apply" if args.apply else "dry-run", "before": before})
        if not args.apply:
            return
        db.execute(text("""
            CREATE TEMP TABLE purge_edition_ids ON COMMIT DROP AS
            SELECT id,work_id FROM app.ediciones WHERE language IS DISTINCT FROM 'es';

            -- Preserve reading attempts by moving them to a Spanish edition of
            -- the same work. Works without one are handled by the guard below.
            UPDATE app.lecturas l SET edition_id=replacement.id
            FROM purge_edition_ids old,
                 LATERAL (SELECT e.id FROM app.ediciones e
                          WHERE e.work_id=old.work_id AND e.language='es'
                          ORDER BY e.created_at,e.id LIMIT 1) replacement
            WHERE l.edition_id=old.id;

            UPDATE app.resenas SET edition_id=NULL
            WHERE edition_id IN (SELECT id FROM purge_edition_ids);
            UPDATE app.revisiones_resena SET edition_id=NULL
            WHERE edition_id IN (SELECT id FROM purge_edition_ids);
            DELETE FROM app.ediciones WHERE id IN (SELECT id FROM purge_edition_ids);
            DELETE FROM app.consultas_catalogo;
        """))
        after = dict(db.execute(COUNTS_SQL).mappings().one())
        if (before["users"], before["profiles"]) != (after["users"], after["profiles"]):
            raise RuntimeError("La limpieza intentó modificar usuarios o perfiles")
        if after["editions_to_remove"] != 0:
            raise RuntimeError("Aún quedan ediciones cuyo language no es 'es'")
        db.commit()
        print({"after": after})


if __name__ == "__main__":
    main()
