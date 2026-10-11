"""Identify on-demand snapshots separately from daily closures."""
from alembic import op

revision = "0018_manual_etl"
down_revision = "0017_review_analytics"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE analytics.ejecuciones_etl
            ADD COLUMN run_kind text NOT NULL DEFAULT 'daily',
            ADD COLUMN requested_by uuid REFERENCES app.usuarios(id),
            ADD COLUMN phase text NOT NULL DEFAULT 'queued';
        UPDATE analytics.ejecuciones_etl SET run_kind='legacy' WHERE business_date IS NULL;
        UPDATE analytics.ejecuciones_etl SET phase=CASE
            WHEN status='succeeded' THEN 'completed' WHEN status='failed' THEN 'failed' ELSE 'queued' END;
        ALTER TABLE analytics.ejecuciones_etl ADD CONSTRAINT ck_etl_run_kind
            CHECK (run_kind IN ('daily', 'manual', 'legacy'));
        ALTER TABLE analytics.ejecuciones_etl ADD CONSTRAINT ck_etl_manual_identity
            CHECK (run_kind <> 'manual' OR (business_date IS NULL AND requested_by IS NOT NULL AND period_start IS NOT NULL));
    """)


def downgrade():
    raise RuntimeError("Manual ETL history must be preserved.")
