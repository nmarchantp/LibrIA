"""Expand the controlled trope catalog while preserving existing IDs and choices."""
from alembic import op
import sqlalchemy as sa
import unicodedata

revision = "0044_trope_catalog_groups"
down_revision = "0043_literary_preferences"
branch_labels = None
depends_on = None

GROUPS = {
    "Romance y relaciones": [
        ("matrimonio-por-conveniencia", "Matrimonio por conveniencia"), ("segunda-oportunidad", "Segunda oportunidad"),
        ("proximidad-forzada", "Proximidad forzada"), ("amor-no-correspondido", "Amor no correspondido"),
        ("relacion-falsa", "Relación falsa"), ("triangulo-amoroso", "Triángulo amoroso"),
        ("grumpy-x-sunshine", "Grumpy x Sunshine"), ("rivales-academicos", "Rivales académicos")],
    "Fantasía y magia": [
        ("hombres-lobo", "Hombres lobo"), ("profecias", "Profecías"), ("magia-oscura", "Magia oscura"),
        ("dioses-y-mitologia", "Dioses y mitología"), ("poderes-ocultos", "Poderes ocultos"),
        ("portales-a-otros-mundos", "Portales a otros mundos")],
    "Misterio y suspenso": [
        ("asesinatos", "Asesinatos"), ("secretos-familiares", "Secretos familiares"), ("desapariciones", "Desapariciones"),
        ("crimenes-sin-resolver", "Crímenes sin resolver"), ("narrador-poco-fiable", "Narrador poco fiable"),
        ("conspiraciones", "Conspiraciones"), ("investigacion-detectivesca", "Investigación detectivesca")],
    "Aventura y ciencia ficción": [
        ("apocalipsis", "Apocalipsis"), ("supervivencia", "Supervivencia"), ("exploracion-espacial", "Exploración espacial"),
        ("realidades-paralelas", "Realidades paralelas"), ("inteligencia-artificial", "Inteligencia artificial"),
        ("rebeliones", "Rebeliones")],
    "Personajes y emociones": [
        ("antiheroes", "Antihéroes"), ("villanos-complejos", "Villanos complejos"), ("redencion", "Redención"),
        ("traicion", "Traición"), ("venganza", "Venganza"), ("crecimiento-personal", "Crecimiento personal"),
        ("duelo-y-perdida", "Duelo y pérdida"), ("amistades-profundas", "Amistades profundas"),
        ("personajes-moralmente-grises", "Personajes moralmente grises")],
}
EXISTING = {
    "Romance y relaciones": ["enemigos-a-amantes", "amigos-a-amantes", "romance-lento", "amor-prohibido"],
    "Fantasía y magia": ["magia", "vampiros", "brujas", "dragones", "academias-magicas", "criaturas-feericas", "reinos-encantados"],
    "Misterio y suspenso": ["misterios-sobrenaturales"],
    "Aventura y ciencia ficción": ["viajes-en-el-tiempo", "mundos-distopicos"],
    "Personajes y emociones": ["familia-encontrada"],
}


def normalized(name):
    return unicodedata.normalize("NFC", " ".join(name.split())).casefold()


def upgrade():
    op.add_column("catalogo_tropos", sa.Column("group_name", sa.String(80), nullable=False,
                                            server_default="Otras temáticas"), schema="app")
    db = op.get_bind()
    table = sa.table("catalogo_tropos", sa.column("id", sa.String), sa.column("name", sa.String),
                     sa.column("sort_order", sa.Integer), sa.column("active", sa.Boolean),
                     sa.column("group_name", sa.String), schema="app")
    rows = db.execute(sa.select(table.c.id, table.c.name, table.c.sort_order)).all()
    ids = {r.id: r.name for r in rows}
    names = {normalized(r.name): r.id for r in rows}
    order = max((r.sort_order for r in rows), default=-1) + 1
    for group, values in EXISTING.items():
        db.execute(table.update().where(table.c.id.in_(values)).values(group_name=group))
    for group, values in GROUPS.items():
        for key, name in values:
            if key in ids and normalized(ids[key]) != normalized(name):
                raise RuntimeError("Un ID de tropo existente tiene otro significado; revisar antes de migrar")
            existing = key if key in ids else names.get(normalized(name))
            if existing:
                db.execute(table.update().where(table.c.id == existing).values(group_name=group))
                continue
            db.execute(table.insert().values(id=key, name=name, sort_order=order, active=True, group_name=group))
            ids[key] = name
            names[normalized(name)] = key
            order += 1


def downgrade():
    # Keep additive catalog records and all selections: deleting them would lose
    # declarations or violate their foreign keys. Only the grouping is reverted.
    op.drop_column("catalogo_tropos", "group_name", schema="app")
