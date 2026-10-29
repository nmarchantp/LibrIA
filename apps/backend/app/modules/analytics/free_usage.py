"""Daily application allocation; the provider's allowance is configured externally."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def allocation(pool: int, users: int, used: int) -> dict:
    quota = pool // max(1, users)
    return {"configured": pool > 0, "pool_tokens": pool, "active_users": users,
            "allocated_tokens": quota, "used_tokens": used,
            "remaining_tokens": max(0, quota - used),
            "used_percent": min(100, round(used * 100 / quota, 1)) if quota else (100 if used else 0)}


def free_usage(db, user_id, settings):
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    users = db.execute(text("""SELECT count(DISTINCT user_id)
        FROM app.sesiones_autenticacion WHERE revoked_at IS NULL
        AND inactivity_expires_at > :now AND absolute_expires_at > :now"""),
        {"now": now}).scalar_one()
    used = db.execute(text("""SELECT COALESCE(sum(m.input_tokens + m.output_tokens + m.reasoning_tokens), 0)
        FROM ia.usage_metrics m JOIN ia.jobs j ON j.id=m.job_id
        WHERE j.owner_id=:owner AND m.provider=:provider AND m.model=:model
        AND m.created_at >= :start AND m.created_at < :end
        AND NOT EXISTS (SELECT 1 FROM ia.call_ledger c WHERE c.job_id=m.job_id AND c.attempt=m.attempt)"""),
        {"owner": user_id, "provider": settings.ai_provider, "model": settings.gemini_model,
         "start": start, "end": end}).scalar_one()
    observed = db.execute(text('''SELECT COALESCE(sum(COALESCE(c.input_tokens,0)+
        COALESCE(c.output_tokens,0)+COALESCE(c.reasoning_tokens,0)),0) tokens,
        count(*) FILTER (WHERE c.state IN ('reserved','unknown','partial')) unresolved
        FROM ia.call_ledger c JOIN ia.jobs j ON j.id=c.job_id WHERE j.owner_id=:owner
        AND c.provider=:provider AND c.model=:model AND c.created_at>=:start AND c.created_at<:end'''),
        {'owner':user_id,'provider':settings.ai_provider,'model':settings.gemini_model,
         'start':start,'end':end}).mappings().one()
    used += observed['tokens']
    return {**allocation(settings.ai_free_daily_token_pool, max(1, int(users)), int(used)),
            "period_start": start, "resets_at": end, "period": "daily_utc",
            "free_mode": settings.gemini_free_test_mode,
            "pending_reconciliation_calls": observed['unresolved']}
