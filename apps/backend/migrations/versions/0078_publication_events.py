"""One calendar event per publication, durable attendance and schedule history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision='0078_publication_events'
down_revision='0077_hide_draft_reviews'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('eventos_publicacion',
        sa.Column('post_id',pg.UUID(as_uuid=True),sa.ForeignKey('app.publicaciones.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),sa.Column('ends_at',sa.DateTime(timezone=True)),
        sa.Column('timezone',sa.String(64),nullable=False),sa.Column('location',sa.String(300),nullable=False),
        sa.Column('organizer',sa.String(200),nullable=False),sa.Column('category',sa.String(40),nullable=False),
        sa.Column('schedule_revision',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint('ends_at IS NULL OR ends_at >= starts_at',name='ck_evento_fin'),schema='app')
    op.create_index('ix_eventos_publicacion_starts_at','eventos_publicacion',['starts_at'],schema='app')
    op.create_table('asistencias_evento',
        sa.Column('post_id',pg.UUID(as_uuid=True),sa.ForeignKey('app.eventos_publicacion.post_id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('user_id',pg.UUID(as_uuid=True),sa.ForeignKey('app.usuarios.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('attending',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),schema='app')
    op.create_table('actualizaciones_horario_evento',
        sa.Column('id',pg.UUID(as_uuid=True),primary_key=True),
        sa.Column('post_id',pg.UUID(as_uuid=True),sa.ForeignKey('app.eventos_publicacion.post_id',ondelete='RESTRICT'),nullable=False),
        sa.Column('changed_by',pg.UUID(as_uuid=True),sa.ForeignKey('app.usuarios.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('previous_start',sa.DateTime(timezone=True),nullable=False),sa.Column('previous_end',sa.DateTime(timezone=True)),
        sa.Column('previous_timezone',sa.String(64),nullable=False),
        sa.Column('new_start',sa.DateTime(timezone=True),nullable=False),sa.Column('new_end',sa.DateTime(timezone=True)),
        sa.Column('new_timezone',sa.String(64),nullable=False),
        sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('post_id','revision',name='uq_actualizacion_horario_revision'),schema='app')


def downgrade():
    raise RuntimeError('La reversión debe conservar eventos, asistentes e historial de horarios.')
