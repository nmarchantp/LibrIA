"""Private-by-default personal event agendas; existing attendance is unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '0080_profile_events_privacy'
down_revision = '0079_event_representative_image'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuarios', sa.Column('events_visibility', sa.String(16), nullable=False, server_default='private'), schema='app')
    op.create_check_constraint('ck_users_events_visibility', 'usuarios', "events_visibility IN ('private','contacts','public')", schema='app')
    op.create_index('ix_attendance_user_active_event', 'asistencias_evento', ['user_id', 'post_id'], schema='app', postgresql_where=sa.text('attending = true'))


def downgrade():
    raise RuntimeError('Preserva las preferencias de privacidad antes de retirar esta función.')
