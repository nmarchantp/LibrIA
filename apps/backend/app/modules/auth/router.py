"""Capa HTTP del módulo Auth; delega las reglas al servicio."""

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def build_google_authorization_url(client_id: str | None = None, redirect_uri: str | None = None,
                                   state: str | None = None) -> str:
    """Construye la URL de autorización de Google Books OAuth 2.0."""
    settings = get_settings()
    resolved_client_id = client_id or settings.google_client_id
    resolved_redirect_uri = redirect_uri or settings.google_redirect_uri

    if not resolved_client_id or not resolved_redirect_uri:
        raise ValueError("Faltan GOOGLE_CLIENT_ID o GOOGLE_REDIRECT_URI en el entorno")

    params = {
        "client_id": resolved_client_id,
        "redirect_uri": resolved_redirect_uri,
        "response_type": "code",
        "scope": settings.google_oauth_scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


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
    return UserResponse(id=user.id, email=user.auth_account.email, display_name=user.display_name, role=user.role, avatar_url=user.avatar_url, biography=user.biography, created_at=user.created_at)


@router.get("/google/login")
def google_login() -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    try:
        auth_url = build_google_authorization_url(state=state)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    response = RedirectResponse(auth_url)
    response.set_cookie("libria_google_state", state, max_age=600, httponly=True,
                        secure=get_settings().google_redirect_uri.startswith("https://"),
                        samesite="lax", path=f"{get_settings().api_prefix}/auth/google")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None) -> JSONResponse:
    settings = get_settings()
    expected = request.cookies.get("libria_google_state")
    if not state or not expected or not secrets.compare_digest(state, expected):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido; inicia nuevamente la autorización")
    if not code:
        raise HTTPException(status_code=400, detail="Falta el parámetro code en la respuesta de Google")
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise HTTPException(status_code=500, detail="Faltan credenciales de Google en el entorno")

    payload = urllib.parse.urlencode({
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            tokens = json.loads(response.read().decode("utf-8"))
        if not tokens.get("access_token"):
            raise ValueError("Missing access token")
    except (urllib.error.URLError, TimeoutError, ValueError):
        result = JSONResponse(status_code=502, content={"detail": "No se pudo completar la autorización con Google"})
    else:
        # No existe aún almacenamiento de conexiones Google por usuario.
        # Nunca entregar refresh tokens al navegador ni simular una sesión LibrIA.
        result = JSONResponse(content={"status": "authorized", "connected": False})
    result.delete_cookie("libria_google_state", path=f"{settings.api_prefix}/auth/google")
    result.headers["Cache-Control"] = "no-store"
    return result
