"""Resolve social publication context to stable work and edition identifiers."""
from alembic import op
revision='0035_publication_catalog_links'
down_revision='0034_inference_storage'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''ALTER TABLE app.publicaciones ADD COLUMN work_id uuid REFERENCES app.obras(id) ON DELETE RESTRICT;
      ALTER TABLE app.publicaciones ADD COLUMN edition_id uuid;
      ALTER TABLE app.publicaciones ADD CONSTRAINT fk_publicaciones_edicion_obra
        FOREIGN KEY(edition_id,work_id) REFERENCES app.ediciones(id,work_id) DEFERRABLE INITIALLY DEFERRED;
      ALTER TABLE app.publicaciones ADD CONSTRAINT ck_publicaciones_edicion_obra CHECK(edition_id IS NULL OR work_id IS NOT NULL);
      CREATE INDEX ix_publicaciones_work ON app.publicaciones(work_id);
      UPDATE app.publicaciones po SET work_id=link.work_id,edition_id=link.edition_id
      FROM (SELECT s.external_id,min(e.work_id::text)::uuid AS work_id,min(e.id::text)::uuid AS edition_id
        FROM app.fuentes_catalogo s JOIN app.ediciones e ON e.id=s.edition_id
        GROUP BY s.external_id HAVING count(DISTINCT e.work_id)=1) link WHERE po.book_ref=link.external_id;
      INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios ON CONFLICT DO NOTHING;''')


def downgrade():
    raise RuntimeError('Preserve publication origin links')
