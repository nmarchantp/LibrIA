"""Registra revocaciones de permisos en el mantenedor de perfiles."""

from alembic import op
import sqlalchemy as sa

revision = "0009_profile_role_changes"
down_revision = "0008_verification_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publicaciones", sa.Column("author_role", sa.String(20), nullable=True), schema="app")
    op.execute("UPDATE app.publicaciones AS post SET author_role = users.role FROM app.usuarios AS users WHERE post.user_id = users.id")
    op.alter_column("publicaciones", "author_role", nullable=False, schema="app")
    op.create_table(
        "cambios_rol_perfil",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("admin_user_id", sa.Uuid(), sa.ForeignKey("app.usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_role", sa.String(20), nullable=False),
        sa.Column("new_role", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="app",
    )
    op.create_index("ix_cambios_rol_perfil_user_id", "cambios_rol_perfil", ["user_id"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_cambios_rol_perfil_user_id", table_name="cambios_rol_perfil", schema="app")
    op.drop_table("cambios_rol_perfil", schema="app")
    op.drop_column("publicaciones", "author_role", schema="app")
