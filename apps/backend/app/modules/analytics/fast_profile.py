"""Disabled compatibility surface for the frozen local profile implementation."""
from app.modules.analytics.adaptive_ai import LegacyAIFlowDisabled


def generate_profile(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El generador de perfil heredado esta desactivado")


async def request_json(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El transporte local heredado esta desactivado")


async def stream_json(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El transporte local heredado esta desactivado")
