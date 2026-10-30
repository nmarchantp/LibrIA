"""Account security challenges, sanitized audit events and validated avatar bytes."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.model_mixins import EntityMixin


class AccountAudit(EntityMixin, Base):
    __tablename__ = "auditoria_cuentas"
    __table_args__ = {"schema": "app"}
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(64))
    origin: Mapped[str] = mapped_column(String(40))
    correlation_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    reason: Mapped[str | None] = mapped_column(Text)
    before_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    after_state: Mapped[dict] = mapped_column(JSONB, default=dict)


class AccountChallenge(EntityMixin, Base):
    __tablename__ = "desafios_cuenta"
    __table_args__ = {"schema": "app"}
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    target_email: Mapped[str | None] = mapped_column(String(320))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountAvatar(Base):
    __tablename__ = "fotos_cuenta"
    __table_args__ = {"schema": "app"}
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
