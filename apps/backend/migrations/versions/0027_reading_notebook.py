"""Store the private notebook attached to a reading."""

from alembic import op

revision = "0027_reading_notebook"
down_revision = "0026_review_dimension_ratings"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE app.lecturas
            ADD COLUMN notebook jsonb NOT NULL DEFAULT '{}'::jsonb;
    """)


def downgrade():
    op.execute("ALTER TABLE app.lecturas DROP COLUMN notebook;")
