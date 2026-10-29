"""Empty, additive catalog identity/provenance structures; no data consolidation."""
from alembic import op

revision = "0055_catalog_foundation"
down_revision = "0054_gemini_ledger_dna"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("""
      CREATE TABLE app.operaciones_catalogo (
        id uuid PRIMARY KEY,
        actor_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
        operation_type text NOT NULL CHECK (operation_type IN ('library_add','admin_import','merge','reversal')),
        request_key text NOT NULL CHECK (length(trim(request_key)) BETWEEN 1 AND 200),
        request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
        source_work_id uuid REFERENCES app.obras(id) ON DELETE RESTRICT,
        target_work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
        reverses_operation_id uuid REFERENCES app.operaciones_catalogo(id) ON DELETE RESTRICT,
        identity_version bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
        reason text NOT NULL CHECK (length(trim(reason)) > 0),
        evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
        context jsonb NOT NULL CHECK (jsonb_typeof(context)='object'),
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_catalog_operation_request UNIQUE(actor_user_id,operation_type,request_key),
        CONSTRAINT uq_catalog_operation_actor UNIQUE(id,actor_user_id),
        CONSTRAINT uq_catalog_operation_target UNIQUE(id,target_work_id),
        CONSTRAINT uq_catalog_operation_pair UNIQUE(id,source_work_id,target_work_id),
        CONSTRAINT ck_catalog_operation_pair CHECK (
          (operation_type='merge' AND source_work_id IS NOT NULL AND source_work_id<>target_work_id)
          OR (operation_type<>'merge' AND source_work_id IS NULL)),
        CONSTRAINT ck_catalog_operation_reversal CHECK
          ((operation_type='reversal') = (reverses_operation_id IS NOT NULL))
      );
      CREATE INDEX ix_catalog_operations_target ON app.operaciones_catalogo(target_work_id,created_at);
      CREATE INDEX ix_catalog_operations_source ON app.operaciones_catalogo(source_work_id)
        WHERE source_work_id IS NOT NULL;
      CREATE TABLE app.referencias_obras (
        id uuid PRIMARY KEY,
        work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
        provider text NOT NULL CHECK (provider IN ('google-books','open-library')),
        reference_type text NOT NULL CHECK (reference_type IN ('work','volume','edition')),
        external_id text NOT NULL CHECK (length(trim(external_id)) BETWEEN 1 AND 200),
        verification_status text NOT NULL CHECK
          (verification_status IN ('provisional','confirmed','contradictory','rejected')),
        evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
        verified_by text,
        verified_at timestamptz,
        operation_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_catalog_reference_work UNIQUE(id,work_id),
        FOREIGN KEY(operation_id,work_id) REFERENCES app.operaciones_catalogo(id,target_work_id) ON DELETE RESTRICT,
        CONSTRAINT ck_catalog_reference_provider CHECK
          ((provider='google-books' AND reference_type='volume') OR
           (provider='open-library' AND reference_type IN ('work','edition'))),
        CONSTRAINT ck_catalog_reference_verified CHECK (verification_status<>'confirmed' OR
          (verified_at IS NOT NULL AND verified_by IS NOT NULL AND length(trim(verified_by))>0 AND evidence<>'{}'::jsonb))
      );
      CREATE UNIQUE INDEX uq_catalog_reference_binding ON app.referencias_obras(provider,reference_type,external_id)
        WHERE verification_status IN ('provisional','confirmed');
      CREATE INDEX ix_catalog_references_work ON app.referencias_obras(work_id);
      CREATE INDEX ix_catalog_references_operation ON app.referencias_obras(operation_id);
      CREATE TABLE app.incorporaciones_catalogo (
        id uuid PRIMARY KEY,
        operation_id uuid NOT NULL UNIQUE,
        actor_user_id uuid NOT NULL,
        origin text NOT NULL CHECK (origin IN ('library','admin_import')),
        work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
        edition_id uuid,
        edition_selected boolean NOT NULL DEFAULT false,
        library_entry_id uuid,
        reference_id uuid,
        requested_reference jsonb NOT NULL CHECK (jsonb_typeof(requested_reference)='object'),
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY(operation_id,actor_user_id) REFERENCES app.operaciones_catalogo(id,actor_user_id) ON DELETE RESTRICT,
        FOREIGN KEY(operation_id,work_id) REFERENCES app.operaciones_catalogo(id,target_work_id) ON DELETE RESTRICT,
        FOREIGN KEY(edition_id,work_id) REFERENCES app.ediciones(id,work_id) ON DELETE RESTRICT,
        FOREIGN KEY(library_entry_id,work_id) REFERENCES app.entradas_biblioteca(id,work_id) ON DELETE RESTRICT,
        FOREIGN KEY(reference_id,work_id) REFERENCES app.referencias_obras(id,work_id) ON DELETE RESTRICT,
        CONSTRAINT ck_catalog_incorporation_edition CHECK (edition_selected = (edition_id IS NOT NULL)),
        CONSTRAINT ck_catalog_incorporation_library CHECK
          ((origin='library' AND library_entry_id IS NOT NULL) OR (origin='admin_import' AND library_entry_id IS NULL))
      );
      CREATE INDEX ix_catalog_incorporations_work ON app.incorporaciones_catalogo(work_id,created_at);
      CREATE INDEX ix_catalog_incorporations_actor ON app.incorporaciones_catalogo(actor_user_id,created_at);
      CREATE TABLE app.redirecciones_obras (
        id uuid PRIMARY KEY,
        source_work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
        target_work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
        operation_id uuid NOT NULL UNIQUE,
        active_from timestamptz NOT NULL DEFAULT now(),
        retired_at timestamptz,
        retirement_operation_id uuid REFERENCES app.operaciones_catalogo(id) ON DELETE RESTRICT,
        FOREIGN KEY(operation_id,source_work_id,target_work_id)
          REFERENCES app.operaciones_catalogo(id,source_work_id,target_work_id) ON DELETE RESTRICT,
        CHECK(source_work_id<>target_work_id),
        CHECK((retired_at IS NULL AND retirement_operation_id IS NULL) OR
              (retired_at IS NOT NULL AND retirement_operation_id IS NOT NULL AND retired_at>=active_from))
      );
      CREATE UNIQUE INDEX uq_catalog_redirect_active ON app.redirecciones_obras(source_work_id) WHERE retired_at IS NULL;
      CREATE INDEX ix_catalog_redirect_target ON app.redirecciones_obras(target_work_id) WHERE retired_at IS NULL;
      CREATE TABLE app.efectos_operacion_catalogo (
        id uuid PRIMARY KEY,
        operation_id uuid NOT NULL REFERENCES app.operaciones_catalogo(id) ON DELETE RESTRICT,
        ordinal integer NOT NULL CHECK (ordinal>0),
        entity_table text NOT NULL CHECK(length(trim(entity_table))>0),
        entity_id uuid NOT NULL,
        before_state jsonb,
        after_state jsonb,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(operation_id,ordinal),
        CHECK(before_state IS NOT NULL OR after_state IS NOT NULL),
        CHECK(before_state IS NULL OR jsonb_typeof(before_state)='object'),
        CHECK(after_state IS NULL OR jsonb_typeof(after_state)='object')
      );
      CREATE INDEX ix_catalog_effects_entity ON app.efectos_operacion_catalogo(entity_table,entity_id);

      CREATE FUNCTION app.catalog_history_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        RAISE EXCEPTION 'Catalog history is append-only; use a compensating operation' USING ERRCODE='23514';
      END $$;
      CREATE TRIGGER catalog_operations_immutable BEFORE UPDATE OR DELETE ON app.operaciones_catalogo
        FOR EACH ROW EXECUTE FUNCTION app.catalog_history_immutable();
      CREATE TRIGGER catalog_effects_immutable BEFORE UPDATE OR DELETE ON app.efectos_operacion_catalogo
        FOR EACH ROW EXECUTE FUNCTION app.catalog_history_immutable();
      CREATE TRIGGER catalog_incorporations_immutable BEFORE UPDATE OR DELETE ON app.incorporaciones_catalogo
        FOR EACH ROW EXECUTE FUNCTION app.catalog_history_immutable();

      CREATE FUNCTION app.validate_catalog_incorporation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM app.operaciones_catalogo o WHERE o.id=NEW.operation_id
          AND o.operation_type=CASE NEW.origin WHEN 'library' THEN 'library_add' ELSE 'admin_import' END) OR
          (NEW.origin='library' AND NOT EXISTS(SELECT 1 FROM app.entradas_biblioteca b
            WHERE b.id=NEW.library_entry_id AND b.user_id=NEW.actor_user_id)) THEN
          RAISE EXCEPTION 'Incorporation origin or library owner mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER catalog_incorporation_validation BEFORE INSERT ON app.incorporaciones_catalogo
        FOR EACH ROW EXECUTE FUNCTION app.validate_catalog_incorporation();

      CREATE FUNCTION app.validate_catalog_redirect() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE cycle_found boolean;
      BEGIN
        -- All future identity writers must take this same transaction-level graph lock.
        PERFORM pg_advisory_xact_lock(73155,1);
        IF current_setting('transaction_isolation')<>'read committed' THEN
          RAISE EXCEPTION 'Catalog graph writes require READ COMMITTED and the graph lock' USING ERRCODE='25001';
        END IF;
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Preserve historical redirects' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' THEN
          IF (to_jsonb(NEW)-ARRAY['retired_at','retirement_operation_id']) IS DISTINCT FROM
             (to_jsonb(OLD)-ARRAY['retired_at','retirement_operation_id']) OR OLD.retired_at IS NOT NULL THEN
            RAISE EXCEPTION 'Redirect identity is immutable' USING ERRCODE='23514';
          END IF;
          IF NEW.retired_at IS NULL OR NOT EXISTS (
            SELECT 1 FROM app.operaciones_catalogo o WHERE o.id=NEW.retirement_operation_id
              AND o.operation_type='reversal' AND o.reverses_operation_id=OLD.operation_id) THEN
            RAISE EXCEPTION 'Retirement requires its compensating reversal' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END IF;
        IF NEW.retired_at IS NOT NULL THEN
          RAISE EXCEPTION 'New redirects must be active' USING ERRCODE='23514';
        END IF;
        WITH RECURSIVE path(id) AS (
          SELECT NEW.target_work_id
          UNION
          SELECT r.target_work_id FROM app.redirecciones_obras r JOIN path p ON r.source_work_id=p.id
            WHERE r.retired_at IS NULL
        ) SELECT EXISTS(SELECT 1 FROM path WHERE id=NEW.source_work_id) INTO cycle_found;
        IF cycle_found THEN
          RAISE EXCEPTION 'Canonical redirect cycle' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER catalog_redirect_validation BEFORE INSERT OR UPDATE OR DELETE ON app.redirecciones_obras
        FOR EACH ROW EXECUTE FUNCTION app.validate_catalog_redirect();
      REVOKE ALL ON app.operaciones_catalogo,app.referencias_obras,app.incorporaciones_catalogo,
        app.redirecciones_obras,app.efectos_operacion_catalogo FROM PUBLIC;
    """)


def downgrade():
    raise RuntimeError("Preserve catalog provenance and UUIDs; use a reviewed forward migration")
