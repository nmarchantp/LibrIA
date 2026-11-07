"""Reader-selected decoration for the biography card."""
from alembic import op
import sqlalchemy as sa

revision = "0071_story_illustration"
down_revision = "0070_favorite_quotes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("story_illustration", sa.String(16), nullable=False, server_default="flowers"), schema="app")
    op.create_check_constraint("ck_story_illustration", "usuarios", "story_illustration IN ('flowers', 'books', 'none')", schema="app")


def downgrade():
    op.drop_constraint("ck_story_illustration", "usuarios", schema="app", type_="check")
    op.drop_column("usuarios", "story_illustration", schema="app")
