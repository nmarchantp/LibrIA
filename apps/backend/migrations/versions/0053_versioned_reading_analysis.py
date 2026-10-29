"""Allow versioned Gemini analysis for one terminal reading event.

Revision ID: 0053_versioned_reading_analysis
Revises: 0052_ai_usage_calls
"""

from alembic import op


revision = "0053_versioned_reading_analysis"
down_revision = "0052_ai_usage_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ia.uq_ai_job_reading_event_request;
        CREATE UNIQUE INDEX uq_ai_job_reading_event_request
          ON ia.jobs(reading_event_id, provider, model, prompt_version)
          WHERE job_kind = 'reading_event_analysis';

        DROP INDEX IF EXISTS ia.uq_ai_analysis_reading_event;
        CREATE INDEX ix_ai_analysis_reading_event
          ON ia.analyses(reading_event_id, created_at DESC)
          WHERE reading_event_id IS NOT NULL;

        COMMENT ON INDEX ia.uq_ai_job_reading_event_request IS
          'One durable request per terminal event and versioned Gemini contract.';
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Versioned reading analyses may contain multiple rows per event; "
        "restore the former uniqueness only through a reviewed forward migration."
    )
