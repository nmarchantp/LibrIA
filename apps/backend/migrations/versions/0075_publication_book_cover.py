"""Add an optional publication-only cover, without changing catalog data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0075_publication_book_cover"
down_revision = "0074_reading_comment_words"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("portadas_publicacion",
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.publicaciones.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("revision", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False), schema="app")


def downgrade():
    raise RuntimeError("La reversión requiere conservar las portadas personalizadas existentes.")
