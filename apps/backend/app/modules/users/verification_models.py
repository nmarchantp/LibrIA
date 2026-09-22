"""Solicitudes de verificación de perfiles profesionales."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VerificationRequest(Base):
    __tablename__ = "solicitudes_verificacion"
    __table_args__ = (
        CheckConstraint("requested_role IN ('influencer', 'autor')", name="ck_solicitudes_verificacion_role"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_solicitudes_verificacion_status"),
        Index("uq_solicitudes_verificacion_pending_user", "user_id", unique=True,
              postgresql_where=text("status = 'pending'")),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"))
    requested_role: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.usuarios.id", ondelete="SET NULL"))
