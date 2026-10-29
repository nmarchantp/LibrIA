"""Disabled compatibility module; new jobs are consumed by gemini_worker."""
from app.modules.analytics.adaptive_ai import LegacyAIFlowDisabled


async def worker_loop(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El worker adaptativo heredado esta desactivado")
