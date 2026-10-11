"""Reseñas al corte y preparación restringida de valoraciones."""
from alembic import op

revision = "0017_review_analytics"
down_revision = "0016_normalized_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE analytics.hechos_resenas (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            source_id uuid NOT NULL,
            user_id uuid NOT NULL,
            work_id uuid NOT NULL,
            edition_id uuid,
            rating integer CHECK (rating BETWEEN 1 AND 5),
            status text NOT NULL CHECK (status IN ('published','hidden')),
            first_published_at timestamptz NOT NULL,
            revision_number integer NOT NULL,
            revision_recorded_at timestamptz NOT NULL,
            provenance text NOT NULL CHECK (provenance IN ('operational','simulated','unclassified')),
            PRIMARY KEY (etl_run_id, source_id),
            FOREIGN KEY (etl_run_id, work_id) REFERENCES analytics.catalogo_obras(etl_run_id, work_id)
        );
        CREATE INDEX ix_analytics_resenas_owner ON analytics.hechos_resenas(user_id);
        CREATE TABLE analytics.preparacion_valoraciones_obras (
            etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id),
            work_id uuid NOT NULL,
            provenance text NOT NULL CHECK (provenance IN ('operational','simulated','unclassified')),
            review_count integer NOT NULL CHECK (review_count >= 0),
            rated_count integer NOT NULL CHECK (rated_count >= 0 AND rated_count <= review_count),
            rating_sum integer NOT NULL CHECK (rating_sum >= 0),
            rating_average numeric,
            distribution jsonb NOT NULL,
            PRIMARY KEY (etl_run_id, work_id, provenance),
            FOREIGN KEY (etl_run_id, work_id) REFERENCES analytics.catalogo_obras(etl_run_id, work_id),
            CHECK ((rated_count=0 AND rating_average IS NULL) OR (rated_count>0 AND rating_average BETWEEN 1 AND 5))
        );
        REVOKE ALL ON analytics.hechos_resenas, analytics.preparacion_valoraciones_obras FROM PUBLIC;
    """)


def downgrade():
    raise RuntimeError("Restaurar respaldo para preservar los cortes históricos.")
