"""Único acceso de Auth a PostgreSQL."""

import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User
from app.core.exceptions import EmailAlreadyRegisteredError


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_account_by_email(self, email: str) -> AuthAccount | None:
        statement = select(AuthAccount).options(joinedload(AuthAccount.user)).where(AuthAccount.email == email.lower())
        return self.db.scalar(statement)

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        statement = select(User).options(joinedload(User.auth_account)).where(User.id == user_id)
        return self.db.scalar(statement)

    def create_account(self, email: str, password_hash: str, display_name: str) -> User:
        user = User(display_name=display_name.strip())
        user.auth_account = AuthAccount(email=email.lower(), password_hash=password_hash)
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise EmailAlreadyRegisteredError from None
        self.db.refresh(user)
        return user
