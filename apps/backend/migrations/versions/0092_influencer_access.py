"""Structured influencer applications and temporary publishing restrictions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0092_influencer_access'
down_revision = '0091_influencer_phase1'
branch_labels = None
depends_on = None


def upgrade():
    for name, datatype in [('activity_description', sa.Text()), ('topics', JSONB()),
                           ('motivation', sa.Text()), ('evidence_links', JSONB())]:
        op.add_column('solicitudes_verificacion', sa.Column(name, datatype, nullable=True), schema='app')
    op.add_column('usuarios', sa.Column('influencer_suspended_until', sa.DateTime(timezone=True), nullable=True), schema='app')


def downgrade():
    op.drop_column('usuarios', 'influencer_suspended_until', schema='app')
    for name in ('evidence_links', 'motivation', 'topics', 'activity_description'):
        op.drop_column('solicitudes_verificacion', name, schema='app')
