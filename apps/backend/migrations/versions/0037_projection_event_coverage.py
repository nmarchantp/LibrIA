"""Invalidate analytics for every business event, without forcing model inference."""
from alembic import op
revision='0037_projection_event_coverage'
down_revision='0036_peer_discovery'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE OR REPLACE FUNCTION analytics.social_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE rec jsonb; uid uuid;
    BEGIN
      rec=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
      uid=COALESCE(rec->>'user_id',rec->>'actor_user_id',rec->>'created_by_user_id')::uuid;
      IF uid IS NULL AND rec ? 'library_entry_id' THEN
        SELECT user_id INTO uid FROM app.entradas_biblioteca WHERE id=(rec->>'library_entry_id')::uuid;
      END IF;
      PERFORM analytics.mark_reader(uid);
      RETURN NULL;
    END $$;''')
    for table in ('publicaciones','eventos_lectura','lecturas'):
        op.execute(f'CREATE TRIGGER projection_business_dirty AFTER INSERT OR UPDATE OR DELETE ON app.{table} FOR EACH ROW EXECUTE FUNCTION analytics.social_dirty()')
    op.execute('INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios ON CONFLICT DO NOTHING')


def downgrade():
    raise RuntimeError('Preserve event coverage')
