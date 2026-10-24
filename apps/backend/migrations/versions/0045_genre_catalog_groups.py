"""Expand and group genres without replacing existing identities or selections."""
from alembic import op
import sqlalchemy as sa
import unicodedata

revision = "0045_genre_catalog_groups"
down_revision = "0044_trope_catalog_groups"
branch_labels = None
depends_on = None

GROUPS = {'Romance': [('romance-contemporaneo', 'Romance contemporáneo'),
             ('romance-historico', 'Romance histórico'),
             ('romance-juvenil', 'Romance juvenil'),
             ('romance-adulto', 'Romance adulto'),
             ('comedia-romantica', 'Comedia romántica'),
             ('romance-deportivo', 'Romance deportivo'),
             ('romance-universitario', 'Romance universitario'),
             ('romance-paranormal', 'Romance paranormal')],
 'Romance intenso': [('dark-romance', 'Dark Romance'),
                     ('romance-erotico', 'Romance erótico'),
                     ('mafia-romance', 'Mafia Romance'),
                     ('monster-romance', 'Monster Romance'),
                     ('bully-romance', 'Bully Romance'),
                     ('suspenso-romantico', 'Suspenso romántico')],
 'Fantasía romántica': [('romantasy', 'Romantasy'),
                        ('dark-romantasy', 'Dark Romantasy'),
                        ('romance-fantastico', 'Romance fantástico'),
                        ('fantasia-paranormal', 'Fantasía paranormal')],
 'Fantasía': [('fantasia-epica', 'Fantasía épica'),
              ('fantasia-urbana', 'Fantasía urbana'),
              ('fantasia-oscura', 'Fantasía oscura'),
              ('fantasia-medieval', 'Fantasía medieval'),
              ('cozy-fantasy', 'Cozy Fantasy'),
              ('alta-fantasia', 'Alta fantasía'),
              ('baja-fantasia', 'Baja fantasía')],
 'Misterio y suspenso': [('thriller-psicologico', 'Thriller psicológico'),
                         ('thriller-romantico', 'Thriller romántico'),
                         ('thriller-policial', 'Thriller policial'),
                         ('misterio', 'Misterio'),
                         ('suspenso', 'Suspenso'),
                         ('novela-policial', 'Novela policial'),
                         ('crimen', 'Crimen')],
 'Terror': [('terror-psicologico', 'Terror psicológico'),
            ('terror-sobrenatural', 'Terror sobrenatural'),
            ('terror-gotico', 'Terror gótico'),
            ('terror-cosmico', 'Terror cósmico'),
            ('horror-corporal', 'Horror corporal')],
 'Ciencia ficción': [('ciencia-ficcion', 'Ciencia ficción'),
                     ('distopia', 'Distopía'),
                     ('ciencia-ficcion-romantica', 'Ciencia ficción romántica'),
                     ('ciencia-ficcion-espacial', 'Ciencia ficción espacial'),
                     ('cyberpunk', 'Cyberpunk'),
                     ('ficcion-postapocaliptica', 'Ficción postapocalíptica')],
 'Narrativa': [('drama', 'Drama'),
               ('ficcion-contemporanea', 'Ficción contemporánea'),
               ('novela-historica', 'Novela histórica'),
               ('realismo-magico', 'Realismo mágico'),
               ('ficcion-literaria', 'Ficción literaria'),
               ('aventura', 'Aventura')],
 'Juvenil': [('young-adult', 'Young Adult'),
             ('new-adult', 'New Adult'),
             ('ficcion-juvenil', 'Ficción juvenil'),
             ('novela-de-formacion', 'Novela de formación')],
 'Otros': [('clasicos', 'Clásicos'),
           ('poesia', 'Poesía'),
           ('novela-grafica', 'Novela gráfica'),
           ('manga', 'Manga'),
           ('literatura-lgbtq', 'Literatura LGBTQ+'),
           ('desarrollo-personal', 'Desarrollo personal'),
           ('biografias', 'Biografías'),
           ('no-ficcion', 'No ficción')]}
EXISTING = {'Romance': ['romance'], 'Fantasía': ['fantasia'], 'Misterio y suspenso': ['misterio', 'thriller'], 'Terror': ['terror'], 'Ciencia ficción': ['ciencia-ficcion'], 'Narrativa': ['historica', 'contemporanea', 'aventura'], 'Juvenil': ['juvenil'], 'Otros': ['poesia', 'ensayo', 'biografia', 'no-ficcion', 'infantil']}


def normalized(name):
    return unicodedata.normalize("NFC", " ".join(name.split())).casefold()


def upgrade():
    op.add_column("catalogo_generos", sa.Column("group_name", sa.String(80), nullable=False,
                                            server_default="Otros"), schema="app")
    db = op.get_bind()
    table = sa.table("catalogo_generos", sa.column("id", sa.String), sa.column("name", sa.String),
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
                raise RuntimeError("Un ID de género existente tiene otro significado; revisar antes de migrar")
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
    op.drop_column("catalogo_generos", "group_name", schema="app")
