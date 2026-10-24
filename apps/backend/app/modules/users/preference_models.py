"""Explicit account preferences; never inferred from reading activity."""
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class Genre(Base):
    __tablename__ = "catalogo_generos"
    __table_args__ = {"schema": "app"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    group_name: Mapped[str] = mapped_column(String(80), default="Otros", server_default="Otros")


class Trope(Base):
    __tablename__ = "catalogo_tropos"
    __table_args__ = {"schema": "app"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    group_name: Mapped[str] = mapped_column(String(80), default="Otras temáticas", server_default="Otras temáticas")


class FavoriteGenre(Base):
    __tablename__ = "gustos_generos"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 5", name="ck_gustos_generos_position"),
        UniqueConstraint("user_id", "position", name="uq_gustos_generos_position"),
        {"schema": "app"},
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True)
    genre_id: Mapped[str] = mapped_column(ForeignKey("app.catalogo_generos.id", ondelete="RESTRICT"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)


class FavoriteTrope(Base):
    __tablename__ = "gustos_tropos"
    __table_args__ = {"schema": "app"}
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True)
    trope_id: Mapped[str] = mapped_column(ForeignKey("app.catalogo_tropos.id", ondelete="RESTRICT"), primary_key=True)


class IntensityCategory(Base):
    __tablename__ = "catalogo_intensidades"
    __table_args__ = {"schema": "app"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    icon: Mapped[str] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(32))
    levels: Mapped[list[str]] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class FavoriteIntensity(Base):
    __tablename__ = "gustos_intensidades"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_gustos_intensidades_level"),
        CheckConstraint("position BETWEEN 1 AND 5", name="ck_gustos_intensidades_position"),
        UniqueConstraint("user_id", "position", name="uq_gustos_intensidades_position"),
        Index("uq_gustos_intensidades_featured", "user_id", unique=True, postgresql_where=text("featured")),
        {"schema": "app"},
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("app.catalogo_intensidades.id", ondelete="RESTRICT"), primary_key=True)
    level: Mapped[int] = mapped_column(SmallInteger)
    position: Mapped[int] = mapped_column(SmallInteger)

    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Interest(Base):
    __tablename__ = "catalogo_intereses"
    __table_args__ = {"schema": "app"}
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    group_name: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class FavoriteInterest(Base):
    __tablename__ = "gustos_intereses"
    __table_args__ = {"schema": "app"}
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="CASCADE"), primary_key=True)
    interest_id: Mapped[str] = mapped_column(ForeignKey("app.catalogo_intereses.id", ondelete="RESTRICT"), primary_key=True)
