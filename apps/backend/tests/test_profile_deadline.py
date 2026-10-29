"""Gemini job boundaries replace local profile deadline behavior."""
import unittest
from decimal import Decimal

from app.core.config import Settings
from app.modules.analytics.gemini_worker import (
    AttemptBudget, _attempt_reservation, _conservative_attempt_cost,
)
from app.modules.analytics.providers.base import AIProviderInvalidResponseError


class GeminiBudgetTest(unittest.TestCase):
    def test_attempt_call_and_token_limits_are_hard(self):
        budget=AttemptBudget(max_calls=1,max_tokens=100)
        budget.reserve(50,40)
        with self.assertRaises(AIProviderInvalidResponseError):
            budget.reserve(1,1)

    def test_reservation_uses_the_more_expensive_rate(self):
        settings=Settings(_env_file=None,ai_job_token_budget=100000,
                          ai_input_cost_per_million_usd=.3,ai_output_cost_per_million_usd=2.5)
        self.assertEqual(_attempt_reservation(settings),Decimal("0.25000000"))

    def test_ambiguous_request_keeps_a_nonzero_cost_reservation(self):
        settings=Settings(_env_file=None,ai_input_cost_per_million_usd=.3,
                          ai_output_cost_per_million_usd=2.5)
        budget=AttemptBudget(max_calls=2,max_tokens=10000)
        budget.reserve(8000,1000)
        self.assertEqual(_conservative_attempt_cost(settings,budget),Decimal("0.02250000"))

    def test_real_worker_is_disabled_without_paid_approval(self):
        settings=Settings(_env_file=None)
        self.assertFalse(settings.gemini_worker_enabled)
        self.assertFalse(settings.gemini_paid_service_confirmed)
