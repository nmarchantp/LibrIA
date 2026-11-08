"""Allow hiding a never-published draft without inventing a publication date."""
from alembic import op
revision='0077_hide_draft_reviews'
down_revision='0076_content_management'
branch_labels=None
depends_on=None


def upgrade():
    op.drop_constraint('ck_resenas_publicacion','resenas',schema='app',type_='check')
    op.create_check_constraint('ck_resenas_publicacion','resenas',"(status='draft' AND published_at IS NULL) OR (status='published' AND published_at IS NOT NULL AND published_at>=created_at) OR (status='hidden' AND (published_at IS NULL OR published_at>=created_at))",schema='app')


def downgrade():
    raise RuntimeError('Se deben conservar los borradores ocultos sin inventar fechas de publicación.')
