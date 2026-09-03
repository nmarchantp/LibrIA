"""Crea schemas y tablas iniciales de usuarios y autenticación."""

from alembic import op
import sqlalchemy as sa

revision = "0001_auth_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai")
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("display_name", sa.String(100), nullable=False), sa.Column("avatar_url", sa.String(500)), sa.Column("biography", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), schema="app")
    op.create_table("auth_accounts", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("email", sa.String(320), nullable=False, unique=True), sa.Column("password_hash", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), schema="app")
    op.create_index("ix_auth_accounts_email", "auth_accounts", ["email"], unique=True, schema="app")


def downgrade() -> None:
    op.drop_table("auth_accounts", schema="app")
    op.drop_table("users", schema="app")
    op.execute("DROP SCHEMA IF EXISTS ai")
    op.execute("DROP SCHEMA IF EXISTS analytics")
    op.execute("DROP SCHEMA IF EXISTS app")
