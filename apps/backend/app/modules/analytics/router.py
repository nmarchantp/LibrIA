"""El administrador monitorea procesos; cada titular consulta sus indicadores."""
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.identity_models import AccountPermission
from app.modules.users.models import User
from app.modules.analytics.etl import ZONE, VERSION, LOCK_KEY, day_bounds, last_closed_day, run_manual

router = APIRouter(prefix="/analytics", tags=["analytics"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


def require_admin(user: CurrentUser, db: Database):
    if db.get(AccountPermission, (user.id, "admin")) is None:
        raise HTTPException(status_code=403, detail="Se requiere permiso administrativo de cuenta")
    return user


class ManualEtlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID


@router.post("/admin/etl/run", status_code=202)
def request_manual_etl(payload: ManualEtlRequest, tasks: BackgroundTasks, response: Response,
                       db: Database, admin: Annotated[User, Depends(require_admin)]):
    response.headers["Cache-Control"] = "no-store"
    existing = db.execute(text("SELECT id, status, run_kind FROM analytics.ejecuciones_etl WHERE id=:id"),
                          {"id": payload.request_id}).mappings().first()
    if existing:
        if existing["run_kind"] != "manual":
            raise HTTPException(status_code=409, detail="Identificador de solicitud ya utilizado")
        return {"id": str(existing["id"]), "status": existing["status"]}
    acquired = db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
    if not acquired or db.execute(text("SELECT 1 FROM analytics.ejecuciones_etl WHERE status='running' LIMIT 1")).first():
        raise HTTPException(status_code=409, detail="Ya hay una ejecución ETL en curso")
    cutoff = datetime.now(timezone.utc)
    start = day_bounds(cutoff.astimezone(ZONE).date() - timedelta(days=29))[0]
    db.execute(text("""INSERT INTO analytics.ejecuciones_etl
        (id, status, started_at, period_start, source_cutoff_at, transform_version, run_kind, requested_by, phase)
        VALUES (:id, 'running', now(), :start, :cutoff, :version, 'manual', :admin, 'queued')"""),
        {"id": payload.request_id, "start": start, "cutoff": cutoff, "version": VERSION, "admin": admin.id})
    db.commit()
    tasks.add_task(run_manual, payload.request_id)
    return {"id": str(payload.request_id), "status": "running"}


@router.get("/admin/etl")
def etl_overview(response: Response, db: Database, admin: Annotated[User, Depends(require_admin)],
                 limit: Annotated[int, Query(ge=1, le=100)] = 30):
    response.headers["Cache-Control"] = "no-store"
    rows = db.execute(text("""SELECT id, business_date, status, started_at, finished_at,
        period_start, source_cutoff_at, transform_version, attempt_count, error_code, summary, run_kind, phase
        FROM analytics.ejecuciones_etl WHERE business_date IS NOT NULL OR run_kind='manual'
        ORDER BY started_at DESC LIMIT :limit"""), {"limit": limit}).mappings().all()
    latest = db.execute(text("""SELECT max(business_date) FROM analytics.ejecuciones_etl
        WHERE status='succeeded' AND business_date IS NOT NULL""")).scalar_one()
    closed = last_closed_day()
    pending_days = db.execute(text("""SELECT count(*) FROM generate_series(
        COALESCE((SELECT min(business_date)::timestamp FROM analytics.ejecuciones_etl), CAST(:closed AS timestamp)),
        CAST(:closed AS timestamp), interval '1 day') AS days(day)
        WHERE NOT EXISTS (SELECT 1 FROM analytics.ejecuciones_etl e
                          WHERE e.business_date=days.day::date AND e.status='succeeded')"""), {"closed": closed}).scalar_one()
    counts = db.execute(text("""SELECT
        (SELECT count(*) FROM analytics.catalogo_obras) AS catalog_rows,
        (SELECT count(*) FROM analytics.hechos_lectura) AS reading_rows,
        (SELECT count(*) FROM analytics.hechos_publicaciones) AS publication_rows,
        (SELECT count(*) FROM analytics.indicadores_personales) AS indicator_rows,
        (SELECT count(*) FROM analytics.hechos_resenas) AS review_rows""")).mappings().one()
    migration = db.execute(text("SELECT result, reason_code, count(*) AS total FROM app.migraciones_resenas GROUP BY result, reason_code ORDER BY result, reason_code")).mappings().all()
    today = datetime.now(timezone.utc).astimezone(ZONE).date()
    _, next_run = day_bounds(today)
    return {"timezone": ZONE.key, "schedule": "00:00", "scheduler_enabled": get_settings().analytics_scheduler_enabled,
            "next_run_at": next_run, "latest_closed_day": closed, "last_loaded_day": latest,
            "up_to_date": latest == closed and pending_days == 0, "pending_days": pending_days, "transform_version": VERSION,
            "counts": dict(counts), "runs": [dict(row) for row in rows],
            "group_analysis_enabled": True, "review_migration": [dict(row) for row in migration]}


@router.get("/admin/etl/{run_id}/validations")
def etl_validations(run_id: uuid.UUID, response: Response, db: Database,
                    admin: Annotated[User, Depends(require_admin)]):
    response.headers["Cache-Control"] = "no-store"
    exists = db.execute(text("SELECT id FROM analytics.ejecuciones_etl WHERE id=:id AND (business_date IS NOT NULL OR run_kind='manual')"), {"id": run_id}).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    rows = db.execute(text("""SELECT rule_code, severity, affected_rows FROM analytics.validaciones_etl
        WHERE etl_run_id=:id ORDER BY affected_rows DESC, rule_code"""), {"id": run_id}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/me")
def personal_indicators(response: Response, user: CurrentUser, db: Database,
                        start: date | None = None, end: date | None = None):
    response.headers["Cache-Control"] = "no-store"
    closed = last_closed_day()
    end = end or closed
    start = start or end - timedelta(days=29)
    if start > end or (end - start).days > 365 or end > closed:
        raise HTTPException(status_code=422, detail="Elige un intervalo cerrado de hasta 366 días")
    rows = db.execute(text("""SELECT e.business_date, i.indicator_code, i.value,
        i.definition_version, i.provenance FROM analytics.indicadores_personales i
        JOIN analytics.ejecuciones_etl e ON e.id=i.etl_run_id
        WHERE i.user_id=:user AND i.provenance <> 'simulated' AND e.status='succeeded' AND e.business_date BETWEEN :start AND :end
        ORDER BY e.business_date, i.indicator_code, i.provenance"""),
        {"user": user.id, "start": start, "end": end}).mappings().all()
    return {"start": start, "end": end, "items": [dict(row) for row in rows]}
