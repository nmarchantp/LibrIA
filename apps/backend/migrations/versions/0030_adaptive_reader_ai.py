"""Private versioned AI experiences, feedback and a durable event queue."""
from alembic import op

revision = "0030_adaptive_reader_ai"
down_revision = "0029_book_notes_theories"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE app.lecturas DROP CONSTRAINT ck_lecturas_abandoned;
    ALTER TABLE app.lecturas ADD CONSTRAINT ck_lecturas_abandoned CHECK (
      (status='abandoned' AND abandoned_at IS NOT NULL AND abandoned_at >= started_at)
      OR (status<>'abandoned' AND abandoned_at IS NULL AND abandonment_reason IS NULL));
    CREATE SCHEMA IF NOT EXISTS ia;
    CREATE TABLE ia.jobs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
      target text NOT NULL, status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','completed','failed')),
      revision integer NOT NULL DEFAULT 1, attempts integer NOT NULL DEFAULT 0,
      not_before timestamptz NOT NULL DEFAULT now(), locked_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      error_code text, UNIQUE(owner_id,target));
    CREATE INDEX ix_ai_job_queue ON ia.jobs(status,not_before);
    CREATE TABLE ia.analyses (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
      target text NOT NULL, version integer NOT NULL, data_hash text NOT NULL,
      content jsonb NOT NULL, model text NOT NULL, prompt_version text NOT NULL,
      valid boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(owner_id,target,version));
    CREATE INDEX ix_ai_analysis_owner ON ia.analyses(owner_id,target,version DESC);
    CREATE TABLE ia.feedback (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
      analysis_id uuid NOT NULL REFERENCES ia.analyses(id) ON DELETE CASCADE,
      action text NOT NULL CHECK (action IN ('confirm','correct','reject')),
      original_interpretation jsonb NOT NULL, information text NOT NULL,
      status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processed')),
      created_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz);
    CREATE TABLE ia.evidence (
      analysis_id uuid NOT NULL REFERENCES ia.analyses(id) ON DELETE CASCADE,
      source_key text NOT NULL, source_kind text NOT NULL, source_id uuid NOT NULL,
      work_id uuid, source_hash text NOT NULL,
      PRIMARY KEY(analysis_id,source_key));
    REVOKE ALL ON SCHEMA ia FROM PUBLIC;
    REVOKE ALL ON ALL TABLES IN SCHEMA ia FROM PUBLIC;

    CREATE FUNCTION ia.enqueue(p_owner uuid,p_target text) RETURNS void LANGUAGE plpgsql AS $$
    BEGIN
      INSERT INTO ia.jobs(owner_id,target,not_before) VALUES(p_owner,p_target,now()+interval '3 seconds')
      ON CONFLICT(owner_id,target) DO UPDATE SET
        revision=ia.jobs.revision+1,
        status=CASE WHEN ia.jobs.status='processing' THEN 'processing' ELSE 'pending' END,
        attempts=CASE WHEN ia.jobs.status='processing' THEN ia.jobs.attempts ELSE 0 END,
        not_before=now()+interval '3 seconds',updated_at=now(),error_code=NULL;
    END $$;
    CREATE FUNCTION ia.book_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE uid uuid; wid uuid; entry_id uuid; ref text; kind text;
    BEGIN
      IF TG_TABLE_NAME='lecturas' THEN
        IF TG_OP='UPDATE' AND NEW.status=OLD.status AND NEW.notebook=OLD.notebook
          AND NEW.abandonment_reason IS NOT DISTINCT FROM OLD.abandonment_reason THEN RETURN NEW; END IF;
        entry_id:=COALESCE(NEW.library_entry_id,OLD.library_entry_id);
        SELECT user_id,work_id INTO uid,wid FROM app.entradas_biblioteca WHERE id=entry_id;
      ELSIF TG_TABLE_NAME='entradas_biblioteca' THEN
        IF TG_OP='UPDATE' AND NEW.archived_at IS NOT DISTINCT FROM OLD.archived_at THEN RETURN NEW; END IF;
        uid:=COALESCE(NEW.user_id,OLD.user_id); wid:=COALESCE(NEW.work_id,OLD.work_id);
      ELSIF TG_TABLE_NAME='resenas' THEN
        IF TG_OP='UPDATE' AND NEW.body=OLD.body AND NEW.rating IS NOT DISTINCT FROM OLD.rating
          AND NEW.dimension_ratings=OLD.dimension_ratings AND NEW.status=OLD.status THEN RETURN NEW; END IF;
        SELECT p.owner_user_id INTO uid FROM app.perfiles p
          WHERE p.id=COALESCE(NEW.author_profile_id,OLD.author_profile_id) AND p.kind='personal';
        wid:=COALESCE(NEW.work_id,OLD.work_id);
      ELSIF TG_TABLE_NAME='eventos_lectura' THEN
        IF NEW.reflection IS NULL THEN RETURN NEW; END IF;
        SELECT le.user_id,le.work_id INTO uid,wid FROM app.lecturas r
          JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id WHERE r.id=NEW.reading_id;
      ELSE
        kind:=COALESCE(NEW.publication_type,OLD.publication_type);
        IF kind NOT IN ('note','theory') THEN RETURN COALESCE(NEW,OLD); END IF;
        SELECT p.owner_user_id INTO uid FROM app.perfiles p
          WHERE p.id=COALESCE(NEW.author_profile_id,OLD.author_profile_id) AND p.kind='personal';
        ref:=COALESCE(NEW.book_ref,OLD.book_ref);
        SELECT CASE WHEN count(DISTINCT ed.work_id)=1 THEN min(ed.work_id::text)::uuid END INTO wid
          FROM app.fuentes_catalogo s JOIN app.ediciones ed ON ed.id=s.edition_id WHERE s.external_id=ref;
      END IF;
      IF uid IS NULL OR wid IS NULL THEN RETURN COALESCE(NEW,OLD); END IF;
      IF NOT EXISTS(SELECT 1 FROM app.usuarios WHERE id=uid) THEN RETURN COALESCE(NEW,OLD); END IF;
      IF EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='obras' AND d.entity_id=wid)
        THEN RETURN COALESCE(NEW,OLD); END IF;
      IF TG_OP='DELETE' OR (TG_TABLE_NAME='entradas_biblioteca' AND TG_OP='UPDATE') THEN
        -- Source deletion/archival scrubs derived narratives, including history.
        UPDATE ia.analyses SET valid=false,content='{}' WHERE owner_id=uid
          AND target IN ('profile','book:'||wid::text);
        UPDATE ia.feedback f SET original_interpretation='{}', information='[Origen retirado]'
          FROM ia.analyses a WHERE a.id=f.analysis_id AND a.owner_id=uid
          AND a.target IN ('profile','book:'||wid::text);
      END IF;
      PERFORM ia.enqueue(uid,'book:'||wid::text);
      PERFORM ia.enqueue(uid,'profile');
      RETURN COALESCE(NEW,OLD);
    END $$;
    CREATE TRIGGER ai_reading_change AFTER INSERT OR UPDATE ON app.lecturas FOR EACH ROW EXECUTE FUNCTION ia.book_changed();
    CREATE TRIGGER ai_library_change AFTER INSERT OR UPDATE OR DELETE ON app.entradas_biblioteca FOR EACH ROW EXECUTE FUNCTION ia.book_changed();
    CREATE TRIGGER ai_review_change AFTER INSERT OR UPDATE OR DELETE ON app.resenas FOR EACH ROW EXECUTE FUNCTION ia.book_changed();
    CREATE TRIGGER ai_reflection_change AFTER INSERT ON app.eventos_lectura FOR EACH ROW EXECUTE FUNCTION ia.book_changed();
    CREATE TRIGGER ai_post_change AFTER INSERT OR UPDATE OR DELETE ON app.publicaciones FOR EACH ROW EXECUTE FUNCTION ia.book_changed();
    """)


def downgrade():
    raise RuntimeError("Preserve private AI history and feedback")
