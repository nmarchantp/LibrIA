"""Credenciales separadas del perfil del usuario."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AuthAccount(Base):
    __tablename__ = "cuentas_autenticacion"
    __table_args__ = {"schema": "app"}
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    google_email: Mapped[str | None] = mapped_column(String(320))
    google_email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    google_email_code_hash: Mapped[str | None] = mapped_column(String(64))
    google_email_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    google_email_code_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    google_email_code_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped["User"] = relationship(back_populates="auth_account")
