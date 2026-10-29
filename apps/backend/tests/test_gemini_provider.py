"""Gemini adapter contracts use a fake SDK client and never make network calls."""

import json
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.modules.analytics.providers import (
    AIProviderAuthenticationError,
    AIProviderInvalidResponseError,
    AIProviderQuotaError,
    AIProviderServerError,
    AIProviderTimeoutError,
    PromptKind,
    StructuredGenerationRequest,
    build_ai_provider,
)
from app.modules.analytics.providers.gemini import GeminiProvider


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    score: int


class FakeResponse:
    def __init__(self, text, *, usage=None):
        self.text = text
        self.response_id = "gemini-response-1"
        self.usage_metadata = usage or SimpleNamespace(
            prompt_token_count=11,
            candidates_token_count=7,
            total_token_count=18,
            cached_content_token_count=2,
            thoughts_token_count=3,
        )
        self.candidates = [SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))]


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = MagicMock()
        if error is not None:
            self.models.generate_content.side_effect = error
        else:
            self.models.generate_content.return_value = response

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class FakeApiError(Exception):
    def __init__(self, code):
        self.code = code


class GeminiProviderTest(unittest.TestCase):
    secret = "test-secret-must-never-appear"

    def request(self):
        return StructuredGenerationRequest.for_pydantic(
            prompt_kind=PromptKind.BOOK_ANALYSIS,
            system_instruction="Return grounded book analysis.",
            user_content=json.dumps({"evidence": "reader-owned"}),
            response_model=ExampleOutput,
            max_output_tokens=200,
        )

    def provider(self, *, response=None, error=None, capture=None):
        def factory(**kwargs):
            if capture is not None:
                capture.update(kwargs)
            return FakeClient(response=response, error=error)
        return GeminiProvider(api_key=self.secret, model="gemini-3.5-flash-lite",
                              timeout_seconds=12, client_factory=factory)

    def test_valid_structured_response_and_token_usage(self):
        captured = {}
        provider = self.provider(response=FakeResponse('{"title":"Válido","score":4}'), capture=captured)
        result = provider.generate_structured(self.request())
        self.assertEqual(result.content, {"title": "Válido", "score": 4})
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model, "gemini-3.5-flash-lite")
        self.assertEqual((result.usage.input_tokens, result.usage.output_tokens, result.usage.total_tokens), (11, 7, 18))
        self.assertEqual(result.usage.cached_input_tokens, 2)
        self.assertEqual(result.usage.reasoning_tokens, 3)
        self.assertEqual(result.finish_reason, "STOP")
        self.assertEqual(captured["api_key"], self.secret)
        self.assertEqual(captured["http_options"].timeout, 12000)
        self.assertIsNone(captured["http_options"].retry_options)

    def test_invalid_json_and_schema_are_rejected(self):
        for value in ("not-json", '{"title":"missing score"}'):
            with self.subTest(value=value):
                with self.assertRaises(AIProviderInvalidResponseError):
                    self.provider(response=FakeResponse(value)).generate_structured(self.request())

    def assert_api_error(self, status, expected):
        with patch("app.modules.analytics.providers.gemini.errors.APIError", FakeApiError):
            with self.assertRaises(expected) as raised:
                self.provider(error=FakeApiError(status)).generate_structured(self.request())
        self.assertNotIn(self.secret, str(raised.exception))

    def test_authentication_error_is_classified(self):
        self.assert_api_error(401, AIProviderAuthenticationError)

    def test_quota_error_is_classified(self):
        self.assert_api_error(429, AIProviderQuotaError)

    def test_server_error_is_classified(self):
        self.assert_api_error(503, AIProviderServerError)

    def test_timeout_is_classified(self):
        with self.assertRaises(AIProviderTimeoutError):
            self.provider(error=TimeoutError()).generate_structured(self.request())

    def test_credentials_are_isolated_and_masked_by_settings(self):
        settings = Settings(gemini_api_key=self.secret, _env_file=None)
        provider = build_ai_provider(settings)
        self.assertNotIn(self.secret, repr(provider))
        self.assertNotIn(self.secret, repr(settings.gemini_api_key))
        self.assertFalse(hasattr(provider, "api_key"))

    def test_adapter_has_no_local_provider_dependency(self):
        response = FakeResponse('{"title":"Solo Gemini","score":5}')
        result = self.provider(response=response).generate_structured(self.request())
        self.assertEqual(result.content["score"], 5)
        source = inspect.getsource(GeminiProvider)
        self.assertNotIn("fast_profile", source)
        self.assertNotIn("interpretation_provider", source)


if __name__ == "__main__":
    unittest.main()
