"""Allow the cat and books biography illustration."""
from alembic import op

revision = "0072_story_cat_illustration"
down_revision = "0071_story_illustration"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_story_illustration", "usuarios", schema="app", type_="check")
    op.create_check_constraint("ck_story_illustration", "usuarios", "story_illustration IN ('flowers', 'books', 'cat', 'none')", schema="app")


def downgrade():
    op.execute("UPDATE app.usuarios SET story_illustration = 'books' WHERE story_illustration = 'cat'")
    op.drop_constraint("ck_story_illustration", "usuarios", schema="app", type_="check")
    op.create_check_constraint("ck_story_illustration", "usuarios", "story_illustration IN ('flowers', 'books', 'none')", schema="app")
