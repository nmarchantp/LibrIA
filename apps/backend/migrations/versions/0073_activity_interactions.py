"""Add reading-event likes and unique intentional activity views; no backfill."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0073_activity_interactions"
down_revision = "0072_story_cat_illustration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("me_gusta_evento_lectura",
        sa.Column("reading_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.eventos_lectura.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.usuarios.id", ondelete="RESTRICT"), primary_key=True), schema="app")
    op.create_table("visualizaciones_actividad",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.publicaciones.id", ondelete="RESTRICT")),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.resenas.id", ondelete="RESTRICT")),
        sa.Column("reading_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app.eventos_lectura.id", ondelete="RESTRICT")),
        sa.CheckConstraint("num_nonnulls(post_id, review_id, reading_event_id) = 1", name="ck_visualizaciones_destino"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_visualizacion_publicacion_usuario"),
        sa.UniqueConstraint("review_id", "user_id", name="uq_visualizacion_resena_usuario"),
        sa.UniqueConstraint("reading_event_id", "user_id", name="uq_visualizacion_evento_usuario"), schema="app")
    op.create_index("ix_comentarios_evento_created", "comentarios_publicacion", ["reading_event_id", "created_at"], schema="app")
    op.create_index("ix_comentarios_resena_created", "comentarios_publicacion", ["review_id", "created_at"], schema="app")


def downgrade():
    # Intentionally refuse to erase persisted social interactions.
    raise RuntimeError("La reversión requiere una migración de conservación de interacciones")
