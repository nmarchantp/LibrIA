import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from fastapi import Response
from app.core.config import Settings
from app.modules.analytics.generation_runtime import generation_runtime
from app.modules.analytics import insights_router


class GenerationRuntimeTest(unittest.TestCase):
    def test_disabled_is_reported_without_activating_service(self):
        result = generation_runtime(Settings(_env_file=None))
        self.assertFalse(result['generation_enabled'])
        self.assertEqual(result['generation_blocked_reason'], 'worker_disabled')

    def test_activation_is_required_even_if_worker_flag_is_on(self):
        result = generation_runtime(Settings(_env_file=None, gemini_worker_enabled=True))
        self.assertFalse(result['generation_enabled'])
        self.assertEqual(result['generation_blocked_reason'], 'activation_required')

    def test_existing_authorized_config_is_reported_as_enabled(self):
        for flags in ({'gemini_paid_service_confirmed':True}, {'gemini_free_test_mode':True}):
            with self.subTest(flags=flags):
                settings = Settings(_env_file=None, app_env='development', gemini_worker_enabled=True, **flags)
                self.assertTrue(generation_runtime(settings)['generation_enabled'])

    def test_recommendation_get_keeps_result_and_does_not_enqueue(self):
        db, owner = MagicMock(), SimpleNamespace(id='owner')
        stored = {'status':'outdated','generation_status':'pending','recommendations':None,'job_id':'saved'}
        with patch.object(insights_router,'recommendation_state',return_value=stored) as read, \
             patch.object(insights_router,'get_settings',return_value=Settings(_env_file=None)):
            result=insights_router.current_recommendation_state(Response(),owner,db)
        self.assertEqual(result['job_id'],'saved')
        self.assertEqual(result['generation_status'],'pending')
        self.assertFalse(result['generation_enabled'])
        read.assert_called_once_with(db,owner.id,enqueue=False)
        db.execute.assert_not_called()
