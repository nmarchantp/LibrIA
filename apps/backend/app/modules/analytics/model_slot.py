"""Disabled compatibility surface; provider concurrency lives in gemini_worker."""
from contextlib import asynccontextmanager

from app.modules.analytics.adaptive_ai import LegacyAIFlowDisabled


@asynccontextmanager
async def model_slot(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El bloqueo del modelo local heredado esta desactivado")
    yield
