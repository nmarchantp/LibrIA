"""Role notices are committed atomically with their application or decision."""
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from app.modules.users.identity_models import AccountPermission
from app.modules.users.models import User
from app.modules.users.verification_models import RoleNotification


def notify_request(db, request):
    db.flush()
    recipients = db.scalars(select(User.id).join(AccountPermission, AccountPermission.user_id == User.id).where(
        AccountPermission.permission == 'admin', User.account_status == 'active', User.suspended_at.is_(None), User.id != request.user_id)).all()
    for recipient in recipients:
        db.execute(insert(RoleNotification).values(request_id=request.id, recipient_user_id=recipient, kind='requested').on_conflict_do_nothing())


def notify_decision(db, request):
    db.execute(insert(RoleNotification).values(request_id=request.id, recipient_user_id=request.user_id, kind=request.status).on_conflict_do_nothing())
    db.execute(update(RoleNotification).where(RoleNotification.request_id == request.id,
        RoleNotification.kind == 'requested', RoleNotification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
