import asyncio
import unittest
from unittest.mock import patch
from pydantic import SecretStr
from app.core.config import Settings
from app.modules.analytics.gemini_worker import worker_loop


class WorkerConfigurationReloadTest(unittest.IsolatedAsyncioTestCase):
    async def run_two_batches(self, configurations):
        calls = []
        sleeps = 0
        def process(**kwargs):
            calls.append(kwargs['settings'])
            return True
        async def pause(seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps == 2:
                raise asyncio.CancelledError()
        with patch('app.modules.analytics.gemini_worker.get_settings', side_effect=configurations) as settings, \
             patch('app.modules.analytics.gemini_worker.process_one', side_effect=process), \
             patch('app.modules.analytics.gemini_worker.asyncio.sleep', side_effect=pause):
            with self.assertRaises(asyncio.CancelledError):
                await worker_loop()
            self.assertEqual(settings.cache_clear.call_count, 2)
        return calls

    async def test_new_credentials_are_loaded_between_batches(self):
        first = Settings(_env_file=None, gemini_worker_enabled=True, gemini_paid_service_confirmed=True,
                         ai_max_concurrent_requests=1, gemini_api_key=SecretStr('first-fixture-key'))
        second = first.model_copy(update={'gemini_api_key':SecretStr('second-fixture-key')})
        calls = await self.run_two_batches([first, second])
        self.assertEqual(calls, [first, second])
        self.assertNotEqual(calls[0].gemini_api_key, calls[1].gemini_api_key)

    async def test_disabling_worker_prevents_provider_calls(self):
        enabled = Settings(_env_file=None, gemini_worker_enabled=True, gemini_paid_service_confirmed=True,
                           ai_max_concurrent_requests=1)
        disabled = enabled.model_copy(update={'gemini_worker_enabled':False})
        self.assertEqual(await self.run_two_batches([enabled, disabled]), [enabled])

    async def test_invalid_configuration_does_not_kill_worker_or_log_secrets(self):
        enabled = Settings(_env_file=None, gemini_worker_enabled=True, gemini_paid_service_confirmed=True,
                           ai_max_concurrent_requests=1)
        with patch('app.modules.analytics.gemini_worker.LOGGER.error') as error_log:
            calls = await self.run_two_batches([ValueError('private configuration details'), enabled])
        self.assertEqual(calls, [enabled])
        error_log.assert_called_once()
        self.assertNotIn('private configuration details', str(error_log.call_args))
