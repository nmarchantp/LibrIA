"""Account owner, recovery and authorized administrator endpoints."""
import io
import uuid
import warnings
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Query
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_password
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import AuthAccount, AuthSession
from app.modules.auth.repository import AuthRepository
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from app.modules.users.roles_router import get_admin
from app.modules.users.account_models import AccountAvatar, AccountAudit
from app.modules.users.account_schemas import (PublicAccountUpdate, PasswordChange, IdentityConfirmation,
    EmailStart, EmailRequest, TokenInput, ResetPassword, AdminState, AdminUsername, AdminRole, AdminVerification)
from app.modules.users.account_service import (audit, lock_user, require_active, revoke_all, issue_challenge,
    consume_challenge, change_password, request_deletion, cancel_deletion, now,
    verify_current_password, invalidate_challenges)
from app.modules.users.account_mail import send_account_email

router = APIRouter(prefix="/accounts", tags=["accounts"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(get_admin)]


def representation(user):
    return {"id": user.id, "username": user.username, "email": user.auth_account.email,
            "display_name": user.display_name, "biography": user.biography, "avatar_url": user.avatar_url,
            "role": user.role, "account_status": user.account_status,
            "suspended": user.suspended_at is not None, "google_linked": bool(user.auth_account.google_subject),
            "email_verified": user.auth_account.email_verified_at is not None,
            "deletion_scheduled_at": user.deletion_scheduled_at}


@router.get("/me")
def account_me(user: Owner, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return representation(user)


@router.patch("/me")
def update_public_account(data: PublicAccountUpdate, user: Owner, db: DB):
    user = lock_user(db, user.id)
    require_active(user)
    before = {"display_name": user.display_name, "biography": user.biography}
    user.display_name, user.biography = data.display_name, data.biography
    profile = db.scalar(select(Profile).where(Profile.owner_user_id == user.id))
    if profile:
        profile.display_name = user.display_name
    audit(db, user, user.id, "profile_updated", before=before, after=data.model_dump())
    db.commit()
    return representation(user)


@router.post("/me/password", status_code=204)
def password_change(data: PasswordChange, user: Owner, db: DB):
    change_password(db, user, data.current_password, data.new_password)
    db.commit()


@router.post("/me/email/request")
def email_request(data: EmailStart, user: Owner, db: DB):
    user = lock_user(db, user.id)
    require_active(user)
    verify_current_password(user, data.current_password)
    email = str(data.email).lower()
    if AuthRepository(db).get_account_by_email(email):
        raise HTTPException(409, "El correo ya está registrado")
    token = issue_challenge(db, user, "email_change", email)
    send_account_email(email, "Confirma tu nuevo correo de LibrIAverse",
                       f"Confirma el cambio desde Mi cuenta con este código de un solo uso (10 minutos):\n{token}")
    audit(db, user, user.id, "email_change_requested")
    db.commit()
    return {"status": "sent"}


@router.post("/me/email/confirm", status_code=204)
def email_confirm(data: TokenInput, user: Owner, db: DB):
    locked, challenge = consume_challenge(db, data.token, "email_change")
    if locked.id != user.id:
        raise HTTPException(400, "Código inválido")
    require_active(locked)
    old_email = locked.auth_account.email
    locked.auth_account.email = challenge.target_email
    locked.auth_account.email_verified_at = now()
    revoke_all(db, locked.id, "email_changed")
    invalidate_challenges(db, locked.id)
    audit(db, locked, locked.id, "email_changed", after={"email_changed": True})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "El correo ya está registrado") from None
    try:
        send_account_email(old_email, "Cambió tu correo en LibrIAverse",
                           "Se confirmó un cambio del correo principal de tu cuenta. Si no lo solicitaste, contacta al administrador.")
    except HTTPException:
        # The committed change remains valid if the old address cannot receive mail.
        pass


@router.post("/recovery/request")
def recovery_request(data: EmailRequest, db: DB, purpose: str = Query(pattern="^(password_reset|recover_deletion)$")):
    account = AuthRepository(db).get_account_by_email(str(data.email))
    if account:
        user = lock_user(db, account.user_id)
        eligible = (purpose == "password_reset" and user.account_status == "active" and user.suspended_at is None) or (
            purpose == "recover_deletion" and user.account_status == "pending_deletion" and now() < user.deletion_scheduled_at)
        audit(db, user, None, "recovery_requested", origin="recovery")
        if eligible:
            try:
                token = issue_challenge(db, user, purpose)
            except HTTPException as exc:
                if exc.status_code != 429:
                    raise
                token = None
            if token:
                send_account_email(account.email, "Recuperación de cuenta LibrIAverse",
                    f"Usa este código en la pantalla de acceso para confirmar la operación (vence en 10 minutos):\n{token}\nSi no lo solicitaste, ignora este mensaje.")
        db.commit()
    return {"status": "Si la cuenta es elegible, recibirás un correo con instrucciones"}


@router.post("/recovery/password", status_code=204)
def reset_password(data: ResetPassword, db: DB):
    user, challenge = consume_challenge(db, data.token, "password_reset")
    require_active(user)
    user.auth_account.password_hash = hash_password(data.new_password)
    user.auth_account.email_verified_at = now()
    revoke_all(db, user.id, "password_reset")
    invalidate_challenges(db, user.id)
    audit(db, user, user.id, "password_reset", origin="recovery")
    db.commit()


@router.post("/recovery/deletion")
def recover_deleted_account(data: TokenInput, db: DB):
    user = cancel_deletion(db, data.token)
    db.commit()
    return {"status": "recovered", "suspended": user.suspended_at is not None}


@router.post("/me/deletion")
def deletion_request(data: IdentityConfirmation, user: Owner, db: DB):
    user = request_deletion(db, user, data.current_password)
    db.commit()
    return {"status": user.account_status, "deletion_requested_at": user.deletion_requested_at,
            "deletion_scheduled_at": user.deletion_scheduled_at}


@router.post("/me/google/unlink", status_code=204)
def unlink_google(data: IdentityConfirmation, user: Owner, db: DB):
    user = lock_user(db, user.id)
    require_active(user)
    verify_current_password(user, data.current_password)
    # All existing registrations require a password. Verify it before removing Google.
    account = user.auth_account
    if not account.email_verified_at:
        raise HTTPException(409, "Verifica tu correo principal antes de desvincular Google")
    account.google_subject = account.google_email = account.google_email_code_hash = None
    account.google_email_verified_at = account.google_email_code_expires_at = None
    revoke_all(db, user.id, "google_unlinked")
    audit(db, user, user.id, "google_unlinked", before={"google_linked": True}, after={"google_linked": False})
    db.commit()


@router.post("/me/email/verify/request")
def primary_email_request(data: IdentityConfirmation, user: Owner, db: DB):
    user = lock_user(db, user.id)
    require_active(user)
    verify_current_password(user, data.current_password)
    token = issue_challenge(db, user, "verify_primary")
    send_account_email(user.auth_account.email, "Verifica tu correo principal de LibrIAverse",
        f"Confirma tu correo desde Mi cuenta con este código de un solo uso (10 minutos):\n{token}")
    db.commit()
    return {"status": "sent"}


@router.post("/me/email/verify/confirm", status_code=204)
def primary_email_confirm(data: TokenInput, user: Owner, db: DB):
    locked, challenge = consume_challenge(db, data.token, "verify_primary")
    if locked.id != user.id:
        raise HTTPException(400, "Código inválido")
    require_active(locked)
    locked.auth_account.email_verified_at = now()
    audit(db, locked, locked.id, "primary_email_verified")
    db.commit()


@router.get("/me/sessions")
def list_sessions(user: Owner, db: DB):
    return [{"id": s.id, "created_at": s.created_at, "last_activity_at": s.last_activity_at,
             "absolute_expires_at": s.absolute_expires_at} for s in db.scalars(select(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None),
        AuthSession.inactivity_expires_at > now(), AuthSession.absolute_expires_at > now()))]


