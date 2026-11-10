"""24 hour profile stories."""
from alembic import op
import sqlalchemy as sa

revision = '0089_user_stories'
down_revision = '0088_profile_privacy'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('historias',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('profile_id', sa.Uuid(), sa.ForeignKey('app.perfiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), schema='app')
    op.create_index('ix_historias_profile_expiry', 'historias', ['profile_id', 'expires_at'], schema='app')
    op.create_index('ix_app_historias_expires_at', 'historias', ['expires_at'], schema='app')


def downgrade():
    op.drop_table('historias', schema='app')
