"""Declared reading intensities and independent interests; no inferred preferences."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0046_reading_tastes"
down_revision = "0045_genre_catalog_groups"
branch_labels = None
depends_on = None

CATEGORIES = [
    ("romance", "Romance", "heart", "affection", ["Un toque de romance", "Romance discreto", "Romance presente", "Romance protagonista", "Romance como eje de la historia"]),
    ("spicy", "Spicy", "flame", "warmth", ["Intimidad sugerida", "Sensualidad suave", "Escenas íntimas moderadas", "Escenas explícitas frecuentes", "Erotismo muy protagonista"]),
    ("terror", "Terror", "ghost", "mystic", ["Un toque inquietante", "Sustos suaves", "Terror moderado", "Terror intenso", "Terror extremo y perturbador"]),
    ("guerra-batallas", "Guerra y batallas", "swords", "energy", ["Conflictos de fondo", "Enfrentamientos ocasionales", "Batallas presentes", "Combates frecuentes", "Guerra como eje de la historia"]),
    ("drama-emocional", "Drama emocional", "cloud-rain", "calm", ["Emociones ligeras", "Momentos emotivos", "Drama moderado", "Emociones intensas", "Historias profundamente conmovedoras"]),
    ("humor", "Humor", "smile", "warmth", ["Algún guiño divertido", "Humor ocasional", "Humor presente", "Humor frecuente", "Comedia como eje de la historia"]),
    ("misterio", "Misterio", "search", "calm", ["Pequeñas incógnitas", "Enigmas sencillos", "Misterio moderado", "Enigmas complejos", "Misterio como eje de la historia"]),
    ("accion", "Acción", "zap", "energy", ["Ritmo tranquilo", "Acción ocasional", "Acción equilibrada", "Acción frecuente", "Acción constante y vertiginosa"]),
    ("fantasia", "Fantasía", "sparkles", "mystic", ["Un toque fantástico", "Magia discreta", "Fantasía presente", "Mundos muy mágicos", "Fantasía que lo impregna todo"]),
    ("suspenso", "Suspenso", "clock", "energy", ["Tensión ligera", "Intriga ocasional", "Tensión moderada", "Tensión sostenida", "Suspenso al límite"]),
]
INTERESTS = [
    ("autoayuda", "Autoayuda", "Bienestar y desarrollo personal"),
    ("crecimiento-personal", "Crecimiento personal", "Bienestar y desarrollo personal"),
    ("psicologia", "Psicología", "Bienestar y desarrollo personal"),
    ("historia", "Historia", "Historia y sociedad"),
    ("politica", "Política", "Historia y sociedad"),
    ("mitologia", "Mitología", "Ideas y creencias"),
    ("filosofia", "Filosofía", "Ideas y creencias"),
    ("espiritualidad", "Espiritualidad", "Ideas y creencias"),
    ("aventura", "Aventura", "Exploración y conocimiento"),
    ("ciencia", "Ciencia", "Exploración y conocimiento"),
]


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names(schema="app"))
    if existing & {"catalogo_intensidades", "gustos_intensidades", "catalogo_intereses", "gustos_intereses"}:
        raise RuntimeError("Existen tablas de gustos: revisar compatibilidad antes de migrar")
    categories = op.create_table("catalogo_intensidades",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("icon", sa.String(32), nullable=False),
        sa.Column("color", sa.String(32), nullable=False),
        sa.Column("levels", postgresql.JSONB, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("jsonb_typeof(levels) = 'array' AND jsonb_array_length(levels) = 5", name="ck_intensidades_descriptions"), schema="app")
    op.bulk_insert(categories, [dict(id=key, name=name, icon=icon, color=color, levels=levels, sort_order=i, active=True)
                               for i, (key, name, icon, color, levels) in enumerate(CATEGORIES)])
    interests = op.create_table("catalogo_intereses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("group_name", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), schema="app")
    op.bulk_insert(interests, [dict(id=key, name=name, group_name=group, sort_order=i, active=True)
                              for i, (key, name, group) in enumerate(INTERESTS)])
    op.create_table("gustos_intensidades",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("app.catalogo_intensidades.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("level", sa.SmallInteger, nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 5", name="ck_gustos_intensidades_level"),
        sa.CheckConstraint("position BETWEEN 1 AND 5", name="ck_gustos_intensidades_position"),
        sa.UniqueConstraint("user_id", "position", name="uq_gustos_intensidades_position"), schema="app")
    op.create_table("gustos_intereses",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("interest_id", sa.String(64), sa.ForeignKey("app.catalogo_intereses.id", ondelete="RESTRICT"), primary_key=True), schema="app")
    # Explicit cardinality check, independent from position constraints. Serialize
    # direct writers through the account row, just like the existing PATCH does.
    op.execute("""
        CREATE FUNCTION app.enforce_intensity_limit() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE current_count integer;
        BEGIN
            PERFORM 1 FROM app.usuarios WHERE id = NEW.user_id FOR UPDATE;
            IF TG_OP = 'UPDATE' THEN
                SELECT count(*) INTO current_count FROM app.gustos_intensidades
                WHERE user_id = NEW.user_id
                  AND NOT (user_id = OLD.user_id AND category_id = OLD.category_id);
            ELSE
                SELECT count(*) INTO current_count FROM app.gustos_intensidades WHERE user_id = NEW.user_id;
            END IF;
            IF current_count >= 5 THEN
                RAISE EXCEPTION 'Maximum five intensity categories per user'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_gustos_intensidades_count';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER gustos_intensidades_limit BEFORE INSERT OR UPDATE ON app.gustos_intensidades
        FOR EACH ROW EXECUTE FUNCTION app.enforce_intensity_limit();
    """)


def downgrade():
    op.drop_table("gustos_intereses", schema="app")
    op.drop_table("gustos_intensidades", schema="app")
    op.execute("DROP FUNCTION app.enforce_intensity_limit()")
    op.drop_table("catalogo_intereses", schema="app")
    op.drop_table("catalogo_intensidades", schema="app")
