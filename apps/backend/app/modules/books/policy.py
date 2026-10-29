"""Rollout and transaction policy shared by the phase-3 entry points."""
from contextlib import contextmanager
from contextvars import ContextVar
import time
import os

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings

_provider_deadline = ContextVar("catalog_provider_deadline", default=None)


def reject_legacy_writer():
    if get_settings().catalog_discovery_enabled:
        raise HTTPException(409, detail={"code": "legacy_catalog_writer_disabled",
                                        "message": "Usa la incorporación de biblioteca o una importación administrativa autorizada."})


def require_disposable_fixture(db):
    """Synthetic seeders are fixtures, not an alternate persistent catalog writer."""
    marker = os.environ.get("CATALOG_PHASE1_DISPOSABLE_MARKER", "")
    if not marker.startswith("catalog-phase1-"):
        raise RuntimeError("Synthetic catalog fixtures require the owned disposable PostgreSQL harness")
    name, actual = db.execute(text("SELECT current_database(),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).one()
    if name != "catalog_phase1_disposable" or actual != marker:
        raise RuntimeError("Refusing synthetic catalog writes outside the disposable database")


@contextmanager
def provider_budget():
    token = _provider_deadline.set(time.monotonic() + get_settings().catalog_provider_timeout_seconds)
    try:
        yield
    finally:
        _provider_deadline.reset(token)


def provider_remaining(default):
    deadline = _provider_deadline.get()
    if deadline is None:
        return default
    remaining = min(default, deadline - time.monotonic())
    if remaining <= 0:
        raise HTTPException(502, detail={"code": "provider_timeout", "message": "El proveedor excedió el tiempo de consulta. Reintenta más tarde."})
    return remaining


def provider_sleep(delay):
    if provider_remaining(float("inf")) <= delay:
        raise HTTPException(502, detail={"code": "provider_timeout", "message": "El proveedor excedió el tiempo de consulta. Reintenta más tarde."})
    time.sleep(delay)


def execute_catalog_command(db, operation):
    """Facade owns commit/retry; helpers never commit. Only use a clean request session."""
    settings = get_settings()
    db.rollback()  # release authentication/read-only transactions before a write attempt
    for attempt in range(settings.catalog_write_attempts):
        try:
            with db.begin():
                db.execute(text("SELECT set_config('lock_timeout',:value,true)"), {"value": f"{settings.catalog_lock_timeout_ms}ms"})
                db.execute(text("SELECT set_config('statement_timeout',:value,true)"), {"value": f"{settings.catalog_statement_timeout_ms}ms"})
                return operation()
        except DBAPIError as error:
            db.rollback()
            code = getattr(error.orig, "sqlstate", None)
            if code not in {"55P03", "40P01", "40001"}:
                raise
            if attempt + 1 == settings.catalog_write_attempts:
                raise HTTPException(503, headers={"Retry-After": "1"}, detail={"code": "catalog_busy", "message": "El catálogo está ocupado. Reintenta con la misma clave de solicitud."}) from None
            time.sleep(0.05 * (2 ** attempt))
