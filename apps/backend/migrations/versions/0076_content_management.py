"""Preserve publications on deletion and track comment edits without rewriting history."""
from alembic import op
import sqlalchemy as sa
revision = "0076_content_management"
down_revision = "0075_publication_book_cover"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('publicaciones', sa.Column('updated_at',sa.DateTime(timezone=True),nullable=True),schema='app')
    op.add_column('publicaciones', sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True),schema='app')
    op.add_column('comentarios_publicacion',sa.Column('edited_at',sa.DateTime(timezone=True),nullable=True),schema='app')


def downgrade():
    raise RuntimeError('La reversión debe conservar los marcadores de eliminación y edición.')
