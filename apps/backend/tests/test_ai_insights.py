"""Classic insight evidence remains readable while generation is explicitly pending."""
import unittest
from pathlib import Path

from app.modules.analytics.insights import aggregate_evidence, interpret
from app.modules.analytics.interpretation_provider import validate_interpretation

ROOT = Path(__file__).resolve().parents[2]


class InsightCutoverTest(unittest.TestCase):
    def test_small_group_is_not_released(self):
        self.assertIsNone(aggregate_evidence([], [], {}, "unclassified"))

    def test_historical_narrative_validation_rejects_invented_numbers(self):
        content = {"title":"Lectura", "summary":"Promedio 99", "observations":[{"metric":"RATING","interpretation":"Valor 4"}],
                   "suggestions":[], "limitations":["Muestra limitada"]}
        with self.assertRaises(ValueError):
            validate_interpretation(content, {"RATING":{"value":4}})

    def test_generation_function_is_explicitly_unavailable(self):
        with self.assertRaises(Exception) as caught:
            interpret(None, {}, "personal", None)
        self.assertEqual(caught.exception.status_code, 501)

    def test_post_routes_are_not_provider_calls(self):
        source = (ROOT / "backend/app/modules/analytics/insights_router.py").read_text(encoding="utf-8")
        self.assertIn("status_code=501", source)
        self.assertNotIn("generate_interpretation", source)
