"""Registra solicitudes de autor e influencer para aprobación administrativa."""

from alembic import op
import sqlalchemy as sa

revision = "0008_verification_requests"
down_revision = "0007_post_book_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitudes_verificacion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app.usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_role", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("app.usuarios.id", ondelete="SET NULL")),
        sa.CheckConstraint("requested_role IN ('influencer', 'autor')", name="ck_solicitudes_verificacion_role"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_solicitudes_verificacion_status"),
        schema="app",
    )
    op.create_index("uq_solicitudes_verificacion_pending_user", "solicitudes_verificacion", ["user_id"],
                    unique=True, postgresql_where=sa.text("status = 'pending'"), schema="app")


def downgrade() -> None:
    op.drop_index("uq_solicitudes_verificacion_pending_user", table_name="solicitudes_verificacion", schema="app")
    op.drop_table("solicitudes_verificacion", schema="app")