@router.delete("/me/sessions/{session_id}", status_code=204)
def close_session(session_id: uuid.UUID, user: Owner, db: DB):
    user = lock_user(db, user.id)
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id,
        AuthSession.user_id == user.id).with_for_update())
    if not session:
        raise HTTPException(404, "Sesión no encontrada")
    session.revoked_at, session.revocation_reason = now(), "owner_revoked"
    audit(db, user, user.id, "session_revoked")
    db.commit()


@router.put("/me/avatar")
async def avatar_upload(user: Owner, db: DB, file: UploadFile = File(...)):
    raw = await file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "La foto debe pesar como máximo 2 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 16_000_000:
                    raise ValueError()
                image.load()
                image = image.convert("RGB")
                image.thumbnail((1024, 1024))
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=85)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Usa una imagen JPEG, PNG o WebP válida de hasta 16 megapíxeles") from None
    user = lock_user(db, user.id)
    require_active(user)
    avatar = db.get(AccountAvatar, user.id)
    if avatar is None:
        avatar = AccountAvatar(user_id=user.id)
        db.add(avatar)
    avatar.data, avatar.content_type = output.getvalue(), "image/jpeg"
    before = {"avatar_present": bool(user.avatar_url)}
    user.avatar_url = f"{get_settings().api_prefix}/accounts/avatars/{user.id}?v={uuid.uuid4().hex}"
    audit(db, user, user.id, "avatar_updated", before=before, after={"avatar_present": True})
    db.commit()
    return representation(user)


