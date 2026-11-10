from datetime import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class DemoMode(Base):
    __tablename__ = 'modo_demo'
    __table_args__ = (
        CheckConstraint('id = 1', name='ck_demo_singleton'),
        CheckConstraint('interval_seconds BETWEEN 10 AND 3600', name='ck_demo_interval'),
        {'schema': 'app'},
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    interval_seconds: Mapped[int] = mapped_column(Integer, default=30, server_default='30')
    sequence: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    catalog_edition_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]')
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('app.usuarios.id', ondelete='RESTRICT'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
