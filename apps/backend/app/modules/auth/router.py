"""Capa HTTP del módulo Auth; delega las reglas al servicio."""

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, GoogleEmailRequest, GoogleEmailConfirm
from app.modules.auth.email_verification import request_code, confirm_code
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def build_google_authorization_url(client_id: str | None = None, redirect_uri: str | None = None,
                                   state: str | None = None) -> str:
    """Construye la URL de autorización de Google OpenID Connect."""
    settings = get_settings()
    resolved_client_id = client_id or settings.google_client_id
    resolved_redirect_uri = redirect_uri or settings.google_redirect_uri

    if not resolved_client_id or not resolved_redirect_uri:
        raise ValueError("Faltan GOOGLE_CLIENT_ID o GOOGLE_REDIRECT_URI en el entorno")

    params = {
        "client_id": resolved_client_id,
        "redirect_uri": resolved_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "nonce": state or "",
        "prompt": "select_account",
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
    response.delete_cookie("libria_google_link", path=f"{get_settings().api_prefix}/auth/google")
    return response


google_keys = PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=10)


@router.get("/google/link")
def google_link_status(user: Annotated[User, Depends(get_current_user)]):
    account = user.auth_account
    return {"linked": bool(account.google_subject and account.google_email_verified_at),
            "email": account.google_email, "email_verified": bool(account.google_email_verified_at),
            "code_sent": bool(account.google_email_code_hash),
            "expires_at": account.google_email_code_expires_at,
            "resend_at": (account.google_email_code_sent_at + timedelta(seconds=60)
                          if account.google_email_code_sent_at else None)}


@router.post("/google/email/request")
def google_email_request(data: GoogleEmailRequest, user: Annotated[User, Depends(get_current_user)],
                         db: Annotated[Session, Depends(get_db)]):
    return request_code(db, user.id, str(data.email))


@router.post("/google/email/confirm")
def google_email_confirm(data: GoogleEmailConfirm, user: Annotated[User, Depends(get_current_user)],
                         db: Annotated[Session, Depends(get_db)]):
    confirm_code(db, user.id, data.code)
    return {"status": "verified"}


@router.post("/google/link")
def google_link_start(user: Annotated[User, Depends(get_current_user)]):
    settings = get_settings()
    if not user.auth_account.google_email_verified_at or not user.auth_account.google_email:
        raise HTTPException(409, "Primero verifica tu correo desde Mi cuenta.")
    state = secrets.token_urlsafe(32)
    try:
        url = build_google_authorization_url(state=state)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    context = jwt.encode({"sub": str(user.id), "state": state, "aud": "google-link",
                          "email": user.auth_account.google_email,
                          "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
                         settings.jwt_secret, algorithm="HS256")
    result = JSONResponse({"url": url})
    for name, value in (("libria_google_state", state), ("libria_google_link", context)):
        result.set_cookie(name, value, max_age=600, httponly=True,
                          secure=settings.google_redirect_uri.startswith("https://"),
                          samesite="lax", path=f"{settings.api_prefix}/auth/google")
    result.headers["Cache-Control"] = "no-store"
    return result


def google_result(error: str | None = None, linking: bool = False) -> RedirectResponse:
    settings = get_settings()
    target = settings.cors_origins[0].rstrip("/")
    destination = ("/profile?tab=account&google_link=" + (error or "success") if linking else
                   "/login?google_error=" + error if error else "/auth/google/callback")
    result = RedirectResponse(target + destination, status_code=303)
    result.delete_cookie("libria_google_state", path=f"{settings.api_prefix}/auth/google")
    result.delete_cookie("libria_google_link", path=f"{settings.api_prefix}/auth/google")
    result.headers["Cache-Control"] = "no-store"
    result.headers["Referrer-Policy"] = "no-referrer"
    return result


@router.post("/google/session", response_model=TokenResponse)
def google_session(request: Request, service: Annotated[AuthService, Depends(get_auth_service)]):
    settings = get_settings()
    if request.headers.get("origin") not in settings.cors_origins:
        raise HTTPException(403, "Origen no autorizado")
    try:
        claims = jwt.decode(request.cookies.get("libria_google_session", ""), settings.jwt_secret,
                            algorithms=["HS256"], audience="google-session",
                            options={"require": ["sub", "exp", "aud"]})
        user = service.repository.get_user_by_id(uuid.UUID(claims["sub"]))
        if not user:
            raise ValueError("Unknown user")
    except (PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "La sesión de Google expiró; vuelve a intentarlo") from None
    result = JSONResponse(content=json.loads(service._token_response(user).model_dump_json()))
    result.delete_cookie("libria_google_session", path=f"{settings.api_prefix}/auth/google")
    result.headers["Cache-Control"] = "no-store"
    return result


@router.get("/google/callback")
def google_callback(request: Request, service: Annotated[AuthService, Depends(get_auth_service)],
                    code: str | None = None, state: str | None = None, error: str | None = None):
    settings = get_settings()
    expected = request.cookies.get("libria_google_state")
    if not state or not expected or not secrets.compare_digest(state.encode(), expected.encode()):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido; inicia nuevamente la autorización")
    link_user_id = None
    context = request.cookies.get("libria_google_link")
    if context:
        try:
            intent = jwt.decode(context, settings.jwt_secret, algorithms=["HS256"], audience="google-link",
                                options={"require": ["sub", "state", "aud", "exp", "email"]})
            if not secrets.compare_digest(intent["state"].encode(), state.encode()):
                raise ValueError("Invalid linking state")
            link_user_id = uuid.UUID(intent["sub"])
        except (PyJWTError, ValueError, TypeError):
            return google_result("failed", linking=True)
    linking = link_user_id is not None
    if error:
        return google_result("cancelled", linking)
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
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str):
            raise ValueError("Missing ID token")
        signing_key = google_keys.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(id_token, signing_key.key, algorithms=["RS256"],
                            audience=settings.google_client_id,
                            issuer=["https://accounts.google.com", "accounts.google.com"],
                            options={"require": ["sub", "exp", "iat", "iss", "aud", "nonce"]})
        if not secrets.compare_digest(str(claims["nonce"]).encode(), state.encode()):
            raise ValueError("Invalid nonce")
        if linking:
            if str(claims.get("email", "")).lower() != intent["email"]:
                raise InvalidCredentialsError
            service.google_link(link_user_id, claims)
        else:
            session = service.google_login(claims)
    except (urllib.error.URLError, TimeoutError, ValueError, PyJWTError):
        return google_result("failed", linking)
    except (InvalidCredentialsError, EmailAlreadyRegisteredError):
        return google_result("account", linking)
    if linking:
        return google_result(linking=True)
    result = google_result()
    handoff = jwt.encode({"sub": str(session.user.id), "aud": "google-session",
                          "exp": datetime.now(timezone.utc) + timedelta(seconds=60)},
                         settings.jwt_secret, algorithm="HS256")
    result.set_cookie("libria_google_session", handoff, max_age=60, httponly=True,
                      secure=settings.google_redirect_uri.startswith("https://"), samesite="lax",
                      path=f"{settings.api_prefix}/auth/google")
    return result
