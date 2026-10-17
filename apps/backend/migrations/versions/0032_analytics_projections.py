"""Incremental ETL projections, social facts and inference provenance."""
from alembic import op
revision='0032_analytics_projections'
down_revision='0031_profile_deadline'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''
    CREATE TABLE analytics.projection_runs (
      id uuid PRIMARY KEY, owner_id uuid REFERENCES app.usuarios(id) ON DELETE CASCADE,
      source_cutoff_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz NOT NULL DEFAULT now(),
      transform_version text NOT NULL, source_hash text NOT NULL, payload jsonb NOT NULL);
    CREATE TABLE analytics.reader_current (
      owner_id uuid PRIMARY KEY REFERENCES app.usuarios(id) ON DELETE CASCADE,
      run_id uuid NOT NULL REFERENCES analytics.projection_runs(id));
    CREATE TABLE analytics.dirty_readers (
      owner_id uuid PRIMARY KEY REFERENCES app.usuarios(id) ON DELETE CASCADE,
      changed_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE analytics.catalog_current (
      work_id uuid PRIMARY KEY, processed_at timestamptz NOT NULL DEFAULT now(), payload jsonb NOT NULL);
    CREATE TABLE analytics.dirty_catalog (work_id uuid PRIMARY KEY);
    ALTER TABLE ia.analyses ADD COLUMN analytics_run_id uuid REFERENCES analytics.projection_runs(id);
    CREATE INDEX ix_projection_owner_date ON analytics.projection_runs(owner_id,processed_at DESC);
    CREATE FUNCTION analytics.mark_reader(p_owner uuid) RETURNS void LANGUAGE plpgsql AS $$
    BEGIN
      IF p_owner IS NOT NULL THEN
        INSERT INTO analytics.dirty_readers(owner_id) VALUES(p_owner)
          ON CONFLICT(owner_id) DO UPDATE SET changed_at=clock_timestamp();
      END IF;
    END $$;
    CREATE FUNCTION analytics.ai_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN PERFORM analytics.mark_reader(NEW.owner_id); RETURN NEW; END $$;
    CREATE TRIGGER projection_ai_dirty AFTER INSERT OR UPDATE ON ia.jobs
      FOR EACH ROW EXECUTE FUNCTION analytics.ai_dirty();
    CREATE FUNCTION analytics.social_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE rec jsonb;
    BEGIN
      rec=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
      PERFORM analytics.mark_reader((rec->>'user_id')::uuid);
      RETURN NULL;
    END $$;
    CREATE TRIGGER projection_feedback_dirty AFTER INSERT OR UPDATE OR DELETE ON ia.feedback
      FOR EACH ROW EXECUTE FUNCTION analytics.ai_dirty();
    ''')
    # Feedback deletion requires OLD; use a dedicated generic ownership trigger.
    op.execute('''
    CREATE OR REPLACE FUNCTION analytics.ai_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN PERFORM analytics.mark_reader(CASE WHEN TG_OP='DELETE' THEN OLD.owner_id ELSE NEW.owner_id END); RETURN NULL; END $$;
    ''')
    for table in ('seguimientos_perfil','comentarios_publicacion','me_gusta_publicacion','me_gusta_resena'):
        op.execute(f'CREATE TRIGGER projection_social_dirty AFTER INSERT OR UPDATE OR DELETE ON app.{table} FOR EACH ROW EXECUTE FUNCTION analytics.social_dirty()')
    op.execute('''
    CREATE FUNCTION analytics.catalog_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE rec jsonb; wid uuid;
    BEGIN
      rec=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
      IF TG_TABLE_NAME='obras' THEN wid=(rec->>'id')::uuid;
      ELSIF TG_TABLE_NAME='fuentes_catalogo' THEN SELECT work_id INTO wid FROM app.ediciones WHERE id=(rec->>'edition_id')::uuid;
      ELSE wid=(rec->>'work_id')::uuid; END IF;
      IF wid IS NOT NULL THEN
        INSERT INTO analytics.dirty_catalog VALUES(wid) ON CONFLICT DO NOTHING;
        INSERT INTO analytics.dirty_readers(owner_id) SELECT user_id FROM app.entradas_biblioteca WHERE work_id=wid GROUP BY user_id
          ON CONFLICT(owner_id) DO UPDATE SET changed_at=clock_timestamp();
      END IF;
      RETURN NULL;
    END $$;
    ''')
    for table in ('obras','ediciones','fuentes_catalogo','obras_autores'):
        op.execute(f'CREATE TRIGGER projection_catalog_dirty AFTER INSERT OR UPDATE OR DELETE ON app.{table} FOR EACH ROW EXECUTE FUNCTION analytics.catalog_dirty()')
    op.execute('''INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios;
      INSERT INTO analytics.dirty_catalog(work_id) SELECT id FROM app.obras;''')


def downgrade():
    raise RuntimeError('Preserve analytical provenance; use a forward migration')
