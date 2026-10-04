"""Consulta de identidades propias y gestión explícita de organizaciones."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.identities import require_actor
from app.modules.users.identity_models import AccountPermission, IdentityAudit, Profile, ProfileCapability, ProfileMember
from app.modules.users.models import User

router = APIRouter(prefix="/profiles", tags=["profiles"])
SessionDB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    administrator_user_id: uuid.UUID
    organization_type: Literal["libreria", "editorial"] = "libreria"


class MemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permission: Literal["admin", "editor"]


def profile_response(db: Session, profile: Profile):
    return {"id": profile.id, "kind": profile.kind, "display_name": profile.display_name,
            "organization_type": profile.organization_type,
            "verification_status": profile.verification_status,
            "capabilities": list(db.scalars(select(ProfileCapability.capability)
                                            .where(ProfileCapability.profile_id == profile.id)
                                            .order_by(ProfileCapability.capability)))}


@router.get("/me")
def my_profiles(user: CurrentUser, db: SessionDB):
    member_ids = select(ProfileMember.profile_id).where(ProfileMember.user_id == user.id)
    profiles = db.scalars(select(Profile).where((Profile.owner_user_id == user.id) | Profile.id.in_(member_ids))
                         .order_by(Profile.created_at, Profile.id)).all()
    return [profile_response(db, profile) for profile in profiles]


@router.post("/organizations", status_code=201)
def create_organization(data: OrganizationCreate, user: CurrentUser, db: SessionDB):
    if db.get(AccountPermission, (user.id, "admin")) is None:
        raise HTTPException(status_code=403, detail="Se requiere permiso administrativo de cuenta")
    personal = db.scalar(select(Profile).where(Profile.owner_user_id == data.administrator_user_id,
                                               Profile.kind == "personal"))
    if personal is None:
        raise HTTPException(status_code=422, detail="El responsable debe tener una cuenta personal")
    profile = Profile(kind="organization", organization_type=data.organization_type, display_name=data.display_name)
    db.add(profile)
    db.flush()
    db.add(ProfileMember(profile_id=profile.id, user_id=data.administrator_user_id, permission="admin"))
    db.add(IdentityAudit(profile_id=profile.id, actor_user_id=user.id, action="organization_created",
                         detail=str(data.administrator_user_id)))
    db.commit()
    return profile_response(db, profile)


@router.put("/{profile_id}/members/{member_id}")
def set_member(profile_id: uuid.UUID, member_id: uuid.UUID, data: MemberUpdate,
               user: CurrentUser, db: SessionDB):
    profile = require_actor(db, user, profile_id, manage=True)
    if profile.kind != "organization":
        raise HTTPException(status_code=422, detail="Un perfil personal no admite miembros")
    if db.scalar(select(Profile.id).where(Profile.owner_user_id == member_id)) is None:
        raise HTTPException(status_code=422, detail="El miembro debe tener una cuenta personal")
    existing = db.get(ProfileMember, (profile.id, member_id))
    if existing and existing.permission == "admin" and data.permission != "admin":
        another = db.scalar(select(ProfileMember.user_id).where(ProfileMember.profile_id == profile.id,
                            ProfileMember.permission == "admin", ProfileMember.user_id != member_id))
        if another is None:
            raise HTTPException(status_code=409, detail="La organización debe conservar un administrador")
    if existing:
        existing.permission = data.permission
    else:
        db.add(ProfileMember(profile_id=profile.id, user_id=member_id, permission=data.permission))
    db.add(IdentityAudit(profile_id=profile.id, actor_user_id=user.id, action="member_updated",
                         detail=f"{member_id}:{data.permission}"))
    db.commit()
    return {"user_id": member_id, "permission": data.permission}
