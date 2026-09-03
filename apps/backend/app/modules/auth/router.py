"""Capa HTTP del módulo Auth; delega las reglas al servicio."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(AuthRepository(db))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, service: Annotated[AuthService, Depends(get_auth_service)]) -> TokenResponse:
    try:
        return service.register(data)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="El correo ya está registrado") from None


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, service: Annotated[AuthService, Depends(get_auth_service)]) -> TokenResponse:
    try:
        return service.login(data)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos") from None


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(id=user.id, email=user.auth_account.email, display_name=user.display_name, avatar_url=user.avatar_url, biography=user.biography, created_at=user.created_at)
