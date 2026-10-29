"""Stage 6 regressions for the disabled adaptive provider and retained schemas."""
import asyncio
import unittest

from app.modules.analytics.adaptive_ai import (
    LegacyAIFlowDisabled, process_one, validate_book_quality, validate_profile_quality,
)
from app.modules.analytics.adaptive_worker import worker_loop


class AdaptiveCutoverTest(unittest.TestCase):
    def test_legacy_worker_fails_closed(self):
        with self.assertRaises(LegacyAIFlowDisabled):
            process_one()
        with self.assertRaises(LegacyAIFlowDisabled):
            asyncio.run(worker_loop())

    def test_placeholder_profiles_remain_rejected(self):
        with self.assertRaises(ValueError):
            validate_profile_quality({"literary_identity": "resumen", "interpretation": "texto"})

    def test_placeholder_book_analysis_remains_rejected(self):
        with self.assertRaises(ValueError):
            validate_book_quality({"interpretation": "summary", "emotions": [],
                                   "valued_aspects": [], "questioned_aspects": [], "preferences": []})
