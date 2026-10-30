"""Reject incomplete deletion timestamps, including PostgreSQL CHECK null cases."""
from alembic import op
revision = "0068_account_state_integrity"
down_revision = "0067_account_security_version"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE app.usuarios DROP CONSTRAINT ck_deletion_dates;
      ALTER TABLE app.usuarios ADD CONSTRAINT ck_deletion_dates CHECK(
        (account_status='pending_deletion' AND deletion_requested_at IS NOT NULL AND
         deletion_scheduled_at IS NOT NULL AND deletion_scheduled_at=deletion_requested_at + interval '720 hours') OR
        (account_status<>'pending_deletion' AND deletion_requested_at IS NULL AND deletion_scheduled_at IS NULL));
      ALTER TABLE app.usuarios ADD CONSTRAINT ck_anonymized_date CHECK(
        (account_status='anonymized')=(anonymized_at IS NOT NULL));
    """)


def downgrade():
    raise RuntimeError("Keep account lifecycle integrity checks")
