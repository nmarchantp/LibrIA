"""Historical phase-1 schema; retained for databases that already applied it.

The Influencer feature was reverted, but applied migration history must remain
resolvable. Keeping these additive structures preserves existing data and does
not enable any feature routes or permissions.
"""
from alembic import op
import sqlalchemy as sa

revision = '0091_influencer_phase1'
down_revision = '0090_story_views'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('solicitudes_verificacion', sa.Column('decision_reason', sa.Text(), nullable=True), schema='app')
    op.create_table('enlaces_perfil',
        sa.Column('profile_id', sa.Uuid(), sa.ForeignKey('app.perfiles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('platform', sa.String(20), primary_key=True),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.CheckConstraint("platform IN ('tiktok','instagram','x','facebook','pinterest','youtube','spotify','website')", name='ck_enlaces_plataforma'),
        schema='app')


def downgrade():
    op.drop_table('enlaces_perfil', schema='app')
    op.drop_column('solicitudes_verificacion', 'decision_reason', schema='app')
