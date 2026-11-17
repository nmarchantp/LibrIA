"""Explicit existing-account fixture for tests unrelated to initial registration."""
import uuid
from app.modules.users.models import User


def existing_account(db, response):
    account = response.json()
    user = db.get(User, uuid.UUID(account['user']['id']))
    user.onboarding = {}
    db.commit()
    return account
