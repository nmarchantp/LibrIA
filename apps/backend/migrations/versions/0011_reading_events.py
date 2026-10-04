"""Historial operacional y comentarios sobre eventos, sin duplicar posts."""

from alembic import op

revision = "0011_reading_events"
down_revision = "0010_profile_identities"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE app.eventos_lectura (
            id uuid PRIMARY KEY,
            reading_id uuid NOT NULL REFERENCES app.lecturas(id) ON DELETE RESTRICT,
            actor_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            kind text NOT NULL,
            previous_page integer NOT NULL,
            page integer NOT NULL,
            total_pages integer NOT NULL,
            is_public boolean NOT NULL DEFAULT false,
            reason text,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_eventos_lectura_kind CHECK (kind IN ('start', 'progress', 'correction', 'finish', 'abandon')),
            CONSTRAINT ck_eventos_lectura_pages CHECK (total_pages > 0 AND page BETWEEN 0 AND total_pages AND previous_page BETWEEN 0 AND total_pages),
            CONSTRAINT ck_eventos_lectura_correction CHECK (kind <> 'correction' OR (reason IS NOT NULL AND length(trim(reason)) > 0 AND NOT is_public))
        );
        CREATE INDEX ix_eventos_lectura_reading ON app.eventos_lectura(reading_id, created_at);
        ALTER TABLE app.comentarios_publicacion ALTER COLUMN post_id DROP NOT NULL;
        ALTER TABLE app.comentarios_publicacion ADD COLUMN reading_event_id uuid REFERENCES app.eventos_lectura(id) ON DELETE RESTRICT;
        ALTER TABLE app.comentarios_publicacion ADD CONSTRAINT ck_comentarios_destino CHECK (num_nonnulls(post_id, reading_event_id) = 1);
        CREATE INDEX ix_comentarios_reading_event ON app.comentarios_publicacion(reading_event_id);
    """)


def downgrade():
    raise RuntimeError("Restaurar respaldo: el historial operacional no se elimina automáticamente.")
