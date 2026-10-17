"""Keep model results in ia; retain compatible analytics read views."""
from alembic import op
revision='0034_inference_storage'
down_revision='0033_community_releases'
branch_labels=None
depends_on=None


def upgrade():
    for table in ('interpretaciones_ia','recomendaciones_ia'):
        op.execute(f'ALTER TABLE analytics.{table} SET SCHEMA ia')
        op.execute(f'CREATE VIEW analytics.{table} AS SELECT * FROM ia.{table}')
    op.execute('ALTER TABLE ia.recomendaciones_ia ADD COLUMN analytics_run_id uuid REFERENCES analytics.projection_runs(id)')


def downgrade():
    raise RuntimeError('Preserve inference history')
