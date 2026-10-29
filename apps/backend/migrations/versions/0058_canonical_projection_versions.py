"""Add identity provenance and transactional dirty markers, without data rewrites."""
from alembic import op

revision = "0058_canonical_versions"
down_revision = "0057_reading_optional_progress"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    for table in ("analytics.projection_runs", "analytics.ejecuciones_etl", "ia.reader_profile_versions", "ia.analyses"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN identity_version text")
    op.execute("""
      CREATE FUNCTION analytics.mark_canonical_identity_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios ON CONFLICT DO NOTHING;
        INSERT INTO analytics.dirty_catalog(work_id) SELECT id FROM app.obras ON CONFLICT DO NOTHING;
        RETURN NEW;
      END $$;
      CREATE TRIGGER trg_canonical_identity_dirty AFTER INSERT OR UPDATE ON app.redirecciones_obras
        FOR EACH STATEMENT EXECUTE FUNCTION analytics.mark_canonical_identity_dirty();
    """)


def downgrade():
    raise RuntimeError("Keep identity provenance; use a reviewed forward migration")
