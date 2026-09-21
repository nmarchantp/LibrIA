import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Post(Base):
    __tablename__ = "publicaciones"
    __table_args__ = (Index("ix_publicaciones_created_at", "created_at"), {"schema": "app"})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app.usuarios.id", ondelete="RESTRICT"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
