"""Retain the exact before/after context of administrative decisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0085_moderation_audit_context'
down_revision='0084_moderation_reports'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('auditoria_moderacion',sa.Column('context',postgresql.JSONB(),nullable=False,server_default='{}'),schema='app')
    op.create_check_constraint('ck_mod_audit_context','auditoria_moderacion',"jsonb_typeof(context)='object'",schema='app')


def downgrade():
    raise RuntimeError('El contexto de decisiones es evidencia inmutable; no se elimina automáticamente.')
