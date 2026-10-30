"""Keep legacy seed/import inserts compatible with the immutable username column."""
from alembic import op
revision = "0064_account_insert_default"
down_revision = "0063_exclusive_account_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE app.usuarios ALTER COLUMN username
      SET DEFAULT ('reader_' || replace(gen_random_uuid()::text, '-', ''))""")


def downgrade():
    op.execute("ALTER TABLE app.usuarios ALTER COLUMN username DROP DEFAULT")
