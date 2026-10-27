import uuid
from decimal import Decimal
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
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
    legacy_content: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    author_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.perfiles.id", ondelete="RESTRICT"))
    publication_type: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40))
    author_role: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    book_ref: Mapped[str | None] = mapped_column(String(200))
    work_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.obras.id',ondelete='RESTRICT'))
    edition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.ediciones.id'))
    book_title: Mapped[str | None] = mapped_column(String(200))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    progress_percent: Mapped[int | None] = mapped_column(Integer)
    reading_event: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PostImage(Base):
    __tablename__ = "imagenes_publicacion"
    __table_args__ = (
        Index("ix_imagenes_publicacion_post", "post_id"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.publicaciones.id", ondelete="CASCADE"))
    content_type: Mapped[str] = mapped_column(String(20))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PostLike(Base):
    __tablename__ = "me_gusta_publicacion"
    __table_args__ = {"schema": "app"}

    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.publicaciones.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileFollow(Base):
    __tablename__ = "seguimientos_perfil"
    __table_args__ = {"schema": "app"}

    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.perfiles.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PostComment(Base):
    __tablename__ = "comentarios_publicacion"
    __table_args__ = (
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 1000", name="ck_comentarios_publicacion_body"),
        CheckConstraint("num_nonnulls(post_id, reading_event_id, review_id) = 1", name="ck_comentarios_destino"),
        Index("ix_comentarios_publicacion_post_created", "post_id", "created_at"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.publicaciones.id", ondelete="CASCADE"))
    reading_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.eventos_lectura.id", ondelete="RESTRICT"), index=True)
    review_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.resenas.id", ondelete="RESTRICT"), index=True)
    author_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.perfiles.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    __tablename__ = "resenas"
    __table_args__ = (
        UniqueConstraint("author_profile_id", "work_id", name="uq_resenas_perfil_obra"),
        ForeignKeyConstraint(["edition_id", "work_id"], ["app.ediciones.id", "app.ediciones.work_id"], name="fk_resenas_edicion_obra"),
        {"schema": "app"},
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.perfiles.id", ondelete="RESTRICT"))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.obras.id", ondelete="RESTRICT"))
    edition_id: Mapped[uuid.UUID | None] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    dimension_ratings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revision_number: Mapped[int] = mapped_column(Integer, default=1)


class ReviewRevision(Base):
    __tablename__ = "revisiones_resena"
    __table_args__ = {"schema": "app"}
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.resenas.id", ondelete="RESTRICT"), primary_key=True)
    revision_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    dimension_ratings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    is_spoiler: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(Text)
    edition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.ediciones.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewImage(Base):
    __tablename__ = "imagenes_resena"
    __table_args__ = {"schema": "app"}
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.resenas.id", ondelete="CASCADE"))
    content_type: Mapped[str] = mapped_column(String(20))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewLike(Base):
    __tablename__ = "me_gusta_resena"
    __table_args__ = {"schema": "app"}
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.resenas.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
