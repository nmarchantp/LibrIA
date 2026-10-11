"""Private interpretations and fixed daily aggregate releases."""
from alembic import op

revision = "0019_ai_interpretations"
down_revision = "0018_manual_etl"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE analytics.interpretaciones_ia (
            id uuid PRIMARY KEY,
            scope text NOT NULL CHECK (scope IN ('personal','group')),
            subject_key text NOT NULL,
            owner_user_id uuid REFERENCES app.usuarios(id),
            data_hash text NOT NULL,
            provider text NOT NULL,
            model text NOT NULL,
            prompt_version text NOT NULL,
            content jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((scope='personal' AND owner_user_id IS NOT NULL AND subject_key=owner_user_id::text)
                OR (scope='group' AND owner_user_id IS NULL AND subject_key='group')),
            UNIQUE (scope, subject_key, data_hash, provider, model, prompt_version)
        );
        CREATE TABLE analytics.resumenes_grupales (
            release_date date NOT NULL,
            provenance text NOT NULL CHECK (provenance IN ('simulated','unclassified','operational')),
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (release_date, provenance)
        );
        REVOKE ALL ON analytics.interpretaciones_ia, analytics.resumenes_grupales FROM PUBLIC;
    """)


def downgrade():
    raise RuntimeError("Interpretation history must be preserved.")
