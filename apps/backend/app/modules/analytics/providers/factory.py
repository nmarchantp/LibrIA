"""Construct providers from application settings without coupling callers to SDKs."""

from app.core.config import Settings, get_settings
from app.modules.analytics.providers.base import AIProvider, AIProviderConfigurationError
from app.modules.analytics.providers.gemini import GeminiProvider


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    resolved = settings or get_settings()
    if resolved.ai_provider == "gemini":
        return GeminiProvider(
            api_key=resolved.gemini_api_key,
            model=resolved.gemini_model,
            timeout_seconds=resolved.ai_timeout_seconds,
        )
    raise AIProviderConfigurationError("Unsupported AI provider")
