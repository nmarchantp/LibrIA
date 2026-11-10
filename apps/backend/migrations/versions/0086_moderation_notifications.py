"""Private moderation inbox; no backfill or simulated historical notifications."""
from alembic import op

revision='0086_moderation_notifications'
down_revision='0085_moderation_audit_context'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""CREATE TABLE app.notificaciones_moderacion (
      id uuid PRIMARY KEY,
      recipient_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      revision_id uuid NOT NULL REFERENCES app.revisiones_moderacion(id) ON DELETE RESTRICT,
      kind varchar(16) NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), read_at timestamptz,
      CONSTRAINT ck_mod_notification_kind CHECK (kind IN ('pending_review','approved','rejected'))
    )""")
    op.create_index('uq_mod_notification_event','notificaciones_moderacion',['recipient_user_id','revision_id','kind'],unique=True,schema='app')
    op.create_index('ix_mod_notification_inbox','notificaciones_moderacion',['recipient_user_id','created_at','id'],schema='app')


def downgrade():
    raise RuntimeError('Preserva las notificaciones privadas antes de revertir la migración.')
