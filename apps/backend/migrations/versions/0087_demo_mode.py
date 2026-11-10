"""Persistent administrator switch for simulated demonstration activity."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0087_demo_mode'
down_revision = '0086_moderation_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('modo_demo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('interval_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('catalog_edition_ids', JSONB(), nullable=False, server_default='[]'),
        sa.Column('last_run_at', sa.DateTime(timezone=True)),
        sa.Column('last_error', sa.String(300)),
        sa.Column('updated_by', sa.Uuid(), sa.ForeignKey('app.usuarios.id', ondelete='RESTRICT')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('id = 1', name='ck_demo_singleton'),
        sa.CheckConstraint('interval_seconds BETWEEN 10 AND 3600', name='ck_demo_interval'), schema='app')
    op.execute('INSERT INTO app.modo_demo (id) VALUES (1)')


def downgrade():
    raise RuntimeError('Conserva la configuración y la actividad demo antes de revertir.')
