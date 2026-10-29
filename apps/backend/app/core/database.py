"""Conexión compartida a PostgreSQL mediante SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine,event,text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Clase base de la que heredarán todos los modelos persistentes."""


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session,'do_orm_execute')
def catalog_lock_before_rows(state):
    """Row-locking ORM consumers join the catalog barrier before locking rows.

    DB statement triggers cover DML from all clients; this additionally avoids
    lock promotion/inversion in existing API SELECT ... FOR UPDATE paths.
    """
    if getattr(state.statement,'_for_update_arg',None) is not None and get_settings().catalog_canonical_enabled:
        state.session.connection().execute(text('SELECT pg_advisory_xact_lock_shared(73155,1)'))


def get_db() -> Generator[Session, None, None]:
    """Entrega una sesión por solicitud y garantiza su cierre."""
    with SessionLocal() as session:
        yield session
