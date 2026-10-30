"""Enforce the same case-insensitive uniqueness used by account services."""
from alembic import op
revision = "0066_normalized_account_email"
down_revision = "0065_account_audit_redaction"
branch_labels = None
depends_on = None


def upgrade():
    # Fail atomically rather than merge/delete accounts if legacy data conflicts.
    op.execute("CREATE UNIQUE INDEX uq_auth_email_normalized ON app.cuentas_autenticacion(lower(email))")


def downgrade():
    op.execute("DROP INDEX app.uq_auth_email_normalized")
