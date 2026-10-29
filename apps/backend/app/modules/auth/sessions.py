"""Revocable sessions backing short access JWTs and rotating refresh cookies."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_token_claims
from app.modules.auth.models import AuthSession


class SessionValidationError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SessionGrant:
    session: AuthSession
    access_token: str
    refresh_token: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _expiry_reason(session: AuthSession, now: datetime) -> str | None:
    if session.revoked_at is not None:
        return "session_revoked"
    if now >= session.absolute_expires_at:
        return "session_absolute_expired"
    if now >= session.inactivity_expires_at:
        return "session_inactive"
    return None


def _revoke(db: Session, session: AuthSession, reason: str, now: datetime) -> None:
    if session.revoked_at is None:
        session.revoked_at = now
        session.revocation_reason = reason
        session.updated_at = now
        db.commit()


def create_session(db: Session, user_id: uuid.UUID, *, now: datetime | None = None) -> SessionGrant:
    settings = get_settings()
    current = now or utcnow()
    absolute = current + timedelta(hours=settings.session_absolute_hours)
    session = AuthSession(
        user_id=user_id,
        refresh_token_hash="0" * 64,
        refresh_generation=1,
        created_at=current,
        last_activity_at=current,
        inactivity_expires_at=min(
            current + timedelta(hours=settings.session_inactivity_hours), absolute
        ),
        absolute_expires_at=absolute,
        updated_at=current,
    )
    db.add(session)
    db.flush()
    refresh = create_refresh_token(str(user_id), session.id, 1, absolute, now=current)
    session.refresh_token_hash = _digest(refresh)
    access = create_access_token(str(user_id), session.id, now=current)
    db.commit()
    return SessionGrant(session=session, access_token=access, refresh_token=refresh)


def validate_access_session(db: Session, token: str, *, now: datetime | None = None) -> AuthSession:
    claims = decode_token_claims(token, "access")
    if claims is None:
        raise SessionValidationError("access_token_expired")
    current = now or utcnow()
    session = db.get(AuthSession, uuid.UUID(claims["sid"]))
    if session is None or str(session.user_id) != claims["sub"]:
        raise SessionValidationError("session_invalid")
    reason = _expiry_reason(session, current)
    if reason:
        _revoke(db, session, reason, current)
        raise SessionValidationError(reason)
    return session


def rotate_refresh_token(db: Session, token: str, *, now: datetime | None = None) -> SessionGrant:
    claims = decode_token_claims(token, "refresh")
    if claims is None:
        raise SessionValidationError("refresh_token_expired")
    current = now or utcnow()
    session = db.scalar(
        select(AuthSession).where(AuthSession.id == uuid.UUID(claims["sid"])).with_for_update()
    )
    if session is None or str(session.user_id) != claims["sub"]:
        raise SessionValidationError("session_invalid")
    reason = _expiry_reason(session, current)
    if reason:
        _revoke(db, session, reason, current)
        raise SessionValidationError(reason)
    expected_generation = int(claims.get("rgn", -1))
    if expected_generation != session.refresh_generation or not hmac.compare_digest(
        _digest(token), session.refresh_token_hash
    ):
        _revoke(db, session, "refresh_reuse", current)
        raise SessionValidationError("refresh_reuse")
    session.refresh_generation += 1
    refresh = create_refresh_token(
        str(session.user_id), session.id, session.refresh_generation, session.absolute_expires_at, now=current
    )
    session.refresh_token_hash = _digest(refresh)
    session.updated_at = current
    access = create_access_token(str(session.user_id), session.id, now=current)
    db.commit()
    return SessionGrant(session=session, access_token=access, refresh_token=refresh)


def record_activity(db: Session, session_id: uuid.UUID, *, now: datetime | None = None) -> AuthSession:
    """Extend inactivity only for explicit human activity, with throttled writes."""
    settings = get_settings()
    current = now or utcnow()
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id).with_for_update())
    if session is None:
        raise SessionValidationError("session_invalid")
    reason = _expiry_reason(session, current)
    if reason:
        _revoke(db, session, reason, current)
        raise SessionValidationError(reason)
    write_after = timedelta(seconds=settings.session_activity_write_interval_seconds)
    if current - session.last_activity_at >= write_after:
        session.last_activity_at = current
        session.inactivity_expires_at = min(
            current + timedelta(hours=settings.session_inactivity_hours), session.absolute_expires_at
        )
        session.updated_at = current
        db.commit()
    return session


def revoke_session(db: Session, session_id: uuid.UUID, reason: str = "logout",
                   *, now: datetime | None = None) -> None:
    session = db.get(AuthSession, session_id)
    if session is not None:
        _revoke(db, session, reason, now or utcnow())


def revoke_refresh_token(db: Session, token: str, reason: str = "logout",
                         *, now: datetime | None = None) -> None:
    claims = decode_token_claims(token, "refresh")
    if claims:
        revoke_session(db, uuid.UUID(claims["sid"]), reason, now=now)
