"""Expired-account minimization, serialized with cancellation by the account row lock.

Only direct account data is processed here. Free text in historical content is retained
under the approved policy and requires a separate privacy review.
"""
import asyncio
import secrets
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import array
from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from app.modules.users.account_models import AccountAvatar, AccountChallenge, AccountAudit
from app.modules.auth.models import AuthSession
from app.modules.users.account_service import audit, invalidate_challenges, now, revoke_all


def process_expired_accounts(db, *, batch_size=50):
    rows = db.scalars(select(User).where(User.account_status == "pending_deletion",
        User.deletion_scheduled_at <= now()).order_by(User.id).limit(batch_size)
        .with_for_update(skip_locked=True).execution_options(populate_existing=True)).all()
    for user in rows:
        # Preserve UUID and all content/reference rows. Remove direct identifying data.
        account = user.auth_account
        account.email = f"deleted-{user.id.hex}@example.com"
        account.password_hash = hash_password(secrets.token_urlsafe(64))
        account.email_verified_at = None
        account.google_subject = account.google_email = account.google_email_verified_at = None
        account.google_email_code_hash = account.google_email_code_expires_at = account.google_email_code_sent_at = None
        account.google_email_code_attempts = 0
        user.username = "deleted_" + user.id.hex
        user.display_name = "Cuenta eliminada"
        user.biography = user.avatar_url = None
        user.account_status, user.anonymized_at = "anonymized", now()
        user.deletion_requested_at = user.deletion_scheduled_at = None
        for profile in db.scalars(select(Profile).where(Profile.owner_user_id == user.id)):
            profile.display_name = "Cuenta eliminada"
        avatar = db.get(AccountAvatar, user.id)
        if avatar:
            db.delete(avatar)
        revoke_all(db, user.id, "account_anonymized")
        invalidate_challenges(db, user.id)
        db.execute(update(AccountChallenge).where(AccountChallenge.user_id == user.id).values(target_email=None))
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(refresh_token_hash="0" * 64))
        audit(db, user, None, "account_anonymized", before={"account_status": "pending_deletion"},
              after={"account_status": "anonymized"}, origin="lifecycle")
        db.flush()
        # The audit trigger permits precisely this irreversible minimization;
        # operations, actors, dates, reasons and correlation remain immutable.
        pii = array(['display_name', 'biography', 'username'])
        db.execute(update(AccountAudit).where(AccountAudit.user_id == user.id).values(
            before_state=AccountAudit.before_state.op('-')(pii),
            after_state=AccountAudit.after_state.op('-')(pii)))
    db.flush()
    return len(rows)


async def account_lifecycle_scheduler():
    import logging
    from app.core.database import SessionLocal
    def step():
        with SessionLocal() as db:
            process_expired_accounts(db)
            db.commit()
    while True:
        try:
            await asyncio.to_thread(step)
        except Exception:
            logging.getLogger(__name__).exception("Account lifecycle failed; pending accounts retained for retry")
        await asyncio.sleep(60)
