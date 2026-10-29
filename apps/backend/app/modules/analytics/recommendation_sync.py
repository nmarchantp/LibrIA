"""Read and idempotently synchronize recommendation work after nightly ETL."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.analytics.persistence import enqueue_recommendation_job

RECOMMENDATION_STATES = frozenset({
    "waiting_for_etl", "insufficient_data", "pending", "processing", "ready", "outdated", "failed",
    "budget_exhausted",
})


def _latest_state(db: Session, owner_id: uuid.UUID):
    state = db.execute(
        text(
            """SELECT s.*, p.version AS profile_version, p.data_hash, e.source_cutoff_at
               FROM ia.reader_profile_etl_states s
               JOIN analytics.ejecuciones_etl e ON e.id=s.etl_run_id
               LEFT JOIN ia.reader_profile_versions p ON p.id=s.profile_version_id
               WHERE s.owner_id=:owner AND e.status='succeeded'
                 AND e.run_kind IN ('daily','manual')
               ORDER BY e.source_cutoff_at DESC, e.finished_at DESC NULLS LAST, s.created_at DESC
               LIMIT 1"""
        ),
        {"owner": owner_id},
    ).mappings().first()
    from app.modules.books.canonical import enabled, identity_version
    if enabled() and state:
        recorded = db.execute(text("SELECT identity_version FROM analytics.ejecuciones_etl WHERE id=:id"), {"id": state["etl_run_id"]}).scalar()
        if recorded != identity_version(db):
            return None  # stale identity: await ETL; never enqueue inference here
    return state


def recommendation_state(
    db: Session,
    owner_id: uuid.UUID,
    *,
    enqueue: bool = False,
    retry_failed: bool = False,
) -> dict[str, Any]:
    """Return the UI state; only the explicit sync path is allowed to enqueue."""
    settings = get_settings()
    state = _latest_state(db, owner_id)
    if state is None:
        return {"status": "waiting_for_etl", "profile_version": None, "recommendations": None,
                "positive_books_count": 0}
    if state["outcome"] == "empty" or state["profile_version_id"] is None:
        return {"status": "insufficient_data", "profile_version": None, "recommendations": None,
                "positive_books_count": 0, "source_cutoff_at": state['source_cutoff_at']}

    request_params = {
        "owner": owner_id,
        "profile": state["profile_version_id"],
        "provider": settings.ai_provider,
        "model": settings.gemini_model,
        "prompt": settings.recommendation_prompt_version,
    }
    current = db.execute(
        text(
            """SELECT id,content,created_at FROM ia.recomendaciones_ia
               WHERE owner_user_id=:owner AND profile_version_id=:profile
                 AND provider=:provider AND model=:model AND version=:prompt AND is_current
               ORDER BY created_at DESC LIMIT 1"""
        ),
        request_params,
    ).mappings().first()
    if current:
        return {"status": "ready", "profile_version": state["profile_version"],
                "positive_books_count": state["eligible_books_count"],
                "recommendations": current["content"], "job_id": None}

    job = db.execute(
        text(
            """SELECT id,status,error_code FROM ia.jobs
               WHERE owner_id=:owner AND job_kind='recommendation' AND profile_version_id=:profile
                 AND provider=:provider AND model=:model AND prompt_version=:prompt
               LIMIT 1"""
        ),
        request_params,
    ).mappings().first()
    if job is None and enqueue:
        job = enqueue_recommendation_job(
            db,
            profile_version_id=state["profile_version_id"],
            provider=settings.ai_provider,
            model=settings.gemini_model,
            prompt_version=settings.recommendation_prompt_version,
        )
        db.commit()
    elif (
        job is not None
        and enqueue
        and retry_failed
        and job["status"] == "failed"
        and job["error_code"] in {
            "provider_invalid_response", "provider_error", "provider_timeout",
            "provider_server", "worker_internal"
        }
    ):
        job = db.execute(
            text(
                """UPDATE ia.jobs SET status='pending',error_code=NULL,not_before=now(),
                     locked_at=NULL,updated_at=now()
                   WHERE id=:id AND status='failed' AND attempts<:max_attempts
                   RETURNING id,status,error_code"""
            ),
            {"id": job["id"], "max_attempts": settings.ai_job_max_attempts},
        ).mappings().first() or job
        if job["status"] == "pending":
            db.execute(
                text(
                    """UPDATE ia.reader_profile_versions
                       SET status='pending',error_code=NULL,generated_at=NULL,updated_at=now()
                       WHERE id=:profile"""
                ),
                {"profile": state["profile_version_id"]},
            )
            db.commit()

    previous = db.execute(
        text(
            """SELECT content,created_at FROM ia.recomendaciones_ia
               WHERE owner_user_id=:owner
               ORDER BY created_at DESC LIMIT 1"""
        ),
        {"owner": owner_id},
    ).mappings().first()
    if previous:
        generation_status = ("budget_exhausted" if job and job["error_code"] == "monthly_budget_exhausted"
                             else job["status"] if job else "pending")
        return {"status": "outdated", "profile_version": state["profile_version"],
                "positive_books_count": state["eligible_books_count"],
                "generation_status": generation_status,
                "recommendations": previous["content"], "job_id": str(job["id"]) if job else None}
    if job is None:
        return {"status": "pending", "profile_version": state["profile_version"],
                "positive_books_count": state["eligible_books_count"],
                "recommendations": None, "job_id": None}
    status = ("budget_exhausted" if job["error_code"] == "monthly_budget_exhausted" else
              job["status"] if job["status"] in {"pending", "processing", "failed"} else "failed")
    return {"status": status, "profile_version": state["profile_version"],
            "positive_books_count": state["eligible_books_count"],
            "recommendations": None, "job_id": str(job["id"]),
            "error_code": job["error_code"] or ("result_missing" if status == "failed" else None)}


def safe_sync_recommendations(db: Session, owner_id: uuid.UUID) -> str | None:
    """Authentication must succeed even when recommendation infrastructure is unavailable."""
    try:
        return recommendation_state(db, owner_id, enqueue=True)["status"]
    except Exception:
        db.rollback()
        return None
