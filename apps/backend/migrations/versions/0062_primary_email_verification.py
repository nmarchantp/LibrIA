"""Track explicit primary mailbox verification without trusting legacy addresses."""
from alembic import op
revision = "0062_primary_email_verification"
down_revision = "0061_account_management"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app.cuentas_autenticacion ADD COLUMN email_verified_at timestamptz")


def downgrade():
    raise RuntimeError("Keep mailbox verification history")
