"""No atribuir origen real a registros sin procedencia acreditada."""
from alembic import op

revision = "0015_analytics_provenance"
down_revision = "0014_daily_analytics"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("hechos_lectura", "hechos_publicaciones", "indicadores_personales"):
        op.execute(f"ALTER TABLE analytics.{table} DROP CONSTRAINT {table}_provenance_check")
        op.execute(f"ALTER TABLE analytics.{table} ADD CONSTRAINT {table}_provenance_check CHECK (provenance IN ('operational','simulated','unclassified'))")
        # 'operational' indicaba tabla de origen en la primera carga, no datos reales.
        op.execute(f"UPDATE analytics.{table} SET provenance='unclassified' WHERE provenance='operational'")


def downgrade():
    raise RuntimeError("La procedencia desconocida no se convierte automáticamente en real.")
