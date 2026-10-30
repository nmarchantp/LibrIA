"""Autorización de actores públicos; el ejecutor siempre viene de la sesión."""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.identity_models import Profile, ProfileCapability, ProfileMember
from app.modules.users.models import User


def create_personal_profile(db: Session, user: User) -> Profile:
    profile = Profile(kind="personal", owner_user_id=user.id, display_name=user.display_name)
    db.add(profile)
    db.flush()
    db.add(ProfileCapability(profile_id=profile.id, capability="lector"))
    return profile


def personal_profile(db: Session, user: User) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.owner_user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=403, detail="Esta cuenta legada no tiene perfil personal; usa una cuenta personal")
    return profile


def publication_role(db: Session, profile: Profile) -> str:
    if profile.kind == "organization":
        return profile.organization_type
    user = db.get(User, profile.owner_user_id)
    return user.role if user else "lector"


def require_actor(db: Session, user: User, profile_id: uuid.UUID,
                  *, capability: str | None = None, manage: bool = False) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.id == profile_id).with_for_update())
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if profile.kind == "personal":
        allowed = profile.owner_user_id == user.id
    else:
        # Organizations remain historical/administrative relationships, not an
        # alternative publishing identity selected by the account owner.
        member = db.get(ProfileMember, (profile.id, user.id))
        allowed = manage and member is not None and member.permission == "admin"
    if not allowed:
        raise HTTPException(status_code=403, detail="No puedes actuar por este perfil")
    if capability and (profile.kind != "personal" or user.role != capability):
        raise HTTPException(status_code=403, detail="El perfil no tiene la capacidad requerida")
    return profile
