"""Ephemeral images; every read checks expiry and current profile access."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Story(Base):
    __tablename__ = 'historias'
    __table_args__ = (Index('ix_historias_profile_expiry', 'profile_id', 'expires_at'), {'schema': 'app'})
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.perfiles.id', ondelete='CASCADE'))
    content_type: Mapped[str] = mapped_column(String(30))
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class StoryView(Base):
    __tablename__ = 'historias_vistas'
    __table_args__ = {'schema': 'app'}
    story_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.historias.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='CASCADE'), primary_key=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
