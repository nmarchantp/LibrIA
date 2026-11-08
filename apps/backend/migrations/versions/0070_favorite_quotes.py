"""Store up to four favorite quotes on the reader account."""
from alembic import op
import sqlalchemy as sa

revision = "0070_favorite_quotes"
down_revision = "0069_nightly_book_analysis"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("favorite_quotes", sa.JSON(), nullable=False, server_default="[]"), schema="app")


def downgrade():
    op.drop_column("usuarios", "favorite_quotes", schema="app")
