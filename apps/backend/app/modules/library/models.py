"""Biblioteca por obra e intentos independientes de lectura."""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.model_mixins import EditableMixin, EntityMixin


class LibraryEntry(EditableMixin, Base):
    __tablename__ = "entradas_biblioteca"
    __table_args__ = (
        UniqueConstraint("user_id", "work_id", name="uq_biblioteca_user_work"),
        UniqueConstraint("id", "work_id", name="uq_biblioteca_id_work"),
        {"schema": "app"},
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"), index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Reading(EditableMixin, Base):
    __tablename__ = "lecturas"
    __table_args__ = (
        ForeignKeyConstraint(["library_entry_id", "work_id"], ["app.entradas_biblioteca.id", "app.entradas_biblioteca.work_id"], ondelete="RESTRICT", name="fk_lecturas_biblioteca_obra"),
        ForeignKeyConstraint(["edition_id", "work_id"], ["app.ediciones.id", "app.ediciones.work_id"], ondelete="RESTRICT", name="fk_lecturas_edicion_obra"),
        CheckConstraint("status IN ('pending', 'reading', 'finished', 'abandoned')", name="ck_lecturas_status"),
        CheckConstraint("current_page >= 0 AND (total_pages IS NULL OR (total_pages > 0 AND current_page <= total_pages))", name="ck_lecturas_pages"),
        CheckConstraint("(status = 'pending' AND current_page = 0 AND started_at IS NULL) OR (status <> 'pending' AND total_pages IS NOT NULL AND started_at IS NOT NULL)", name="ck_lecturas_started"),
        CheckConstraint("(status = 'finished' AND finished_at IS NOT NULL AND current_page = total_pages AND finished_at >= started_at) OR (status <> 'finished' AND finished_at IS NULL)", name="ck_lecturas_finished"),
        CheckConstraint("(status = 'abandoned' AND abandoned_at IS NOT NULL AND abandonment_reason IS NOT NULL AND length(trim(abandonment_reason)) > 0 AND abandoned_at >= started_at) OR (status <> 'abandoned' AND abandoned_at IS NULL AND abandonment_reason IS NULL)", name="ck_lecturas_abandoned"),
        Index("ix_lecturas_biblioteca_created", "library_entry_id", "created_at"),
        {"schema": "app"},
    )
    library_entry_id: Mapped[uuid.UUID] = mapped_column()
    work_id: Mapped[uuid.UUID] = mapped_column()
    edition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    current_page: Mapped[int] = mapped_column(Integer, server_default="0")
    total_pages: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abandonment_reason: Mapped[str | None] = mapped_column(Text)

    @property
    def progress_percentage(self) -> Decimal | None:
        if self.total_pages is None:
            return None
        return (Decimal(self.current_page) * 100 / Decimal(self.total_pages)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ReadingProgress(EntityMixin, Base):
    __tablename__ = "progreso_lectura"
    __table_args__ = (
        CheckConstraint("page >= 0", name="ck_progreso_lectura_page"),
        Index("ix_progreso_lectura_recorded", "reading_id", "recorded_at"),
        {"schema": "app"},
    )
    reading_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.lecturas.id", ondelete="RESTRICT"))
    page: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
