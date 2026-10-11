"""Publicación atómica por día cerrado. El feed legado no es fuente de avances."""
import json
import logging
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database import engine
from app.modules.library.schemas import ReadingReflection
from pydantic import ValidationError

ZONE = ZoneInfo("America/Santiago")
VERSION = "daily-v3"
LOCK_KEY = 963470014


def day_bounds(day: date):
    # Medianoches locales independientes: los días de cambio de hora no duran 24h.
    return (datetime.combine(day, time.min, ZONE).astimezone(timezone.utc),
            datetime.combine(day + timedelta(days=1), time.min, ZONE).astimezone(timezone.utc))


def last_closed_day(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(ZONE).date() - timedelta(days=1)


def extract(connection, start, cutoff):
    params = {"start": start, "cutoff": cutoff}
    works = connection.execute(text("""SELECT id, title FROM app.obras
        WHERE created_at < :cutoff ORDER BY id"""), params).mappings().all()
    events = connection.execute(text("""SELECT ev.*, le.user_id, r.work_id, r.edition_id,
        r.started_at, r.finished_at, r.abandoned_at, r.total_pages AS reading_total,
        ed.work_id AS edition_work, le.work_id AS library_work,
        CASE WHEN p.entity_id IS NULL THEN 'unclassified' ELSE 'simulated' END AS provenance
        FROM app.eventos_lectura ev
        JOIN app.lecturas r ON r.id = ev.reading_id
        JOIN app.entradas_biblioteca le ON le.id = r.library_entry_id
        JOIN app.ediciones ed ON ed.id = r.edition_id
        LEFT JOIN app.procedencia_demo p ON p.entity_type = 'event' AND p.entity_id = ev.id
        WHERE ev.created_at >= :start AND ev.created_at < :cutoff ORDER BY ev.created_at, ev.id"""), params).mappings().all()
    posts = connection.execute(text("""SELECT po.*, pr.kind AS profile_kind,
        pr.owner_user_id, pr.organization_type,
        CASE WHEN p.entity_id IS NULL THEN 'unclassified' ELSE 'simulated' END AS provenance
        FROM app.publicaciones po LEFT JOIN app.perfiles pr ON pr.id = po.author_profile_id
        LEFT JOIN app.procedencia_demo p ON p.entity_type = 'post' AND p.entity_id = po.id
        WHERE po.created_at >= :start AND po.created_at < :cutoff ORDER BY po.id"""), params).mappings().all()
    entries = connection.execute(text("""SELECT le.id, le.user_id, le.work_id,
        CASE WHEN p.entity_id IS NULL THEN 'unclassified' ELSE 'simulated' END AS provenance
        FROM app.entradas_biblioteca le
        LEFT JOIN app.procedencia_demo p ON p.entity_type = 'library' AND p.entity_id = le.id
        WHERE le.created_at >= :start AND le.created_at < :cutoff"""), params).mappings().all()
    reviews = connection.execute(text("""SELECT r.id, r.work_id, r.created_by_user_id,
        p.owner_user_id, p.kind AS profile_kind, rv.edition_id, ed.work_id AS edition_work,
        rv.rating, rv.status, rv.revision_number, rv.recorded_at,
        CASE WHEN r.published_at < :cutoff THEN r.published_at END AS published_at,
        (r.published_at >= :start AND r.published_at < :cutoff) AS first_published_in_period,
        CASE WHEN prov.entity_id IS NULL THEN 'unclassified' ELSE 'simulated' END AS provenance
        FROM app.resenas r JOIN app.perfiles p ON p.id=r.author_profile_id
        JOIN LATERAL (SELECT v.* FROM app.revisiones_resena v
            WHERE v.review_id=r.id AND v.recorded_at < :cutoff
            ORDER BY v.recorded_at DESC, v.revision_number DESC LIMIT 1) rv ON true
        LEFT JOIN app.ediciones ed ON ed.id=rv.edition_id
        LEFT JOIN app.procedencia_demo prov ON prov.entity_type='review' AND prov.entity_id=r.id
        WHERE r.created_at < :cutoff ORDER BY r.id"""), params).mappings().all()
    return works, events, posts, entries, reviews


def transform(works, events, posts, entries, reviews=()):
    rules = Counter()
    catalog = [{"work_id": w["id"], "title": w["title"].strip()} for w in works if w["title"].strip()]
    valid_work_ids = {w["work_id"] for w in catalog}
    rules["invalid_work_title"] = len(works) - len(catalog)
    clean_events, clean_posts = [], []
    clean_reflections = []
    metrics = defaultdict(Counter)
    for event in events:
        pages = event["total_pages"]
        if (event["work_id"] not in valid_work_ids or event["work_id"] != event["edition_work"]
                or event["work_id"] != event["library_work"] or event["actor_user_id"] != event["user_id"]):
            rules["event_identity_mismatch"] += 1
            continue
        kind = event["kind"]
        if (kind not in {"start", "progress", "correction", "finish", "abandon"}
                or pages <= 0 or not 0 <= event["page"] <= pages
                or not 0 <= event["previous_page"] <= pages or pages != event["reading_total"]):
            rules["event_invalid_pages"] += 1
            continue
        started = event["started_at"]
        if started is None or event["created_at"] < started:
            rules["event_invalid_date"] += 1
            continue
        if ((kind == "start" and (event["page"] != 0 or event["previous_page"] != 0 or event["created_at"] != started))
                or (kind == "finish" and (event["page"] != pages or event["finished_at"] != event["created_at"]))
                or (kind == "abandon" and event["abandoned_at"] != event["created_at"])
                or (kind == "progress" and event["page"] <= event["previous_page"])
                or (kind == "correction" and (event["page"] >= event["previous_page"] or event["is_public"]))):
            rules["event_invalid_transition"] += 1
            continue
        clean_events.append({"source_id": event["id"], "user_id": event["user_id"],
                             "work_id": event["work_id"], "edition_id": event["edition_id"],
                             "event_kind": kind, "occurred_at": event["created_at"],
                             "previous_page": event["previous_page"], "page": event["page"],
                             "total_pages": pages, "provenance": event["provenance"]})
        if event.get("reflection") is not None:
            try:
                if kind != "finish":
                    raise ValueError("Reflection must belong to a completion")
                reflection = ReadingReflection.model_validate(event["reflection"]).model_dump()
                clean_reflections.append({"source_id": event["id"], "user_id": event["user_id"],
                    "work_id": event["work_id"], "occurred_at": event["created_at"],
                    "provenance": event["provenance"], "reflection": json.dumps(reflection)})
            except (ValidationError, ValueError):
                rules["reflection_invalid_contract"] += 1
        key = (event["user_id"], event["provenance"])
        if kind in {"start", "finish", "abandon"}:
            metrics[key][{"start": "L04", "finish": "L05", "abandon": "L06"}[kind]] += 1
        if kind != "correction":
            metrics[key]["L09"] = 1
        if kind in {"progress", "correction", "finish"}:
            metrics[key]["L10"] += event["page"] - event["previous_page"]
    for post in posts:
        if post["source"] in {"reading", "review"}:
            rules["legacy_reading_post" if post["source"] == "reading" else "review_model_pending"] += 1
            continue
        if post["author_profile_id"] is None or post["profile_kind"] is None:
            rules["publication_missing_profile"] += 1
            continue
        if (post["source"] not in {"community", "event"} or post["kind"] != "community"
                or post["publication_type"] not in {"free", "institutional", "launch", "event", "news", "promotion"}
                or (post["publication_type"] == "event") != (post["source"] == "event")
                or not post["body"].strip()
                or (post["profile_kind"] == "personal" and post["owner_user_id"] != post["user_id"])):
            rules["publication_invalid_contract"] += 1
            continue
        clean_posts.append({"source_id": post["id"], "user_id": post["user_id"],
                            "profile_id": post["author_profile_id"], "publication_type": post["publication_type"],
                            "published_at": post["created_at"], "provenance": post["provenance"]})
        if post["profile_kind"] == "personal":
            metrics[(post["user_id"], post["provenance"])]["S03"] += 1
    valid_entries = 0
    for entry in entries:
        if entry["work_id"] not in valid_work_ids:
            rules["library_unknown_work"] += 1
            continue
        metrics[(entry["user_id"], entry["provenance"])]["L02"] += 1
        valid_entries += 1
    clean_reviews = []
    valuation_groups = defaultdict(list)
    for review in reviews:
        if (review["work_id"] not in valid_work_ids or review["profile_kind"] != "personal"
                or review["created_by_user_id"] != review["owner_user_id"]
                or (review["edition_id"] and review["edition_work"] != review["work_id"])):
            rules["review_invalid_identity"] += 1
            continue
        if review["status"] == "draft" and review["published_at"] is None:
            rules["review_draft_not_published"] += 1
            continue
        if (review["status"] not in {"published", "hidden"} or review["published_at"] is None
                or review["published_at"] > review["recorded_at"]
                or (review["rating"] is not None and not 1 <= review["rating"] <= 5)):
            rules["review_invalid_revision"] += 1
            continue
        clean_reviews.append({"source_id": review["id"], "user_id": review["owner_user_id"],
                              "work_id": review["work_id"], "edition_id": review["edition_id"],
                              "rating": review["rating"], "status": review["status"],
                              "first_published_at": review["published_at"], "revision_number": review["revision_number"],
                              "revision_recorded_at": review["recorded_at"], "provenance": review["provenance"]})
        metrics[(review["owner_user_id"], review["provenance"])]["S02"] += int(bool(review["first_published_in_period"]))
        if review["status"] == "published":
            valuation_groups[(review["work_id"], review["provenance"])].append(review["rating"])
    valuations = []
    for (work_id, provenance), ratings in valuation_groups.items():
        rated = [rating for rating in ratings if rating is not None]
        valuations.append({"work_id": work_id, "provenance": provenance, "review_count": len(ratings),
                           "rated_count": len(rated), "rating_sum": sum(rated),
                           "rating_average": sum(rated) / len(rated) if rated else None,
                           "distribution": json.dumps({str(value): rated.count(value) for value in range(1, 6)})})
    indicators = []
    for (user_id, provenance), values in metrics.items():
        for code in ("L02", "L04", "L05", "L06", "L09", "L10", "S03", "S02"):
            indicators.append({"user_id": user_id, "indicator_code": code, "value": values[code],
                               "definition_version": VERSION, "provenance": provenance})
    return catalog, clean_events, clean_posts, indicators, rules, {
        "source_events": len(events), "source_posts": len(posts), "source_library_entries": len(entries),
        "catalog_rows": len(catalog), "loaded_events": len(clean_events), "loaded_posts": len(clean_posts),
        "loaded_library_entries": valid_entries, "indicator_rows": len(indicators), "excluded_rows": sum(rules.values()),
        "simulated_events": sum(e["provenance"] == "simulated" for e in clean_events),
        "source_reviews": len(reviews), "loaded_reviews": len(clean_reviews),
        "valuation_rows": len(valuations), "simulated_reviews": sum(r["provenance"] == "simulated" for r in clean_reviews),
        "group_analysis": "protected_global_aggregates_only",
        "loaded_reflections": len(clean_reflections),
        "source_reflections": sum(event.get("reflection") is not None for event in events),
    }, clean_reviews, valuations, clean_reflections


def publish(connection, run_id, prepared):
    catalog, events, posts, indicators, rules, summary, reviews, valuations, reflections = prepared
    statements = (
        (reflections, """INSERT INTO analytics.hechos_reflexiones
            (etl_run_id,source_id,user_id,work_id,occurred_at,provenance,reflection)
            VALUES (:etl_run_id,:source_id,:user_id,:work_id,:occurred_at,:provenance,CAST(:reflection AS jsonb))"""),
        (catalog, """INSERT INTO analytics.catalogo_obras (etl_run_id, work_id, title)
            VALUES (:etl_run_id, :work_id, :title)"""),
        (events, """INSERT INTO analytics.hechos_lectura
            (etl_run_id, source_id, user_id, work_id, edition_id, event_kind, occurred_at, previous_page, page, total_pages, provenance)
            VALUES (:etl_run_id, :source_id, :user_id, :work_id, :edition_id, :event_kind, :occurred_at, :previous_page, :page, :total_pages, :provenance)"""),
        (posts, """INSERT INTO analytics.hechos_publicaciones
            (etl_run_id, source_id, user_id, profile_id, publication_type, published_at, provenance)
            VALUES (:etl_run_id, :source_id, :user_id, :profile_id, :publication_type, :published_at, :provenance)"""),
        (indicators, """INSERT INTO analytics.indicadores_personales
            (etl_run_id, user_id, indicator_code, value, definition_version, provenance)
            VALUES (:etl_run_id, :user_id, :indicator_code, :value, :definition_version, :provenance)"""),
        (reviews, """INSERT INTO analytics.hechos_resenas
            (etl_run_id, source_id, user_id, work_id, edition_id, rating, status, first_published_at,
             revision_number, revision_recorded_at, provenance)
            VALUES (:etl_run_id, :source_id, :user_id, :work_id, :edition_id, :rating, :status,
             :first_published_at, :revision_number, :revision_recorded_at, :provenance)"""),
        (valuations, """INSERT INTO analytics.preparacion_valoraciones_obras
            (etl_run_id, work_id, provenance, review_count, rated_count, rating_sum, rating_average, distribution)
            VALUES (:etl_run_id, :work_id, :provenance, :review_count, :rated_count, :rating_sum,
                    :rating_average, CAST(:distribution AS jsonb))"""),
    )
    for rows, statement in statements:
        if rows:
            connection.execute(text(statement), [{**row, "etl_run_id": run_id} for row in rows])
    validations = [{"etl_run_id": run_id, "rule_code": key, "severity": "warning" if count else "info", "affected_rows": count}
                   for key, count in rules.items()]
    for validation in validations:
        if validation["rule_code"] == "review_draft_not_published":
            validation["severity"] = "info"
    validations.append({"etl_run_id": run_id, "rule_code": "reconciliation", "severity": "info", "affected_rows": 0})
    connection.execute(text("""INSERT INTO analytics.validaciones_etl
        (etl_run_id, rule_code, severity, affected_rows) VALUES (:etl_run_id, :rule_code, :severity, :affected_rows)"""), validations)
    for table, expected in (("catalogo_obras", len(catalog)), ("hechos_lectura", len(events)),
                            ("hechos_publicaciones", len(posts)), ("indicadores_personales", len(indicators)),
                            ("hechos_resenas", len(reviews)), ("preparacion_valoraciones_obras", len(valuations)),
                            ("hechos_reflexiones", len(reflections))):
        actual = connection.execute(text(f"SELECT count(*) FROM analytics.{table} WHERE etl_run_id = :id"), {"id": run_id}).scalar_one()
        if actual != expected:
            raise ValueError("reconciliation_failed")
    connection.execute(text("""UPDATE analytics.ejecuciones_etl SET status='succeeded',
        phase='completed', finished_at=now(), error_code=NULL, summary=CAST(:summary AS jsonb) WHERE id=:id"""),
                       {"id": run_id, "summary": json.dumps(summary)})
    return summary


def run_day(day: date, *, db_engine=engine, now=None):
    if day > last_closed_day(now):
        raise ValueError("Solo se pueden cargar días completamente cerrados en America/Santiago")
    start, cutoff = day_bounds(day)
    with db_engine.connect() as lock_connection:
        acquired = lock_connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        lock_connection.commit()
        if not acquired:
            return {"status": "busy", "business_date": str(day)}
        try:
            with lock_connection.begin():
                row = lock_connection.execute(text("""SELECT id, status FROM analytics.ejecuciones_etl
                    WHERE business_date=:day FOR UPDATE"""), {"day": day}).mappings().first()
                if row and row["status"] == "succeeded":
                    return {"status": "already_completed", "business_date": str(day), "id": str(row["id"])}
                if row:
                    run_id = row["id"]
                    lock_connection.execute(text("""UPDATE analytics.ejecuciones_etl SET status='running', phase='queued', started_at=now(),
                        finished_at=NULL, error_code=NULL, attempt_count=attempt_count+1 WHERE id=:id"""), {"id": run_id})
                else:
                    run_id = uuid.uuid4()
                    lock_connection.execute(text("""INSERT INTO analytics.ejecuciones_etl
                        (id, business_date, status, started_at, period_start, source_cutoff_at, transform_version)
                        VALUES (:id, :day, 'running', now(), :start, :cutoff, :version)"""),
                        {"id": run_id, "day": day, "start": start, "cutoff": cutoff, "version": VERSION})
            try:
                with db_engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                    with connection.begin():
                        summary = publish(connection, run_id, transform(*extract(connection, start, cutoff)))
                return {"status": "succeeded", "business_date": str(day), "id": str(run_id), "summary": summary}
            except Exception:
                with lock_connection.begin():
                    lock_connection.execute(text("""UPDATE analytics.ejecuciones_etl SET status='failed', phase='failed', finished_at=now(),
                        error_code='daily_transform_failed' WHERE id=:id"""), {"id": run_id})
                raise
        finally:
            if lock_connection.in_transaction():
                lock_connection.rollback()
            lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            lock_connection.commit()


def run_pending(*, db_engine=engine, now=None):
    """Recupera cierres pendientes desde la primera fecha cargada; nunca hoy."""
    closed = last_closed_day(now)
    with db_engine.connect() as connection:
        first = connection.execute(text("SELECT min(business_date) FROM analytics.ejecuciones_etl")).scalar_one()
        completed = set(connection.execute(text("SELECT business_date FROM analytics.ejecuciones_etl WHERE status='succeeded' AND business_date IS NOT NULL")).scalars())
    current = first or closed
    results = []
    while current <= closed:
        if current not in completed:
            result = run_day(current, db_engine=db_engine, now=now)
            results.append(result)
            if result["status"] == "busy":
                break
        current += timedelta(days=1)
    return results


def run_manual(run_id, *, db_engine=engine):
    """Run a requested snapshot in a worker; publish only after reconciliation."""
    with db_engine.connect() as lock_connection:
        acquired = lock_connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        lock_connection.commit()
        if not acquired:
            return
        try:
            with lock_connection.begin():
                run = lock_connection.execute(text("""SELECT status, period_start, source_cutoff_at
                    FROM analytics.ejecuciones_etl WHERE id=:id AND run_kind='manual' FOR UPDATE"""), {"id": run_id}).mappings().one()
                if run["status"] != "running":
                    return
                lock_connection.execute(text("UPDATE analytics.ejecuciones_etl SET phase='extracting' WHERE id=:id"), {"id": run_id})
            with db_engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                with connection.begin():
                    sources = extract(connection, run["period_start"], run["source_cutoff_at"])
                    with lock_connection.begin():
                        lock_connection.execute(text("UPDATE analytics.ejecuciones_etl SET phase='transforming' WHERE id=:id"), {"id": run_id})
                    prepared = transform(*sources)
            with lock_connection.begin():
                lock_connection.execute(text("""UPDATE analytics.ejecuciones_etl SET phase='loading',
                    summary=CAST(:summary AS jsonb) WHERE id=:id"""),
                    {"id": run_id, "summary": json.dumps(prepared[5])})
            with db_engine.begin() as connection:
                publish(connection, run_id, prepared)
        except Exception:
            logging.getLogger(__name__).exception("Manual ETL failed: %s", run_id)
            if lock_connection.in_transaction():
                lock_connection.rollback()
            with lock_connection.begin():
                lock_connection.execute(text("""UPDATE analytics.ejecuciones_etl SET status='failed', phase='failed',
                    finished_at=now(), error_code='manual_transform_failed' WHERE id=:id"""), {"id": run_id})
        finally:
            if lock_connection.in_transaction():
                lock_connection.rollback()
            if acquired:
                lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                lock_connection.commit()


def resume_manual_pending(*, db_engine=engine):
    """Resume interrupted requests with their original cutoff and shared lock."""
    with db_engine.connect() as connection:
        ids = connection.execute(text("""SELECT id FROM analytics.ejecuciones_etl
            WHERE run_kind='manual' AND status='running' ORDER BY started_at""")).scalars().all()
    for run_id in ids:
        run_manual(run_id, db_engine=db_engine)
