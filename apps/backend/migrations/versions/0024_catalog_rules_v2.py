"""Catalog business rules v2 metadata, alternate titles and traceability."""
from alembic import op

revision = "0024_catalog_rules_v2"
down_revision = "0023_work_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE app.obras
        ADD COLUMN series_title text,
        ADD COLUMN volume_number text,
        ADD COLUMN first_publication_date text,
        ADD COLUMN categories jsonb;
        ALTER TABLE app.ediciones
        ADD COLUMN isbn10 varchar(10) UNIQUE,
        ADD COLUMN publication_date text,
        ADD COLUMN format text;
        ALTER TABLE app.fuentes_catalogo
        ADD COLUMN synced_at timestamptz,
        ADD COLUMN validation_status text NOT NULL DEFAULT 'validated',
        ADD COLUMN consolidation_status text NOT NULL DEFAULT 'automatic';
        CREATE TABLE app.titulos_alternativos (
            id uuid PRIMARY KEY, work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE CASCADE,
            title text NOT NULL, normalized_title text NOT NULL, language text,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_titulos_alternativos_obra UNIQUE(work_id,normalized_title,language));
        CREATE INDEX ix_titulos_alternativos_work ON app.titulos_alternativos(work_id);
        CREATE INDEX ix_titulos_alternativos_normalized ON app.titulos_alternativos(normalized_title);""")


def downgrade():
    raise RuntimeError("Catalog v2 metadata must be preserved")
