"""One annual target per account; progress is always derived from the library."""
import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ReadingChallenge(Base):
    __tablename__ = 'retos_lectura'
    __table_args__ = (
        CheckConstraint('target BETWEEN 1 AND 1000', name='ck_reading_challenge_target'),
        CheckConstraint('year BETWEEN 1900 AND 9999', name='ck_reading_challenge_year'),
        {'schema': 'app'},
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
