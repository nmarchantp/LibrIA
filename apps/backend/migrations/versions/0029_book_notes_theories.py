"""Allow the note and theory types already exposed by the book UI and API."""
from alembic import op

revision = "0029_book_notes_theories"
down_revision = "0028_personal_reading_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE app.publicaciones DROP CONSTRAINT ck_publicaciones_type;
        ALTER TABLE app.publicaciones ADD CONSTRAINT ck_publicaciones_type
        CHECK (publication_type IN ('free','event','promotion','news','launch','institutional','note','theory'));""")


def downgrade():
    raise RuntimeError("Preserve saved reader notes and theories")
