"""Durable individual requests and immutable nightly evidence snapshots."""
from alembic import op

revision = '0069_nightly_book_analysis'
down_revision = '0068_account_state_integrity'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      DROP TRIGGER consolidate_reading_notebook ON app.lecturas;
      DROP TRIGGER consolidate_reading_review ON app.resenas;
      DROP TRIGGER consolidate_reading_post ON app.publicaciones;
      CREATE TABLE ia.reading_analysis_requests (
        reading_event_id uuid PRIMARY KEY REFERENCES app.eventos_lectura(id) ON DELETE CASCADE,
        owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
        changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        prepared_at timestamptz,
        error_code text
      );
      CREATE INDEX ix_reading_requests_pending ON ia.reading_analysis_requests(changed_at);
      CREATE INDEX ix_reading_requests_owner ON ia.reading_analysis_requests(owner_id,reading_event_id);
      CREATE TABLE ia.reading_analysis_snapshots (
        job_id uuid PRIMARY KEY REFERENCES ia.jobs(id) ON DELETE CASCADE,
        payload jsonb NOT NULL,
        prepared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        etl_run_id uuid NOT NULL REFERENCES analytics.ejecuciones_etl(id)
      );
      DROP INDEX ia.uq_ai_job_reading_event_request;
      CREATE UNIQUE INDEX uq_ai_job_reading_event_request ON ia.jobs
        (reading_event_id,provider,model,prompt_version,evidence_hash)
        WHERE job_kind='reading_event_analysis';
      CREATE FUNCTION ia.request_reading_analysis() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE rec jsonb; uid uuid; wid uuid;
      BEGIN
        rec := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        wid := (rec->>'work_id')::uuid;
        IF TG_TABLE_NAME='publicaciones' AND rec->>'publication_type' NOT IN ('note','theory') THEN
          RETURN COALESCE(NEW,OLD);
        END IF;
        IF TG_TABLE_NAME='lecturas' THEN
          SELECT user_id INTO uid FROM app.entradas_biblioteca WHERE id=(rec->>'library_entry_id')::uuid;
        ELSIF TG_TABLE_NAME='eventos_lectura' THEN
          uid:=(rec->>'actor_user_id')::uuid;
          SELECT work_id INTO wid FROM app.lecturas WHERE id=(rec->>'reading_id')::uuid;
        ELSIF TG_TABLE_NAME='entradas_biblioteca' THEN uid:=(rec->>'user_id')::uuid;
        ELSE
          SELECT owner_user_id INTO uid FROM app.perfiles
            WHERE id=(rec->>'author_profile_id')::uuid AND kind='personal';
        END IF;
        IF uid IS NOT NULL THEN
          INSERT INTO ia.reading_analysis_requests(reading_event_id,owner_id)
            WITH RECURSIVE connected(id) AS (
              SELECT wid UNION
              SELECT CASE WHEN d.source_work_id=c.id THEN d.target_work_id ELSE d.source_work_id END
              FROM connected c JOIN app.redirecciones_obras d
                ON (d.source_work_id=c.id OR d.target_work_id=c.id)
                AND d.retired_at IS NULL AND d.active_from<=statement_timestamp()
              JOIN app.operaciones_catalogo o ON o.id=d.operation_id AND o.operation_type='merge'
            )
            SELECT ev.id,uid FROM app.eventos_lectura ev JOIN app.lecturas r ON r.id=ev.reading_id
            JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
            WHERE le.user_id=uid AND ev.actor_user_id=uid AND ev.kind IN ('finish','abandon')
              AND r.work_id IN (SELECT id FROM connected) ORDER BY ev.id
          ON CONFLICT(reading_event_id) DO UPDATE SET changed_at=clock_timestamp(),
            error_code=CASE WHEN ia.reading_analysis_requests.error_code='retry_requested' THEN 'retry_requested' ELSE NULL END;
          -- Source removal scrubs event-derived text as well as the legacy book target.
          IF TG_OP='DELETE' OR (TG_TABLE_NAME='entradas_biblioteca' AND rec->>'archived_at' IS NOT NULL) THEN
            UPDATE ia.analyses SET valid=false,content='{}' WHERE owner_id=uid
              AND prompt_version LIKE '%' || chr(58) || 'event-summary-v1';
            UPDATE ia.analyses a SET valid=false,content='{}' WHERE a.owner_id=uid
              AND a.reading_event_id IS NOT NULL AND (
                EXISTS(SELECT 1 FROM ia.evidence e WHERE e.analysis_id=a.id AND e.source_id=(rec->>'id')::uuid)
                OR EXISTS(SELECT 1 FROM ia.reading_analysis_snapshots s,
                  LATERAL jsonb_array_elements(COALESCE(s.payload->'evidence','[]')) e
                  WHERE s.job_id=a.job_id AND split_part(e->>'evidence_id',':',2)=rec->>'id')
                OR (TG_TABLE_NAME='entradas_biblioteca' AND EXISTS(SELECT 1 FROM app.eventos_lectura ev
                  JOIN app.lecturas r ON r.id=ev.reading_id WHERE ev.id=a.reading_event_id
                  AND r.library_entry_id=(rec->>'id')::uuid)));
            UPDATE ia.feedback f SET original_interpretation='{}',information='[Origen retirado]'
              FROM ia.analyses a WHERE f.analysis_id=a.id AND a.owner_id=uid AND NOT a.valid
              AND a.reading_event_id IS NOT NULL;
            UPDATE ia.reading_analysis_snapshots s SET payload='{}' FROM ia.jobs j
              WHERE j.id=s.job_id AND j.owner_id=uid AND j.job_kind='reading_event_analysis'
              AND (EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(s.payload->'evidence','[]')) e
                WHERE split_part(e->>'evidence_id',':',2)=rec->>'id')
                OR (TG_TABLE_NAME='entradas_biblioteca' AND EXISTS(SELECT 1 FROM app.eventos_lectura ev
                  JOIN app.lecturas r ON r.id=ev.reading_id WHERE ev.id=j.reading_event_id
                  AND r.library_entry_id=(rec->>'id')::uuid)));
            UPDATE ia.jobs j SET status='failed',error_code='withdrawn_evidence',locked_at=NULL,updated_at=now()
              WHERE j.owner_id=uid AND j.job_kind='reading_event_analysis' AND j.status='pending'
              AND EXISTS(SELECT 1 FROM ia.reading_analysis_snapshots s WHERE s.job_id=j.id AND s.payload='{}');
          END IF;
        END IF;
        RETURN COALESCE(NEW,OLD);
      END $$;
      INSERT INTO ia.reading_analysis_requests(reading_event_id,owner_id)
        SELECT ev.id,le.user_id FROM app.eventos_lectura ev JOIN app.lecturas r ON r.id=ev.reading_id
        JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
        WHERE ev.kind IN ('finish','abandon') AND ev.actor_user_id=le.user_id;
      REVOKE ALL ON ia.reading_analysis_requests,ia.reading_analysis_snapshots FROM PUBLIC;
      CREATE FUNCTION ia.request_catalog_reading_analysis() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE rec jsonb; previous jsonb; wid uuid;
      BEGIN
        rec:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        IF TG_OP='UPDATE' THEN
          previous:=to_jsonb(OLD);
          IF TG_TABLE_NAME='obras' AND
            (rec->'title',rec->'description',rec->'categories') IS NOT DISTINCT FROM
            (previous->'title',previous->'description',previous->'categories') THEN RETURN NEW; END IF;
          IF TG_TABLE_NAME='ediciones' AND
            (rec->'title',rec->'language',rec->'page_count') IS NOT DISTINCT FROM
            (previous->'title',previous->'language',previous->'page_count') THEN RETURN NEW; END IF;
          IF TG_TABLE_NAME='autores' AND rec->'name' IS NOT DISTINCT FROM previous->'name' THEN RETURN NEW; END IF;
        END IF;
        wid:=CASE WHEN TG_TABLE_NAME='obras' THEN (rec->>'id')::uuid ELSE (rec->>'work_id')::uuid END;
        UPDATE ia.reading_analysis_requests q SET changed_at=clock_timestamp()
          FROM app.eventos_lectura ev,app.lecturas r WHERE q.reading_event_id=ev.id AND ev.reading_id=r.id
          AND (r.work_id=wid OR TG_TABLE_NAME='redirecciones_obras' OR
            (TG_TABLE_NAME='autores' AND EXISTS(SELECT 1 FROM app.obras_autores wa
              WHERE wa.work_id=r.work_id AND wa.author_id=(rec->>'id')::uuid)));
        RETURN COALESCE(NEW,OLD);
      END $$;
    """)
    for table in ('lecturas', 'eventos_lectura', 'entradas_biblioteca', 'resenas', 'publicaciones'):
        op.execute(f'CREATE TRIGGER nightly_reading_request AFTER INSERT OR UPDATE OR DELETE ON app.{table} '
                   'FOR EACH ROW EXECUTE FUNCTION ia.request_reading_analysis()')
    for table in ('obras', 'ediciones', 'autores', 'obras_autores', 'redirecciones_obras'):
        op.execute(f'CREATE TRIGGER nightly_catalog_reading_request AFTER INSERT OR UPDATE OR DELETE ON app.{table} '
                   'FOR EACH ROW EXECUTE FUNCTION ia.request_catalog_reading_analysis()')


def downgrade():
    raise RuntimeError('Preserve reading evidence history; use a reviewed forward migration.')
