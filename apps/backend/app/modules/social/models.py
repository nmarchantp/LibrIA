import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Post(Base):
    __tablename__ = "publicaciones"
    __table_args__ = (
        Index("ix_publicaciones_created_at", "created_at"),
        Index("ix_publicaciones_book_ref", "book_ref"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    author_role: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    book_ref: Mapped[str | None] = mapped_column(String(200))
    book_title: Mapped[str | None] = mapped_column(String(200))
    rating: Mapped[int | None] = mapped_column(Integer)
    progress_percent: Mapped[int | None] = mapped_column(Integer)
    reading_event: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PostComment(Base):
    __tablename__ = "comentarios_publicacion"
    __table_args__ = (
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 1000", name="ck_comentarios_publicacion_body"),
        Index("ix_comentarios_publicacion_post_created", "post_id", "created_at"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.publicaciones.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
