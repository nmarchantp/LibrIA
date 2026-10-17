"""Book inference yields the local model to an interactive ADN request."""
import asyncio
from contextlib import suppress
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.config import get_settings
from app.modules.analytics.fast_profile import request_json


class ProfilePriority(Exception):
    pass


def profile_waiting():
    with SessionLocal() as db:
        return bool(db.execute(text("SELECT 1 FROM ia.jobs WHERE target='profile' AND status IN ('pending','processing') AND deadline_at>now() LIMIT 1")).first())


async def request_book(payload):
    if profile_waiting():
        raise ProfilePriority()
    task=asyncio.create_task(request_json(payload,min(60,get_settings().ai_timeout_seconds)))
    try:
        while not task.done():
            await asyncio.wait({task},timeout=1)
            if not task.done() and profile_waiting():
                raise ProfilePriority()
        return task.result()
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
