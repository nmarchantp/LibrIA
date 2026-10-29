"""Provider-neutral structured generation contracts for LibrIAverse."""

from app.modules.analytics.providers.base import (
    AIProvider,
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderQuotaError,
    AIProviderServerError,
    AIProviderTimeoutError,
    PromptKind,
    StructuredGenerationRequest,
    StructuredGenerationResult,
    TokenUsage,
)
from app.modules.analytics.providers.factory import build_ai_provider

__all__ = [
    "AIProvider",
    "AIProviderAuthenticationError",
    "AIProviderConfigurationError",
    "AIProviderError",
    "AIProviderInvalidResponseError",
    "AIProviderQuotaError",
    "AIProviderServerError",
    "AIProviderTimeoutError",
    "PromptKind",
    "StructuredGenerationRequest",
    "StructuredGenerationResult",
    "TokenUsage",
    "build_ai_provider",
]
