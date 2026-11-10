"""Modelo operacional del perfil de usuario."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("profile_visibility IN ('public','private')", name="ck_users_profile_visibility"),
        CheckConstraint("events_visibility IN ('private','contacts','public')", name="ck_users_events_visibility"),
        CheckConstraint("story_illustration IN ('flowers', 'books', 'cat', 'none')", name="ck_story_illustration"),
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
    story_illustration: Mapped[str] = mapped_column(String(16), default="flowers", server_default="flowers")
    biography: Mapped[str | None] = mapped_column(Text)
    events_visibility: Mapped[str] = mapped_column(String(16), default="private", server_default="private")
    profile_visibility: Mapped[str] = mapped_column(String(16), default="public", server_default="public")
    public_sections: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["biography", "genres", "tropes", "intensities", "interests"], server_default='["biography","genres","tropes","intensities","interests"]')
    favorite_quotes: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    auth_account: Mapped["AuthAccount"] = relationship(back_populates="user", cascade="all, delete-orphan")
