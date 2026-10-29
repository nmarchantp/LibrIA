"""Account for provider calls and context fragments per AI attempt.

Revision ID: 0052_ai_usage_calls
Revises: 0051_sessions_controlled_ai
"""
from alembic import op

revision = "0052_ai_usage_calls"
down_revision = "0051_sessions_controlled_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ia.usage_metrics
          ADD COLUMN request_count integer NOT NULL DEFAULT 0
            CHECK (request_count >= 0),
          ADD COLUMN context_fragments integer NOT NULL DEFAULT 0
            CHECK (context_fragments >= 0);
        ALTER TABLE ia.jobs ALTER COLUMN provider SET DEFAULT 'gemini';
        ALTER TABLE ia.analyses ALTER COLUMN provider SET DEFAULT 'gemini';
        ALTER TABLE ia.recomendaciones_ia ALTER COLUMN provider SET DEFAULT 'gemini';
        COMMENT ON COLUMN ia.usage_metrics.request_count IS
          'Provider calls made by one durable job attempt.';
        COMMENT ON COLUMN ia.usage_metrics.context_fragments IS
          'Initial and reduction fragments processed during the attempt.';
        """
    )


def downgrade() -> None:
    raise RuntimeError("AI usage accounting is audit data and requires a reviewed forward migration")
