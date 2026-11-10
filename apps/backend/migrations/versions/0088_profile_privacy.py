"""Profile visibility, selected sections and follow notifications."""
from alembic import op
import sqlalchemy as sa

revision = '0088_profile_privacy'
down_revision = '0087_demo_mode'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuarios', sa.Column('profile_visibility', sa.String(16), nullable=False, server_default='public'), schema='app')
    op.add_column('usuarios', sa.Column('public_sections', sa.JSON(), nullable=False, server_default='["biography","genres","tropes","intensities","interests"]'), schema='app')
    op.create_check_constraint('ck_users_profile_visibility', 'usuarios', "profile_visibility IN ('public','private')", schema='app')
    op.create_table('notificaciones_seguimiento',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('recipient_user_id', sa.Uuid(), sa.ForeignKey('app.usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_user_id', sa.Uuid(), sa.ForeignKey('app.usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('recipient_user_id', 'actor_user_id', name='uq_follow_notification_pair'), schema='app')
    op.create_index('ix_follow_notifications_recipient', 'notificaciones_seguimiento', ['recipient_user_id', 'created_at'], schema='app')


def downgrade():
    raise RuntimeError('Preserva las preferencias de privacidad y notificaciones antes de retirar esta función.')
