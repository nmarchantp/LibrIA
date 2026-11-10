"""Per-viewer story read state."""
from alembic import op
import sqlalchemy as sa

revision = '0090_story_views'
down_revision = '0089_user_stories'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('historias_vistas',
        sa.Column('story_id', sa.Uuid(), sa.ForeignKey('app.historias.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('app.usuarios.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('viewed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema='app')


def downgrade():
    op.drop_table('historias_vistas', schema='app')
