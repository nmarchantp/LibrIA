"""Prepare unknown reading totals and explicit, auditable edition selection.

No data rewrites. Existing work/edition/library foreign keys are retained.
"""
from alembic import op

revision = "0057_reading_optional_progress"
down_revision = "0056_catalog_nullable_edition"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("""
        ALTER TABLE app.lecturas DROP CONSTRAINT ck_lecturas_started;
        ALTER TABLE app.lecturas ADD CONSTRAINT ck_lecturas_started CHECK (
          (status='pending' AND current_page=0 AND started_at IS NULL)
          OR (status<>'pending' AND started_at IS NOT NULL));
        ALTER TABLE app.lecturas DROP CONSTRAINT ck_lecturas_finished;
        ALTER TABLE app.lecturas ADD CONSTRAINT ck_lecturas_finished CHECK (
          (status='finished' AND finished_at IS NOT NULL AND finished_at>=started_at
            AND (total_pages IS NULL OR current_page=total_pages))
          OR (status<>'finished' AND finished_at IS NULL));
        ALTER TABLE app.eventos_lectura ALTER COLUMN total_pages DROP NOT NULL;
        ALTER TABLE analytics.hechos_lectura ALTER COLUMN total_pages DROP NOT NULL;
        ALTER TABLE app.lecturas ADD CONSTRAINT uq_lecturas_id_work UNIQUE(id,work_id);
        CREATE TABLE app.selecciones_edicion_lectura (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          created_at timestamptz NOT NULL DEFAULT now(),
          reading_id uuid NOT NULL REFERENCES app.lecturas(id) ON DELETE RESTRICT,
          actor_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
          work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
          edition_id uuid NOT NULL,
          before_state jsonb NOT NULL,
          after_state jsonb NOT NULL,
          FOREIGN KEY(edition_id,work_id) REFERENCES app.ediciones(id,work_id) ON DELETE RESTRICT,
          FOREIGN KEY(reading_id,work_id) REFERENCES app.lecturas(id,work_id) ON DELETE RESTRICT,
          UNIQUE(reading_id),
          CHECK(jsonb_typeof(before_state)='object' AND jsonb_typeof(after_state)='object')
        );
        CREATE INDEX ix_seleccion_edicion_actor ON app.selecciones_edicion_lectura(actor_user_id,created_at);
        CREATE FUNCTION app.protect_reading_edition_selection() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Reading edition selection audit is append-only'; END $$;
        CREATE TRIGGER trg_reading_edition_selection_immutable BEFORE UPDATE OR DELETE
          ON app.selecciones_edicion_lectura FOR EACH ROW EXECUTE FUNCTION app.protect_reading_edition_selection();
    """)


def downgrade():
    raise RuntimeError("Preserve editionless reading history; use a reviewed forward migration")
