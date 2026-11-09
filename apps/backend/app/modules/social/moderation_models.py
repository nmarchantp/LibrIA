"""Shared moderation storage: private revisions, immutable evidence and reports."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

STATUS_CHECK = "moderation_status IN ('approved','pending_review','rejected')"


class ModeratedContentMixin:
    moderation_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    moderation_status: Mapped[str] = mapped_column(String(16), default='approved', server_default='approved')
    moderation_version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')


class ModerationRevision(Base):
    __tablename__ = 'revisiones_moderacion'
    __table_args__ = (
        CheckConstraint('num_nonnulls(post_id, review_id, comment_id) = 1', name='ck_mod_revision_destination'),
        CheckConstraint("status IN ('approved','pending_review','rejected')", name='ck_mod_revision_status'),
        CheckConstraint("lifecycle IN ('active','superseded','withdrawn')", name='ck_mod_revision_lifecycle'),
        CheckConstraint('base_version > 0 AND length(base_fingerprint)=64', name='ck_mod_revision_base'),
        CheckConstraint("jsonb_typeof(proposal)='object' AND jsonb_typeof(findings)='array'", name='ck_mod_revision_json'),
        CheckConstraint("(status IN ('pending_review','approved') AND decided_by IS NULL AND decided_at IS NULL AND decision_reason IS NULL) OR (status IN ('approved','rejected') AND decided_by IS NOT NULL AND decided_at IS NOT NULL AND decision_reason IS NOT NULL AND length(trim(decision_reason))>0)", name='ck_mod_revision_decision'),
        *[Index(f'uq_mod_pending_{column}', column, unique=True,
                postgresql_where=text("status='pending_review' AND lifecycle='active'")) for column in ('post_id','review_id','comment_id')],
        Index('ix_mod_revision_queue', 'status', 'lifecycle', 'created_at', 'id'),
        Index('ix_mod_revision_author', 'author_user_id', 'created_at'), {'schema':'app'},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.publicaciones.id', ondelete='RESTRICT'))
    review_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.resenas.id', ondelete='RESTRICT'))
    comment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.comentarios_publicacion.id', ondelete='RESTRICT'))
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'))
    base_version: Mapped[int] = mapped_column(Integer)
    base_fingerprint: Mapped[str] = mapped_column(String(64))
    proposal: Mapped[dict] = mapped_column(JSONB)
    findings: Mapped[list] = mapped_column(JSONB)
    ruleset_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))
    lifecycle: Mapped[str] = mapped_column(String(16), default='active', server_default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)


class ModerationAttachment(Base):
    __tablename__ = 'adjuntos_moderacion'
    __table_args__ = (
        CheckConstraint("role IN ('image','cover')", name='ck_mod_attachment_role'),
        CheckConstraint("content_type IN ('image/jpeg','image/png','image/gif','image/webp')", name='ck_mod_attachment_type'),
        CheckConstraint('octet_length(data) BETWEEN 1 AND 5242880 AND position >= 0', name='ck_mod_attachment_size'),
        Index('uq_mod_attachment_order', 'revision_id', 'role', 'position', unique=True),
        Index('uq_mod_attachment_cover', 'revision_id', unique=True, postgresql_where=text("role='cover'")), {'schema':'app'},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.revisiones_moderacion.id', ondelete='RESTRICT'))
    role: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary)


class ModerationAudit(Base):
    __tablename__ = 'auditoria_moderacion'
    __table_args__ = (
        CheckConstraint("action IN ('prepared','superseded','withdrawn','approved','rejected','hidden','restored','reported','dismissed')", name='ck_mod_audit_action'),
        CheckConstraint('num_nonnulls(revision_id, report_id)=1', name='ck_mod_audit_destination'),
        CheckConstraint('length(trim(reason)) BETWEEN 1 AND 2000', name='ck_mod_audit_reason'),
        CheckConstraint("jsonb_typeof(context)='object'",name='ck_mod_audit_context'),
        Index('ix_mod_audit_revision', 'revision_id', 'created_at'),
        Index('ix_mod_audit_report', 'report_id', 'created_at'), {'schema':'app'},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.revisiones_moderacion.id', ondelete='RESTRICT'))
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.reportes_contenido.id', ondelete='RESTRICT'))
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'))
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModerationRequest(Base):
    __tablename__ = 'solicitudes_moderacion'
    __table_args__ = (
        CheckConstraint('length(payload_hash)=64', name='ck_mod_request_hash'),
        CheckConstraint("result IS NULL OR jsonb_typeof(result)='object'", name='ck_mod_request_result'), {'schema':'app'},
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'), primary_key=True)
    operation: Mapped[str] = mapped_column(String(160), primary_key=True)
    key: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentReport(Base):
    __tablename__ = 'reportes_contenido'
    __table_args__ = (
        CheckConstraint('num_nonnulls(post_id, review_id, comment_id)=1', name='ck_content_report_destination'),
        CheckConstraint("reason IN ('discrimination','harassment','threats','sexual_content','spam','other')", name='ck_content_report_reason'),
        CheckConstraint('length(detail)<=2000', name='ck_content_report_detail'),
        CheckConstraint("status IN ('pending','dismissed','hidden')", name='ck_content_report_status'),
        CheckConstraint("(status='pending' AND resolved_by IS NULL AND resolved_at IS NULL AND resolution_reason IS NULL) OR (status!='pending' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL AND length(trim(resolution_reason)) BETWEEN 1 AND 2000)", name='ck_content_report_resolution'),
        *[Index(f'uq_content_report_{column}', 'reporter_user_id', column, unique=True) for column in ('post_id','review_id','comment_id')],
        Index('ix_content_report_queue','status','created_at','id'), {'schema':'app'},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.publicaciones.id', ondelete='RESTRICT'))
    review_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.resenas.id', ondelete='RESTRICT'))
    comment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.comentarios_publicacion.id', ondelete='RESTRICT'))
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'))
    reason: Mapped[str] = mapped_column(String(24))
    detail: Mapped[str] = mapped_column(Text, default='', server_default='')
    content_snapshot: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default='pending', server_default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(Text)


class ModerationNotification(Base):
    __tablename__='notificaciones_moderacion'
    __table_args__=(
        CheckConstraint("kind IN ('pending_review','approved','rejected')",name='ck_mod_notification_kind'),
        Index('uq_mod_notification_event','recipient_user_id','revision_id','kind',unique=True),
        Index('ix_mod_notification_inbox','recipient_user_id','created_at','id'), {'schema':'app'},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True,default=uuid.uuid4)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id',ondelete='RESTRICT'))
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.revisiones_moderacion.id',ondelete='RESTRICT'))
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
