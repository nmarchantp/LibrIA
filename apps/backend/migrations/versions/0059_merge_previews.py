"""Isolated append-only administrative simulations; no catalog rewrites."""
from alembic import op

revision = '0059_merge_previews'
down_revision = '0058_canonical_versions'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE app.simulaciones_fusion (
      id uuid PRIMARY KEY,
      actor_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      version integer NOT NULL CHECK (version = 1),
      source_work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
      target_work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
      fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
      result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
      created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      expires_at timestamptz NOT NULL CHECK (expires_at > created_at),
      CHECK (source_work_id <> target_work_id)
    );
    CREATE INDEX ix_merge_preview_actor_date ON app.simulaciones_fusion(actor_user_id,created_at);
    CREATE FUNCTION app.prevent_preview_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Merge previews are immutable'; END $$;
    CREATE TRIGGER trg_merge_preview_immutable BEFORE UPDATE OR DELETE ON app.simulaciones_fusion
      FOR EACH ROW EXECUTE FUNCTION app.prevent_preview_mutation();
    """)


def downgrade():
    raise RuntimeError('Preserve administrative audit; use reviewed forward recovery')
