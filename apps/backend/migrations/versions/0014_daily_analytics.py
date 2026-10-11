"""Carga diaria atómica y datos analíticos separados del feed legado."""
from alembic import op

revision = "0014_daily_analytics"
down_revision = "0013_post_interactions_media"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE analytics.ejecuciones_etl ADD COLUMN business_date date;
        ALTER TABLE analytics.ejecuciones_etl ADD COLUMN period_start timestamptz;
        ALTER TABLE analytics.ejecuciones_etl ADD COLUMN attempt_count integer NOT NULL DEFAULT 1;
        ALTER TABLE analytics.ejecuciones_etl ADD COLUMN summary jsonb NOT NULL DEFAULT '{}';
        ALTER TABLE analytics.ejecuciones_etl ADD CONSTRAINT uq_etl_business_date UNIQUE (business_date);
        ALTER TABLE analytics.ejecuciones_etl ADD CONSTRAINT ck_etl_status CHECK (status IN ('running', 'succeeded', 'failed'));

        CREATE TABLE analytics.catalogo_obras (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            work_id uuid NOT NULL,
            title text NOT NULL CHECK (length(trim(title)) > 0),
            PRIMARY KEY (etl_run_id, work_id)
        );
        CREATE TABLE analytics.hechos_lectura (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            source_id uuid NOT NULL,
            user_id uuid NOT NULL,
            work_id uuid NOT NULL,
            edition_id uuid NOT NULL,
            event_kind text NOT NULL CHECK (event_kind IN ('start','progress','correction','finish','abandon')),
            occurred_at timestamptz NOT NULL,
            previous_page integer NOT NULL CHECK (previous_page >= 0),
            page integer NOT NULL CHECK (page >= 0),
            total_pages integer NOT NULL CHECK (total_pages > 0 AND page <= total_pages AND previous_page <= total_pages),
            provenance text NOT NULL CHECK (provenance IN ('operational','simulated')),
            PRIMARY KEY (etl_run_id, source_id),
            FOREIGN KEY (etl_run_id, work_id) REFERENCES analytics.catalogo_obras(etl_run_id, work_id)
        );
        CREATE INDEX ix_analytics_lectura_owner ON analytics.hechos_lectura(user_id, occurred_at);
        CREATE TABLE analytics.hechos_publicaciones (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            source_id uuid NOT NULL,
            user_id uuid NOT NULL,
            profile_id uuid NOT NULL,
            publication_type text NOT NULL CHECK (publication_type IN ('free','institutional','launch','event','news','promotion')),
            published_at timestamptz NOT NULL,
            provenance text NOT NULL CHECK (provenance IN ('operational','simulated')),
            PRIMARY KEY (etl_run_id, source_id)
        );
        CREATE TABLE analytics.indicadores_personales (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            user_id uuid NOT NULL,
            indicator_code text NOT NULL,
            value numeric NOT NULL,
            definition_version text NOT NULL,
            provenance text NOT NULL CHECK (provenance IN ('operational','simulated')),
            PRIMARY KEY (etl_run_id, user_id, indicator_code, provenance)
        );
        CREATE INDEX ix_analytics_indicadores_owner ON analytics.indicadores_personales(user_id);
        CREATE TABLE analytics.validaciones_etl (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            rule_code text NOT NULL,
            severity text NOT NULL CHECK (severity IN ('info','warning','error')),
            affected_rows integer NOT NULL CHECK (affected_rows >= 0),
            PRIMARY KEY (etl_run_id, rule_code)
        );
        CREATE TABLE app.procedencia_demo (
            entity_type text NOT NULL,
            entity_id uuid NOT NULL,
            dataset_version text NOT NULL,
            PRIMARY KEY (entity_type, entity_id)
        );
        REVOKE ALL ON analytics.catalogo_obras, analytics.hechos_lectura,
            analytics.hechos_publicaciones, analytics.indicadores_personales,
            analytics.validaciones_etl FROM PUBLIC;
    """)


def downgrade():
    raise RuntimeError("La carga analítica conserva historial; restaurar respaldo para revertir.")
