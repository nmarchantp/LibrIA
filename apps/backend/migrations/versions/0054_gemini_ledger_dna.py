"""Durable per-call reservations and independently reusable reader DNA."""
from alembic import op

revision = "0054_gemini_ledger_dna"
down_revision = "0053_versioned_reading_analysis"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      DROP INDEX ia.uq_ai_analysis_job;
      CREATE INDEX ix_ai_analysis_job ON ia.analyses(job_id) WHERE job_id IS NOT NULL;
      ALTER TABLE ia.jobs DROP CONSTRAINT ck_ai_jobs_kind;
      ALTER TABLE ia.jobs DROP CONSTRAINT ck_ai_jobs_context;
      ALTER TABLE ia.jobs ADD CONSTRAINT ck_ai_jobs_kind CHECK
        (job_kind IN ('adaptive_analysis','recommendation','reading_event_analysis','reader_profile'));
      ALTER TABLE ia.jobs ADD CONSTRAINT ck_ai_jobs_context CHECK
        ((job_kind='adaptive_analysis' AND profile_version_id IS NULL AND reading_event_id IS NULL)
         OR (job_kind IN ('recommendation','reader_profile') AND profile_version_id IS NOT NULL
             AND reading_event_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL)
         OR (job_kind='reading_event_analysis' AND reading_event_id IS NOT NULL
             AND profile_version_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL));
      ALTER TABLE ia.jobs ADD COLUMN evidence_hash text;
      ALTER TABLE ia.jobs ADD COLUMN consolidation_seconds integer NOT NULL DEFAULT 1800;
      CREATE FUNCTION ia.consolidate_reading_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE relevant boolean; affected_work uuid; affected_owner uuid;
      BEGIN
        affected_work := COALESCE((to_jsonb(NEW)->>'work_id')::uuid,(to_jsonb(OLD)->>'work_id')::uuid);
        affected_owner := COALESCE((to_jsonb(NEW)->>'created_by_user_id')::uuid,
          (to_jsonb(NEW)->>'user_id')::uuid,(to_jsonb(OLD)->>'created_by_user_id')::uuid,
          (to_jsonb(OLD)->>'user_id')::uuid);
        IF TG_TABLE_NAME='lecturas' THEN
          relevant := (to_jsonb(NEW)->'notebook') IS DISTINCT FROM (to_jsonb(OLD)->'notebook');
        ELSE
          relevant := TG_OP<>'UPDATE' OR
            (to_jsonb(NEW)-ARRAY['updated_at','like_count','view_count']) IS DISTINCT FROM
            (to_jsonb(OLD)-ARRAY['updated_at','like_count','view_count']);
        END IF;
        IF TG_TABLE_NAME='publicaciones' AND
          COALESCE(to_jsonb(NEW)->>'publication_type','') NOT IN ('note','theory') AND
          COALESCE(to_jsonb(OLD)->>'publication_type','') NOT IN ('note','theory') THEN
          relevant := false;
        END IF;
        IF relevant THEN
          UPDATE ia.jobs j SET not_before=now()+j.consolidation_seconds*interval '1 second',updated_at=now()
          FROM app.eventos_lectura ev,app.lecturas r
          WHERE j.reading_event_id=ev.id AND ev.reading_id=r.id
            AND r.work_id=affected_work AND j.job_kind='reading_event_analysis' AND j.status='pending'
            AND (affected_owner IS NULL OR j.owner_id=affected_owner)
            AND (TG_TABLE_NAME<>'lecturas' OR r.id=COALESCE((to_jsonb(NEW)->>'id')::uuid,(to_jsonb(OLD)->>'id')::uuid));
        END IF;
        RETURN COALESCE(NEW,OLD);
      END $$;
      CREATE TRIGGER consolidate_reading_notebook AFTER UPDATE ON app.lecturas
        FOR EACH ROW EXECUTE FUNCTION ia.consolidate_reading_evidence();
      CREATE TRIGGER consolidate_reading_review AFTER INSERT OR UPDATE OR DELETE ON app.resenas
        FOR EACH ROW EXECUTE FUNCTION ia.consolidate_reading_evidence();
      CREATE TRIGGER consolidate_reading_post AFTER INSERT OR UPDATE OR DELETE ON app.publicaciones
        FOR EACH ROW EXECUTE FUNCTION ia.consolidate_reading_evidence();
      CREATE TABLE ia.call_ledger (
        id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES ia.jobs(id) ON DELETE RESTRICT,
        attempt integer NOT NULL CHECK(attempt>0), ordinal integer NOT NULL CHECK(ordinal>0),
        provider text NOT NULL, model text NOT NULL, phase text NOT NULL,
        state text NOT NULL CHECK(state IN ('reserved','measured','partial','unknown','released')),
        reserved_tokens bigint NOT NULL CHECK(reserved_tokens>=0),
        reserved_cost_usd numeric(18,8) NOT NULL CHECK(reserved_cost_usd>=0),
        input_tokens bigint, output_tokens bigint, reasoning_tokens bigint, total_tokens bigint,
        cached_input_tokens bigint, metadata_fields jsonb NOT NULL DEFAULT '[]',
        measured_cost_usd numeric(18,8), request_id text, finish_reason text, error_code text,
        reconciliation_reference text,
        created_at timestamptz NOT NULL DEFAULT now(), settled_at timestamptz,
        UNIQUE(job_id,ordinal),
        CHECK(input_tokens IS NULL OR input_tokens>=0),
        CHECK(output_tokens IS NULL OR output_tokens>=0),
        CHECK(reasoning_tokens IS NULL OR reasoning_tokens>=0),
        CHECK(total_tokens IS NULL OR total_tokens>=0),
        CHECK(cached_input_tokens IS NULL OR cached_input_tokens>=0),
        CHECK(measured_cost_usd IS NULL OR measured_cost_usd>=0)
      );
      CREATE INDEX ix_call_ledger_month ON ia.call_ledger(provider,created_at);
      CREATE TABLE ia.provider_cooldowns (
        provider text NOT NULL, model text NOT NULL, until_at timestamptz NOT NULL,
        reason text NOT NULL, PRIMARY KEY(provider,model)
      );
      CREATE TABLE ia.reader_dna (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        analysis_id uuid NOT NULL REFERENCES ia.analyses(id) ON DELETE RESTRICT,
        owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
        source_profile_id uuid NOT NULL REFERENCES ia.reader_profile_versions(id) ON DELETE RESTRICT,
        source_hash text NOT NULL, model text NOT NULL, prompt_version text NOT NULL,
        content jsonb NOT NULL, trace jsonb NOT NULL DEFAULT '{}',
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(owner_id,source_hash,model,prompt_version)
      );
      REVOKE ALL ON ia.call_ledger,ia.reader_dna,ia.provider_cooldowns FROM PUBLIC;
      COMMENT ON TABLE ia.call_ledger IS
        'New calls only. Historical attempt estimates remain unverified and unchanged. Costs are local equivalents, not invoices.';
    """)


def downgrade():
    raise RuntimeError('Accounting and DNA history require a reviewed forward migration.')
