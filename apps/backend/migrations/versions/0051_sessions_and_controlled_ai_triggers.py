"""Add revocable sessions and stop broad legacy AI enqueue triggers.

Revision ID: 0051_sessions_controlled_ai
Revises: 0050_nightly_reader_profiles

Projection triggers are intentionally untouched. Individual reading jobs are
created by the transactional reading-event command so deployment configuration
supplies provider/model/prompt and the consolidation delay.
"""

from alembic import op


revision = "0051_sessions_controlled_ai"
down_revision = "0050_nightly_reader_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE app.sesiones_autenticacion (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
          refresh_token_hash varchar(64) NOT NULL UNIQUE
            CHECK (length(refresh_token_hash) = 64),
          refresh_generation bigint NOT NULL DEFAULT 1 CHECK (refresh_generation > 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          last_activity_at timestamptz NOT NULL DEFAULT now(),
          inactivity_expires_at timestamptz NOT NULL,
          absolute_expires_at timestamptz NOT NULL,
          revoked_at timestamptz,
          revocation_reason text,
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_auth_session_times CHECK (
            created_at <= last_activity_at
            AND last_activity_at < inactivity_expires_at
            AND inactivity_expires_at <= absolute_expires_at
          ),
          CONSTRAINT ck_auth_session_revocation CHECK (
            (revoked_at IS NULL AND revocation_reason IS NULL)
            OR (revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)
          )
        );
        CREATE INDEX ix_auth_session_user_active
          ON app.sesiones_autenticacion(user_id, inactivity_expires_at DESC)
          WHERE revoked_at IS NULL;
        CREATE INDEX ix_auth_session_expiration
          ON app.sesiones_autenticacion(inactivity_expires_at, absolute_expires_at)
          WHERE revoked_at IS NULL;
        REVOKE ALL ON app.sesiones_autenticacion FROM PUBLIC;

        COMMENT ON TABLE app.sesiones_autenticacion IS
          'Revocable browser sessions. Refresh credentials are stored only as SHA-256 hashes.';
        COMMENT ON COLUMN app.sesiones_autenticacion.inactivity_expires_at IS
          'Extended only after explicit user activity, never by refresh or polling.';
        COMMENT ON COLUMN app.sesiones_autenticacion.absolute_expires_at IS
          'Non-renewable maximum lifetime configured independently from inactivity.';

        DROP TRIGGER IF EXISTS projection_explicit_note ON app.publicaciones;
        DROP FUNCTION IF EXISTS analytics.explicit_note_changed();

        CREATE OR REPLACE FUNCTION ia.book_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE uid uuid; wid uuid; entry_id uuid; ref text; kind text;
        BEGIN
          -- Broad source changes no longer enqueue AI work. Privacy-driven source
          -- removals retain the historical row but scrub its derived narrative.
          IF TG_TABLE_NAME='entradas_biblioteca' THEN
            IF TG_OP='INSERT' OR (TG_OP='UPDATE'
               AND NEW.archived_at IS NOT DISTINCT FROM OLD.archived_at) THEN
              RETURN COALESCE(NEW,OLD);
            END IF;
            uid:=COALESCE(NEW.user_id,OLD.user_id); wid:=COALESCE(NEW.work_id,OLD.work_id);
          ELSIF TG_TABLE_NAME='resenas' THEN
            IF TG_OP <> 'DELETE' THEN RETURN COALESCE(NEW,OLD); END IF;
            SELECT p.owner_user_id INTO uid FROM app.perfiles p
              WHERE p.id=OLD.author_profile_id AND p.kind='personal';
            wid:=OLD.work_id;
          ELSIF TG_TABLE_NAME='publicaciones' THEN
            IF TG_OP <> 'DELETE' THEN RETURN COALESCE(NEW,OLD); END IF;
            kind:=OLD.publication_type;
            IF kind NOT IN ('note','theory') THEN RETURN COALESCE(NEW,OLD); END IF;
            SELECT p.owner_user_id INTO uid FROM app.perfiles p
              WHERE p.id=OLD.author_profile_id AND p.kind='personal';
            ref:=OLD.book_ref;
            SELECT CASE WHEN count(DISTINCT ed.work_id)=1 THEN min(ed.work_id::text)::uuid END INTO wid
              FROM app.fuentes_catalogo s JOIN app.ediciones ed ON ed.id=s.edition_id
              WHERE s.external_id=ref;
          ELSE
            RETURN COALESCE(NEW,OLD);
          END IF;
          IF uid IS NULL OR wid IS NULL THEN RETURN COALESCE(NEW,OLD); END IF;
          UPDATE ia.analyses SET valid=false,content='{}' WHERE owner_id=uid
            AND target IN ('profile','book:'||wid::text);
          UPDATE ia.feedback f SET original_interpretation='{}', information='[Origen retirado]'
            FROM ia.analyses a WHERE a.id=f.analysis_id AND a.owner_id=uid
            AND a.target IN ('profile','book:'||wid::text);
          RETURN COALESCE(NEW,OLD);
        END $$;

        COMMENT ON FUNCTION ia.book_changed() IS
          'Legacy source invalidation only. It intentionally never creates AI jobs.';
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Revocable session state and controlled AI trigger semantics must be preserved; "
        "reverse them only through a reviewed forward migration."
    )
