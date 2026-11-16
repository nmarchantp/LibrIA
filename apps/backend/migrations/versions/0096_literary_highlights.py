"""Personal literary crush and essential books."""
from alembic import op
import sqlalchemy as sa

revision = '0096_literary_highlights'
down_revision = '0095_edition_covers'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuarios', sa.Column('literary_highlights', sa.JSON(), nullable=False, server_default='{}'), schema='app')


def downgrade():
    op.drop_column('usuarios', 'literary_highlights', schema='app')
