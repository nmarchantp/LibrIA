"""Associate a stable Google identity with an existing authentication account."""
from alembic import op
import sqlalchemy as sa

revision = "0041_google_login"
down_revision = "0040_projection_source_changes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cuentas_autenticacion", sa.Column("google_subject", sa.String(255), nullable=True), schema="app")
    op.create_unique_constraint("uq_auth_google_subject", "cuentas_autenticacion", ["google_subject"], schema="app")


def downgrade():
    op.drop_constraint("uq_auth_google_subject", "cuentas_autenticacion", schema="app")
    op.drop_column("cuentas_autenticacion", "google_subject", schema="app")
