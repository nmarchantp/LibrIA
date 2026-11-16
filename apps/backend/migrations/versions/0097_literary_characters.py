"""Curated portraits tied to local works."""
import uuid
import unicodedata
from alembic import op
import sqlalchemy as sa

revision = '0097_literary_characters'
down_revision = '0096_literary_highlights'
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table('personajes_literarios',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('work_id', sa.Uuid(), sa.ForeignKey('app.obras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('portrait_url', sa.String(500)), sa.Column('portrait_data', sa.LargeBinary()),
        sa.Column('portrait_type', sa.String(30)), sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.UniqueConstraint('work_id', 'name', name='uq_personaje_obra_nombre'), schema='app')
    op.create_index('ix_personajes_literarios_work_id', 'personajes_literarios', ['work_id'], schema='app')
    connection = op.get_bind()
    for work in connection.execute(sa.text('SELECT id, title FROM app.obras')).mappings():
        title = ''.join(c for c in unicodedata.normalize('NFKD', work['title']) if not unicodedata.combining(c)).lower().strip()
        characters = []
        if title in ('erase una vez un corazon roto', 'once upon a broken heart'):
            characters = [('jacks', 'Jacks'), ('evangeline', 'Evangeline Fox'), ('apollo', 'Apollo')]
        elif title in ('una corte de rosas y espinas', 'una corte de rosas y espinas (ne)', 'a court of thorns and roses'):
            characters = [('rhysand', 'Rhysand'), ('feyre', 'Feyre Archeron'), ('tamlin', 'Tamlin')]
        if characters:
            connection.execute(table.insert(), [{'id': uuid.uuid4(), 'work_id': work['id'], 'name': name,
                'portrait_url': f'/images/characters/{slug}-v1.webp'} for slug, name in characters])


def downgrade():
    op.drop_table('personajes_literarios', schema='app')
