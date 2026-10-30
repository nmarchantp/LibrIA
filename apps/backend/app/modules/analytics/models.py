"""SQLAlchemy mappings for analytical projections and durable AI persistence."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectionRun(Base):
    __tablename__ = "projection_runs"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_projection_runs_id_owner"),
        Index("ix_projection_owner_date", "owner_id", text("processed_at DESC")),
        {"schema": "analytics"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app.usuarios.id", ondelete="CASCADE")
    )
    source_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transform_version: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(Text)
    identity_version: Mapped[str | None] = mapped_column(Text, deferred=True, server_default=text("NULL"))
    payload: Mapped[dict] = mapped_column(JSONB)


class ETLRun(Base):
    """Identity of a historical daily or manually requested ETL snapshot."""

    __tablename__ = "ejecuciones_etl"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transform_version: Mapped[str] = mapped_column(String(20))
    identity_version: Mapped[str | None] = mapped_column(Text, deferred=True, server_default=text("NULL"))
    error_code: Mapped[str | None] = mapped_column(String(100))
    business_date: Mapped[date | None] = mapped_column(Date)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="1")
    summary: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    run_kind: Mapped[str] = mapped_column(Text, server_default="daily")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app.usuarios.id")
    )
    phase: Mapped[str] = mapped_column(Text, server_default="queued")


class ReaderProfileVersion(Base):
    __tablename__ = "reader_profile_versions"
    __table_args__ = (
        UniqueConstraint("owner_id", "version", name="uq_reader_profile_owner_version"),
        UniqueConstraint("owner_id", "data_hash", name="uq_reader_profile_owner_hash"),
        UniqueConstraint("id", "owner_id", name="uq_reader_profile_id_owner"),
        CheckConstraint("length(data_hash) = 64", name="reader_profile_versions_data_hash_check"),
        CheckConstraint("version > 0", name="reader_profile_versions_version_check"),
        CheckConstraint(
            "status IN ('pending', 'ready', 'failed')",
            name="reader_profile_versions_status_check",
        ),
        CheckConstraint(
            "(status = 'ready' AND generated_at IS NOT NULL AND error_code IS NULL) "
            "OR (status <> 'ready' AND generated_at IS NULL)",
            name="ck_reader_profile_ready_at",
        ),
        CheckConstraint(
            "payload IS NULL OR (jsonb_typeof(payload) = 'object' "
            "AND payload->>'hash_version' = 'recommendation-profile-v1' "
            "AND jsonb_typeof(payload->'books') = 'array')",
            name="ck_reader_profile_payload",
        ),
        Index("ix_reader_profile_owner_status", "owner_id", "status", text("created_at DESC")),
        Index(
            "uq_reader_profile_owner_etl_run",
            "owner_id",
            "etl_run_id",
            unique=True,
            postgresql_where=text("etl_run_id IS NOT NULL"),
        ),
        {"schema": "ia"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app.usuarios.id", ondelete="CASCADE")
    )
    projection_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analytics.projection_runs.id", ondelete="RESTRICT"),
        comment="Legacy 0049 association only; nightly profiles use etl_run_id.",
    )
    etl_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analytics.ejecuciones_etl.id", ondelete="RESTRICT"),
        comment="First successful daily ETL cutoff that produced this content version.",
    )
    identity_version: Mapped[str | None] = mapped_column(Text, deferred=True, server_default=text("NULL"))
    data_hash: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ReaderProfileETLState(Base):
    __tablename__ = "reader_profile_etl_states"
    __table_args__ = (
        UniqueConstraint("owner_id", "etl_run_id", name="uq_reader_profile_etl_state"),
        ForeignKeyConstraint(
            ["profile_version_id", "owner_id"],
            ["ia.reader_profile_versions.id", "ia.reader_profile_versions.owner_id"],
            name="fk_reader_profile_etl_state_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "outcome IN ('empty', 'eligible_pending', 'unchanged')",
            name="reader_profile_etl_states_outcome_check",
        ),
        CheckConstraint("eligible_books_count >= 0", name="reader_profile_etl_states_eligible_books_count_check"),
        CheckConstraint("context_bytes >= 0", name="reader_profile_etl_states_context_bytes_check"),
        CheckConstraint("estimated_tokens >= 0", name="reader_profile_etl_states_estimated_tokens_check"),
        CheckConstraint(
            "(outcome = 'empty' AND profile_version_id IS NULL AND eligible_books_count = 0) "
            "OR (outcome IN ('eligible_pending', 'unchanged') "
            "AND profile_version_id IS NOT NULL AND eligible_books_count > 0)",
            name="ck_reader_profile_etl_state_profile",
        ),
        Index("ix_reader_profile_etl_state_latest", "owner_id", text("created_at DESC")),
        {
            "schema": "ia",
            "comment": "One idempotent outcome per reader and successful daily ETL cutoff.",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app.usuarios.id", ondelete="CASCADE")
    )
    etl_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analytics.ejecuciones_etl.id", ondelete="RESTRICT")
    )
    profile_version_id: Mapped[uuid.UUID | None] = mapped_column()
    outcome: Mapped[str] = mapped_column(Text)
    eligible_books_count: Mapped[int] = mapped_column(Integer)
    context_bytes: Mapped[int] = mapped_column(BigInteger)
    estimated_tokens: Mapped[int] = mapped_column(BigInteger)
    requires_segmentation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ReadingAnalysisRequest(Base):
    __tablename__ = 'reading_analysis_requests'
    __table_args__ = (Index('ix_reading_requests_pending', 'changed_at'),
                      Index('ix_reading_requests_owner', 'owner_id', 'reading_event_id'), {'schema': 'ia'})
    reading_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.eventos_lectura.id', ondelete='CASCADE'), primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='CASCADE'))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('clock_timestamp()'))
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)


class ReadingAnalysisSnapshot(Base):
    __tablename__ = 'reading_analysis_snapshots'
    __table_args__ = {'schema': 'ia'}
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ia.jobs.id', ondelete='CASCADE'), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('clock_timestamp()'))
    etl_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('analytics.ejecuciones_etl.id'))


class AIJob(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "target", name="jobs_owner_id_target_key"),
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="jobs_status_check",
        ),
        CheckConstraint(
            "job_kind IN ('adaptive_analysis', 'recommendation', 'reading_event_analysis', 'reader_profile')",
            name="ck_ai_jobs_kind",
        ),
        CheckConstraint(
            "(job_kind = 'adaptive_analysis' AND profile_version_id IS NULL AND reading_event_id IS NULL) "
            "OR (job_kind IN ('recommendation','reader_profile') AND profile_version_id IS NOT NULL "
            "AND reading_event_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL) "
            "OR (job_kind = 'reading_event_analysis' AND reading_event_id IS NOT NULL "
            "AND profile_version_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL)",
            name="ck_ai_jobs_context",
        ),
        Index("ix_ai_job_queue", "status", "not_before"),
        Index("ix_ai_job_kind_queue", "job_kind", "status", "not_before"),
        Index(
            "uq_ai_job_recommendation_request",
            "owner_id",
            "profile_version_id",
            "provider",
            "model",
            "prompt_version",
            unique=True,
            postgresql_where=text("job_kind = 'recommendation'"),
        ),
        Index(
            "uq_ai_job_reading_event_request",
            "reading_event_id",
            "provider",
            "model",
            "prompt_version",
            "evidence_hash",
            unique=True,
            postgresql_where=text("job_kind = 'reading_event_analysis'"),
        ),
        {"schema": "ia"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app.usuarios.id", ondelete="CASCADE")
    )
    target: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    error_code: Mapped[str | None] = mapped_column(Text)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_hash: Mapped[str | None] = mapped_column(Text)
    consolidation_seconds: Mapped[int] = mapped_column(Integer, default=1800, server_default='1800')
    job_kind: Mapped[str] = mapped_column(Text, default="adaptive_analysis", server_default="adaptive_analysis")
    provider: Mapped[str] = mapped_column(
        Text,
        default="gemini",
        server_default="gemini",
        comment="New rows default to Gemini; historical rows retain their original provider.",
    )
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    profile_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ia.reader_profile_versions.id", ondelete="RESTRICT")
    )
    reading_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app.eventos_lectura.id", ondelete="RESTRICT")
    )


class AIAnalysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint("owner_id", "target", "version", name="analyses_owner_id_target_version_key"),
        Index("ix_ai_analysis_owner", "owner_id", "target", text("version DESC")),
        Index("ix_ai_analysis_job", "job_id", postgresql_where=text("job_id IS NOT NULL")),
        Index(
            "ix_ai_analysis_reading_event",
            "reading_event_id",
            text("created_at DESC"),
            postgresql_where=text("reading_event_id IS NOT NULL"),
        ),
        {"schema": "ia"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app.usuarios.id", ondelete="CASCADE")
    )
    target: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    data_hash: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    valid: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    analytics_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analytics.projection_runs.id")
    )
    identity_version: Mapped[str | None] = mapped_column(Text, deferred=True, server_default=text("NULL"))
    provider: Mapped[str] = mapped_column(
        Text,
        default="gemini",
        server_default="gemini",
        comment="Historical rows predate remote providers and were produced exclusively by the Ollama flow.",
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ia.jobs.id", ondelete="SET NULL"))
    reading_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app.eventos_lectura.id", ondelete="RESTRICT")
    )


class AIEvidence(Base):
    __tablename__ = "evidence"
    __table_args__ = {"schema": "ia"}

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ia.analyses.id", ondelete="CASCADE"), primary_key=True
    )
    source_key: Mapped[str] = mapped_column(Text, primary_key=True)
    source_kind: Mapped[str] = mapped_column(Text)
    source_id: Mapped[uuid.UUID] = mapped_column()
    work_id: Mapped[uuid.UUID | None] = mapped_column()
    source_hash: Mapped[str] = mapped_column(Text)


class AIInterpretation(Base):
    __tablename__ = "interpretaciones_ia"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "subject_key",
            "data_hash",
            "provider",
            "model",
            "prompt_version",
            name="interpretaciones_ia_scope_subject_key_data_hash_provider_mo_key",
        ),
        CheckConstraint(
            "scope IN ('personal','group')",
            name="interpretaciones_ia_scope_check",
        ),
        CheckConstraint(
            "(scope='personal' AND owner_user_id IS NOT NULL AND subject_key=owner_user_id::text) "
            "OR (scope='group' AND owner_user_id IS NULL AND subject_key='group')",
            name="interpretaciones_ia_check",
        ),
        {"schema": "ia"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(Text)
    subject_key: Mapped[str] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.usuarios.id"))
    data_hash: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AIRecommendation(Base):
    __tablename__ = "recomendaciones_ia"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "data_hash",
            "model",
            "version",
            name="recomendaciones_ia_owner_user_id_data_hash_model_version_key",
        ),
        Index(
            "uq_ai_recommendation_profile_request",
            "owner_user_id",
            "profile_version_id",
            "provider",
            "model",
            "version",
            unique=True,
            postgresql_where=text("profile_version_id IS NOT NULL"),
        ),
        Index(
            "uq_ai_recommendation_job",
            "job_id",
            unique=True,
            postgresql_where=text("job_id IS NOT NULL"),
        ),
        Index(
            "ix_ai_recommendation_current",
            "owner_user_id",
            text("created_at DESC"),
            postgresql_where=text("is_current"),
        ),
        CheckConstraint(
            "(is_current AND invalidated_at IS NULL AND invalidated_by_etl_run_id IS NULL) "
            "OR (NOT is_current AND invalidated_at IS NOT NULL "
            "AND invalidated_by_etl_run_id IS NOT NULL)",
            name="ck_ai_recommendation_invalidation",
        ),
        {"schema": "ia"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id"))
    data_hash: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(
        "version",
        Text,
        comment="Prompt version; retained under its historical column name for compatibility.",
    )
    content: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    analytics_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analytics.projection_runs.id")
    )
    provider: Mapped[str] = mapped_column(
        Text,
        default="gemini",
        server_default="gemini",
        comment="Historical rows predate remote providers and were produced exclusively by the Ollama flow.",
    )
    profile_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ia.reader_profile_versions.id", ondelete="RESTRICT")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ia.jobs.id", ondelete="SET NULL"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_by_etl_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analytics.ejecuciones_etl.id", ondelete="RESTRICT")
    )


class AIUsageMetric(Base):
    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt", name="uq_ai_usage_job_attempt"),
        CheckConstraint("attempt > 0", name="usage_metrics_attempt_check"),
        CheckConstraint("input_tokens >= 0", name="usage_metrics_input_tokens_check"),
        CheckConstraint("output_tokens >= 0", name="usage_metrics_output_tokens_check"),
        CheckConstraint("reasoning_tokens >= 0", name="usage_metrics_reasoning_tokens_check"),
        CheckConstraint("cached_input_tokens >= 0", name="usage_metrics_cached_input_tokens_check"),
        CheckConstraint("request_count >= 0", name="usage_metrics_request_count_check"),
        CheckConstraint("context_fragments >= 0", name="usage_metrics_context_fragments_check"),
        CheckConstraint("duration_ms >= 0", name="usage_metrics_duration_ms_check"),
        CheckConstraint(
            "final_status IN ('succeeded', 'failed', 'cancelled')",
            name="usage_metrics_final_status_check",
        ),
        CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
            name="usage_metrics_estimated_cost_usd_check",
        ),
        Index("ix_ai_usage_provider_created", "provider", "model", text("created_at DESC")),
        {"schema": "ia"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ia.jobs.id", ondelete="RESTRICT"))
    attempt: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    context_fragments: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duration_ms: Mapped[int] = mapped_column(BigInteger)
    final_status: Mapped[str] = mapped_column(Text)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AICallLedger(Base):
    __tablename__ = 'call_ledger'
    __table_args__ = (UniqueConstraint('job_id','ordinal'), {'schema':'ia'})
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ia.jobs.id', ondelete='RESTRICT'))
    attempt: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger)
    reserved_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18,8))
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    reasoning_tokens: Mapped[int | None] = mapped_column(BigInteger)
    total_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cached_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    metadata_fields: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    measured_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18,8))
    request_id: Mapped[str | None] = mapped_column(Text)
    reconciliation_reference: Mapped[str | None] = mapped_column(Text)
    finish_reason: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('now()'))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReaderDna(Base):
    __tablename__ = 'reader_dna'
    __table_args__ = (UniqueConstraint('owner_id','source_hash','model','prompt_version'), {'schema':'ia'})
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ia.analyses.id', ondelete='RESTRICT'))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='CASCADE'))
    source_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ia.reader_profile_versions.id', ondelete='RESTRICT'))
    source_hash: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB)
    trace: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('now()'))


class ProviderCooldown(Base):
    __tablename__ = 'provider_cooldowns'
    __table_args__ = {'schema':'ia'}
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    until_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
