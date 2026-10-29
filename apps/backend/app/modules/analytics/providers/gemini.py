"""Gemini implementation of LibrIAverse structured AI generation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from google import genai
from google.genai import errors, types
from pydantic import SecretStr, ValidationError

from app.modules.analytics.providers.base import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderQuotaError,
    AIProviderServerError,
    AIProviderTimeoutError,
    StructuredGenerationRequest,
    StructuredGenerationResult,
    TokenUsage,
)

ResultT = TypeVar("ResultT")
ClientFactory = Callable[..., Any]


class GeminiProvider:
    """Official google-genai adapter; it owns transport, never business prompts."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: SecretStr | str,
        model: str,
        timeout_seconds: float,
        client_factory: ClientFactory | None = None,
    ) -> None:
        secret = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not secret:
            raise AIProviderConfigurationError("GEMINI_API_KEY is not configured")
        if not model.strip():
            raise AIProviderConfigurationError("GEMINI_MODEL is not configured")
        if timeout_seconds <= 0:
            raise AIProviderConfigurationError("AI timeout must be positive")
        self._api_key = secret
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory or genai.Client

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self._model!r}, timeout_seconds={self._timeout_seconds!r})"

    def generate_structured(
        self, request: StructuredGenerationRequest[ResultT]
    ) -> StructuredGenerationResult[ResultT]:
        model = request.model or self._model
        timeout_seconds = request.timeout_seconds or self._timeout_seconds
        config_values: dict[str, Any] = {
            "system_instruction": request.system_instruction,
            "response_mime_type": "application/json",
            "response_json_schema": dict(request.response_schema),
            "temperature": request.temperature,
        }
        if request.max_output_tokens is not None:
            config_values["max_output_tokens"] = request.max_output_tokens

        try:
            with self._client_factory(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
            ) as client:
                response = client.models.generate_content(
                    model=model,
                    contents=request.user_content,
                    config=types.GenerateContentConfig(**config_values),
                )
        except errors.APIError as error:
            raise self._map_api_error(error) from None
        except (TimeoutError, httpx.TimeoutException):
            raise AIProviderTimeoutError("Gemini request timed out") from None
        except AIProviderError:
            raise
        except Exception:
            # The SDK can surface transport implementations other than httpx.
            # Do not include its message: it may contain request details.
            raise AIProviderServerError("Gemini request failed") from None

        usage = self._usage(response)
        request_id = getattr(response, "response_id", None)
        finish_reason = self._finish_reason(response)
        try:
            if finish_reason == "MAX_TOKENS":
                raise ValueError("truncated response")
            raw_text = response.text
            if not isinstance(raw_text, str) or not raw_text.strip():
                raise ValueError("empty response")
            payload = json.loads(raw_text)
            content = request.validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError, KeyError):
            raise AIProviderInvalidResponseError("Gemini returned an invalid structured response",
                usage=usage, request_id=request_id, finish_reason=finish_reason) from None

        return StructuredGenerationResult(
            content=content,
            provider=self.name,
            model=model,
            usage=usage,
            finish_reason=self._finish_reason(response),
            provider_request_id=getattr(response, "response_id", None),
        )

    @staticmethod
    def _map_api_error(error: errors.APIError) -> AIProviderError:
        status = getattr(error, "code", None)
        if status in {401, 403}:
            return AIProviderAuthenticationError("Gemini authentication failed", status_code=status)
        if status == 408:
            return AIProviderTimeoutError('Gemini request timed out', status_code=status)
        if status == 429:
            response = getattr(error, "response", None)
            headers = getattr(response, "headers", {}) or {}
            retry_after = None
            value = headers.get("Retry-After") or headers.get("retry-after")
            if value:
                try:
                    retry_after = max(0, float(value))
                except (ValueError, TypeError):
                    try:
                        retry_after = max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError):
                        pass
            # Inspect provider details locally; never persist their private text.
            details = str(getattr(error, "details", "")) + str(getattr(error, "message", ""))
            exhausted = bool(re.search(r"per.?day|daily|billing|quota.{0,30}limit.{0,10}0", details, re.I))
            match = re.search(r"retryDelay['\"]?\s*:\s*['\"]([0-9.]+)s", details)
            if match:
                retry_after = max(retry_after or 0, float(match.group(1)))
            return AIProviderQuotaError("Gemini quota was exceeded", status_code=status,
                retry_after=retry_after, quota_exhausted=exhausted)
        if isinstance(status, int) and status >= 500:
            value = (getattr(getattr(error, 'response', None), 'headers', {}) or {}).get('Retry-After')
            retry_after = None
            if value:
                try:
                    retry_after = max(0, float(value))
                except (ValueError, TypeError):
                    try:
                        retry_after = max(0, (parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError):
                        pass
            return AIProviderServerError("Gemini service is unavailable", status_code=status, retry_after=retry_after)
        return AIProviderError("Gemini request was rejected", status_code=status)

    @staticmethod
    def _usage(response: Any) -> TokenUsage:
        usage = getattr(response, "usage_metadata", None)
        fields = ("prompt_token_count", "candidates_token_count", "total_token_count",
                  "cached_content_token_count", "thoughts_token_count")
        return TokenUsage(
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            total_tokens=getattr(usage, "total_token_count", 0) or 0,
            cached_input_tokens=getattr(usage, "cached_content_token_count", 0) or 0,
            reasoning_tokens=getattr(usage, "thoughts_token_count", 0) or 0,
            present_fields=frozenset(name for name in fields if getattr(usage, name, None) is not None),
        )

    @staticmethod
    def _finish_reason(response: Any) -> str | None:
        candidates = getattr(response, "candidates", None) or []
        reason = getattr(candidates[0], "finish_reason", None) if candidates else None
        return getattr(reason, "value", None) or (str(reason) if reason is not None else None)
