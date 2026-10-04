"""Perfiles autores y tipos organizacionales sin reinterpretar autores legados."""
from alembic import op

revision = "0012_content_profiles"
down_revision = "0011_reading_events"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE app.perfiles ADD COLUMN organization_type varchar(20);
        ALTER TABLE app.perfiles ADD CONSTRAINT ck_perfiles_org_type CHECK (
            (kind = 'personal' AND organization_type IS NULL) OR
            (kind = 'organization' AND organization_type IN ('libreria', 'editorial')));
        ALTER TABLE app.publicaciones ADD COLUMN author_profile_id uuid REFERENCES app.perfiles(id) ON DELETE RESTRICT;
        ALTER TABLE app.publicaciones ADD COLUMN publication_type varchar(20);
        ALTER TABLE app.publicaciones ADD CONSTRAINT ck_publicaciones_type CHECK (publication_type IN ('free', 'event', 'promotion', 'news', 'launch', 'institutional'));
        ALTER TABLE app.comentarios_publicacion ADD COLUMN author_profile_id uuid REFERENCES app.perfiles(id) ON DELETE RESTRICT;
    """)


def downgrade():
    raise RuntimeError("Restaurar respaldo para conservar la autoría de contenidos.")
