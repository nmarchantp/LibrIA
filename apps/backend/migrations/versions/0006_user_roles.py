"""Guarda el tipo de cuenta de cada usuario."""

from alembic import op
import sqlalchemy as sa

revision = "0006_user_roles"
down_revision = "0005_post_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("role", sa.String(20), server_default="lector", nullable=False), schema="app")
    op.create_check_constraint(
        "ck_usuarios_role", "usuarios",
        "role IN ('lector', 'influencer', 'autor', 'libreria', 'admin')", schema="app",
    )


def downgrade() -> None:
    op.drop_constraint("ck_usuarios_role", "usuarios", schema="app", type_="check")
    op.drop_column("usuarios", "role", schema="app")
