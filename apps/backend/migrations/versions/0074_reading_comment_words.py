"""Allow reading-event comments beyond 1000 characters; retain historical rows."""
from alembic import op

revision = "0074_reading_comment_words"
down_revision = "0073_activity_interactions"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_comentarios_publicacion_body", "comentarios_publicacion", schema="app", type_="check")
    # The API validates 200 words on new reading comments. Do not reject or rewrite
    # historical comments that may contain more words under the old character cap.
    op.create_check_constraint("ck_comentarios_publicacion_body", "comentarios_publicacion",
        "length(trim(body)) >= 1 AND (reading_event_id IS NOT NULL OR length(trim(body)) <= 1000)", schema="app")


def downgrade():
    raise RuntimeError("La reversión podría invalidar comentarios de lectura existentes; requiere una migración de conservación.")
