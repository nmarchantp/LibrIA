"""Professional verification supports bookstore accounts, without converting organizations."""
from alembic import op
revision = "0063_exclusive_account_roles"
down_revision = "0062_primary_email_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE app.solicitudes_verificacion DROP CONSTRAINT ck_solicitudes_verificacion_role;
      ALTER TABLE app.solicitudes_verificacion ADD CONSTRAINT ck_solicitudes_verificacion_role
        CHECK(requested_role IN ('influencer','autor','libreria'));
    """)


def downgrade():
    raise RuntimeError("Retain approved bookstore verification records")
