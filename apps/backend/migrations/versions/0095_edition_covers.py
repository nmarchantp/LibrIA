"""Store uploaded catalog edition covers."""
from alembic import op
import sqlalchemy as sa

revision = '0095_edition_covers'
down_revision = '0094_role_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('portadas_ediciones',
        sa.Column('edition_id', sa.Uuid(), sa.ForeignKey('app.ediciones.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False), schema='app')


def downgrade():
    op.drop_table('portadas_ediciones', schema='app')
