"""Evidence from analytics only; owner isolation and bounded aggregate releases."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text

from app.modules.analytics.reader_evidence import personal_samples
from app.modules.analytics.etl import ZONE, day_bounds

MIN_GROUP = 10
MIN_CONTRIBUTORS = 5
LABELS = {
    "Q02": ("Aportes personales incluidos sobre libros", "aportes"),
    "Q01": ("Reflexiones personales al finalizar", "reflexiones"),
    "L02": ("Libros incorporados", "libros"), "L04": ("Intentos iniciados", "intentos"),
    "L05": ("Intentos finalizados", "intentos"), "L06": ("Intentos abandonados", "intentos"),
    "L09": ("Días con actividad registrada", "días"), "L10": ("Cambio neto de posición", "páginas de posición"),
    "S02": ("Reseñas publicadas por primera vez", "reseñas"), "S03": ("Publicaciones personales", "publicaciones"),
    "RATING": ("Valoración media de tus reseñas publicadas", "sobre 5"),
    "G_READERS": ("Participantes con actividad", "participantes, aprox."),
    "G_STARTS": ("Intentos iniciados", "intentos, aprox."),
    "G_FINISHES": ("Intentos finalizados", "intentos, aprox."),
    "G_ABANDONS": ("Intentos abandonados", "intentos, aprox."),
    "G_REVIEWS": ("Reseñas publicadas al corte", "reseñas, aprox."),
    "G_RATING": ("Valoración media agregada", "sobre 5, aprox."),
}


def group_access(db, user_id):
    return db.execute(text("""SELECT 1 FROM app.perfiles p WHERE p.verification_status NOT IN ('rejected','suspended')
        AND ((p.kind='personal' AND p.owner_user_id=:user AND EXISTS
              (SELECT 1 FROM app.capacidades_perfil c WHERE c.profile_id=p.id AND c.capability='autor'))
             OR (p.kind='organization' AND p.organization_type IN ('editorial','libreria') AND EXISTS
              (SELECT 1 FROM app.miembros_perfil m WHERE m.profile_id=p.id AND m.user_id=:user))) LIMIT 1"""),
        {"user": user_id}).first() is not None


def require_group_access(db, user_id):
    if not group_access(db, user_id):
        raise HTTPException(status_code=403, detail="Se requiere un perfil de autor o pertenecer a una editorial o librería")


def metric(code, value):
    label, unit = LABELS[code]
    return {"label": label, "value": value, "unit": unit}


def source_runs(db):
    latest = db.execute(text("""SELECT id, business_date, run_kind, period_start, source_cutoff_at
        FROM analytics.ejecuciones_etl WHERE status='succeeded' AND (business_date IS NOT NULL OR run_kind='manual')
        ORDER BY source_cutoff_at DESC, finished_at DESC LIMIT 1""")).mappings().first()
    if latest is None:
        return [], None
    from app.modules.books.canonical import enabled, identity_version
    identity = identity_version(db) if enabled() else None
    if identity and db.execute(text('SELECT identity_version FROM analytics.ejecuciones_etl WHERE id=:id'), {'id':latest['id']}).scalar() != identity:
        return [], None
    if latest["run_kind"] == "manual":
        runs = [latest]
        start = latest["period_start"]
    else:
        first = latest["business_date"] - timedelta(days=29)
        runs = db.execute(text("""SELECT id FROM analytics.ejecuciones_etl WHERE status='succeeded'
            AND business_date BETWEEN :first AND :last ORDER BY business_date"""),
            {"first": first, "last": latest["business_date"]}).mappings().all()
        start = day_bounds(first)[0]
    if identity:
        versions = db.execute(text('SELECT identity_version FROM analytics.ejecuciones_etl WHERE id=ANY(:ids)'), {'ids':[r['id'] for r in runs]}).scalars().all()
        if any(version != identity for version in versions):
            return [], None
    period = {"start": start.isoformat(), "cutoff": latest["source_cutoff_at"].isoformat(),
              "source": latest["run_kind"], "daily_closures": len(runs) if latest["run_kind"] == "daily" else None}
    return [run["id"] for run in runs], {"period": period, "latest_id": latest["id"]}


def facts(db, ids, latest_id, provenance, owner=None):
    params = {"ids": ids, "latest": latest_id, "provenance": provenance, "owner": owner}
    owner_clause = " AND user_id=:owner" if owner is not None else ""
    events = db.execute(text("""SELECT user_id, event_kind, occurred_at, page, previous_page
        FROM analytics.hechos_lectura WHERE etl_run_id=ANY(CAST(:ids AS uuid[])) AND provenance=:provenance"""
        + owner_clause), params).mappings().all()
    reviews = db.execute(text("""SELECT user_id, rating FROM analytics.hechos_resenas
        WHERE etl_run_id=:latest AND status='published' AND provenance=:provenance"""
        + owner_clause), params).mappings().all()
    return events, reviews


def personal_evidence(db, user_id, provenance):
    ids, source = source_runs(db)
    if not ids:
        return None
    events, reviews = facts(db, ids, source["latest_id"], provenance, user_id)
    indicators = db.execute(text("""SELECT indicator_code, sum(value) AS value FROM analytics.indicadores_personales
        WHERE etl_run_id=ANY(CAST(:ids AS uuid[])) AND user_id=:owner AND provenance=:provenance
        GROUP BY indicator_code"""), {"ids": ids, "owner": user_id, "provenance": provenance}).mappings().all()
    reflections = db.execute(text("""SELECT reflection,occurred_at FROM analytics.hechos_reflexiones
        WHERE etl_run_id=ANY(CAST(:ids AS uuid[])) AND user_id=:owner AND provenance=:provenance
        ORDER BY occurred_at DESC,source_id DESC LIMIT 10"""),
        {"ids": ids, "owner": user_id, "provenance": provenance}).mappings().all()
    samples, truncated = personal_samples(db, source["latest_id"], user_id, provenance)
    if not indicators and not events and not reviews and not reflections and not samples:
        return None
    values = {row["indicator_code"]: float(row["value"]) for row in indicators}
    values["L09"] = len({event["occurred_at"].astimezone(ZONE).date() for event in events if event["event_kind"] != "correction"})
    ratings = [row["rating"] for row in reviews if row["rating"] is not None]
    if ratings:
        values["RATING"] = round(sum(ratings) / len(ratings), 2)
    if reflections:
        values["Q01"] = len(reflections)
    if samples:
        values["Q02"] = len(samples)
    return {"scope": "personal", "period": source["period"], "provenance": provenance,
            "qualitative": [row["reflection"] for row in reflections],
            "reader_contributions": samples, "contributions_truncated": truncated,
            "metrics": {code: metric(code, value) for code, value in values.items() if code in LABELS},
            "limitations": ["Se interpretan registros disponibles, no toda tu actividad lectora.",
                            "El cambio de posición no equivale a páginas efectivamente leídas.",
                            "Las emociones se interpretan solo cuando las declaras sobre un libro; no describen tu personalidad ni tu salud mental.",
                            "La muestra cualitativa incluye hasta diez reflexiones privadas dentro del periodo cargado.",
                            "Los aportes son una instant?nea acumulada al corte, no actividad exclusiva del intervalo. Incluyen rese?as privadas, valoraciones, notas, teor?as y cuadernos propios.",
                            "Se env?an hasta 32 aportes recientes y 18000 caracteres de texto; la muestra puede estar recortada. Los cuadernos no tienen historial de versiones."]}


def round_count(value):
    return int((value + 2) // 5 * 5)


def aggregate_evidence(events, reviews, period, provenance):
    readers = {row["user_id"] for row in events if row["event_kind"] != "correction"} | {row["user_id"] for row in reviews}
    if len(readers) < MIN_GROUP:
        return None
    values = {"G_READERS": metric("G_READERS", round_count(len(readers)))}
    for kind, code in (("start", "G_STARTS"), ("finish", "G_FINISHES"), ("abandon", "G_ABANDONS")):
        counts = Counter(row["user_id"] for row in events if row["event_kind"] == kind)
        if len(counts) >= MIN_CONTRIBUTORS:
            values[code] = metric(code, round_count(sum(min(count, 10) for count in counts.values())))
    review_counts = Counter(row["user_id"] for row in reviews)
    if len(review_counts) >= MIN_CONTRIBUTORS:
        values["G_REVIEWS"] = metric("G_REVIEWS", round_count(sum(min(count, 10) for count in review_counts.values())))
    ratings = defaultdict(list)
    for row in reviews:
        if row["rating"] is not None:
            ratings[row["user_id"]].append(row["rating"])
    if len(ratings) >= MIN_CONTRIBUTORS:
        # Equal weight for each contributor, rather than prolific reviewers.
        average = sum(sum(items) / len(items) for items in ratings.values()) / len(ratings)
        values["G_RATING"] = metric("G_RATING", int(average * 2 + .5) / 2)
    return {"scope": "group", "period": period, "provenance": provenance, "metrics": values,
            "minimum_participants": MIN_GROUP,
            "limitations": ["Resumen general de participantes registrados; no representa el mercado completo.",
                            "Conteos redondeados a múltiplos de cinco y contribuciones limitadas por participante.",
                            "Se omiten métricas con menos de cinco contribuyentes. No hay filtros por persona, libro o segmento.",
                            "Las valoraciones ponderan a cada participante por igual y se redondean a medio punto.",
                            "No permite inferir ventas, emociones, géneros preferidos ni causalidad."]}


def group_evidence(db, provenance):
    release_day = datetime.now(timezone.utc).astimezone(ZONE).date()
    params = {"day": release_day, "provenance": provenance}
    stored = db.execute(text("SELECT payload FROM analytics.resumenes_grupales WHERE release_date=:day AND provenance=:provenance"), params).scalar_one_or_none()
    if stored is not None:
        return stored
    ids, source = source_runs(db)
    if not ids:
        return None
    events, reviews = facts(db, ids, source["latest_id"], provenance)
    evidence = aggregate_evidence(events, reviews, source["period"], provenance)
    if evidence is None:
        return None
    evidence["release_date"] = release_day.isoformat()
    db.execute(text("""INSERT INTO analytics.resumenes_grupales (release_date, provenance, payload)
        VALUES (:day, :provenance, CAST(:payload AS jsonb)) ON CONFLICT DO NOTHING"""),
        {**params, "payload": json.dumps(evidence)})
    # Concurrent readers receive the same release, not separate evolving cuts.
    stored = db.execute(text("SELECT payload FROM analytics.resumenes_grupales WHERE release_date=:day AND provenance=:provenance"), params).scalar_one()
    db.commit()
    return stored


def cache_params(evidence, scope, user_id):
    fingerprint = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    return {"scope": scope, "subject": str(user_id) if scope == "personal" else "group", "hash": fingerprint}


def cached_interpretation(db, evidence, scope, user_id):
    params = cache_params(evidence, scope, user_id)
    row = db.execute(text("""SELECT id, content, created_at, provider, model FROM ia.interpretaciones_ia
        WHERE scope=:scope AND subject_key=:subject AND data_hash=:hash
        ORDER BY created_at DESC LIMIT 1"""), params).mappings().first()
    return dict(row) if row else None


def interpret(db, evidence, scope, user_id):
    raise HTTPException(status_code=501, detail="Esta interpretación aún no tiene contrato Gemini aprobado")
