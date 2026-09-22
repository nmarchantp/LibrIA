"""Permite comentar publicaciones, reseñas y avances."""

from alembic import op
import sqlalchemy as sa

revision = "0005_post_comments"
down_revision = "0004_social_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comentarios_publicacion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("app.publicaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 1000", name="ck_comentarios_publicacion_body"),
        schema="app",
    )
    op.create_index("ix_comentarios_publicacion_post_created", "comentarios_publicacion", ["post_id", "created_at"], schema="app")
    op.create_index("ix_app_comentarios_publicacion_user_id", "comentarios_publicacion", ["user_id"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_app_comentarios_publicacion_user_id", table_name="comentarios_publicacion", schema="app")
    op.drop_index("ix_comentarios_publicacion_post_created", table_name="comentarios_publicacion", schema="app")
    op.drop_table("comentarios_publicacion", schema="app")
