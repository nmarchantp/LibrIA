"""Phase-1 storage only; no identity resolver or write endpoint is activated."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Identity, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.model_mixins import EntityMixin


class CatalogOperation(EntityMixin, Base):
    __tablename__ = "operaciones_catalogo"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "operation_type", "request_key", name="uq_catalog_operation_request"),
        UniqueConstraint("id", "actor_user_id", name="uq_catalog_operation_actor"),
        UniqueConstraint("id", "target_work_id", name="uq_catalog_operation_target"),
        UniqueConstraint("id", "source_work_id", "target_work_id", name="uq_catalog_operation_pair"),
        CheckConstraint("operation_type IN ('library_add','admin_import','merge','reversal')"),
        CheckConstraint("length(trim(request_key)) BETWEEN 1 AND 200"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'"),
        CheckConstraint("length(trim(reason))>0"),
        CheckConstraint("jsonb_typeof(evidence)='object'"),
        CheckConstraint("jsonb_typeof(context)='object'"),
        CheckConstraint("(operation_type='merge' AND source_work_id IS NOT NULL AND source_work_id<>target_work_id) OR (operation_type<>'merge' AND source_work_id IS NULL)", name="ck_catalog_operation_pair"),
        CheckConstraint("(operation_type='reversal') = (reverses_operation_id IS NOT NULL)", name="ck_catalog_operation_reversal"),
        Index("ix_catalog_operations_target", "target_work_id", "created_at"),
        Index("ix_catalog_operations_source", "source_work_id", postgresql_where=text("source_work_id IS NOT NULL")),
        {"schema": "app"},
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    operation_type: Mapped[str] = mapped_column(Text)
    request_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    source_work_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    target_work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    reverses_operation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.operaciones_catalogo.id", ondelete="RESTRICT"))
    identity_version: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSONB)
    context: Mapped[dict] = mapped_column(JSONB)


class WorkReference(EntityMixin, Base):
    __tablename__ = "referencias_obras"
    __table_args__ = (
        UniqueConstraint("id", "work_id", name="uq_catalog_reference_work"),
        ForeignKeyConstraint(["operation_id", "work_id"], ["app.operaciones_catalogo.id", "app.operaciones_catalogo.target_work_id"], ondelete="RESTRICT"),
        CheckConstraint("provider IN ('google-books','open-library')"),
        CheckConstraint("reference_type IN ('work','volume','edition')"),
        CheckConstraint("length(trim(external_id)) BETWEEN 1 AND 200"),
        CheckConstraint("verification_status IN ('provisional','confirmed','contradictory','rejected')"),
        CheckConstraint("jsonb_typeof(evidence)='object'"),
        CheckConstraint("(provider='google-books' AND reference_type='volume') OR (provider='open-library' AND reference_type IN ('work','edition'))", name="ck_catalog_reference_provider"),
        CheckConstraint("verification_status<>'confirmed' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL AND length(trim(verified_by))>0 AND evidence<>'{}'::jsonb)", name="ck_catalog_reference_verified"),
        Index("uq_catalog_reference_binding", "provider", "reference_type", "external_id", unique=True, postgresql_where=text("verification_status IN ('provisional','confirmed')")),
        Index("ix_catalog_references_work", "work_id"),
        Index("ix_catalog_references_operation", "operation_id"),
        {"schema": "app"},
    )
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(Text)
    reference_type: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSONB)
    verified_by: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    operation_id: Mapped[uuid.UUID] = mapped_column()


class CatalogIncorporation(EntityMixin, Base):
    __tablename__ = "incorporaciones_catalogo"
    __table_args__ = (
        ForeignKeyConstraint(["operation_id", "actor_user_id"], ["app.operaciones_catalogo.id", "app.operaciones_catalogo.actor_user_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["operation_id", "work_id"], ["app.operaciones_catalogo.id", "app.operaciones_catalogo.target_work_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["edition_id", "work_id"], ["app.ediciones.id", "app.ediciones.work_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["library_entry_id", "work_id"], ["app.entradas_biblioteca.id", "app.entradas_biblioteca.work_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["reference_id", "work_id"], ["app.referencias_obras.id", "app.referencias_obras.work_id"], ondelete="RESTRICT"),
        CheckConstraint("origin IN ('library','admin_import')"),
        CheckConstraint("jsonb_typeof(requested_reference)='object'"),
        CheckConstraint("edition_selected = (edition_id IS NOT NULL)", name="ck_catalog_incorporation_edition"),
        CheckConstraint("(origin='library' AND library_entry_id IS NOT NULL) OR (origin='admin_import' AND library_entry_id IS NULL)", name="ck_catalog_incorporation_library"),
        Index("ix_catalog_incorporations_work", "work_id", "created_at"),
        Index("ix_catalog_incorporations_actor", "actor_user_id", "created_at"),
        {"schema": "app"},
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column()
    origin: Mapped[str] = mapped_column(Text)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    edition_id: Mapped[uuid.UUID | None] = mapped_column()
    edition_selected: Mapped[bool] = mapped_column(Boolean, server_default="false")
    library_entry_id: Mapped[uuid.UUID | None] = mapped_column()
    reference_id: Mapped[uuid.UUID | None] = mapped_column()
    requested_reference: Mapped[dict] = mapped_column(JSONB)


class WorkRedirect(Base):
    __tablename__ = "redirecciones_obras"
    __table_args__ = (
        ForeignKeyConstraint(["operation_id", "source_work_id", "target_work_id"], ["app.operaciones_catalogo.id", "app.operaciones_catalogo.source_work_id", "app.operaciones_catalogo.target_work_id"], ondelete="RESTRICT"),
        CheckConstraint("source_work_id<>target_work_id"),
        CheckConstraint("(retired_at IS NULL AND retirement_operation_id IS NULL) OR (retired_at IS NOT NULL AND retirement_operation_id IS NOT NULL AND retired_at>=active_from)"),
        Index("uq_catalog_redirect_active", "source_work_id", unique=True, postgresql_where=text("retired_at IS NULL")),
        Index("ix_catalog_redirect_target", "target_work_id", postgresql_where=text("retired_at IS NULL")),
        {"schema": "app"},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    target_work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    operation_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_operation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.operaciones_catalogo.id", ondelete="RESTRICT"))


class CatalogOperationEffect(EntityMixin, Base):
    __tablename__ = "efectos_operacion_catalogo"
    __table_args__ = (
        UniqueConstraint("operation_id", "ordinal"),
        CheckConstraint("ordinal>0"),
        CheckConstraint("length(trim(entity_table))>0"),
        CheckConstraint("before_state IS NOT NULL OR after_state IS NOT NULL"),
        CheckConstraint("before_state IS NULL OR jsonb_typeof(before_state)='object'"),
        CheckConstraint("after_state IS NULL OR jsonb_typeof(after_state)='object'"),
        Index("ix_catalog_effects_entity", "entity_table", "entity_id"),
        {"schema": "app"},
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.operaciones_catalogo.id", ondelete="RESTRICT"))
    ordinal: Mapped[int] = mapped_column(Integer)
    entity_table: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID] = mapped_column()
    before_state: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    after_state: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
