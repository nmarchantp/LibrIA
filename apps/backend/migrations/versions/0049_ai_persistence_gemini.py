"""Version AI persistence and prepare durable Gemini work.

Revision ID: 0049_ai_persistence_gemini
Revises: 0048_quarter_ratings

The existing queue remains the source of leases, retries and concurrency. New
columns are nullable where legacy adaptive jobs cannot provide the new context.
"""

from alembic import op


revision = "0049_ai_persistence_gemini"
down_revision = "0048_quarter_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics.projection_runs
          ADD CONSTRAINT uq_projection_runs_id_owner UNIQUE (id, owner_id);

        CREATE TABLE ia.reader_profile_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
          analytics_run_id uuid NOT NULL,
          data_hash text NOT NULL CHECK (length(data_hash) = 64),
          version integer NOT NULL CHECK (version > 0),
          status text NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'ready', 'failed')),
          error_code text,
          created_at timestamptz NOT NULL DEFAULT now(),
          generated_at timestamptz,
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_reader_profile_run_owner
            FOREIGN KEY (analytics_run_id, owner_id)
            REFERENCES analytics.projection_runs(id, owner_id) ON DELETE RESTRICT,
          CONSTRAINT uq_reader_profile_owner_version UNIQUE (owner_id, version),
          CONSTRAINT uq_reader_profile_owner_hash UNIQUE (owner_id, data_hash),
          CONSTRAINT uq_reader_profile_owner_run UNIQUE (owner_id, analytics_run_id),
          CONSTRAINT ck_reader_profile_ready_at CHECK (
            (status = 'ready' AND generated_at IS NOT NULL AND error_code IS NULL)
            OR (status <> 'ready' AND generated_at IS NULL)
          )
        );
        CREATE INDEX ix_reader_profile_owner_status
          ON ia.reader_profile_versions(owner_id, status, created_at DESC);

        ALTER TABLE ia.jobs
          ADD COLUMN job_kind text NOT NULL DEFAULT 'adaptive_analysis',
          ADD COLUMN provider text NOT NULL DEFAULT 'ollama',
          ADD COLUMN model text,
          ADD COLUMN prompt_version text,
          ADD COLUMN profile_version_id uuid REFERENCES ia.reader_profile_versions(id) ON DELETE RESTRICT,
          ADD COLUMN reading_event_id uuid REFERENCES app.eventos_lectura(id) ON DELETE RESTRICT,
          ADD CONSTRAINT ck_ai_jobs_kind CHECK (
            job_kind IN ('adaptive_analysis', 'recommendation', 'reading_event_analysis')
          ),
          ADD CONSTRAINT ck_ai_jobs_context CHECK (
            (job_kind = 'adaptive_analysis' AND profile_version_id IS NULL AND reading_event_id IS NULL)
            OR (job_kind = 'recommendation' AND profile_version_id IS NOT NULL
                AND reading_event_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL)
            OR (job_kind = 'reading_event_analysis' AND reading_event_id IS NOT NULL
                AND profile_version_id IS NULL AND model IS NOT NULL AND prompt_version IS NOT NULL)
          );
        CREATE INDEX ix_ai_job_kind_queue
          ON ia.jobs(job_kind, status, not_before);
        CREATE UNIQUE INDEX uq_ai_job_recommendation_request
          ON ia.jobs(owner_id, profile_version_id, provider, model, prompt_version)
          WHERE job_kind = 'recommendation';
        CREATE UNIQUE INDEX uq_ai_job_reading_event_request
          ON ia.jobs(reading_event_id)
          WHERE job_kind = 'reading_event_analysis';

        ALTER TABLE ia.analyses ADD COLUMN provider text;
        UPDATE ia.analyses SET provider = 'ollama' WHERE provider IS NULL;
        ALTER TABLE ia.analyses
          ALTER COLUMN provider SET NOT NULL,
          ALTER COLUMN provider SET DEFAULT 'ollama',
          ADD COLUMN job_id uuid REFERENCES ia.jobs(id) ON DELETE SET NULL,
          ADD COLUMN reading_event_id uuid REFERENCES app.eventos_lectura(id) ON DELETE RESTRICT;
        CREATE UNIQUE INDEX uq_ai_analysis_job
          ON ia.analyses(job_id) WHERE job_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_ai_analysis_reading_event
          ON ia.analyses(reading_event_id) WHERE reading_event_id IS NOT NULL;

        ALTER TABLE ia.recomendaciones_ia ADD COLUMN provider text;
        UPDATE ia.recomendaciones_ia SET provider = 'ollama' WHERE provider IS NULL;
        ALTER TABLE ia.recomendaciones_ia
          ALTER COLUMN provider SET NOT NULL,
          ALTER COLUMN provider SET DEFAULT 'ollama',
          ADD COLUMN profile_version_id uuid REFERENCES ia.reader_profile_versions(id) ON DELETE RESTRICT,
          ADD COLUMN job_id uuid REFERENCES ia.jobs(id) ON DELETE SET NULL;
        CREATE UNIQUE INDEX uq_ai_recommendation_profile_request
          ON ia.recomendaciones_ia(owner_user_id, profile_version_id, provider, model, version)
          WHERE profile_version_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_ai_recommendation_job
          ON ia.recomendaciones_ia(job_id) WHERE job_id IS NOT NULL;

        CREATE TABLE ia.usage_metrics (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          job_id uuid NOT NULL REFERENCES ia.jobs(id) ON DELETE RESTRICT,
          attempt integer NOT NULL CHECK (attempt > 0),
          provider text NOT NULL,
          model text NOT NULL,
          input_tokens integer NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
          output_tokens integer NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
          reasoning_tokens integer NOT NULL DEFAULT 0 CHECK (reasoning_tokens >= 0),
          cached_input_tokens integer NOT NULL DEFAULT 0 CHECK (cached_input_tokens >= 0),
          duration_ms bigint NOT NULL CHECK (duration_ms >= 0),
          final_status text NOT NULL CHECK (final_status IN ('succeeded', 'failed', 'cancelled')),
          estimated_cost_usd numeric(18,8) CHECK (estimated_cost_usd IS NULL OR estimated_cost_usd >= 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_ai_usage_job_attempt UNIQUE (job_id, attempt)
        );
        CREATE INDEX ix_ai_usage_provider_created
          ON ia.usage_metrics(provider, model, created_at DESC);

        COMMENT ON COLUMN ia.analyses.provider IS
          'Historical rows predate remote providers and were produced exclusively by the Ollama flow.';
        COMMENT ON COLUMN ia.recomendaciones_ia.provider IS
          'Historical rows predate remote providers and were produced exclusively by the Ollama flow.';
        COMMENT ON COLUMN ia.jobs.provider IS
          'Defaults to Ollama only for compatibility with the unchanged legacy enqueue function.';
        COMMENT ON COLUMN ia.recomendaciones_ia.version IS
          'Prompt version; retained under its historical column name for compatibility.';

        CREATE OR REPLACE VIEW analytics.recomendaciones_ia AS
          SELECT * FROM ia.recomendaciones_ia;

        REVOKE ALL ON ia.reader_profile_versions, ia.usage_metrics FROM PUBLIC;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "AI profile versions, event identities, provider lineage and usage metrics "
        "may contain new results; remove them only through a reviewed forward migration."
    )
