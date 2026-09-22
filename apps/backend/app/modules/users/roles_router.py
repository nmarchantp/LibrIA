"""Verificación manual de perfiles y creación de librerías por admin."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.database import get_db
from app.core.exceptions import EmailAlreadyRegisteredError
from app.core.security import hash_password
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import AuthAccount
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User
from app.modules.users.profile_models import ProfileRoleChange
from app.modules.users.role_schemas import (
    AdminProfile, AdminProfilePage, AdminProfileUpdate, BookstoreCreate,
    RoleChangeResponse, RoleRevocation, VerificationCreate, VerificationResponse,
)
from app.modules.users.roles import UserRole
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


def profile_response(user: User, email: str, pending_role: str | None = None) -> AdminProfile:
    return AdminProfile(id=user.id, display_name=user.display_name, email=email, role=user.role,
                        biography=user.biography, created_at=user.created_at, pending_role=pending_role)


def require_profile(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return user


@router.get("/profiles", response_model=AdminProfilePage)
def list_profiles(admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)],
                  q: str = Query("", max_length=100), role: UserRole | None = None,
                  limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> AdminProfilePage:
    filters = []
    if q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.display_name.ilike(pattern), AuthAccount.email.ilike(pattern)))
    if role:
        filters.append(User.role == role)
    total = db.scalar(select(func.count(User.id)).join(AuthAccount, AuthAccount.user_id == User.id).where(*filters)) or 0
    rows = db.execute(select(User, AuthAccount.email, VerificationRequest.requested_role)
                      .join(AuthAccount, AuthAccount.user_id == User.id)
                      .outerjoin(VerificationRequest, and_(VerificationRequest.user_id == User.id,
                                                           VerificationRequest.status == "pending"))
                      .where(*filters).order_by(User.created_at.desc(), User.id.desc())
                      .limit(limit).offset(offset)).all()
    return AdminProfilePage(items=[profile_response(user, email, pending) for user, email, pending in rows], total=total)


@router.patch("/profiles/{user_id}", response_model=AdminProfile)
def update_profile(user_id: uuid.UUID, data: AdminProfileUpdate,
                   admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]) -> AdminProfile:
    user = require_profile(db, user_id)
    user.display_name = data.display_name
    user.biography = data.biography
    db.commit()
    db.refresh(user)
    pending = db.scalar(select(VerificationRequest.requested_role).where(
        VerificationRequest.user_id == user.id, VerificationRequest.status == "pending"))
    return profile_response(user, user.auth_account.email, pending)


@router.post("/profiles/{user_id}/revoke", response_model=AdminProfile)
def revoke_profile_role(user_id: uuid.UUID, data: RoleRevocation,
                        admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]) -> AdminProfile:
    user = require_profile(db, user_id)
    if user.role not in {"autor", "influencer"}:
        raise HTTPException(status_code=409, detail="Solo se pueden revocar perfiles de autor o influencer")
    previous_role = user.role
    user.role = "lector"
    db.add(ProfileRoleChange(user_id=user.id, admin_user_id=admin.id,
                             previous_role=previous_role, new_role="lector", reason=data.reason))
    db.commit()
    db.refresh(user)
    return profile_response(user, user.auth_account.email)


@router.get("/profiles/{user_id}/requests", response_model=list[VerificationResponse])
def profile_requests(user_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                     db: Annotated[Session, Depends(get_db)]) -> list[VerificationResponse]:
    user = require_profile(db, user_id)
    requests = db.scalars(select(VerificationRequest).where(VerificationRequest.user_id == user_id)
                          .order_by(VerificationRequest.created_at.desc())).all()
    return [verification_response(request, user, user.auth_account.email) for request in requests]


@router.get("/profiles/{user_id}/history", response_model=list[RoleChangeResponse])
def profile_role_history(user_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                         db: Annotated[Session, Depends(get_db)]) -> list[RoleChangeResponse]:
    require_profile(db, user_id)
    administrator = aliased(User)
    rows = db.execute(select(ProfileRoleChange, administrator.display_name)
                      .join(administrator, ProfileRoleChange.admin_user_id == administrator.id)
                      .where(ProfileRoleChange.user_id == user_id)
                      .order_by(ProfileRoleChange.created_at.desc())).all()
    return [RoleChangeResponse(id=change.id, previous_role=change.previous_role,
                               new_role=change.new_role, reason=change.reason,
                               created_at=change.created_at, admin_name=name) for change, name in rows]


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
