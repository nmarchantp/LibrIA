"""Transactional account operations. Tokens and credential hashes never enter audit."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.security import hash_password, verify_password
from app.modules.auth.models import AuthAccount, AuthSession
from app.modules.users.models import User
from app.modules.users.account_models import AccountAudit, AccountChallenge
from app.modules.users.identity_models import Profile, ProfileMember


def now():
    return datetime.now(timezone.utc)


def lock_user(db, user_id):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if user is None:
        raise HTTPException(404, "Cuenta no encontrada")
    return user


def require_active(user):
    if user.account_status != "active" or user.suspended_at is not None:
        raise HTTPException(403, {"code": "account_restricted", "message": "Cuenta restringida; usa el flujo de recuperación si solicitaste eliminarla"})


def audit(db, user, actor, action, *, before=None, after=None, reason=None, origin="account"):
    # Deliberate field allowlist, including calls from legacy endpoints.
    allowed = {"display_name", "biography", "avatar_present", "username", "role", "account_status",
               "suspended", "google_linked", "deletion_scheduled_at", "email_changed"}
    clean = lambda values: {k: v for k, v in (values or {}).items() if k in allowed}
    db.add(AccountAudit(user_id=user.id, actor_user_id=actor, action=action, origin=origin,
                        before_state=clean(before), after_state=clean(after), reason=reason))


def revoke_all(db, user_id, reason):
    db.execute(update(AuthAccount).where(AuthAccount.user_id == user_id)
               .values(security_version=AuthAccount.security_version + 1))
    db.execute(update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=now(), revocation_reason=reason, updated_at=now()))


def invalidate_challenges(db, user_id, purpose=None):
    query = update(AccountChallenge).where(AccountChallenge.user_id == user_id, AccountChallenge.consumed_at.is_(None))
    if purpose:
        query = query.where(AccountChallenge.purpose == purpose)
    db.execute(query.values(consumed_at=now()))


def issue_challenge(db, user, purpose, email=None):
    latest = db.scalar(select(AccountChallenge).where(AccountChallenge.user_id == user.id,
        AccountChallenge.purpose == purpose).order_by(AccountChallenge.created_at.desc()).limit(1))
    if latest and now() - latest.created_at < timedelta(seconds=60):
        raise HTTPException(429, "Espera un minuto antes de solicitar otro correo")
    invalidate_challenges(db, user.id, purpose)
    token = secrets.token_urlsafe(32)
    db.add(AccountChallenge(user_id=user.id, purpose=purpose, target_email=email,
        token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=now() + timedelta(minutes=10)))
    return token


def consume_challenge(db, token, purpose):
    digest = hashlib.sha256(token.encode()).hexdigest()
    # Lock order shared by recovery, deletion and challenge creation: user first.
    candidate = db.scalar(select(AccountChallenge).where(AccountChallenge.token_hash == digest))
    if candidate is None:
        raise HTTPException(400, "Código inválido o vencido")
    user = lock_user(db, candidate.user_id)
    challenge = db.scalar(select(AccountChallenge).where(AccountChallenge.id == candidate.id)
        .with_for_update().execution_options(populate_existing=True))
    if challenge.purpose != purpose or challenge.consumed_at or now() >= challenge.expires_at:
        audit(db, user, None, "challenge_rejected", origin="recovery")
        db.commit()
        raise HTTPException(400, "Código inválido o vencido")
    challenge.consumed_at = now()
    return user, challenge


def verify_current_password(user, password):
    if not password or not verify_password(password, user.auth_account.password_hash):
        raise HTTPException(400, "No fue posible verificar tu identidad")


def change_password(db, user, current, new):
    user = lock_user(db, user.id)
    require_active(user)
    verify_current_password(user, current)
    user.auth_account.password_hash = hash_password(new)
    revoke_all(db, user.id, "password_changed")
    invalidate_challenges(db, user.id)
    audit(db, user, user.id, "password_changed")


def request_deletion(db, user, password):
    user = lock_user(db, user.id)
    require_active(user)
    verify_current_password(user, password)
    # Existing organization policy: do not orphan an organization.
    memberships = db.scalars(select(ProfileMember).where(ProfileMember.user_id == user.id,
        ProfileMember.permission == "admin").order_by(ProfileMember.profile_id)).all()
    for member in memberships:
        # Membership edits lock the same organization row. Serialize two
        # administrators requesting deletion so they cannot orphan it together.
        db.scalar(select(Profile).where(Profile.id == member.profile_id).with_for_update())
        other = db.scalar(select(ProfileMember.user_id).join(User, User.id == ProfileMember.user_id).where(
            ProfileMember.profile_id == member.profile_id, ProfileMember.user_id != user.id,
            ProfileMember.permission == "admin", User.account_status == "active", User.suspended_at.is_(None)))
        if other is None:
            raise HTTPException(409, "Transfiere la administración de tu organización antes de eliminar la cuenta")
    user.account_status = "pending_deletion"
    user.deletion_requested_at = now()
    user.deletion_scheduled_at = user.deletion_requested_at + timedelta(days=30)
    revoke_all(db, user.id, "pending_deletion")
    invalidate_challenges(db, user.id)
    audit(db, user, user.id, "deletion_requested", before={"account_status": "active"},
          after={"account_status": user.account_status, "deletion_scheduled_at": user.deletion_scheduled_at.isoformat()})
    return user


def cancel_deletion(db, token):
    user, challenge = consume_challenge(db, token, "recover_deletion")
    if user.account_status != "pending_deletion" or now() >= user.deletion_scheduled_at:
        audit(db, user, None, "recovery_rejected", origin="recovery")
        db.commit()
        raise HTTPException(400, "La cuenta ya no puede recuperarse por este procedimiento")
    user.account_status = "active"
    user.deletion_requested_at = user.deletion_scheduled_at = None
    invalidate_challenges(db, user.id)
    audit(db, user, user.id, "deletion_cancelled", before={"account_status": "pending_deletion"},
          after={"account_status": "active", "suspended": user.suspended_at is not None}, origin="recovery")
    return user


def assign_role(db, user, admin, role, reason, *, approved=False):
    from sqlalchemy import delete
    from app.modules.users.identity_models import ProfileCapability, AccountPermission, IdentityAudit
    from app.modules.users.verification_models import VerificationRequest
    from app.modules.users.profile_models import ProfileRoleChange
    from app.modules.social.models import Post
    user = lock_user(db, user.id)
    require_active(user)
    if user.id == admin.id:
        raise HTTPException(403, "No puedes cambiar tu propio tipo de perfil")
    if role == user.role:
        raise HTTPException(409, "La cuenta ya tiene ese tipo de perfil")
    permission = db.get(AccountPermission, (user.id, "admin"))
    if permission and role != "admin":
        other_admin = db.scalar(select(AccountPermission.user_id).join(User, User.id == AccountPermission.user_id).where(
            AccountPermission.permission == "admin", AccountPermission.user_id != user.id,
            User.account_status == "active", User.suspended_at.is_(None)).limit(1))
        if not other_admin:
            raise HTTPException(409, "El sistema debe conservar un administrador activo")
    profile = db.scalar(select(Profile).where(Profile.owner_user_id == user.id))
    if not profile:
        raise HTTPException(409, "La cuenta legada requiere adaptación de identidad antes de cambiar su tipo")
    if user.role in {"autor", "influencer", "libreria"} and db.scalar(select(Post.id).where(
        Post.user_id == user.id, Post.author_role == user.role).limit(1)):
        raise HTTPException(409, "Hay publicaciones profesionales asociadas al tipo actual; requieren revisión antes del cambio")
    if role in {"autor", "influencer", "libreria"} and not approved:
        verification = db.scalar(select(VerificationRequest.id).where(VerificationRequest.user_id == user.id,
            VerificationRequest.requested_role == role, VerificationRequest.status == "approved").limit(1))
        if not verification:
            raise HTTPException(409, "El tipo de destino requiere una verificación profesional aprobada")
    if role == "libreria":
        from app.modules.library.models import LibraryEntry
        if db.scalar(select(LibraryEntry.id).where(LibraryEntry.user_id == user.id,
                                                   LibraryEntry.archived_at.is_(None)).limit(1)):
            raise HTTPException(409, "Archiva la biblioteca personal antes de cambiar al tipo librería; su historial se conservará")
    old = user.role
    old_capabilities = list(db.scalars(select(ProfileCapability.capability).where(ProfileCapability.profile_id == profile.id)))
    db.execute(delete(ProfileCapability).where(ProfileCapability.profile_id == profile.id,
        ProfileCapability.capability != "lector"))
    if role in {"autor", "influencer"}:
        db.add(ProfileCapability(profile_id=profile.id, capability=role))
    user.role = role
    if role == "admin" and not permission:
        db.add(AccountPermission(user_id=user.id, permission="admin"))
    elif role != "admin" and permission:
        db.delete(permission)
    db.add(ProfileRoleChange(user_id=user.id, admin_user_id=admin.id, previous_role=old,
                            new_role=role, reason=reason, created_at=now()))
    db.add(IdentityAudit(profile_id=profile.id, actor_user_id=admin.id, action="exclusive_role_changed",
                         detail=f"{old_capabilities} -> {role}; {reason}"))
    audit(db, user, admin.id, "role_changed", before={"role": old}, after={"role": role}, reason=reason, origin="admin")
    revoke_all(db, user.id, "role_changed")
    return user
