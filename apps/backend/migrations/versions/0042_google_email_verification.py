"""Verify email ownership before allowing a Google identity to be linked."""
from alembic import op
import sqlalchemy as sa

revision = "0042_google_email_verification"
down_revision = "0041_google_login"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("google_email", sa.String(320)),
        sa.Column("google_email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("google_email_code_hash", sa.String(64)),
        sa.Column("google_email_code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("google_email_code_sent_at", sa.DateTime(timezone=True)),
        sa.Column("google_email_code_attempts", sa.Integer(), nullable=False, server_default="0"),
    ):
        op.add_column("cuentas_autenticacion", column, schema="app")


def downgrade():
    for name in ("google_email_code_attempts", "google_email_code_sent_at", "google_email_code_expires_at",
                 "google_email_code_hash", "google_email_verified_at", "google_email"):
        op.drop_column("cuentas_autenticacion", name, schema="app")
