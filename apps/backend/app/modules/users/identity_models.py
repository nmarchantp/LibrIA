"""Identidades públicas, capacidades y pertenencia a organizaciones."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Profile(Base):
    __tablename__ = "perfiles"
    __table_args__ = (
        CheckConstraint("kind IN ('personal', 'organization')", name="ck_perfiles_kind"),
        CheckConstraint("(kind = 'personal' AND organization_type IS NULL) OR (kind = 'organization' AND organization_type IN ('libreria', 'editorial'))", name="ck_perfiles_org_type"),
        CheckConstraint("(kind = 'personal' AND owner_user_id IS NOT NULL) OR (kind = 'organization' AND owner_user_id IS NULL)", name="ck_perfiles_owner"),
        CheckConstraint("verification_status IN ('pending', 'verified', 'rejected', 'suspended')", name="ck_perfiles_verification"),
        CheckConstraint("length(trim(display_name)) BETWEEN 2 AND 100", name="ck_perfiles_name"),
        Index("uq_perfiles_owner", "owner_user_id", unique=True, postgresql_where=text("owner_user_id IS NOT NULL")),
        {"schema": "app"},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    organization_type: Mapped[str | None] = mapped_column(String(20))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    display_name: Mapped[str] = mapped_column(String(100))
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileCapability(Base):
    __tablename__ = "capacidades_perfil"
    __table_args__ = (
        CheckConstraint("capability IN ('lector', 'autor', 'influencer')", name="ck_capacidades_perfil_value"),
        {"schema": "app"},
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.perfiles.id", ondelete="CASCADE"), primary_key=True)
    capability: Mapped[str] = mapped_column(String(20), primary_key=True)


class ProfileMember(Base):
    __tablename__ = "miembros_perfil"
    __table_args__ = (
        CheckConstraint("permission IN ('admin', 'editor')", name="ck_miembros_perfil_permission"),
        {"schema": "app"},
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.perfiles.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(20))


class AccountPermission(Base):
    __tablename__ = "permisos_cuenta"
    __table_args__ = (
        CheckConstraint("permission = 'admin'", name="ck_permisos_cuenta_permission"),
        {"schema": "app"},
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(20), primary_key=True)


class IdentityAudit(Base):
    __tablename__ = "auditoria_identidades"
    __table_args__ = {"schema": "app"}
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.perfiles.id", ondelete="RESTRICT"), index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
