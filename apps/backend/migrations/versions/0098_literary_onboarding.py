"""Progressive registration; existing accounts remain optional."""
from alembic import op
import sqlalchemy as sa

revision = '0098_literary_onboarding'
down_revision = '0097_literary_characters'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuarios', sa.Column('onboarding', sa.JSON(), nullable=False, server_default='{}'), schema='app')
    op.add_column('usuarios', sa.Column('visual_theme', sa.String(64)), schema='app')
    op.create_table('onboarding_favoritos',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('app.usuarios.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('work_id', sa.Uuid(), sa.ForeignKey('app.obras.id', ondelete='RESTRICT'), primary_key=True), schema='app')
    op.create_index('ix_app_onboarding_favoritos_work_id', 'onboarding_favoritos', ['work_id'], schema='app')
    op.execute("""ALTER TABLE ia.jobs DROP CONSTRAINT ck_ai_jobs_kind;
      ALTER TABLE ia.jobs ADD CONSTRAINT ck_ai_jobs_kind CHECK
        (job_kind IN ('adaptive_analysis','recommendation','reading_event_analysis','reader_profile','onboarding'));
      ALTER TABLE ia.jobs DROP CONSTRAINT ck_ai_jobs_context;
      ALTER TABLE ia.jobs ADD CONSTRAINT ck_ai_jobs_context CHECK
        ((job_kind IN ('adaptive_analysis','onboarding') AND profile_version_id IS NULL AND reading_event_id IS NULL)
         OR (job_kind IN ('recommendation','reader_profile') AND profile_version_id IS NOT NULL AND reading_event_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL)
         OR (job_kind='reading_event_analysis' AND reading_event_id IS NOT NULL AND profile_version_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL));""")


def downgrade():
    # Never discard completed preferences or queued jobs implicitly.
    raise RuntimeError('Restore a backup to reverse literary onboarding without losing user preferences')
