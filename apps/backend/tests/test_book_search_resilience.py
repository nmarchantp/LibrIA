from datetime import datetime, timedelta, timezone
import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from app.core.config import Settings
from app.modules.books.models import CatalogQuery
from tests import test_catalog_mirror


class SearchResilienceTest(unittest.TestCase):
    setUp = test_catalog_mirror.CatalogMirrorTest.setUp
    tearDown = test_catalog_mirror.CatalogMirrorTest.tearDown

    def query(self):
        return 'Stable ' + uuid.uuid4().hex

    def cached(self, query, age, **metadata):
        self.db.add(CatalogQuery(query='es-only-v4:all:' + query.casefold() + ':google_books:0',
            payload={'items': [], 'has_more': False, **metadata},
            fetched_at=datetime.now(timezone.utc) - timedelta(seconds=age)))
        self.db.flush()

    def test_expired_empty_cache_is_refreshed(self):
        query = self.query()
        self.cached(query, 601)
        with patch('app.modules.books.router.google_request', return_value={'items': []}) as provider:
            self.assertEqual(self.client.get('/api/books', params={'q': query}).status_code, 200)
            provider.assert_called_once()

    def test_force_refresh_bypasses_success_cache_after_cooldown(self):
        query = self.query()
        self.cached(query, 11)
        with patch('app.modules.books.router.google_request', return_value={'items': []}) as provider:
            self.client.get('/api/books', params={'q': query})
            provider.assert_not_called()
            self.client.get('/api/books', params={'q': query, 'refresh': True})
            provider.assert_called_once()
            self.client.get('/api/books', params={'q': query, 'refresh': True})
            provider.assert_called_once()

    def test_success_cache_expires_after_day(self):
        query = self.query()
        self.cached(query, 86401, items=[{'id': 'old'}])
        with patch('app.modules.books.router.google_request', return_value={'items': []}) as provider:
            self.client.get('/api/books', params={'q': query})
            provider.assert_called_once()

    def test_retry_after_also_applies_to_subsequent_requests(self):
        query = self.query()
        self.cached(query, 40, partial=True, error_code='quota', retry_after=120)
        with patch('app.modules.books.router.google_request') as provider:
            result = self.client.get('/api/books', params={'q': query, 'refresh': True}).json()
            self.assertTrue(result['partial'])
            provider.assert_not_called()

    def test_available_provider_books_survive_partial_failure_and_reload(self):
        query = self.query()
        good = {**self.volume, 'volumeInfo': {**self.volume['volumeInfo'], 'title': query}}
        with patch('app.modules.books.router.google_request', return_value={
                'items': [good], 'partial': True, 'error_code': 'unavailable',
                'warning': 'Temporary failure', 'has_more': True, 'next_start_index': 40}):
            first = self.client.get('/api/books', params={'q': query}).json()
        self.assertEqual(len(first['items']), 1)
        self.assertTrue(first['partial'])
        with patch('app.modules.books.router.google_request') as provider:
            self.db.expire_all()
            again = self.client.get('/api/books', params={'q': query}).json()
            self.assertEqual(again['items'][0]['id'], first['items'][0]['id'])
            provider.assert_not_called()

    def test_malformed_items_and_optional_fields_do_not_break_good_books(self):
        query = self.query()
        good = {**self.volume, 'volumeInfo': {**self.volume['volumeInfo'], 'title': query,
            'authors': None, 'industryIdentifiers': [None], 'imageLinks': None, 'subtitle': 42}}
        with patch('app.modules.books.router.google_request', return_value={'items': [None, {}, good]}):
            result = self.client.get('/api/books', params={'q': query}).json()
        self.assertEqual(len(result['items']), 1)
        self.assertTrue(result['partial'])

    def test_explicit_page_is_forwarded_and_metadata_returned(self):
        with patch('app.modules.books.router.google_request', return_value={'items': [], 'has_more': False,
                     'next_start_index': None}) as provider:
            query = self.query()
            result = self.client.get('/api/books', params={'q': query, 'start_index': 40}).json()
            provider.assert_called_once_with(query=query, start_index=40)
            self.assertFalse(result['has_more'])

    def test_cache_is_rechecked_after_lock(self):
        query = self.query()
        ready = {'items': [], 'totalItems': 0}
        with patch('app.modules.books.router.cached_search_payload', side_effect=[None, ready]) as cache, \
             patch('app.modules.books.router.google_request') as provider:
            self.assertEqual(self.client.get('/api/books', params={'q': query}).json(), ready)
            self.assertEqual(cache.call_count, 2)
            provider.assert_not_called()

    def test_known_books_remain_available_when_google_is_unavailable(self):
        from app.modules.books.router import store_volume
        source = store_volume(self.db, self.volume, complete=True)
        self.db.flush()
        with patch('app.modules.books.router.google_request', side_effect=HTTPException(502, 'offline')) as provider:
            result = self.client.get('/api/books/' + self.volume['id'])
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['libria']['editionId'], str(source.edition_id))
            provider.assert_not_called()


class LocalOriginsTest(unittest.TestCase):
    def test_only_configured_loopback_development_origin_is_aliased(self):
        settings = Settings(frontend_origins='http://localhost:5173', app_env='development')
        self.assertEqual(settings.cors_origins, ['http://localhost:5173', 'http://127.0.0.1:5173'])
        self.assertNotIn('http://example.com:5173', settings.cors_origins)
        self.assertEqual(Settings(frontend_origins='http://localhost:9999').cors_origins, ['http://localhost:9999'])

    def test_production_origin_is_not_expanded(self):
        settings = Settings(
            app_env='production',
            jwt_secret='x' * 64,
            frontend_origins='https://libria.example',
            gemini_free_test_mode=False,
        )
        self.assertEqual(settings.cors_origins, ['https://libria.example'])
