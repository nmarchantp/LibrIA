"""Disabled compatibility surface for the frozen local book transport."""
from app.modules.analytics.adaptive_ai import LegacyAIFlowDisabled


class ProfilePriority(Exception):
    pass


async def request_book(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El transporte de libro heredado esta desactivado")
