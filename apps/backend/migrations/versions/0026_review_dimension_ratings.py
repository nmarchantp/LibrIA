"""Add expressive rating dimensions to reviews."""

from alembic import op

revision = "0026_review_dimension_ratings"
down_revision = "0025_physical_work_consolidation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE app.resenas
            ADD COLUMN dimension_ratings jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE app.revisiones_resena
            ADD COLUMN dimension_ratings jsonb NOT NULL DEFAULT '{}'::jsonb;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE app.revisiones_resena DROP COLUMN dimension_ratings;
        ALTER TABLE app.resenas DROP COLUMN dimension_ratings;
    """)
