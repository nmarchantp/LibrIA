"""Invalidate in-flight OAuth intents when account credentials or access change."""
from alembic import op
revision = "0067_account_security_version"
down_revision = "0066_normalized_account_email"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app.cuentas_autenticacion ADD COLUMN security_version integer NOT NULL DEFAULT 0")


def downgrade():
    raise RuntimeError("Keep security invalidation generations")
