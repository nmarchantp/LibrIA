"""Owner-scoped, evidence-versioned book recommendations."""
from alembic import op
revision = "0021_ai_recommendations"
down_revision = "0020_catalog_mirror"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""CREATE TABLE analytics.recomendaciones_ia (
        id uuid PRIMARY KEY, owner_user_id uuid NOT NULL REFERENCES app.usuarios(id),
        data_hash text NOT NULL, model text NOT NULL, version text NOT NULL,
        content jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(owner_user_id,data_hash,model,version));
        REVOKE ALL ON analytics.recomendaciones_ia FROM PUBLIC;""")

def downgrade():
    raise RuntimeError("Recommendation history must be preserved")
