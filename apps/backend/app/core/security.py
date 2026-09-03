"""Hash de contraseñas y creación/verificación de tokens JWT."""

from datetime import datetime, timedelta, timezone

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


def create_access_token(subject: str) -> str:
    """Firma un JWT de duración limitada usando el id como subject."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expires_at}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Retorna el subject si la firma y expiración son válidas."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except InvalidTokenError:
        return None
