"""Imágenes e interacciones para publicaciones del mural."""

from alembic import op

revision = "0013_post_interactions_media"
down_revision = "0012_content_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE app.imagenes_publicacion (
            id uuid PRIMARY KEY,
            post_id uuid NOT NULL REFERENCES app.publicaciones(id) ON DELETE CASCADE,
            content_type varchar(20) NOT NULL,
            data bytea NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_imagenes_publicacion_post ON app.imagenes_publicacion(post_id);

        CREATE TABLE app.me_gusta_publicacion (
            post_id uuid NOT NULL REFERENCES app.publicaciones(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (post_id, user_id)
        );

        CREATE TABLE app.seguimientos_perfil (
            profile_id uuid NOT NULL REFERENCES app.perfiles(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (profile_id, user_id)
        );
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.seguimientos_perfil;
        DROP TABLE app.me_gusta_publicacion;
        DROP TABLE app.imagenes_publicacion;
    """)
