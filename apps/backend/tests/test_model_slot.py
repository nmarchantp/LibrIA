"""Cross-connection exclusion and cancellation release with real PostgreSQL."""
import asyncio
import unittest
import uuid
from app.modules.analytics.model_slot import model_slot


class ModelSlotTest(unittest.TestCase):
    def test_parallel_callers_use_only_one_slot(self):
        key=1230000000+uuid.uuid4().int%100000000
        active=0
        async def request():
            nonlocal active
            async with model_slot(key):
                active+=1
                self.assertEqual(active,1)
                await asyncio.sleep(.01)
                active-=1
        async def run():
            await asyncio.gather(request(),request(),request())
        asyncio.run(run())

    def test_queue_deadline_and_cancelled_request_release_connection_lock(self):
        key=1230000000+uuid.uuid4().int%100000000
        async def run():
            async with model_slot(key):
                with self.assertRaises(TimeoutError):
                    async with asyncio.timeout(.03):
                        async with model_slot(key):
                            self.fail('Concurrent model use')
            entered=asyncio.Event()
            async def cancelled_request():
                async with model_slot(key):
                    entered.set()
                    await asyncio.sleep(10)
            task=asyncio.create_task(cancelled_request())
            await entered.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            async with asyncio.timeout(1):
                async with model_slot(key):
                    pass
        asyncio.run(run())
