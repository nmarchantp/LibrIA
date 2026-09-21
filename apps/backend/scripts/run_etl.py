"""Crea una instantanea agregada de publicaciones en analytics."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.database import engine

VERSION = "1"


def run():
    cutoff = datetime.now(timezone.utc)
    start = cutoff - timedelta(days=30)
    run_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO analytics.ejecuciones_etl
            (id, status, started_at, source_cutoff_at, transform_version)
            VALUES (:id, 'running', :started, :cutoff, :version)"""),
            {"id": run_id, "started": cutoff, "cutoff": cutoff, "version": VERSION})
    try:
        with engine.begin() as connection:
            rows = connection.execute(text("""SELECT source, kind, count(*) AS total,
                count(DISTINCT user_id) AS users FROM app.publicaciones
                WHERE created_at >= :start AND created_at < :cutoff
                GROUP BY source, kind ORDER BY source, kind"""), {"start": start, "cutoff": cutoff}).mappings().all()
            total = sum(row["total"] for row in rows)
            metrics = {"total_posts": total, "by_source_and_kind": [dict(row) for row in rows]}
            # JSON serialization stays explicit so this works with SQL text and psycopg.
            import json
            connection.execute(text("""INSERT INTO analytics.instantaneas_actividad
                (id, etl_run_id, period_start, period_end, schema_version, metrics)
                VALUES (:id, :run_id, :start, :cutoff, :version, CAST(:metrics AS jsonb))"""),
                {"id": snapshot_id, "run_id": run_id, "start": start, "cutoff": cutoff,
                 "version": VERSION, "metrics": json.dumps(metrics)})
            connection.execute(text("""UPDATE analytics.ejecuciones_etl SET status='succeeded', finished_at=:finished
                WHERE id=:id"""), {"finished": datetime.now(timezone.utc), "id": run_id})
    except Exception:
        with engine.begin() as connection:
            connection.execute(text("""UPDATE analytics.ejecuciones_etl SET status='failed', finished_at=:finished,
                error_code='transform_failed' WHERE id=:id"""),
                {"finished": datetime.now(timezone.utc), "id": run_id})
        raise
    print(f"ETL {run_id}: {total} publicaciones; instantanea {snapshot_id}")


if __name__ == "__main__":
    run()
