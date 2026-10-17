"""Explicit catalog-linked notes participate in adaptive analysis invalidation."""
from alembic import op
revision='0038_explicit_note_jobs'
down_revision='0037_projection_event_coverage'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE FUNCTION analytics.explicit_note_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP IN ('UPDATE','DELETE') THEN
        IF OLD.work_id IS NOT NULL AND OLD.publication_type IN ('note','theory') THEN
          PERFORM ia.enqueue(OLD.user_id,'book:'||OLD.work_id::text);
          PERFORM ia.enqueue(OLD.user_id,'profile');
        END IF;
      END IF;
      IF TG_OP IN ('INSERT','UPDATE') THEN
        IF NEW.work_id IS NOT NULL AND NEW.publication_type IN ('note','theory') THEN
          PERFORM ia.enqueue(NEW.user_id,'book:'||NEW.work_id::text);
          PERFORM ia.enqueue(NEW.user_id,'profile');
        END IF;
      END IF;
      RETURN NULL;
    END $$;
    CREATE TRIGGER projection_explicit_note AFTER INSERT OR UPDATE OR DELETE ON app.publicaciones
      FOR EACH ROW EXECUTE FUNCTION analytics.explicit_note_changed();''')


def downgrade():
    raise RuntimeError('Preserve note processing')
