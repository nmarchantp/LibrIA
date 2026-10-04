"""Agrega identidades sin convertir cuentas compartidas ni borrar historia."""

from alembic import op

revision = "0010_profile_identities"
down_revision = "0009_profile_role_changes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE app.perfiles (
            id uuid PRIMARY KEY,
            kind varchar(20) NOT NULL,
            owner_user_id uuid REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            display_name varchar(100) NOT NULL,
            verification_status varchar(20) NOT NULL DEFAULT 'pending',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_perfiles_kind CHECK (kind IN ('personal', 'organization')),
            CONSTRAINT ck_perfiles_owner CHECK ((kind = 'personal' AND owner_user_id IS NOT NULL) OR (kind = 'organization' AND owner_user_id IS NULL)),
            CONSTRAINT ck_perfiles_verification CHECK (verification_status IN ('pending', 'verified', 'rejected', 'suspended')),
            CONSTRAINT ck_perfiles_name CHECK (length(trim(display_name)) BETWEEN 2 AND 100)
        );
        CREATE UNIQUE INDEX uq_perfiles_owner ON app.perfiles(owner_user_id) WHERE owner_user_id IS NOT NULL;
        CREATE TABLE app.capacidades_perfil (
            profile_id uuid NOT NULL REFERENCES app.perfiles(id) ON DELETE CASCADE,
            capability varchar(20) NOT NULL,
            PRIMARY KEY (profile_id, capability),
            CONSTRAINT ck_capacidades_perfil_value CHECK (capability IN ('lector', 'autor', 'influencer'))
        );
        CREATE TABLE app.miembros_perfil (
            profile_id uuid NOT NULL REFERENCES app.perfiles(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            permission varchar(20) NOT NULL,
            PRIMARY KEY (profile_id, user_id),
            CONSTRAINT ck_miembros_perfil_permission CHECK (permission IN ('admin', 'editor'))
        );
        CREATE TABLE app.permisos_cuenta (
            user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE CASCADE,
            permission varchar(20) NOT NULL,
            PRIMARY KEY (user_id, permission),
            CONSTRAINT ck_permisos_cuenta_permission CHECK (permission = 'admin')
        );
        CREATE TABLE app.auditoria_identidades (
            id uuid PRIMARY KEY,
            profile_id uuid NOT NULL REFERENCES app.perfiles(id) ON DELETE RESTRICT,
            actor_user_id uuid NOT NULL REFERENCES app.usuarios(id) ON DELETE RESTRICT,
            action varchar(50) NOT NULL,
            detail text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_auditoria_identidades_profile_id ON app.auditoria_identidades(profile_id);
        INSERT INTO app.perfiles (id, kind, owner_user_id, display_name)
            SELECT gen_random_uuid(), 'personal', id, display_name FROM app.usuarios WHERE role <> 'libreria';
        INSERT INTO app.capacidades_perfil (profile_id, capability)
            SELECT id, 'lector' FROM app.perfiles WHERE kind = 'personal';
        INSERT INTO app.capacidades_perfil (profile_id, capability)
            SELECT p.id, u.role FROM app.perfiles p JOIN app.usuarios u ON u.id = p.owner_user_id
            WHERE u.role IN ('autor', 'influencer');
        INSERT INTO app.permisos_cuenta (user_id, permission)
            SELECT id, 'admin' FROM app.usuarios WHERE role = 'admin';
    """)


def downgrade():
    raise RuntimeError("Esta migración conserva identidades: restaura un respaldo para revertirla sin perder datos.")
