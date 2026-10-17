"""Owner-only snapshots of reader-authored book evidence."""
from alembic import op

revision = "0028_personal_reading_evidence"
down_revision = "0027_reading_notebook"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE analytics.evidencia_lectora_personal (
        etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
        user_id uuid NOT NULL, work_id uuid NOT NULL, source_id uuid NOT NULL,
        source_kind text NOT NULL CHECK (source_kind IN ('notebook','review','note','theory')),
        source_at timestamptz NOT NULL,
        provenance text NOT NULL CHECK (provenance IN ('unclassified','operational')),
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
        PRIMARY KEY (etl_run_id, source_kind, source_id));
        CREATE INDEX ix_evidencia_lectora_owner ON
            analytics.evidencia_lectora_personal(user_id, etl_run_id, provenance);
        REVOKE ALL ON analytics.evidencia_lectora_personal FROM PUBLIC;""")


def downgrade():
    op.drop_table("evidencia_lectora_personal", schema="analytics")
