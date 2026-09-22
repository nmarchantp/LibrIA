"""Verificación manual de perfiles y creación de librerías por admin."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EmailAlreadyRegisteredError
from app.core.security import hash_password
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import AuthAccount
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User
from app.modules.users.role_schemas import BookstoreCreate, VerificationCreate, VerificationResponse
from app.modules.users.schemas import UserResponse
from app.modules.users.verification_models import VerificationRequest

router = APIRouter(prefix="/roles", tags=["roles"])


def get_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere una cuenta administradora")
    return user


def verification_response(request: VerificationRequest, user: User, email: str) -> VerificationResponse:
    return VerificationResponse(id=request.id, user_id=user.id, display_name=user.display_name,
                                email=email, requested_role=request.requested_role,
                                note=request.note, status=request.status, created_at=request.created_at)


@router.post("/requests", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
def request_verification(data: VerificationCreate, user: Annotated[User, Depends(get_current_user)],
                         db: Annotated[Session, Depends(get_db)]) -> VerificationResponse:
    if user.role != "lector":
        raise HTTPException(status_code=403, detail="Solo los lectores pueden solicitar verificación")
    pending = db.scalar(select(VerificationRequest).where(
        VerificationRequest.user_id == user.id, VerificationRequest.status == "pending",
    ))
    if pending:
        raise HTTPException(status_code=409, detail="Ya tienes una solicitud pendiente")
    request = VerificationRequest(user_id=user.id, requested_role=data.requested_role, note=data.note)
    db.add(request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya tienes una solicitud pendiente") from None
    db.refresh(request)
    return verification_response(request, user, user.auth_account.email)


@router.get("/requests/me", response_model=list[VerificationResponse])
def my_verifications(user: Annotated[User, Depends(get_current_user)],
                     db: Annotated[Session, Depends(get_db)]) -> list[VerificationResponse]:
    requests = db.scalars(select(VerificationRequest).where(VerificationRequest.user_id == user.id)
                          .order_by(VerificationRequest.created_at.desc())).all()
    return [verification_response(request, user, user.auth_account.email) for request in requests]


@router.get("/requests/pending", response_model=list[VerificationResponse])
def pending_verifications(admin: Annotated[User, Depends(get_admin)],
                          db: Annotated[Session, Depends(get_db)]) -> list[VerificationResponse]:
    rows = db.execute(select(VerificationRequest, User, AuthAccount.email)
                      .join(User, VerificationRequest.user_id == User.id)
                      .join(AuthAccount, AuthAccount.user_id == User.id)
                      .where(VerificationRequest.status == "pending")
                      .order_by(VerificationRequest.created_at)).all()
    return [verification_response(request, user, email) for request, user, email in rows]


def decide_request(request_id: uuid.UUID, admin: User, db: Session, approve: bool) -> VerificationResponse:
    request = db.get(VerificationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="La solicitud ya fue revisada")
    user = db.get(User, request.user_id)
    if approve:
        if user.role != "lector":
            raise HTTPException(status_code=409, detail="El perfil ya cambió de tipo")
        user.role = request.requested_role
    request.status = "approved" if approve else "rejected"
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by_user_id = admin.id
    db.commit()
    db.refresh(request)
    return verification_response(request, user, user.auth_account.email)


@router.post("/requests/{request_id}/approve", response_model=VerificationResponse)
def approve_verification(request_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                         db: Annotated[Session, Depends(get_db)]) -> VerificationResponse:
    return decide_request(request_id, admin, db, True)


@router.post("/requests/{request_id}/reject", response_model=VerificationResponse)
def reject_verification(request_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                        db: Annotated[Session, Depends(get_db)]) -> VerificationResponse:
    return decide_request(request_id, admin, db, False)


@router.post("/bookstores", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_bookstore(data: BookstoreCreate, admin: Annotated[User, Depends(get_admin)],
                     db: Annotated[Session, Depends(get_db)]) -> UserResponse:
    try:
        user = AuthRepository(db).create_account(data.email, hash_password(data.password), data.display_name, "libreria")
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="El correo ya está registrado") from None
    return UserResponse(id=user.id, email=user.auth_account.email, display_name=user.display_name,
                        role=user.role, avatar_url=user.avatar_url, biography=user.biography,
                        created_at=user.created_at)
