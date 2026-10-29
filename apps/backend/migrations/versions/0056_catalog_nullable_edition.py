"""Prepare nullable edition storage without enabling editionless API commands."""
from alembic import op

revision = "0056_catalog_nullable_edition"
down_revision = "0055_catalog_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("ALTER TABLE app.lecturas ALTER COLUMN edition_id DROP NOT NULL")
    op.execute("ALTER TABLE analytics.hechos_lectura ALTER COLUMN edition_id DROP NOT NULL")


def downgrade():
    raise RuntimeError("Do not discard editionless history; use a reviewed forward migration")
