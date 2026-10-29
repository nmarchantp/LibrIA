"""Hash de contraseñas y creación/verificación de tokens JWT."""

from datetime import datetime, timedelta, timezone
import uuid

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Genera un hash Argon2 irreversible; nunca se almacena la contraseña."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Compara una contraseña recibida con el hash persistido."""
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, session_id: str | uuid.UUID, *, now: datetime | None = None) -> str:
    """Firma un access JWT corto y ligado a una sesión revocable."""
    settings = get_settings()
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "sid": str(session_id), "typ": "access", "jti": str(uuid.uuid4()),
         "iat": issued_at, "exp": expires_at},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: str, session_id: str | uuid.UUID, generation: int,
                         expires_at: datetime, *, now: datetime | None = None) -> str:
    """Firma la credencial rotativa; sólo su hash se persiste."""
    settings = get_settings()
    issued_at = now or datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "sid": str(session_id), "typ": "refresh", "rgn": generation,
         "jti": str(uuid.uuid4()), "iat": issued_at, "exp": expires_at},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token_claims(token: str, token_type: str) -> dict | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "sid", "typ", "jti", "iat", "exp"]},
        )
        if payload.get("typ") != token_type:
            return None
        uuid.UUID(str(payload["sub"]))
        uuid.UUID(str(payload["sid"]))
        return payload
    except (InvalidTokenError, ValueError, TypeError):
        return None


def decode_access_token(token: str) -> str | None:
    """Retorna el subject si la firma y expiración son válidas."""
    payload = decode_token_claims(token, "access")
    return payload.get("sub") if payload else None
