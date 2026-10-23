"""Independent controlled catalogs and explicit account literary preferences."""
from alembic import op
import sqlalchemy as sa

revision = "0043_literary_preferences"
down_revision = "0042_google_email_verification"
branch_labels = None
depends_on = None

GENRES = [
    ("fantasia", "Fantasía"), ("romance", "Romance"), ("ciencia-ficcion", "Ciencia ficción"),
    ("misterio", "Misterio"), ("thriller", "Thriller"), ("terror", "Terror"),
    ("historica", "Ficción histórica"), ("aventura", "Aventura"), ("contemporanea", "Ficción contemporánea"),
    ("poesia", "Poesía"), ("ensayo", "Ensayo"), ("biografia", "Biografía y memorias"),
    ("no-ficcion", "No ficción"), ("infantil", "Literatura infantil"), ("juvenil", "Literatura juvenil"),
]
TROPES = [
    ("magia", "Magia"), ("vampiros", "Vampiros"), ("brujas", "Brujas"), ("dragones", "Dragones"),
    ("enemigos-a-amantes", "Enemigos a amantes"), ("amigos-a-amantes", "Amigos a amantes"),
    ("romance-lento", "Romance lento"), ("amor-prohibido", "Amor prohibido"),
    ("familia-encontrada", "Familia encontrada"), ("academias-magicas", "Academias mágicas"),
    ("viajes-en-el-tiempo", "Viajes en el tiempo"), ("mundos-distopicos", "Mundos distópicos"),
    ("criaturas-feericas", "Criaturas feéricas"), ("misterios-sobrenaturales", "Misterios sobrenaturales"),
    ("reinos-encantados", "Reinos encantados"),
]


def upgrade():
    # Fail visibly rather than silently reuse an unexpected pre-existing table.
    existing = set(sa.inspect(op.get_bind()).get_table_names(schema="app"))
    expected = {"catalogo_generos", "catalogo_tropos", "gustos_generos", "gustos_tropos"}
    if existing & expected:
        raise RuntimeError("Existen tablas de preferencias: revisar compatibilidad antes de migrar")
    for name, values in (("catalogo_generos", GENRES), ("catalogo_tropos", TROPES)):
        table = op.create_table(name,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), schema="app")
        op.bulk_insert(table, [{"id": key, "name": label, "sort_order": i, "active": True}
                               for i, (key, label) in enumerate(values)])
    op.create_table("gustos_generos",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre_id", sa.String(64), sa.ForeignKey("app.catalogo_generos.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("position BETWEEN 1 AND 5", name="ck_gustos_generos_position"),
        sa.UniqueConstraint("user_id", "position", name="uq_gustos_generos_position"), schema="app")
    op.create_table("gustos_tropos",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trope_id", sa.String(64), sa.ForeignKey("app.catalogo_tropos.id", ondelete="RESTRICT"), primary_key=True), schema="app")


def downgrade():
    for name in ("gustos_tropos", "gustos_generos", "catalogo_tropos", "catalogo_generos"):
        op.drop_table(name, schema="app")
