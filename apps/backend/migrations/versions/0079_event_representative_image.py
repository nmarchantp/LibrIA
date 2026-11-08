"""Applied compatibility schema retained after the representative-image UI was withdrawn."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision='0079_event_representative_image'
down_revision='0078_publication_events'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('publicaciones',sa.Column('event_image_id',pg.UUID(as_uuid=True),nullable=True),schema='app')
    op.create_foreign_key('fk_publicaciones_event_image','publicaciones','imagenes_publicacion',['event_image_id'],['id'],source_schema='app',referent_schema='app',ondelete='SET NULL')

def downgrade():
    raise RuntimeError('La reversión debe preservar la selección de imágenes de eventos.')
