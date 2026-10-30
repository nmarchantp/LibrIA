"""Non-destructive account lifecycle, immutable audit and one-use challenges."""
from alembic import op

revision = "0061_account_management"
down_revision = "0060_admin_merges"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE app.usuarios ADD COLUMN username varchar(64);
    UPDATE app.usuarios SET username='reader_' || replace(id::text, '-', '');
    ALTER TABLE app.usuarios ALTER COLUMN username SET NOT NULL;
    ALTER TABLE app.usuarios ADD CONSTRAINT uq_usuarios_username UNIQUE(username);
    ALTER TABLE app.usuarios ADD COLUMN account_status varchar(24) NOT NULL DEFAULT 'active',
      ADD COLUMN suspended_at timestamptz, ADD COLUMN deletion_requested_at timestamptz,
      ADD COLUMN deletion_scheduled_at timestamptz, ADD COLUMN anonymized_at timestamptz;
    ALTER TABLE app.usuarios ADD CONSTRAINT ck_account_status CHECK(account_status IN ('active','pending_deletion','anonymized'));
    ALTER TABLE app.usuarios ADD CONSTRAINT ck_deletion_dates CHECK(
      (account_status='pending_deletion' AND deletion_requested_at IS NOT NULL AND
       deletion_scheduled_at=deletion_requested_at + interval '720 hours') OR
      (account_status<>'pending_deletion' AND deletion_requested_at IS NULL AND deletion_scheduled_at IS NULL));
    CREATE TABLE app.auditoria_cuentas (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      actor_user_id uuid REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      action varchar(64) NOT NULL, origin varchar(40) NOT NULL, correlation_id uuid NOT NULL,
      reason text, before_state jsonb NOT NULL, after_state jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now());
    CREATE INDEX ix_account_audit_user ON app.auditoria_cuentas(user_id,created_at);
    CREATE FUNCTION app.protect_account_audit() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Account audit is append only'; END $$;
    CREATE TRIGGER account_audit_immutable BEFORE UPDATE OR DELETE ON app.auditoria_cuentas
      FOR EACH ROW EXECUTE FUNCTION app.protect_account_audit();
    CREATE TABLE app.desafios_cuenta (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      purpose varchar(32) NOT NULL, token_hash varchar(64) NOT NULL UNIQUE,
      target_email varchar(320), expires_at timestamptz NOT NULL, consumed_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now());
    CREATE INDEX ix_account_challenge_user ON app.desafios_cuenta(user_id);
    CREATE TABLE app.fotos_cuenta (
      user_id uuid PRIMARY KEY REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      data bytea NOT NULL, content_type varchar(32) NOT NULL,
      updated_at timestamptz NOT NULL DEFAULT now());
    """)


def downgrade():
    raise RuntimeError("Account management downgrade would discard history; restore a reviewed backup instead")
