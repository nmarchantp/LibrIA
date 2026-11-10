"""Moderation foundation only; existing public consumers stay unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '0082_moderation_foundation'
down_revision = '0081_annual_reading_challenge'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('publicaciones', 'resenas', 'comentarios_publicacion'):
        op.add_column(table, sa.Column('moderation_status', sa.String(16), nullable=False, server_default='approved'), schema='app')
        op.add_column(table, sa.Column('moderation_version', sa.Integer(), nullable=False, server_default='1'), schema='app')
        op.create_check_constraint(f'ck_{table}_moderation_status', table, "moderation_status IN ('approved','pending_review','rejected')", schema='app')
        op.create_check_constraint(f'ck_{table}_moderation_version', table, 'moderation_version > 0', schema='app')
    op.add_column('comentarios_publicacion', sa.Column('deleted_at', sa.DateTime(timezone=True)), schema='app')
    op.execute("""CREATE TABLE app.revisiones_moderacion (
      id uuid PRIMARY KEY,
      post_id uuid REFERENCES app.publicaciones(id) ON DELETE RESTRICT,
      review_id uuid REFERENCES app.resenas(id) ON DELETE RESTRICT,
      comment_id uuid REFERENCES app.comentarios_publicacion(id) ON DELETE RESTRICT,
      author_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      base_version integer NOT NULL, base_fingerprint varchar(64) NOT NULL,
      proposal jsonb NOT NULL, findings jsonb NOT NULL, ruleset_version varchar(80) NOT NULL,
      status varchar(16) NOT NULL, lifecycle varchar(16) NOT NULL DEFAULT 'active',
      created_at timestamptz NOT NULL DEFAULT now(),
      decided_by uuid REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      decided_at timestamptz, decision_reason text,
      CONSTRAINT ck_mod_revision_destination CHECK (num_nonnulls(post_id,review_id,comment_id)=1),
      CONSTRAINT ck_mod_revision_status CHECK (status IN ('approved','pending_review','rejected')),
      CONSTRAINT ck_mod_revision_lifecycle CHECK (lifecycle IN ('active','superseded','withdrawn')),
      CONSTRAINT ck_mod_revision_base CHECK (base_version>0 AND length(base_fingerprint)=64),
      CONSTRAINT ck_mod_revision_json CHECK (jsonb_typeof(proposal)='object' AND jsonb_typeof(findings)='array'),
      CONSTRAINT ck_mod_revision_decision CHECK (
        (status IN ('pending_review','approved') AND decided_by IS NULL AND decided_at IS NULL AND decision_reason IS NULL)
        OR (status IN ('approved','rejected') AND decided_by IS NOT NULL AND decided_at IS NOT NULL
            AND decision_reason IS NOT NULL AND length(trim(decision_reason))>0))
    )""")
    for column in ('post_id','review_id','comment_id'):
        op.create_index(f'uq_mod_pending_{column}', 'revisiones_moderacion', [column], unique=True, schema='app',
                        postgresql_where=sa.text("status='pending_review' AND lifecycle='active'"))
    op.create_index('ix_mod_revision_queue','revisiones_moderacion',['status','lifecycle','created_at','id'],schema='app')
    op.create_index('ix_mod_revision_author','revisiones_moderacion',['author_user_id','created_at'],schema='app')
    op.execute("""CREATE TABLE app.adjuntos_moderacion (
      id uuid PRIMARY KEY,
      revision_id uuid NOT NULL REFERENCES app.revisiones_moderacion(id) ON DELETE RESTRICT,
      role varchar(16) NOT NULL, position integer NOT NULL, content_type varchar(40) NOT NULL, data bytea NOT NULL,
      CONSTRAINT ck_mod_attachment_role CHECK (role IN ('image','cover')),
      CONSTRAINT ck_mod_attachment_type CHECK (content_type IN ('image/jpeg','image/png','image/gif','image/webp')),
      CONSTRAINT ck_mod_attachment_size CHECK (octet_length(data) BETWEEN 1 AND 5242880 AND position>=0)
    )""")
    op.create_index('uq_mod_attachment_order','adjuntos_moderacion',['revision_id','role','position'],unique=True,schema='app')
    op.create_index('uq_mod_attachment_cover','adjuntos_moderacion',['revision_id'],unique=True,schema='app',postgresql_where=sa.text("role='cover'"))
    op.execute("""CREATE TABLE app.auditoria_moderacion (
      id uuid PRIMARY KEY,
      revision_id uuid NOT NULL REFERENCES app.revisiones_moderacion(id) ON DELETE RESTRICT,
      actor_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      action varchar(16) NOT NULL, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_mod_audit_action CHECK (action IN ('prepared','superseded','withdrawn','approved','rejected','hidden','restored')),
      CONSTRAINT ck_mod_audit_reason CHECK (length(trim(reason)) BETWEEN 1 AND 2000)
    )""")
    op.create_index('ix_mod_audit_revision','auditoria_moderacion',['revision_id','created_at'],schema='app')
    op.execute("""CREATE TABLE app.solicitudes_moderacion (
      user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      operation varchar(160) NOT NULL, key uuid NOT NULL, payload_hash varchar(64) NOT NULL,
      result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(user_id,operation,key),
      CONSTRAINT ck_mod_request_hash CHECK (length(payload_hash)=64),
      CONSTRAINT ck_mod_request_result CHECK (result IS NULL OR jsonb_typeof(result)='object')
    )""")
    op.execute("""CREATE FUNCTION app.protect_moderation_audit() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Moderation audit is append-only' USING ERRCODE='23514'; END $$""")
    op.execute("""CREATE TRIGGER moderation_audit_append_only BEFORE UPDATE OR DELETE ON app.auditoria_moderacion
      FOR EACH ROW EXECUTE FUNCTION app.protect_moderation_audit()""")
    op.execute("""CREATE FUNCTION app.protect_moderation_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF ROW(NEW.post_id,NEW.review_id,NEW.comment_id,NEW.author_user_id,NEW.base_version,NEW.base_fingerprint,
          NEW.proposal,NEW.findings,NEW.ruleset_version,NEW.created_at)
        IS DISTINCT FROM ROW(OLD.post_id,OLD.review_id,OLD.comment_id,OLD.author_user_id,OLD.base_version,OLD.base_fingerprint,
          OLD.proposal,OLD.findings,OLD.ruleset_version,OLD.created_at) THEN
        RAISE EXCEPTION 'Moderation proposal is immutable; submit another revision' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER moderation_proposal_immutable BEFORE UPDATE ON app.revisiones_moderacion
      FOR EACH ROW EXECUTE FUNCTION app.protect_moderation_proposal()""")


def downgrade():
    raise RuntimeError('La reversión requiere preservar propuestas y auditoría; no se eliminan automáticamente.')
