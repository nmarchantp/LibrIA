import unittest
from unittest.mock import MagicMock, patch
from app.core.config import Settings
from app.modules.analytics.providers import factory
from app.modules.analytics.providers.base import AIProviderQuotaError, AIProviderConfigurationError
from app.modules.analytics.gemini_worker import _invoke, AttemptBudget


class GeminiOnlyTest(unittest.TestCase):
    def test_factory_has_no_secondary_provider_or_secret_configuration(self):
        self.assertFalse(hasattr(factory, 'build_secondary_provider'))
        self.assertFalse(hasattr(factory, 'OpenAIProvider'))
        settings = Settings(_env_file=None)
        self.assertEqual(settings.ai_provider, 'gemini')
        self.assertNotIn('openai_api_key', Settings.model_fields)
        self.assertNotIn('openai_fallback_enabled', Settings.model_fields)

    def test_gemini_error_propagates_without_a_second_provider_attempt(self):
        provider = MagicMock()
        provider.name = 'gemini'
        budget = AttemptBudget(24, 100000)
        error = AIProviderQuotaError('Gemini quota')
        with patch('app.modules.analytics.gemini_worker._invoke_once', side_effect=error) as invoke:
            with self.assertRaises(AIProviderQuotaError) as raised:
                _invoke(MagicMock(), provider, MagicMock(), budget, Settings(_env_file=None))
        self.assertIs(raised.exception, error)
        invoke.assert_called_once()
        self.assertIs(invoke.call_args.args[1], provider)
        self.assertIs(invoke.call_args.args[3], budget)

    def test_non_gemini_provider_is_rejected_before_any_database_or_network_use(self):
        db, provider = MagicMock(), MagicMock()
        provider.name = 'openai'
        with self.assertRaises(AIProviderConfigurationError):
            _invoke(db, provider, MagicMock(), AttemptBudget(24, 100000), Settings(_env_file=None))
        db.execute.assert_not_called()
        provider.generate_structured.assert_not_called()
