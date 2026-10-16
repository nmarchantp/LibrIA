"""Delete non-Spanish works and their catalog activity, preserving identities."""

import argparse

from sqlalchemy import text

from app.core.database import SessionLocal


COUNTS_SQL = text("""
    SELECT
      (SELECT count(*) FROM app.usuarios) AS users,
      (SELECT count(*) FROM app.perfiles) AS profiles,
      (SELECT count(*) FROM app.obras) AS works,
      (SELECT count(*) FROM app.obras WHERE original_language='es') AS spanish_works,
      (SELECT count(*) FROM app.obras WHERE original_language IS DISTINCT FROM 'es') AS works_to_remove,
      (SELECT count(*) FROM app.ediciones e JOIN app.obras w ON w.id=e.work_id
        WHERE w.original_language IS DISTINCT FROM 'es') AS editions_to_remove,
      (SELECT count(*) FROM app.entradas_biblioteca b JOIN app.obras w ON w.id=b.work_id
        WHERE w.original_language IS DISTINCT FROM 'es') AS library_entries_to_remove,
      (SELECT count(*) FROM app.lecturas l JOIN app.obras w ON w.id=l.work_id
        WHERE w.original_language IS DISTINCT FROM 'es') AS readings_to_remove,
      (SELECT count(*) FROM app.resenas r JOIN app.obras w ON w.id=r.work_id
        WHERE w.original_language IS DISTINCT FROM 'es') AS reviews_to_remove
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
            CREATE TEMP TABLE purge_work_ids ON COMMIT DROP AS
            SELECT id FROM app.obras WHERE original_language IS DISTINCT FROM 'es';

            DELETE FROM app.comentarios_publicacion WHERE review_id IN (
              SELECT id FROM app.resenas WHERE work_id IN (SELECT id FROM purge_work_ids));
            DELETE FROM app.comentarios_publicacion WHERE reading_event_id IN (
              SELECT ev.id FROM app.eventos_lectura ev JOIN app.lecturas l ON l.id=ev.reading_id
              WHERE l.work_id IN (SELECT id FROM purge_work_ids));

            DELETE FROM app.migraciones_resenas WHERE review_id IN (
              SELECT id FROM app.resenas WHERE work_id IN (SELECT id FROM purge_work_ids));
            DELETE FROM app.revisiones_resena WHERE review_id IN (
              SELECT id FROM app.resenas WHERE work_id IN (SELECT id FROM purge_work_ids));
            DELETE FROM app.resenas WHERE work_id IN (SELECT id FROM purge_work_ids);

            DELETE FROM app.progreso_lectura WHERE reading_id IN (
              SELECT id FROM app.lecturas WHERE work_id IN (SELECT id FROM purge_work_ids));
            DELETE FROM app.eventos_lectura WHERE reading_id IN (
              SELECT id FROM app.lecturas WHERE work_id IN (SELECT id FROM purge_work_ids));
            DELETE FROM app.lecturas WHERE work_id IN (SELECT id FROM purge_work_ids);
            DELETE FROM app.entradas_biblioteca WHERE work_id IN (SELECT id FROM purge_work_ids);
            DELETE FROM app.ediciones WHERE work_id IN (SELECT id FROM purge_work_ids);
            DELETE FROM app.obras WHERE id IN (SELECT id FROM purge_work_ids);
            DELETE FROM app.consultas_catalogo;
        """))
        after = dict(db.execute(COUNTS_SQL).mappings().one())
        if (before["users"], before["profiles"]) != (after["users"], after["profiles"]):
            raise RuntimeError("La limpieza intentó modificar usuarios o perfiles")
        if after["works_to_remove"] != 0:
            raise RuntimeError("Aún quedan obras cuyo original_language no es 'es'")
        db.commit()
        print({"after": after})


if __name__ == "__main__":
    main()
