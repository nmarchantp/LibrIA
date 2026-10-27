"""One optional featured taste per account, on its existing selected category."""
from alembic import op
import sqlalchemy as sa

revision = "0047_featured_reading_taste"
down_revision = "0046_reading_tastes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gustos_intensidades", sa.Column("featured", sa.Boolean(), nullable=False,
                                                 server_default=sa.false()), schema="app")
    op.create_index("uq_gustos_intensidades_featured", "gustos_intensidades", ["user_id"],
                    unique=True, schema="app", postgresql_where=sa.text("featured"))


def downgrade():
    op.drop_index("uq_gustos_intensidades_featured", table_name="gustos_intensidades", schema="app")
    op.drop_column("gustos_intensidades", "featured", schema="app")