@router.delete("/me/avatar", status_code=204)
def avatar_remove(user: Owner, db: DB):
    user = lock_user(db, user.id)
    require_active(user)
    avatar = db.get(AccountAvatar, user.id)
    if avatar:
        db.delete(avatar)
    user.avatar_url = None
    audit(db, user, user.id, "avatar_removed", after={"avatar_present": False})
    db.commit()


@router.get("/avatars/{user_id}")
def avatar_read(user_id: uuid.UUID, db: DB):
    user = db.get(User, user_id)
    avatar = db.get(AccountAvatar, user_id)
    if not user or user.account_status != "active" or user.suspended_at or not avatar:
        raise HTTPException(404, "Foto no disponible")
    return Response(avatar.data, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/admin")
def admin_accounts(admin: Admin, db: DB, state: str | None = Query(default=None, pattern="^(active|suspended|pending_deletion|anonymized)$"),
                   limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
                   q: str = Query(default="", max_length=100)):
    query = select(User).join(AuthAccount, AuthAccount.user_id == User.id)
    if q.strip():
        query = query.where(or_(User.username.icontains(q.strip(), autoescape=True),
            User.display_name.icontains(q.strip(), autoescape=True), AuthAccount.email.icontains(q.strip(), autoescape=True)))
    if state == "suspended":
        query = query.where(User.suspended_at.is_not(None))
    elif state:
        query = query.where(User.account_status == state)
        if state == "active":
            query = query.where(User.suspended_at.is_(None))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {"items": [representation(u) for u in db.scalars(query.order_by(User.created_at, User.id).limit(limit).offset(offset))], "total": total}


@router.patch("/admin/{user_id}/suspension")
def admin_suspend(user_id: uuid.UUID, data: AdminState, admin: Admin, db: DB):
    if user_id == admin.id:
        raise HTTPException(409, "No puedes modificar tu propia suspensión")
    user = lock_user(db, user_id)
    if user.account_status == "anonymized":
        raise HTTPException(409, "La cuenta fue anonimizada")
    before = {"suspended": user.suspended_at is not None}
    user.suspended_at = now() if data.suspended else None
    revoke_all(db, user.id, "admin_suspension_changed")
    audit(db, user, admin.id, "suspension_changed", before=before,
          after={"suspended": data.suspended}, reason=data.reason, origin="admin")
    db.commit()
    return representation(user)


@router.patch("/admin/{user_id}/username")
def admin_username(user_id: uuid.UUID, data: AdminUsername, admin: Admin, db: DB):
    user = lock_user(db, user_id)
    if user.account_status == "anonymized":
        raise HTTPException(409, "La cuenta fue anonimizada")
    before = {"username": user.username}
    user.username = data.username
    audit(db, user, admin.id, "username_changed", before=before, after={"username": user.username},
          reason=data.reason, origin="admin")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Nombre de usuario ya registrado") from None
    return representation(user)


@router.get("/admin/{user_id}/history")
def account_history(user_id: uuid.UUID, admin: Admin, db: DB, limit: int = Query(default=50, ge=1, le=100),
                    offset: int = Query(default=0, ge=0)):
    return [{"id": a.id, "actor_user_id": a.actor_user_id, "action": a.action, "origin": a.origin,
             "created_at": a.created_at, "correlation_id": a.correlation_id, "reason": a.reason,
             "before": a.before_state, "after": a.after_state} for a in db.scalars(select(AccountAudit)
            .where(AccountAudit.user_id == user_id).order_by(AccountAudit.created_at.desc(), AccountAudit.id).limit(limit).offset(offset))]


@router.patch("/admin/{user_id}/role")
def change_role(user_id: uuid.UUID, data: AdminRole, admin: Admin, db: DB):
    from app.modules.users.account_service import assign_role
    user = assign_role(db, lock_user(db, user_id), admin, data.role, data.reason)
    db.commit()
    return representation(user)


@router.post("/admin/{user_id}/verification", status_code=201)
def request_professional_verification(user_id: uuid.UUID, data: AdminVerification, admin: Admin, db: DB):
    from app.modules.users.verification_models import VerificationRequest
    if user_id == admin.id:
        raise HTTPException(403, "No puedes solicitar tu propio cambio de tipo")
    user = lock_user(db, user_id)
    require_active(user)
    if db.scalar(select(VerificationRequest.id).where(VerificationRequest.user_id == user_id,
                                                     VerificationRequest.status == "pending")):
        raise HTTPException(409, "Ya hay una solicitud pendiente")
    item = VerificationRequest(user_id=user_id, requested_role=data.requested_role, note=data.note)
    db.add(item)
    audit(db, user, admin.id, "professional_verification_requested", reason=data.note, origin="admin")
    db.commit()
    return {"id": item.id, "status": item.status}
