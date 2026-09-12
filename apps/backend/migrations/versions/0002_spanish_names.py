"""Renombra las tablas existentes sin eliminar usuarios ni credenciales."""

from alembic import op

revision = "0002_spanish_names"
down_revision = "0001_auth_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("users", "usuarios", schema="app")
    op.rename_table("auth_accounts", "cuentas_autenticacion", schema="app")
    op.execute("ALTER INDEX app.ix_auth_accounts_email RENAME TO ix_app_cuentas_autenticacion_email")


def downgrade() -> None:
    op.execute("ALTER INDEX app.ix_app_cuentas_autenticacion_email RENAME TO ix_auth_accounts_email")
    op.rename_table("cuentas_autenticacion", "auth_accounts", schema="app")
    op.rename_table("usuarios", "users", schema="app")
