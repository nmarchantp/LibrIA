"""Dependencias de autenticación reutilizables por módulos protegidos."""

import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado", headers={"WWW-Authenticate": "Bearer"})
    if not credentials:
        raise unauthorized
    subject = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(subject) if subject else None
    except ValueError:
        raise unauthorized from None
    user = AuthRepository(db).get_user_by_id(user_id) if user_id else None
    if not user:
        raise unauthorized
    return user
