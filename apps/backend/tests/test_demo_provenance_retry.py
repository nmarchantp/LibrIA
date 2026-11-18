from contextlib import contextmanager
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
import httpx
from sqlalchemy.exc import DBAPIError
from app.modules.demo.service import mark_demo_result
from app.modules.demo.worker import DemoAPI


def database_error(code):
    class DatabaseFailure(Exception):
        sqlstate = code
    return DBAPIError('INSERT', {}, DatabaseFailure('database failure'))


class Transactions:
    def __init__(self, failures, fail_at=1):
        self.failures = failures
        self.fail_at = fail_at
        self.started = 0
        self.rolled_back = 0
        self.committed = []
        self.attempted = []

    @contextmanager
    def begin(self):
        attempt = self.started
        self.started += 1
        writes = []
        def execute(sql, params):
            writes.append(params)
            self.attempted.append(params)
            if len(writes) == self.fail_at and attempt < len(self.failures):
                raise database_error(self.failures[attempt])
        try:
            yield SimpleNamespace(execute=execute)
        except DBAPIError:
            self.rolled_back += 1
            raise
        else:
            self.committed.extend(writes)


class DemoProvenanceRetryTest(unittest.TestCase):
    def test_deadlock_retries_only_the_same_marker_in_a_fresh_transaction(self):
        transactions = Transactions(['40P01'])
        entity = uuid.uuid4()
        with patch('app.modules.demo.service.SessionLocal', transactions), patch('app.modules.demo.service.time.sleep') as sleep:
            mark_demo_result('/posts/example/comments', {'comment': {'id': str(entity)}})
        self.assertEqual(transactions.started, 2)
        self.assertEqual(transactions.rolled_back, 1)
        self.assertEqual(len(transactions.committed), 1)
        self.assertEqual(transactions.attempted[0], transactions.attempted[1])
        self.assertEqual(transactions.committed[0]['id'], entity)
        sleep.assert_called_once_with(0.05)

    def test_mid_transaction_failure_retries_all_markers_atomically(self):
        transactions = Transactions(['40001'], fail_at=2)
        reading, event = uuid.uuid4(), uuid.uuid4()
        with patch('app.modules.demo.service.SessionLocal', transactions), patch('app.modules.demo.service.time.sleep'):
            mark_demo_result('/readings/events', {'reading_id': str(reading), 'event_id': str(event)})
        self.assertEqual(transactions.rolled_back, 1)
        self.assertEqual(len(transactions.committed), 2)
        self.assertEqual({item['id'] for item in transactions.committed}, {reading,event})
        self.assertEqual(transactions.attempted[:2], transactions.attempted[2:])

    def test_retries_are_bounded_and_exhaustion_is_reported(self):
        transactions = Transactions(['40P01'] * 3)
        with patch('app.modules.demo.service.SessionLocal', transactions), patch('app.modules.demo.service.time.sleep') as sleep:
            with self.assertRaises(DBAPIError):
                mark_demo_result('/posts', {'id':str(uuid.uuid4())})
        self.assertEqual(transactions.started, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(transactions.committed, [])

    def test_schema_and_permission_failures_are_not_retried(self):
        for code in ['42P01', '42501', '23505']:
            with self.subTest(code=code):
                transactions = Transactions([code])
                with patch('app.modules.demo.service.SessionLocal', transactions), patch('app.modules.demo.service.time.sleep') as sleep:
                    with self.assertRaises(DBAPIError):
                        mark_demo_result('/posts', {'id':str(uuid.uuid4())})
                self.assertEqual(transactions.started, 1)
                sleep.assert_not_called()

    def test_unrelated_or_empty_results_do_not_start_transactions(self):
        transactions = Transactions([])
        with patch('app.modules.demo.service.SessionLocal', transactions):
            for path, result in [('/posts', None), ('/posts/example/comments', {}), ('/unknown', {})]:
                mark_demo_result(path, result)
        self.assertEqual(transactions.started, 0)


class DemoApiRetryTest(unittest.IsolatedAsyncioTestCase):
    async def test_marker_deadlock_does_not_repeat_the_http_comment(self):
        requests = []
        entity = str(uuid.uuid4())
        def handler(request):
            requests.append(request)
            return httpx.Response(201, json={'comment': {'id': entity}})
        transactions = Transactions(['40P01'])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='http://demo.test') as client:
            api = DemoAPI(client)
            api.tokens['camila'] = 'fixture-token'
            with patch('app.modules.demo.worker.ensure_enabled'), patch('app.modules.demo.service.SessionLocal', transactions), patch('app.modules.demo.service.time.sleep'):
                result = await api.request('camila', 'POST', '/posts/example/comments', {'body':'Comentario demo'}, sequence=9223)
        self.assertEqual(result['comment']['id'], entity)
        self.assertEqual(len(requests), 1)
        self.assertEqual(transactions.started, 2)
        self.assertEqual(len(transactions.committed), 1)
