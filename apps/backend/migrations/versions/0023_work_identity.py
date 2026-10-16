"""Canonical work identity shared by alternate editions."""
from alembic import op

revision = "0023_work_identity"
down_revision = "0022_reading_reflections"
branch_labels = None
depends_on = None


def upgrade():
    # Existing development data may be discarded. Null keeps this migration safe
    # until catalog records are recreated through the canonical importer.
    op.execute("""ALTER TABLE app.obras ADD COLUMN identity_key text;
        CREATE UNIQUE INDEX ix_obras_identity_key ON app.obras(identity_key)
        WHERE identity_key IS NOT NULL;""")


def downgrade():
    op.execute("DROP INDEX app.ix_obras_identity_key; ALTER TABLE app.obras DROP COLUMN identity_key;")
