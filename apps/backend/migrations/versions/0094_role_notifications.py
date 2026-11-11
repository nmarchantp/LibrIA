"""Persist application/decision notices, including already recorded requests."""
from alembic import op
import sqlalchemy as sa

revision = '0094_role_notifications'
down_revision = '0093_editorial_account'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notificaciones_perfil',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('request_id', sa.Uuid(), sa.ForeignKey('app.solicitudes_verificacion.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_user_id', sa.Uuid(), sa.ForeignKey('app.usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('request_id', 'recipient_user_id', 'kind', name='uq_notificacion_perfil_evento'),
        sa.CheckConstraint("kind IN ('requested','approved','rejected')", name='ck_notificacion_perfil_kind'), schema='app')
    op.create_index('ix_notificacion_perfil_destinatario', 'notificaciones_perfil', ['recipient_user_id', 'read_at'], schema='app')
    op.execute("""INSERT INTO app.notificaciones_perfil(id,request_id,recipient_user_id,kind,created_at)
        SELECT gen_random_uuid(),r.id,p.user_id,'requested',r.created_at
        FROM app.solicitudes_verificacion r CROSS JOIN app.permisos_cuenta p
        JOIN app.usuarios u ON u.id=p.user_id
        WHERE r.status='pending' AND p.permission='admin' AND u.account_status='active'
        AND u.suspended_at IS NULL AND p.user_id<>r.user_id""")
    op.execute("""INSERT INTO app.notificaciones_perfil(id,request_id,recipient_user_id,kind,created_at)
        SELECT gen_random_uuid(),id,user_id,status,decided_at FROM app.solicitudes_verificacion
        WHERE status IN ('approved','rejected') AND decided_at IS NOT NULL""")


def downgrade():
    op.drop_table('notificaciones_perfil', schema='app')
