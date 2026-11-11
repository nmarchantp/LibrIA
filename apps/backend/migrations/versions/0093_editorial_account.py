"""Allow the existing editorial publishing identity as an exclusive account role."""
from alembic import op

revision = '0093_editorial_account'
down_revision = '0092_influencer_access'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app.usuarios DROP CONSTRAINT ck_usuarios_role")
    op.execute("ALTER TABLE app.usuarios ADD CONSTRAINT ck_usuarios_role CHECK(role IN ('lector','influencer','autor','libreria','editorial','admin'))")
    op.execute("ALTER TABLE app.solicitudes_verificacion DROP CONSTRAINT ck_solicitudes_verificacion_role")
    op.execute("ALTER TABLE app.solicitudes_verificacion ADD CONSTRAINT ck_solicitudes_verificacion_role CHECK(requested_role IN ('influencer','autor','libreria','editorial'))")


def downgrade():
    # Existing editorial accounts/requests must be handled explicitly; never convert or delete them.
    op.execute("ALTER TABLE app.solicitudes_verificacion DROP CONSTRAINT ck_solicitudes_verificacion_role")
    op.execute("ALTER TABLE app.solicitudes_verificacion ADD CONSTRAINT ck_solicitudes_verificacion_role CHECK(requested_role IN ('influencer','autor','libreria'))")
    op.execute("ALTER TABLE app.usuarios DROP CONSTRAINT ck_usuarios_role")
    op.execute("ALTER TABLE app.usuarios ADD CONSTRAINT ck_usuarios_role CHECK(role IN ('lector','influencer','autor','libreria','admin'))")
