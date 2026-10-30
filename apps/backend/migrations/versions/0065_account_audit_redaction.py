"""Permit only irreversible removal of identifying snapshots after account minimization."""
from alembic import op
revision = "0065_account_audit_redaction"
down_revision = "0064_account_insert_default"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION app.protect_account_audit() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='UPDATE' THEN
        IF EXISTS(SELECT 1 FROM app.usuarios WHERE id=OLD.user_id AND account_status='anonymized')
          AND (to_jsonb(NEW)-ARRAY['before_state','after_state'])=(to_jsonb(OLD)-ARRAY['before_state','after_state'])
          AND NEW.before_state=OLD.before_state-ARRAY['display_name','biography','username']
          AND NEW.after_state=OLD.after_state-ARRAY['display_name','biography','username'] THEN
          RETURN NEW;
        END IF;
      END IF;
      RAISE EXCEPTION 'Account audit is append only; identifying snapshots may only be minimized after deletion';
    END $$;
    """)


def downgrade():
    raise RuntimeError("Keep the reviewed account minimization policy")
