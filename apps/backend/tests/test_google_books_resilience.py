import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from app.modules.books.google_books import google_request


def response(status=200, data=None, headers=None):
    return httpx.Response(status, json=data or {}, headers=headers,
                          request=httpx.Request('GET', 'https://www.googleapis.com/books/v1/volumes'))


def volume(n):
    return {'id': str(n), 'volumeInfo': {'title': 'Book ' + str(n), 'language': 'es'}}


class GoogleResilienceTest(unittest.TestCase):
    def setUp(self):
        self.client_patch = patch('app.modules.books.google_books.httpx.Client')
        self.transport = self.client_patch.start().return_value.__enter__.return_value
        self.sleep_patch = patch('app.modules.books.google_books.time.sleep')
        self.sleep = self.sleep_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.addCleanup(self.sleep_patch.stop)

    def test_initial_search_only_requests_one_page(self):
        self.transport.get.return_value = response(data={'items': [volume(n) for n in range(40)]})
        result = google_request(query='book')
        self.assertEqual(self.transport.get.call_count, 1)
        self.assertTrue(result['has_more'])
        self.assertEqual(result['next_start_index'], 40)

    def test_explicit_next_page(self):
        self.transport.get.return_value = response(data={'items': [volume(41)]})
        result = google_request(query='book', start_index=40)
        self.assertFalse(result['has_more'])
        self.assertEqual(self.transport.get.call_args.kwargs['params']['startIndex'], 40)

    def test_transient_retry_is_exponential_and_bounded(self):
        self.transport.get.side_effect = [response(503), response(503), response(data={'items': [volume(1)]})]
        self.assertEqual(len(google_request(query='book')['items']), 1)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [0.5, 1])

    def test_later_failure_keeps_first_page_and_retry_cursor(self):
        self.transport.get.side_effect = [response(data={'items': [volume(n) for n in range(40)]})] + [response(503)] * 3
        result = google_request(query='book', pages=2)
        self.assertEqual(len(result['items']), 40)
        self.assertTrue(result['partial'])
        self.assertEqual(result['next_start_index'], 40)

    def test_quota_without_retry_after_does_not_repeat(self):
        self.transport.get.return_value = response(429)
        with self.assertRaises(HTTPException) as caught:
            google_request(query='book')
        self.assertEqual(caught.exception.detail['code'], 'quota')
        self.assertEqual(self.transport.get.call_count, 1)
        self.sleep.assert_not_called()

    def test_retry_after_seconds_and_date(self):
        for header in ['1', format_datetime(datetime.now(timezone.utc) + timedelta(seconds=2), usegmt=True)]:
            self.sleep.reset_mock()
            self.transport.get.side_effect = [response(503, headers={'Retry-After': header}), response(data={'items': []})]
            google_request(query='book')
            self.assertGreaterEqual(self.sleep.call_args.args[0], 0.5)
            self.assertLessEqual(self.sleep.call_args.args[0], 3)

    def test_long_retry_after_never_retries_early(self):
        self.transport.get.return_value = response(503, headers={'Retry-After': '120'})
        with self.assertRaises(HTTPException):
            google_request(query='book')
        self.assertEqual(self.transport.get.call_count, 1)
        self.sleep.assert_not_called()

    def test_null_items_is_empty_and_invalid_entries_are_skipped(self):
        self.transport.get.return_value = response(data={'items': None})
        self.assertEqual(google_request(query='book')['items'], [])
        self.transport.get.return_value = response(data={'items': [None, {}, {'id': 'bad', 'volumeInfo': []}, volume(1)]})
        result = google_request(query='book')
        self.assertEqual(result['items'], [volume(1)])
        self.assertTrue(result['partial'])

    def test_invalid_top_level_and_http_codes_are_classified(self):
        for status, code in [(400, 'invalid_query'), (403, 'permissions'), (429, 'quota'), (500, 'unavailable')]:
            self.transport.get.side_effect = None
            self.transport.get.return_value = response(status)
            with self.assertRaises(HTTPException) as caught:
                google_request(query='book')
            self.assertEqual(caught.exception.detail['code'], code)
        self.transport.get.return_value = response(data=['invalid'])
        with self.assertRaises(HTTPException) as caught:
            google_request(query='book')
        self.assertEqual(caught.exception.detail['code'], 'invalid_response')

    def test_timeouts_are_bounded_and_classified(self):
        self.transport.get.side_effect = httpx.ConnectTimeout('simulated')
        with self.assertRaises(HTTPException) as caught:
            google_request(query='book')
        self.assertEqual(caught.exception.detail['code'], 'connection')
        self.assertEqual(self.transport.get.call_count, 3)
        self.assertLessEqual(sum(call.args[0] for call in self.sleep.call_args_list), 3)

    def test_retry_after_on_quota_can_recover(self):
        self.transport.get.side_effect = [response(429, headers={'Retry-After': '1'}), response(data={'items': []})]
        self.assertEqual(google_request(query='book')['items'], [])
        self.assertEqual(self.sleep.call_args.args[0], 1)

    def test_exhausted_request_budget_stops_before_another_request(self):
        self.transport.get.return_value = response(503)
        with patch('app.modules.books.google_books.time.monotonic', side_effect=[0, 0, 16, 16]):
            with self.assertRaises(HTTPException):
                google_request(query='book')
        self.assertEqual(self.transport.get.call_count, 1)
        self.sleep.assert_not_called()

    def test_logs_do_not_include_key_query_or_provider_body(self):
        from types import SimpleNamespace
        self.transport.get.return_value = response(503, {'error': {'message': 'Sensitive provider body'}})
        with patch('app.modules.books.google_books.get_settings', return_value=SimpleNamespace(google_books_api_key='secret-value')), \
             self.assertLogs('app.modules.books.google_books', level='WARNING') as captured:
            with self.assertRaises(HTTPException):
                google_request(query='private-search-text')
        messages = ' '.join(captured.output)
        for secret in ('secret-value', 'private-search-text', 'Sensitive provider body'):
            self.assertNotIn(secret, messages)
