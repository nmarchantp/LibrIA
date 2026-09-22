"""Relaciona reseñas y avances del feed con libros."""

from alembic import op
import sqlalchemy as sa

revision = "0007_post_book_context"
down_revision = "0006_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("book_ref", sa.String(200)),
        sa.Column("book_title", sa.String(200)),
        sa.Column("rating", sa.Integer()),
        sa.Column("progress_percent", sa.Integer()),
        sa.Column("reading_event", sa.String(20)),
    ):
        op.add_column("publicaciones", column, schema="app")
    op.create_check_constraint("ck_publicaciones_rating", "publicaciones", "rating IS NULL OR rating BETWEEN 1 AND 5", schema="app")
    op.create_check_constraint("ck_publicaciones_progress", "publicaciones", "progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100", schema="app")
    op.create_check_constraint("ck_publicaciones_reading_event", "publicaciones", "reading_event IS NULL OR reading_event IN ('start', 'progress', 'finish', 'abandon')", schema="app")
    op.create_index("ix_publicaciones_book_ref", "publicaciones", ["book_ref"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_publicaciones_book_ref", table_name="publicaciones", schema="app")
    for name in ("ck_publicaciones_reading_event", "ck_publicaciones_progress", "ck_publicaciones_rating"):
        op.drop_constraint(name, "publicaciones", schema="app", type_="check")
    for name in ("reading_event", "progress_percent", "rating", "book_title", "book_ref"):
        op.drop_column("publicaciones", name, schema="app")
