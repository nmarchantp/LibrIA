"""Daily anonymous collaborative discovery releases."""
from alembic import op
revision='0036_peer_discovery'
down_revision='0035_publication_catalog_links'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE TABLE analytics.peer_releases (
      owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
      release_date date NOT NULL,payload jsonb NOT NULL,processed_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(owner_id,release_date));''')


def downgrade():
    raise RuntimeError('Preserve privacy releases')
