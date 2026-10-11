"""Private self-reported reading experiences, prepared by the ETL."""
from alembic import op
revision = "0022_reading_reflections"
down_revision = "0021_ai_recommendations"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""ALTER TABLE app.eventos_lectura ADD COLUMN reflection jsonb,
        ADD CONSTRAINT ck_eventos_reflection CHECK (reflection IS NULL OR (kind='finish' AND jsonb_typeof(reflection)='object'));
        CREATE TABLE analytics.hechos_reflexiones (
        etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
        source_id uuid NOT NULL, user_id uuid NOT NULL, work_id uuid NOT NULL,
        occurred_at timestamptz NOT NULL, provenance text NOT NULL,
        reflection jsonb NOT NULL CHECK (jsonb_typeof(reflection)='object'),
        PRIMARY KEY (etl_run_id,source_id));
        CREATE INDEX ix_reflexiones_owner ON analytics.hechos_reflexiones(user_id,provenance,occurred_at);
        REVOKE ALL ON analytics.hechos_reflexiones FROM PUBLIC;""")

def downgrade():
    raise RuntimeError("Private reading reflections must be preserved")
