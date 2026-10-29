"""Bind recommendation profiles to successful nightly ETL cutoffs.

Revision ID: 0050_nightly_reader_profiles
Revises: 0049_ai_persistence_gemini

0049 prepared the provider-neutral persistence layer, but associated reader
profiles with incremental projection runs.  Nightly recommendation profiles
belong to analytics.ejecuciones_etl instead.  This forward-only correction
keeps the former projection reference nullable for any rows created while
0049 was deployed and records the outcome of every reader/nightly-cutoff pair.
"""

from alembic import op


revision = "0050_nightly_reader_profiles"
down_revision = "0049_ai_persistence_gemini"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ia.reader_profile_versions
          DROP CONSTRAINT fk_reader_profile_run_owner,
          DROP CONSTRAINT uq_reader_profile_owner_run;

        ALTER TABLE ia.reader_profile_versions
          RENAME COLUMN analytics_run_id TO projection_run_id;

        ALTER TABLE ia.reader_profile_versions
          ALTER COLUMN projection_run_id DROP NOT NULL,
          ADD CONSTRAINT fk_reader_profile_projection_run
            FOREIGN KEY (projection_run_id)
            REFERENCES analytics.projection_runs(id) ON DELETE RESTRICT,
          ADD COLUMN etl_run_id uuid
            REFERENCES analytics.ejecuciones_etl(id) ON DELETE RESTRICT,
          ADD COLUMN payload jsonb,
          ADD CONSTRAINT ck_reader_profile_payload CHECK (
            payload IS NULL OR (
              jsonb_typeof(payload) = 'object'
              AND payload->>'hash_version' = 'recommendation-profile-v1'
              AND jsonb_typeof(payload->'books') = 'array'
            )
          ),
          ADD CONSTRAINT uq_reader_profile_id_owner UNIQUE (id, owner_id);

        CREATE UNIQUE INDEX uq_reader_profile_owner_etl_run
          ON ia.reader_profile_versions(owner_id, etl_run_id)
          WHERE etl_run_id IS NOT NULL;

        CREATE TABLE ia.reader_profile_etl_states (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          owner_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
          etl_run_id uuid NOT NULL
            REFERENCES analytics.ejecuciones_etl(id) ON DELETE RESTRICT,
          profile_version_id uuid,
          outcome text NOT NULL CHECK (
            outcome IN ('empty', 'eligible_pending', 'unchanged')
          ),
          eligible_books_count integer NOT NULL CHECK (eligible_books_count >= 0),
          context_bytes bigint NOT NULL CHECK (context_bytes >= 0),
          estimated_tokens bigint NOT NULL CHECK (estimated_tokens >= 0),
          requires_segmentation boolean NOT NULL DEFAULT false,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_reader_profile_etl_state UNIQUE (owner_id, etl_run_id),
          CONSTRAINT fk_reader_profile_etl_state_owner
            FOREIGN KEY (profile_version_id, owner_id)
            REFERENCES ia.reader_profile_versions(id, owner_id) ON DELETE RESTRICT,
          CONSTRAINT ck_reader_profile_etl_state_profile CHECK (
            (outcome = 'empty' AND profile_version_id IS NULL
              AND eligible_books_count = 0)
            OR (outcome IN ('eligible_pending', 'unchanged')
              AND profile_version_id IS NOT NULL
              AND eligible_books_count > 0)
          )
        );
        CREATE INDEX ix_reader_profile_etl_state_latest
          ON ia.reader_profile_etl_states(owner_id, created_at DESC);

        ALTER TABLE ia.recomendaciones_ia
          ADD COLUMN is_current boolean NOT NULL DEFAULT true,
          ADD COLUMN invalidated_at timestamptz,
          ADD COLUMN invalidated_by_etl_run_id uuid
            REFERENCES analytics.ejecuciones_etl(id) ON DELETE RESTRICT,
          ADD CONSTRAINT ck_ai_recommendation_invalidation CHECK (
            (is_current AND invalidated_at IS NULL
              AND invalidated_by_etl_run_id IS NULL)
            OR (NOT is_current AND invalidated_at IS NOT NULL
              AND invalidated_by_etl_run_id IS NOT NULL)
          );
        CREATE INDEX ix_ai_recommendation_current
          ON ia.recomendaciones_ia(owner_user_id, created_at DESC)
          WHERE is_current;

        COMMENT ON COLUMN ia.reader_profile_versions.projection_run_id IS
          'Legacy 0049 association only; nightly profiles use etl_run_id.';
        COMMENT ON COLUMN ia.reader_profile_versions.etl_run_id IS
          'First successful daily ETL cutoff that produced this content version.';
        COMMENT ON TABLE ia.reader_profile_etl_states IS
          'One idempotent outcome per reader and successful daily ETL cutoff.';

        CREATE OR REPLACE VIEW analytics.recomendaciones_ia AS
          SELECT * FROM ia.recomendaciones_ia;

        REVOKE ALL ON ia.reader_profile_etl_states FROM PUBLIC;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Nightly profile lineage and recommendation invalidations preserve "
        "historical state; reverse them only through a reviewed forward migration."
    )
