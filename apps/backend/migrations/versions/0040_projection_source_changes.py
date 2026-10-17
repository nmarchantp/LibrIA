"""Only source changes invalidate analytics, never AI job status transitions."""
from alembic import op
revision='0040_projection_source_changes'
down_revision='0039_release_provenance'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('DROP TRIGGER projection_ai_dirty ON ia.jobs')
    for table in ('entradas_biblioteca','resenas'):
        op.execute(f'CREATE TRIGGER projection_business_dirty AFTER INSERT OR UPDATE OR DELETE ON app.{table} FOR EACH ROW EXECUTE FUNCTION analytics.social_dirty()')
    op.execute('INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios ON CONFLICT DO NOTHING')


def downgrade():
    raise RuntimeError('Preserve source-driven invalidation')
