"""Dependencias de autenticación reutilizables por módulos protegidos."""

from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.repository import AuthRepository
from app.modules.auth.sessions import SessionValidationError, validate_access_session
from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "session_invalid", "message": "Sesión inválida o expirada"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized
    try:
        auth_session = validate_access_session(db, credentials.credentials)
    except SessionValidationError as exc:
        unauthorized.detail = {"code": exc.code, "message": "Sesión inválida o expirada"}
        raise unauthorized from None
    user = AuthRepository(db).get_user_by_id(auth_session.user_id)
    if not user:
        raise unauthorized
    request.state.auth_session = auth_session
    return user


def get_optional_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if not credentials:
        return None
    try:
        auth_session = validate_access_session(db, credentials.credentials)
    except SessionValidationError:
        return None
    request.state.auth_session = auth_session
    return AuthRepository(db).get_user_by_id(auth_session.user_id)
