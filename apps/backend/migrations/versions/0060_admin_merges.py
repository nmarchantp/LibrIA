"""Confirmed review decisions and a database-enforced writer barrier."""
from alembic import op

revision='0060_admin_merges'
down_revision='0059_merge_previews'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""
      ALTER TABLE app.simulaciones_fusion DROP CONSTRAINT simulaciones_fusion_version_check;
      ALTER TABLE app.simulaciones_fusion ADD CONSTRAINT simulaciones_fusion_version_check CHECK(version IN (1,2));
      ALTER TABLE app.resenas ADD CONSTRAINT uq_review_id_profile UNIQUE(id,author_profile_id);
      CREATE TABLE app.selecciones_resena_canonica (
        id uuid PRIMARY KEY, operation_id uuid NOT NULL REFERENCES app.operaciones_catalogo(id) ON DELETE RESTRICT,
        work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
        profile_id uuid NOT NULL REFERENCES app.perfiles(id) ON DELETE RESTRICT,
        review_id uuid NOT NULL REFERENCES app.resenas(id) ON DELETE RESTRICT,
        UNIQUE(operation_id,profile_id),
        FOREIGN KEY(operation_id,work_id) REFERENCES app.operaciones_catalogo(id,target_work_id) ON DELETE RESTRICT,
        FOREIGN KEY(review_id,profile_id) REFERENCES app.resenas(id,author_profile_id) ON DELETE RESTRICT
      );
      CREATE INDEX ix_review_selection_work ON app.selecciones_resena_canonica(work_id);
      CREATE INDEX ix_merge_readings_work ON app.lecturas(work_id);
      CREATE INDEX ix_merge_reviews_work ON app.resenas(work_id);
      CREATE TRIGGER catalog_review_selection_immutable BEFORE UPDATE OR DELETE ON app.selecciones_resena_canonica
        FOR EACH ROW EXECUTE FUNCTION app.catalog_history_immutable();
      CREATE FUNCTION app.catalog_writer_barrier() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        PERFORM pg_advisory_xact_lock_shared(73155,1);
        RETURN NULL;
      END $$;
    """)
    # BEFORE STATEMENT runs before row/FK locks, including legacy writers.
    # The merger takes the exclusive key first in READ COMMITTED.
    tables=('usuarios','permisos_cuenta','perfiles','obras','autores','obras_autores','titulos_alternativos',
            'ediciones','fuentes_catalogo','referencias_obras','entradas_biblioteca','lecturas','eventos_lectura',
            'progreso_lectura','selecciones_edicion_lectura','resenas','revisiones_resena','publicaciones',
            'incorporaciones_catalogo','selecciones_resena_canonica')
    # Resolve optional historical table names from the actual schema.
    for table in tables:
        op.execute(f"""DO $$ BEGIN IF to_regclass('app.{table}') IS NOT NULL THEN
          EXECUTE 'CREATE TRIGGER catalog_writer_barrier BEFORE INSERT OR UPDATE OR DELETE ON app.{table}
          FOR EACH STATEMENT EXECUTE FUNCTION app.catalog_writer_barrier()'; END IF; END $$""")


def downgrade():
    raise RuntimeError('Preserve merge decisions and audit; reviewed forward recovery only')
