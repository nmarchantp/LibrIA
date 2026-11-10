"""Add reports and a separate preventive visibility state; preserve all content."""
from alembic import op
import sqlalchemy as sa

revision = '0084_moderation_reports'
down_revision = '0083_pending_review_date'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('publicaciones','resenas','comentarios_publicacion'):
        op.add_column(table,sa.Column('moderation_hidden',sa.Boolean(),nullable=False,server_default=sa.false()),schema='app')
    op.execute("""CREATE TABLE app.reportes_contenido (
      id uuid PRIMARY KEY,
      post_id uuid REFERENCES app.publicaciones(id) ON DELETE RESTRICT,
      review_id uuid REFERENCES app.resenas(id) ON DELETE RESTRICT,
      comment_id uuid REFERENCES app.comentarios_publicacion(id) ON DELETE RESTRICT,
      reporter_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      reason varchar(24) NOT NULL, detail text NOT NULL DEFAULT '', content_snapshot jsonb NOT NULL,
      status varchar(16) NOT NULL DEFAULT 'pending', created_at timestamptz NOT NULL DEFAULT now(),
      resolved_by uuid REFERENCES app.usuarios(id) ON DELETE RESTRICT,
      resolved_at timestamptz, resolution_reason text,
      CONSTRAINT ck_content_report_destination CHECK (num_nonnulls(post_id,review_id,comment_id)=1),
      CONSTRAINT ck_content_report_reason CHECK (reason IN ('discrimination','harassment','threats','sexual_content','spam','other')),
      CONSTRAINT ck_content_report_detail CHECK (length(detail)<=2000),
      CONSTRAINT ck_content_report_status CHECK (status IN ('pending','dismissed','hidden')),
      CONSTRAINT ck_content_report_resolution CHECK (
        (status='pending' AND resolved_by IS NULL AND resolved_at IS NULL AND resolution_reason IS NULL) OR
        (status!='pending' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL AND length(trim(resolution_reason)) BETWEEN 1 AND 2000))
    )""")
    for column in ('post_id','review_id','comment_id'):
        op.create_index(f'uq_content_report_{column}','reportes_contenido',['reporter_user_id',column],unique=True,schema='app')
    op.create_index('ix_content_report_queue','reportes_contenido',['status','created_at','id'],schema='app')
    op.alter_column('auditoria_moderacion','revision_id',nullable=True,schema='app')
    op.add_column('auditoria_moderacion',sa.Column('report_id',sa.Uuid(),sa.ForeignKey('app.reportes_contenido.id',ondelete='RESTRICT')),schema='app')
    op.create_check_constraint('ck_mod_audit_destination','auditoria_moderacion','num_nonnulls(revision_id,report_id)=1',schema='app')
    op.drop_constraint('ck_mod_audit_action','auditoria_moderacion',schema='app',type_='check')
    op.create_check_constraint('ck_mod_audit_action','auditoria_moderacion',"action IN ('prepared','superseded','withdrawn','approved','rejected','hidden','restored','reported','dismissed')",schema='app')
    op.create_index('ix_mod_audit_report','auditoria_moderacion',['report_id','created_at'],schema='app')
    # Proposal and audit protections from 0082 remain in place. Final decisions
    # and report resolutions cannot be rewritten or deleted by another writer.
    op.execute("""CREATE FUNCTION app.protect_moderation_resolution() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='revisiones_moderacion' THEN
        IF OLD.decided_at IS NOT NULL THEN RAISE EXCEPTION 'Moderation decision is immutable'; END IF;
      ELSE
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Content reports are retained'; END IF;
        IF ROW(NEW.post_id,NEW.review_id,NEW.comment_id,NEW.reporter_user_id,NEW.reason,NEW.detail,NEW.created_at,NEW.content_snapshot)
          IS DISTINCT FROM ROW(OLD.post_id,OLD.review_id,OLD.comment_id,OLD.reporter_user_id,OLD.reason,OLD.detail,OLD.created_at,OLD.content_snapshot)
          OR OLD.resolved_at IS NOT NULL THEN RAISE EXCEPTION 'Report evidence and resolutions are immutable'; END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER protect_mod_decision BEFORE UPDATE ON app.revisiones_moderacion FOR EACH ROW EXECUTE FUNCTION app.protect_moderation_resolution()')
    op.execute('CREATE TRIGGER protect_content_report BEFORE UPDATE OR DELETE ON app.reportes_contenido FOR EACH ROW EXECUTE FUNCTION app.protect_moderation_resolution()')


def downgrade():
    raise RuntimeError('Preserva reportes, decisiones y auditoría antes de revertir esta migración.')
