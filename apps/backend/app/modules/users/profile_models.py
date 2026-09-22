"""Historial de revocaciones de perfiles gestionadas por administradores."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProfileRoleChange(Base):
    __tablename__ = "cambios_rol_perfil"
    __table_args__ = {"schema": "app"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    previous_role: Mapped[str] = mapped_column(String(20))
    new_role: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
