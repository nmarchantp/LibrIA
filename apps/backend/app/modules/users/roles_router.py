"""Verificación manual de perfiles y creación de librerías por admin."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User
from app.modules.users.profile_models import ProfileRoleChange
from app.modules.users.role_schemas import (
    AdminProfile, AdminProfilePage, AdminProfileUpdate, BookstoreCreate,
    RoleChangeResponse, RoleRevocation, VerificationCreate, VerificationResponse,
    VerificationDecision, InfluencerSuspension,
)
from app.modules.users.roles import UserRole
from app.modules.users.schemas import UserResponse
from app.modules.users.verification_models import VerificationRequest
from app.modules.users.identity_models import AccountPermission, Profile
from app.modules.users.identities import personal_profile

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get('/access')
def effective_access(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    from app.core.config import get_settings
    admin = db.get(AccountPermission,(user.id,'admin')) is not None
    return dict(admin=admin,catalog_manage=admin and get_settings().catalog_admin_preview_enabled and get_settings().catalog_discovery_enabled,
                catalog_preview=admin and get_settings().catalog_admin_preview_enabled,
                catalog_merge=admin and get_settings().catalog_admin_merge_enabled)


def get_admin(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> User:
    if db.get(AccountPermission, (user.id, "admin")) is None:
        raise HTTPException(status_code=403, detail="Se requiere una cuenta administradora")
    return user


def verification_response(request: VerificationRequest, user: User, email: str, db: Session) -> VerificationResponse:
    reviewer = db.get(User, request.decided_by_user_id) if request.decided_by_user_id else None
    return VerificationResponse(id=request.id, user_id=user.id, display_name=user.display_name,
                                email=email, requested_role=request.requested_role,
                                note=request.note, status=request.status, created_at=request.created_at,
                                activity_description=request.activity_description, topics=request.topics,
                                motivation=request.motivation, evidence_links=request.evidence_links,
                                decided_at=request.decided_at, decision_reason=request.decision_reason,
                                decided_by_user_id=request.decided_by_user_id,
                                decided_by_name=reviewer.display_name if reviewer else None)


def profile_response(user: User, email: str, pending_role: str | None = None) -> AdminProfile:
    return AdminProfile(id=user.id, display_name=user.display_name, email=email, role=user.role,
                        biography=user.biography, created_at=user.created_at, pending_role=pending_role,
                        influencer_permissions_suspended=user.influencer_permissions_suspended,
                        influencer_suspended_until=user.influencer_suspended_until)


def require_profile(db: Session, user_id: uuid.UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
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
    from app.modules.users.account_service import audit
    audit(db, user, admin.id, "profile_updated", before={"display_name": user.display_name, "biography": user.biography},
          after={"display_name": data.display_name, "biography": data.biography}, reason=data.reason, origin="admin")
    user.display_name = data.display_name
    user.biography = data.biography
    profile = db.scalar(select(Profile).where(Profile.owner_user_id == user.id))
    if profile:
        profile.display_name = data.display_name
    db.commit()
    db.refresh(user)
    pending = db.scalar(select(VerificationRequest.requested_role).where(
        VerificationRequest.user_id == user.id, VerificationRequest.status == "pending"))
    return profile_response(user, user.auth_account.email, pending)


@router.post("/profiles/{user_id}/revoke", response_model=AdminProfile)
def revoke_profile_role(user_id: uuid.UUID, data: RoleRevocation,
                        admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]) -> AdminProfile:
    from app.modules.users.account_service import assign_role
    user = require_profile(db, user_id)
    user = assign_role(db, user, admin, "lector", data.reason, preserve_influencer_history=user.role == 'influencer')
    db.commit()
    return profile_response(user, user.auth_account.email)


@router.get("/profiles/{user_id}/requests", response_model=list[VerificationResponse])
def profile_requests(user_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                     db: Annotated[Session, Depends(get_db)]) -> list[VerificationResponse]:
    user = require_profile(db, user_id)
    requests = db.scalars(select(VerificationRequest).where(VerificationRequest.user_id == user_id)
                          .order_by(VerificationRequest.created_at.desc())).all()
    return [verification_response(request, user, user.auth_account.email, db) for request in requests]


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
    from app.modules.users.account_service import lock_user, require_active, audit
    owner = lock_user(db, user.id)
    require_active(owner)
    if owner.role != 'lector' or data.requested_role != 'influencer' or db.get(AccountPermission, (owner.id, 'admin')):
        raise HTTPException(403, 'Solo un Lector puede solicitar el perfil Influencer')
    personal_profile(db, owner)
    if db.scalar(select(VerificationRequest.id).where(VerificationRequest.user_id == owner.id, VerificationRequest.status == 'pending')):
        raise HTTPException(409, 'Ya existe una solicitud pendiente')
    item = VerificationRequest(user_id=owner.id, requested_role='influencer', note=data.motivation,
        activity_description=data.activity_description, topics=data.topics, motivation=data.motivation,
        evidence_links=[str(url) for url in data.evidence_links])
    db.add(item)
    audit(db, owner, owner.id, 'professional_verification_requested', reason=data.motivation)
    from app.modules.users.role_notifications import notify_request
    notify_request(db, item)
    db.commit()
    return verification_response(item, owner, owner.auth_account.email, db)


@router.get("/requests/me", response_model=list[VerificationResponse])
def my_verifications(user: Annotated[User, Depends(get_current_user)],
                     db: Annotated[Session, Depends(get_db)]) -> list[VerificationResponse]:
    requests = db.scalars(select(VerificationRequest).where(VerificationRequest.user_id == user.id)
                          .order_by(VerificationRequest.created_at.desc())).all()
    return [verification_response(request, user, user.auth_account.email, db) for request in requests]


@router.get("/requests/pending", response_model=list[VerificationResponse])
def pending_verifications(admin: Annotated[User, Depends(get_admin)],
                          db: Annotated[Session, Depends(get_db)]) -> list[VerificationResponse]:
    rows = db.execute(select(VerificationRequest, User, AuthAccount.email)
                      .join(User, VerificationRequest.user_id == User.id)
                      .join(AuthAccount, AuthAccount.user_id == User.id)
                      .where(VerificationRequest.status == "pending")
                      .order_by(VerificationRequest.created_at)).all()
    return [verification_response(request, user, email, db) for request, user, email in rows]


def decide_request(request_id: uuid.UUID, admin: User, db: Session, approve: bool, reason: str | None = None) -> VerificationResponse:
    candidate = db.get(VerificationRequest, request_id)
    if candidate is None:
        raise HTTPException(404, 'Solicitud no encontrada')
    if candidate.user_id == admin.id:
        raise HTTPException(403, 'No puedes decidir tu propia solicitud')
    user = require_profile(db, candidate.user_id)
    from app.modules.users.account_service import require_active
    require_active(user)
    request = db.scalar(select(VerificationRequest).where(VerificationRequest.id == request_id)
                        .with_for_update().execution_options(populate_existing=True))
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="La solicitud ya fue revisada")
    if request.requested_role == 'influencer' and not reason:
        raise HTTPException(422, 'Registra una observación administrativa para decidir')
    reason = reason or request.note  # Preserve the existing non-influencer administrative API.
    if approve:
        from app.modules.users.account_service import assign_role
        assign_role(db, user, admin, request.requested_role, reason, approved=True)
        profile = personal_profile(db, user)
        profile.verification_status = "verified"
    from app.modules.users.account_service import audit
    audit(db, user, admin.id, "professional_verification_approved" if approve else "professional_verification_rejected",
          reason=reason, origin="admin")
    request.status = "approved" if approve else "rejected"
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by_user_id = admin.id
    request.decision_reason = reason
    from app.modules.users.role_notifications import notify_decision
    notify_decision(db, request)
    db.commit()
    db.refresh(request)
    return verification_response(request, user, user.auth_account.email, db)


@router.post("/requests/{request_id}/approve", response_model=VerificationResponse)
def approve_verification(request_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                         db: Annotated[Session, Depends(get_db)], data: VerificationDecision | None = None) -> VerificationResponse:
    return decide_request(request_id, admin, db, True, data.reason if data else None)


@router.post("/requests/{request_id}/reject", response_model=VerificationResponse)
def reject_verification(request_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)],
                        db: Annotated[Session, Depends(get_db)], data: VerificationDecision | None = None) -> VerificationResponse:
    return decide_request(request_id, admin, db, False, data.reason if data else None)


@router.post('/profiles/{user_id}/influencer-suspension', response_model=AdminProfile)
def suspend_influencer(user_id: uuid.UUID, data: InfluencerSuspension,
                       admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]):
    return change_influencer_suspension(db, admin, user_id, data.reason, data.until)


@router.post('/profiles/{user_id}/influencer-resume', response_model=AdminProfile)
def resume_influencer(user_id: uuid.UUID, data: VerificationDecision,
                      admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]):
    return change_influencer_suspension(db, admin, user_id, data.reason, None)


def change_influencer_suspension(db, admin, user_id, reason, until):
    from app.modules.users.account_service import audit, require_active
    user = require_profile(db, user_id)
    require_active(user)
    if user.id == admin.id:
        raise HTTPException(403, 'No puedes cambiar tus propios permisos')
    if user.role != 'influencer':
        raise HTTPException(409, 'La cuenta no tiene el perfil Influencer')
    if until is None and not user.influencer_permissions_suspended:
        raise HTTPException(409, 'No hay una suspensión activa')
    previous = user.influencer_suspended_until
    user.influencer_suspended_until = until
    audit(db, user, admin.id, 'influencer_suspended' if until else 'influencer_resumed',
          before={'influencer_suspended_until': previous.isoformat() if previous else None},
          after={'influencer_suspended_until': until.isoformat() if until else None}, reason=reason, origin='admin')
    db.commit()
    return profile_response(user, user.auth_account.email)


@router.get('/me/influencer-permissions')
def my_influencer_permissions(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    from app.modules.users.account_models import AccountAudit
    latest = db.scalar(select(AccountAudit).where(AccountAudit.user_id == user.id,
        AccountAudit.action.in_(('influencer_suspended', 'influencer_resumed'))).order_by(AccountAudit.created_at.desc(), AccountAudit.id.desc()).limit(1))
    return {'suspended': user.influencer_permissions_suspended, 'until': user.influencer_suspended_until,
            'reason': latest.reason if latest else None}


@router.post("/bookstores", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_bookstore(data: BookstoreCreate, admin: Annotated[User, Depends(get_admin)],
                     db: Annotated[Session, Depends(get_db)]) -> UserResponse:
    raise HTTPException(status_code=410, detail="Solicita la verificación del tipo exclusivo librería en /accounts/admin/{user_id}/verification")
