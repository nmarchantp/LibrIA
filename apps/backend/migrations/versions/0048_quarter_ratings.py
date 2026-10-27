"""Exact quarter-point reviews, revisions and analytics; preserve integer history."""
from alembic import op

revision = '0048_quarter_ratings'
down_revision = '0047_featured_reading_taste'
branch_labels = None
depends_on = None


def upgrade():
    for schema, table, constraint in (
        ('app', 'publicaciones', 'ck_publicaciones_rating'),
        ('app', 'resenas', 'resenas_rating_check'),
        ('app', 'revisiones_resena', 'revisiones_resena_rating_check'),
        ('analytics', 'hechos_resenas', 'hechos_resenas_rating_check'),
    ):
        op.execute(f'ALTER TABLE {schema}.{table} DROP CONSTRAINT {constraint}')
        op.execute(f'ALTER TABLE {schema}.{table} ALTER COLUMN rating TYPE numeric(3,2) USING rating::numeric(3,2)')
        op.execute(f'''ALTER TABLE {schema}.{table} ADD CONSTRAINT {constraint}
            CHECK (rating IS NULL OR (rating BETWEEN 0.25 AND 5 AND mod(rating,0.25)=0))''')
    op.execute('''ALTER TABLE analytics.preparacion_valoraciones_obras
        ALTER COLUMN rating_sum TYPE numeric USING rating_sum::numeric;
        ALTER TABLE analytics.preparacion_valoraciones_obras
        DROP CONSTRAINT preparacion_valoraciones_obras_check;
        ALTER TABLE analytics.preparacion_valoraciones_obras
        DROP CONSTRAINT preparacion_valoraciones_obras_check1;
        ALTER TABLE analytics.preparacion_valoraciones_obras
        ADD CONSTRAINT preparacion_valoraciones_obras_check CHECK (
            rated_count >= 0 AND rated_count <= review_count);
        ALTER TABLE analytics.preparacion_valoraciones_obras
        ADD CONSTRAINT preparacion_valoraciones_obras_check1 CHECK (
            (rated_count=0 AND rating_average IS NULL) OR
            (rated_count>0 AND rating_average BETWEEN 0.25 AND 5));''')


def downgrade():
    raise RuntimeError('Quarter ratings cannot be converted to integers without losing saved scores.')
