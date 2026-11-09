"""Annual targets, separate from authoritative reading records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = '0081_annual_reading_challenge'
down_revision = '0080_profile_events_privacy'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('retos_lectura',
        sa.Column('user_id', pg.UUID(as_uuid=True), sa.ForeignKey('app.usuarios.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('target', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'year'),
        sa.CheckConstraint('target BETWEEN 1 AND 1000', name='ck_reading_challenge_target'),
        sa.CheckConstraint('year BETWEEN 1900 AND 9999', name='ck_reading_challenge_year'), schema='app')


def downgrade():
    raise RuntimeError('Exporta y conserva las metas históricas antes de retirar esta tabla.')
