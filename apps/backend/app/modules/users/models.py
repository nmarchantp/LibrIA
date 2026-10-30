"""Modelo operacional del perfil de usuario."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("role IN ('lector', 'influencer', 'autor', 'libreria', 'admin')", name="ck_usuarios_role"),
        CheckConstraint("account_status IN ('active','pending_deletion','anonymized')", name="ck_account_status"),
        CheckConstraint("(account_status='anonymized')=(anonymized_at IS NOT NULL)", name="ck_anonymized_date"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: "reader_" + uuid.uuid4().hex)
    account_status: Mapped[str] = mapped_column(String(24), default="active", server_default="active")
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="lector", server_default="lector")
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    biography: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    auth_account: Mapped["AuthAccount"] = relationship(back_populates="user", cascade="all, delete-orphan")
