"""Catálogo compartido: obras, ediciones y procedencia bibliográfica."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.model_mixins import EditableMixin, EntityMixin


class Work(EditableMixin, Base):
    __tablename__ = "obras"
    __table_args__ = {"schema": "app"}
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.usuarios.id", ondelete="SET NULL"), index=True)


class Author(EditableMixin, Base):
    __tablename__ = "autores"
    __table_args__ = {"schema": "app"}
    name: Mapped[str] = mapped_column(Text)
    biography: Mapped[str | None] = mapped_column(Text)


class WorkAuthor(Base):
    __tablename__ = "obras_autores"
    __table_args__ = (CheckConstraint("position > 0", name="ck_obras_autores_position"), {"schema": "app"})
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="CASCADE"), primary_key=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.autores.id", ondelete="RESTRICT"), primary_key=True, index=True)
    position: Mapped[int] = mapped_column(Integer)


class Edition(EditableMixin, Base):
    __tablename__ = "ediciones"
    __table_args__ = (
        CheckConstraint("page_count > 0", name="ck_ediciones_page_count"),
        UniqueConstraint("id", "work_id", name="uq_ediciones_id_work"),
        {"schema": "app"},
    )
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    edition_label: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(SmallInteger)
    isbn13: Mapped[str | None] = mapped_column(String(13), unique=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    publisher_name: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.usuarios.id", ondelete="SET NULL"), index=True)


class CatalogSource(EntityMixin, Base):
    __tablename__ = "fuentes_catalogo"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_fuentes_catalogo_provider_external"), {"schema": "app"})
    edition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.ediciones.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
