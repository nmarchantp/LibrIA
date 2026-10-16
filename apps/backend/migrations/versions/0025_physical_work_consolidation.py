"""Allow an atomic, controlled reassignment when duplicate works are consolidated."""

from alembic import op

revision = "0025_physical_work_consolidation"
down_revision = "0024_catalog_rules_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE app.lecturas DROP CONSTRAINT fk_lecturas_edicion_obra;
        ALTER TABLE app.lecturas ADD CONSTRAINT fk_lecturas_edicion_obra
            FOREIGN KEY (edition_id, work_id) REFERENCES app.ediciones(id, work_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY IMMEDIATE;
        ALTER TABLE app.lecturas DROP CONSTRAINT fk_lecturas_biblioteca_obra;
        ALTER TABLE app.lecturas ADD CONSTRAINT fk_lecturas_biblioteca_obra
            FOREIGN KEY (library_entry_id, work_id)
            REFERENCES app.entradas_biblioteca(id, work_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY IMMEDIATE;
        ALTER TABLE app.resenas DROP CONSTRAINT fk_resenas_edicion_obra;
        ALTER TABLE app.resenas ADD CONSTRAINT fk_resenas_edicion_obra
            FOREIGN KEY (edition_id, work_id) REFERENCES app.ediciones(id, work_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY IMMEDIATE;

        CREATE OR REPLACE FUNCTION app.validate_review_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM app.perfiles WHERE id=NEW.author_profile_id
                AND kind='personal' AND owner_user_id=NEW.created_by_user_id) THEN
                RAISE EXCEPTION 'Review requires its personal profile owner' USING ERRCODE='23514';
            END IF;
            IF TG_OP='UPDATE' AND (NEW.author_profile_id IS DISTINCT FROM OLD.author_profile_id OR
                NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
                NEW.created_at IS DISTINCT FROM OLD.created_at OR
                (OLD.published_at IS NOT NULL AND NEW.published_at IS DISTINCT FROM OLD.published_at) OR
                (NEW.work_id IS DISTINCT FROM OLD.work_id AND
                 current_setting('app.catalog_merge', true) IS DISTINCT FROM 'on')) THEN
                RAISE EXCEPTION 'Review identity and first publication are immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
    """)


def downgrade():
    raise RuntimeError("Restaurar respaldo: esta migracion habilita consolidaciones irreversibles de obras.")
