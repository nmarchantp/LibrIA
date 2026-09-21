"""Publicaciones y resumen de actividad."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_social_analytics"
down_revision = "0003_catalogo_lecturas"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    op.create_table("publicaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(body)) > 0", name="ck_publicaciones_body"),
        schema="app")
    op.create_index("ix_app_publicaciones_user_id", "publicaciones", ["user_id"], schema="app")
    op.create_index("ix_publicaciones_created_at", "publicaciones", ["created_at"], schema="app")
    op.create_table("ejecuciones_etl",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("source_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transform_version", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(100)),
        schema="analytics")
    op.create_table("instantaneas_actividad",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("etl_run_id", sa.Uuid(), sa.ForeignKey("analytics.ejecuciones_etl.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="analytics")
    op.create_index("ix_instantaneas_actividad_period", "instantaneas_actividad", ["period_start", "period_end"], schema="analytics")


def downgrade():
    op.drop_index("ix_instantaneas_actividad_period", table_name="instantaneas_actividad", schema="analytics")
    op.drop_table("instantaneas_actividad", schema="analytics")
    op.drop_table("ejecuciones_etl", schema="analytics")
    op.drop_index("ix_publicaciones_created_at", table_name="publicaciones", schema="app")
    op.drop_index("ix_app_publicaciones_user_id", table_name="publicaciones", schema="app")
    op.drop_table("publicaciones", schema="app")
