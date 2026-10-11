"""Reseñas propias, historial y migración conservadora del contenido legado."""
from alembic import op

revision = "0016_normalized_reviews"
down_revision = "0015_analytics_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE app.resenas (
            id uuid PRIMARY KEY,
            author_profile_id uuid NOT NULL REFERENCES app.perfiles(id) ON DELETE RESTRICT,
            created_by_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            work_id uuid NOT NULL REFERENCES app.obras(id) ON DELETE RESTRICT,
            edition_id uuid,
            body text NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 3000),
            rating integer CHECK (rating BETWEEN 1 AND 5),
            is_spoiler boolean NOT NULL DEFAULT false,
            status text NOT NULL CHECK (status IN ('draft','published','hidden')),
            published_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            revision_number integer NOT NULL DEFAULT 1 CHECK (revision_number > 0),
            CONSTRAINT uq_resenas_perfil_obra UNIQUE (author_profile_id, work_id),
            CONSTRAINT fk_resenas_edicion_obra FOREIGN KEY (edition_id, work_id) REFERENCES app.ediciones(id, work_id) ON DELETE RESTRICT,
            CONSTRAINT ck_resenas_publicacion CHECK (
                (status='draft' AND published_at IS NULL) OR
                (status IN ('published','hidden') AND published_at IS NOT NULL AND published_at >= created_at)),
            CONSTRAINT ck_resenas_fechas CHECK (updated_at >= created_at)
        );
        CREATE INDEX ix_resenas_obra_publicacion ON app.resenas(work_id, published_at);
        CREATE TABLE app.revisiones_resena (
            review_id uuid NOT NULL REFERENCES app.resenas(id) ON DELETE RESTRICT,
            revision_number integer NOT NULL,
            recorded_by_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            body text NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 3000),
            rating integer CHECK (rating BETWEEN 1 AND 5),
            is_spoiler boolean NOT NULL,
            status text NOT NULL CHECK (status IN ('draft','published','hidden')),
            edition_id uuid REFERENCES app.ediciones(id) ON DELETE RESTRICT,
            recorded_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (review_id, revision_number)
        );
        CREATE INDEX ix_revisiones_resena_corte ON app.revisiones_resena(review_id, recorded_at);
        CREATE TABLE app.imagenes_resena (
            id uuid PRIMARY KEY,
            review_id uuid NOT NULL REFERENCES app.resenas(id) ON DELETE CASCADE,
            content_type varchar(20) NOT NULL,
            data bytea NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_imagenes_resena_review ON app.imagenes_resena(review_id);
        CREATE TABLE app.me_gusta_resena (
            review_id uuid NOT NULL REFERENCES app.resenas(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (review_id, user_id)
        );
        CREATE TABLE app.migraciones_resenas (
            legacy_post_id uuid PRIMARY KEY REFERENCES app.publicaciones(id) ON DELETE RESTRICT,
            review_id uuid REFERENCES app.resenas(id) ON DELETE RESTRICT,
            result text NOT NULL CHECK (result IN ('migrated','pending')),
            reason_code text NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now()
        );
        ALTER TABLE app.comentarios_publicacion ADD COLUMN review_id uuid REFERENCES app.resenas(id) ON DELETE RESTRICT;
        ALTER TABLE app.comentarios_publicacion DROP CONSTRAINT ck_comentarios_destino;
        ALTER TABLE app.comentarios_publicacion ADD CONSTRAINT ck_comentarios_destino CHECK (num_nonnulls(post_id, reading_event_id, review_id)=1);
        CREATE INDEX ix_comentarios_review ON app.comentarios_publicacion(review_id);

        CREATE TEMP TABLE review_candidates ON COMMIT DROP AS
        SELECT p.*, COALESCE(p.author_profile_id, own.id) AS resolved_profile,
            pr.kind AS profile_kind, pr.owner_user_id, e.work_id AS resolved_work,
            e.id AS resolved_edition,
            count(*) OVER (PARTITION BY COALESCE(p.author_profile_id, own.id), e.work_id) AS pair_count
        FROM app.publicaciones p
        LEFT JOIN app.perfiles own ON own.owner_user_id=p.user_id AND own.kind='personal'
        LEFT JOIN app.perfiles pr ON pr.id=COALESCE(p.author_profile_id, own.id)
        LEFT JOIN app.fuentes_catalogo s ON s.provider='libria-feed' AND s.external_id=p.book_ref
        LEFT JOIN app.ediciones e ON e.id=s.edition_id
        WHERE p.source='review';

        ALTER TABLE review_candidates ADD COLUMN reason_code text;
        UPDATE review_candidates SET reason_code=CASE
            WHEN resolved_profile IS NULL OR profile_kind <> 'personal' OR owner_user_id <> user_id THEN 'profile_unresolved'
            WHEN resolved_work IS NULL THEN 'work_unresolved'
            WHEN kind <> 'reviews' OR length(trim(body)) NOT BETWEEN 1 AND 3000 OR (rating IS NOT NULL AND rating NOT BETWEEN 1 AND 5) THEN 'invalid_contract'
            WHEN pair_count > 1 THEN 'duplicate_profile_work'
            ELSE 'verified' END;
        INSERT INTO app.resenas (id, author_profile_id, created_by_user_id, work_id, edition_id,
            body, rating, status, published_at, created_at, updated_at)
        SELECT id, resolved_profile, user_id, resolved_work, resolved_edition, trim(body), rating,
            'published', created_at, created_at, created_at FROM review_candidates WHERE reason_code='verified';
        INSERT INTO app.revisiones_resena (review_id, revision_number, recorded_by_user_id, body,
            rating, is_spoiler, status, edition_id)
        SELECT id, 1, created_by_user_id, body, rating, is_spoiler, status, edition_id FROM app.resenas;
        INSERT INTO app.migraciones_resenas (legacy_post_id, review_id, result, reason_code)
        SELECT id, CASE WHEN reason_code='verified' THEN id END,
            CASE WHEN reason_code='verified' THEN 'migrated' ELSE 'pending' END, reason_code FROM review_candidates;
        INSERT INTO app.imagenes_resena (id, review_id, content_type, data, created_at)
        SELECT i.id, m.review_id, i.content_type, i.data, i.created_at FROM app.imagenes_publicacion i
        JOIN app.migraciones_resenas m ON m.legacy_post_id=i.post_id AND m.result='migrated';
        INSERT INTO app.me_gusta_resena (review_id, user_id, created_at)
        SELECT m.review_id, l.user_id, l.created_at FROM app.me_gusta_publicacion l
        JOIN app.migraciones_resenas m ON m.legacy_post_id=l.post_id AND m.result='migrated';
        UPDATE app.comentarios_publicacion c SET post_id=NULL, review_id=m.review_id
        FROM app.migraciones_resenas m WHERE c.post_id=m.legacy_post_id AND m.result='migrated';
        INSERT INTO app.procedencia_demo (entity_type, entity_id, dataset_version)
        SELECT 'review', m.review_id, p.dataset_version FROM app.procedencia_demo p
        JOIN app.migraciones_resenas m ON m.legacy_post_id=p.entity_id AND m.result='migrated'
        WHERE p.entity_type='post' ON CONFLICT DO NOTHING;

        ALTER TABLE app.publicaciones ADD COLUMN legacy_content boolean NOT NULL DEFAULT false;
        UPDATE app.publicaciones SET legacy_content=true WHERE source IN ('review','reading');
        ALTER TABLE app.publicaciones ADD CONSTRAINT ck_publicaciones_manual CHECK (
            legacy_content OR (source IN ('community','event') AND kind='community'
            AND rating IS NULL AND progress_percent IS NULL AND reading_event IS NULL));

        CREATE FUNCTION app.validate_review_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM app.perfiles WHERE id=NEW.author_profile_id
                AND kind='personal' AND owner_user_id=NEW.created_by_user_id) THEN
                RAISE EXCEPTION 'Review requires its personal profile owner' USING ERRCODE='23514';
            END IF;
            IF TG_OP='UPDATE' AND (NEW.work_id IS DISTINCT FROM OLD.work_id OR
                NEW.author_profile_id IS DISTINCT FROM OLD.author_profile_id OR
                NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
                NEW.created_at IS DISTINCT FROM OLD.created_at OR
                (OLD.published_at IS NOT NULL AND NEW.published_at IS DISTINCT FROM OLD.published_at)) THEN
                RAISE EXCEPTION 'Review identity and first publication are immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER validate_review_identity BEFORE INSERT OR UPDATE ON app.resenas
            FOR EACH ROW EXECUTE FUNCTION app.validate_review_identity();
    """)


def downgrade():
    raise RuntimeError("Restaurar respaldo para conservar reseñas, versiones e interacciones.")
