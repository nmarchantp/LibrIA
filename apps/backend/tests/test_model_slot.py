"""The local model slot is a fail-closed compatibility surface."""
import asyncio
import unittest

from app.modules.analytics.adaptive_ai import LegacyAIFlowDisabled
from app.modules.analytics.model_slot import model_slot


class ModelSlotCutoverTest(unittest.TestCase):
    def test_slot_cannot_reactivate_local_transport(self):
        async def enter():
            async with model_slot():
                pass
        with self.assertRaises(LegacyAIFlowDisabled):
            asyncio.run(enter())
