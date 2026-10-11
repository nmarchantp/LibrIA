"""Preserve public Google Books resources and search responses."""
from alembic import op

revision = "0020_catalog_mirror"
down_revision = "0019_ai_interpretations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app.fuentes_catalogo ADD COLUMN payload jsonb, ADD COLUMN detail_complete boolean NOT NULL DEFAULT false")
    op.execute("CREATE TABLE app.consultas_catalogo (query text PRIMARY KEY, payload jsonb NOT NULL, fetched_at timestamptz NOT NULL)")


def downgrade():
    op.drop_table("consultas_catalogo", schema="app")
    op.execute("ALTER TABLE app.fuentes_catalogo DROP COLUMN payload, DROP COLUMN detail_complete")
