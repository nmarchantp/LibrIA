"""Provider-neutral contracts for validated structured AI generation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

ResultT = TypeVar("ResultT")


class PromptKind(StrEnum):
    """Keep business prompts distinct without embedding them in an adapter."""

    RECOMMENDATIONS = "recommendations"
    BOOK_ANALYSIS = "book_analysis"
    READER_PROFILE = "reader_profile"
    INDICATOR_INTERPRETATION = "indicator_interpretation"


@dataclass(frozen=True)
class TokenUsage:
    """Normalized token accounting returned by any provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    # None means a synthetic/legacy usage object; Gemini always supplies presence.
    present_fields: frozenset[str] | None = None

    @property
    def verified(self) -> bool:
        return self.present_fields is None or {
            "prompt_token_count", "candidates_token_count", "total_token_count"
        }.issubset(self.present_fields) and self.total_tokens == (
            self.input_tokens + self.output_tokens + self.reasoning_tokens)

    @property
    def accounted_tokens(self) -> int:
        return max(self.total_tokens, self.input_tokens + self.output_tokens + self.reasoning_tokens)

    def __post_init__(self) -> None:
        if any(value < 0 for value in (
            self.input_tokens,
            self.output_tokens,
            self.total_tokens,
            self.cached_input_tokens,
            self.reasoning_tokens,
        )):
            raise ValueError("Token usage cannot be negative")


def _identity(value: Any) -> Any:
    return value


@dataclass(frozen=True)
class StructuredGenerationRequest(Generic[ResultT]):
    """One structured request, with validation owned by the business flow."""

    prompt_kind: PromptKind
    system_instruction: str
    user_content: str
    response_schema: Mapping[str, Any]
    validator: Callable[[Any], ResultT] = field(default=_identity, repr=False)
    model: str | None = None
    timeout_seconds: float | None = None
    temperature: float = 0
    max_output_tokens: int | None = None
    accounting_phase: str | None = None

    def __post_init__(self) -> None:
        if not self.system_instruction.strip() or not self.user_content.strip():
            raise ValueError("Structured generation requires both system and user content")
        if not self.response_schema:
            raise ValueError("Structured generation requires a response schema")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")

    def validate(self, payload: Any) -> ResultT:
        return self.validator(payload)

    @classmethod
    def for_pydantic(
        cls,
        *,
        prompt_kind: PromptKind,
        system_instruction: str,
        user_content: str,
        response_model: type[BaseModel],
        model: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float = 0,
        max_output_tokens: int | None = None,
    ) -> "StructuredGenerationRequest[dict[str, Any]]":
        return cls(
            prompt_kind=prompt_kind,
            system_instruction=system_instruction,
            user_content=user_content,
            response_schema=response_model.model_json_schema(),
            validator=lambda value: response_model.model_validate(value).model_dump(),
            model=model,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )


@dataclass(frozen=True)
class StructuredGenerationResult(Generic[ResultT]):
    content: ResultT
    provider: str
    model: str
    usage: TokenUsage
    finish_reason: str | None = None
    provider_request_id: str | None = None


class AIProviderError(RuntimeError):
    """Safe provider failure: messages must never include credentials or prompts."""

    code = "provider_error"
    retryable = False

    def __init__(self, message: str, *, status_code: int | None = None,
                 usage: TokenUsage | None = None, request_id: str | None = None,
                 finish_reason: str | None = None, retry_after: float | None = None,
                 quota_exhausted: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.usage = usage
        self.request_id = request_id
        self.finish_reason = finish_reason
        self.retry_after = retry_after
        self.quota_exhausted = quota_exhausted


class AIProviderConfigurationError(AIProviderError):
    code = "provider_configuration"


class AIProviderAuthenticationError(AIProviderError):
    code = "provider_authentication"


class AIProviderQuotaError(AIProviderError):
    code = "provider_quota"
    retryable = True


class AIProviderTimeoutError(AIProviderError):
    code = "provider_timeout"
    retryable = True


class AIProviderServerError(AIProviderError):
    code = "provider_server"
    retryable = True


class AIProviderInvalidResponseError(AIProviderError):
    code = "provider_invalid_response"


@runtime_checkable
class AIProvider(Protocol):
    name: str

    def generate_structured(
        self, request: StructuredGenerationRequest[ResultT]
    ) -> StructuredGenerationResult[ResultT]: ...
