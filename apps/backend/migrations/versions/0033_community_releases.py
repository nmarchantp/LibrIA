"""Community daily privacy releases and dependency invalidation."""
from alembic import op
revision='0033_community_releases'
down_revision='0032_analytics_projections'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE TABLE analytics.community_releases (
      release_date date PRIMARY KEY,payload jsonb NOT NULL,processed_at timestamptz NOT NULL DEFAULT now());
    ''')
    op.execute('''CREATE FUNCTION analytics.related_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE rec jsonb; rid uuid;
    BEGIN
      rec=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
      rid=(rec->>'id')::uuid;
      IF TG_TABLE_NAME IN ('publicaciones','resenas') THEN
        INSERT INTO analytics.dirty_readers(owner_id)
        SELECT user_id FROM app.comentarios_publicacion WHERE post_id=rid OR review_id=rid
        UNION SELECT user_id FROM app.me_gusta_publicacion WHERE post_id=rid
        UNION SELECT user_id FROM app.me_gusta_resena WHERE review_id=rid
        ON CONFLICT(owner_id) DO UPDATE SET changed_at=clock_timestamp();
      ELSIF TG_TABLE_NAME='procedencia_demo' THEN
        INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios
          ON CONFLICT(owner_id) DO UPDATE SET changed_at=clock_timestamp();
        INSERT INTO analytics.dirty_catalog(work_id) SELECT id FROM app.obras ON CONFLICT DO NOTHING;
      ELSE
        INSERT INTO analytics.dirty_readers(owner_id)
          SELECT user_id FROM app.seguimientos_perfil WHERE profile_id=COALESCE((rec->>'profile_id')::uuid,rid)
          ON CONFLICT(owner_id) DO UPDATE SET changed_at=clock_timestamp();
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$;''')
    for table in ('publicaciones','resenas','procedencia_demo','perfiles','capacidades_perfil'):
        op.execute(f'CREATE TRIGGER projection_related_dirty BEFORE UPDATE OR DELETE ON app.{table} FOR EACH ROW EXECUTE FUNCTION analytics.related_dirty()')
    op.execute('''CREATE TRIGGER projection_demo_insert AFTER INSERT ON app.procedencia_demo FOR EACH ROW EXECUTE FUNCTION analytics.related_dirty();
      CREATE TRIGGER projection_capability_insert AFTER INSERT ON app.capacidades_perfil FOR EACH ROW EXECUTE FUNCTION analytics.related_dirty();''')


def downgrade():
    raise RuntimeError('Preserve privacy release history')
