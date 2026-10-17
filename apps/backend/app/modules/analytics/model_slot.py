"""Serialize local model use across workers without holding reader/ETL locks."""
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import engine

MODEL_LOCK=963470041


@asynccontextmanager
async def model_slot(key=MODEL_LOCK):
    while True:
        with engine.connect() as connection:
            acquired=connection.execute(text('SELECT pg_try_advisory_lock(:key)'),{'key':key}).scalar_one()
            connection.commit()
            if acquired:
                try:
                    yield
                finally:
                    try:
                        connection.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':key})
                        connection.commit()
                    except Exception:
                        # A session advisory lock must never return to the pool.
                        connection.invalidate()
                return
        await asyncio.sleep(.1)
