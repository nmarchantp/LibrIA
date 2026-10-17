"""Internal lineage of aggregate releases without exposing reader identifiers."""
from alembic import op
revision='0039_release_provenance'
down_revision='0038_explicit_note_jobs'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''ALTER TABLE analytics.community_releases ADD COLUMN source_run_ids uuid[] NOT NULL DEFAULT '{}';
      ALTER TABLE analytics.peer_releases ADD COLUMN source_run_ids uuid[] NOT NULL DEFAULT '{}';''')


def downgrade():
    raise RuntimeError('Preserve release provenance')
