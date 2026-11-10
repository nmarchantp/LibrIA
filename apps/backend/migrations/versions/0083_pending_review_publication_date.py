"""Allow an unpublished moderated review without confusing its editorial status."""
from alembic import op

revision = '0083_pending_review_date'
down_revision = '0082_moderation_foundation'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_resenas_publicacion','resenas',schema='app',type_='check')
    op.create_check_constraint('ck_resenas_publicacion','resenas',
        "(status='draft' AND published_at IS NULL) OR "
        "(status='published' AND ((published_at IS NOT NULL AND published_at>=created_at) "
        "OR (moderation_status IN ('pending_review','rejected') AND published_at IS NULL))) OR "
        "(status='hidden' AND (published_at IS NULL OR published_at>=created_at))",schema='app')


def downgrade():
    raise RuntimeError('Preserva las reseñas pendientes sin fecha pública antes de revertir esta restricción.')
