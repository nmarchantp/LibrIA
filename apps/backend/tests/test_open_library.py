"""Fallback, edition boundaries, selected imports and existing reading/review flow."""
import copy
import unittest
import uuid
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from app.modules.books import open_library
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.open_library_catalog import store_selected
from app.modules.books.router import store_volume
from tests import test_catalog_mirror


def edition_item(number=123456789, title='Spanish book', isbn='9788478885619', work=12345678):
    return open_library.normalize_edition({'key': f'/works/OL{work}W', 'author_name': ['Test Author'], 'subject': ['Fantasy']},
        {'key': f'/books/OL{number}M', 'title': title, 'language': ['spa'], 'isbn': [isbn] if isbn else [],
         'publisher': ['Publisher'], 'publish_date': ['2020'], 'cover_i': 1234, 'number_of_pages': 200})


class OpenLibraryNormalizationTest(unittest.TestCase):
    def test_requires_verified_spanish_edition_not_work_language(self):
        work = {'key': '/works/OL1W', 'language': ['spa'], 'cover_i': 99, 'isbn': ['9788478885619']}
        self.assertIsNone(open_library.normalize_edition(work, {'key': '/books/OL2M', 'title': 'English', 'language': ['eng']}))
        self.assertIsNone(open_library.normalize_edition(work, {'key': '/works/OL2W', 'title': 'Wrong key', 'language': ['spa']}))

    def test_missing_optional_fields_do_not_borrow_other_edition_data(self):
        item = open_library.normalize_edition({'key': '/works/OL1W', 'isbn': ['9788478885619'], 'cover_i': 99, 'number_of_pages': 999},
            {'key': '/books/OL2M', 'title': 'Sin metadatos', 'language': ['spa']})
        self.assertEqual(item['volumeInfo']['language'], 'es')
        for field in ('imageLinks', 'pageCount', 'description', 'publisher', 'publishedDate'):
            self.assertNotIn(field, item['volumeInfo'])
        self.assertEqual(item['volumeInfo']['industryIdentifiers'], [])

    def test_invalid_isbn_is_not_imported(self):
        self.assertIsNone(open_library.isbn('9781234567890'))
        self.assertEqual(open_library.isbn('978-84-7888-561-9'), '9788478885619')

    def test_malformed_edition_language_and_cover_use_safe_defaults(self):
        item = open_library.normalize_edition({'key': '/works/OL1W'}, {'key': '/books/OL2M', 'title': 'Safe',
            'languages': [{'key': None}, {'key': 123}, {'key': '/languages/spa'}], 'cover_i': True, 'covers': [None, -1, True]})
        self.assertIsNotNone(item)
        self.assertNotIn('imageLinks', item['volumeInfo'])

    def test_search_selects_spanish_edition_among_multiple_editions(self):
        data = {'numFound': 22, 'docs': [{'key': '/works/OL1W', 'author_name': ['Author'], 'editions': {'docs': [
            {'key': '/books/OL2M', 'title': 'English', 'language': ['eng']},
            {'key': '/books/OL3M', 'title': 'Español', 'language': ['spa']}]}}]}
        with patch('app.modules.books.open_library.request_json', return_value=data) as provider:
            result = open_library.search('book', 'title', 2)
        self.assertEqual(result['items'][0]['id'], 'openlibrary:OL3M')
        self.assertEqual(result['next_page'], 3)
        self.assertIsNone(result['next_start_index'])
        self.assertEqual(provider.call_args.args[1]['page'], 2)
        self.assertEqual(provider.call_args.args[1]['q'], 'language:spa')

    def test_search_modes_are_explicit_and_no_bulk_detail_calls(self):
        for mode in ('all', 'title', 'author', 'isbn'):
            with patch('app.modules.books.open_library.request_json', return_value={'docs': [], 'numFound': 0}) as request:
                open_library.search('value', mode)
                request.assert_called_once()
                params = request.call_args.args[1]
                self.assertEqual(params['lang'], 'es')
                self.assertEqual(params[mode] if mode != 'all' else params['q'], 'value' if mode != 'all' else 'value language:spa')

    def test_http_failure_is_bounded_and_application_is_identified(self):
        request = httpx.Request('GET', 'https://openlibrary.org/search.json')
        with patch('app.modules.books.open_library.httpx.Client') as client, patch('app.modules.books.open_library.time.sleep'):
            transport = client.return_value.__enter__.return_value
            transport.get.return_value = httpx.Response(503, json={}, request=request)
            with self.assertRaises(HTTPException):
                open_library.search('book')
            self.assertEqual(transport.get.call_count, 2)
            self.assertIn('LibrIAverse', client.call_args.kwargs['headers']['User-Agent'])


class OpenLibraryIntegrationTest(unittest.TestCase):
    setUp = test_catalog_mirror.CatalogMirrorTest.setUp
    tearDown = test_catalog_mirror.CatalogMirrorTest.tearDown

    def item(self, **kwargs):
        return edition_item(number=uuid.uuid4().int % 10**12, title=self.volume['volumeInfo']['title'], **kwargs)

    def search_result(self, item, more=False):
        return {'items': [item], 'active_provider': 'open_library', 'has_more': more,
                'next_page': 2 if more else None, 'next_start_index': None}

    def test_google_success_does_not_call_fallback(self):
        with patch('app.modules.books.router.google_request', return_value={'items': [self.volume], 'has_more': False}):
            result = self.client.get('/api/books', params={'q': self.volume['volumeInfo']['title']}).json()
        self.assertEqual(result['totalItems'], 1)
        self.fallback.assert_not_called()

    def test_google_failures_and_zero_use_fallback_without_bulk_import(self):
        for status in (503, 429, 0):
            item = self.item(isbn=None)
            self.fallback.return_value = self.search_result(item, more=True)
            query = self.volume['volumeInfo']['title'] + str(status)
            before = self.db.scalar(select(func.count()).select_from(Work))
            with patch('app.modules.books.router.google_request', **({'side_effect': HTTPException(502, {'code': 'quota' if status == 429 else 'unavailable'})} if status else {'return_value': {'items': []}})):
                result = self.client.get('/api/books', params={'q': query}).json()
            self.assertEqual(result['items'][0]['id'], item['id'])
            self.assertNotIn('warning', result)
            self.assertTrue(result['has_more'])
            self.assertEqual(self.db.scalar(select(func.count()).select_from(Work)), before)

    def test_both_fail_keep_local_and_offer_retry_not_more(self):
        store_volume(self.db, self.volume, complete=True)
        self.fallback.side_effect = HTTPException(502, 'offline')
        with patch('app.modules.books.router.google_request', side_effect=HTTPException(502, 'offline')):
            result = self.client.get('/api/books', params={'q': self.volume['volumeInfo']['title']}).json()
        self.assertEqual(result['totalItems'], 1)
        self.assertTrue(result['partial'])
        self.assertFalse(result['has_more'])

    def test_existing_isbn_reuses_edition_and_does_not_overwrite_metadata(self):
        item = self.item()
        google = copy.deepcopy(self.volume)
        google['volumeInfo']['publisher'] = 'Trusted publisher'
        google['volumeInfo']['industryIdentifiers'] = item['volumeInfo']['industryIdentifiers']
        source = store_volume(self.db, google, complete=True)
        before = self.db.get(Edition, source.edition_id)
        original = (before.title, before.publisher_name, before.page_count, before.cover_url, before.work_id)
        selected = store_selected(self.db, item)
        self.assertEqual(selected.id, source.edition_id)
        self.assertEqual((selected.title, selected.publisher_name, selected.page_count, selected.cover_url, selected.work_id), original)

    def test_same_work_different_editions_stay_distinct(self):
        first = self.item(isbn=None)
        second = copy.deepcopy(first)
        second['id'] = 'openlibrary:OL987654321M'
        second['openLibrary']['editionKey'] = 'OL987654321M'
        second['volumeInfo']['pageCount'] = 321
        edition1 = store_selected(self.db, first)
        edition2 = store_selected(self.db, second)
        self.assertNotEqual(edition1.id, edition2.id)
        self.assertEqual(edition1.work_id, edition2.work_id)
        self.assertEqual(edition1.page_count, 200)
        self.assertEqual(edition2.page_count, 321)

    def test_duplicate_reference_is_idempotent(self):
        item = self.item(isbn=None)
        self.assertEqual(store_selected(self.db, item).id, store_selected(self.db, item).id)

    def test_later_google_import_reuses_open_library_isbn_without_erasing_fields(self):
        item = self.item()
        first = store_selected(self.db, item)
        google = copy.deepcopy(self.volume)
        google['volumeInfo'].update(title=item['volumeInfo']['title'], authors=item['volumeInfo']['authors'], industryIdentifiers=item['volumeInfo']['industryIdentifiers'])
        google['volumeInfo'].pop('pageCount', None)
        google['volumeInfo'].pop('imageLinks', None)
        source = store_volume(self.db, google, complete=True)
        self.assertEqual(source.edition_id, first.id)
        self.assertEqual(first.page_count, 200)
        self.assertIn('covers.openlibrary.org', first.cover_url)

    def test_same_title_different_named_authors_is_not_merged(self):
        item = self.item(isbn=None)
        first = store_selected(self.db, item)
        second_item = copy.deepcopy(item)
        second_item['id'] = 'openlibrary:OL919191919M'
        second_item['openLibrary'] = {'workKey': 'OL929292929W', 'editionKey': 'OL919191919M'}
        second_item['volumeInfo']['authors'] = ['Different Author']
        second = store_selected(self.db, second_item)
        self.assertNotEqual(first.work_id, second.work_id)

    def test_provider_pagination_does_not_requery_google(self):
        item = self.item(isbn=None)
        self.fallback.return_value = self.search_result(item)
        with patch('app.modules.books.router.google_request') as google:
            result = self.client.get('/api/books', params={'q': self.volume['volumeInfo']['title'], 'provider': 'open_library', 'page': 2}).json()
        google.assert_not_called()
        self.fallback.assert_called_once_with(self.volume['volumeInfo']['title'], 'all', 2)
        self.assertFalse(result['has_more'])

    def test_cached_transient_results_survive_reload(self):
        item = self.item(isbn=None)
        self.fallback.return_value = self.search_result(item)
        query = self.volume['volumeInfo']['title']
        self.client.get('/api/books', params={'q': query})
        self.fallback.reset_mock()
        result = self.client.get('/api/books', params={'q': query}).json()
        self.assertEqual(result['items'][0]['id'], item['id'])
        self.fallback.assert_not_called()

    def test_failed_refresh_keeps_last_successful_discovery_and_one_warning(self):
        from datetime import timedelta
        from app.modules.books.models import CatalogQuery
        item = self.item(isbn=None)
        self.fallback.return_value = self.search_result(item)
        query = self.volume['volumeInfo']['title']
        self.client.get('/api/books', params={'q': query, 'search_by': 'title'})
        cached = self.db.get(CatalogQuery, 'es-only-v4:title:' + query.casefold() + ':google_books:0')
        cached.fetched_at -= timedelta(seconds=11)
        self.db.flush()
        self.fallback.side_effect = HTTPException(502, 'Open Library timeout')
        with patch('app.modules.books.router.google_request', side_effect=HTTPException(502, 'Google unavailable')):
            response = self.client.get('/api/books', params={'q': query, 'search_by': 'title', 'refresh': True})
        data = response.json()
        self.assertEqual(data['items'][0]['id'], item['id'])
        self.assertTrue(data['partial'])
        self.assertFalse(data['has_more'])
        self.assertEqual(data['warning'].count('temporalmente limitada'), 1)
        self.assertNotIn('pueden faltar libros', data['warning'])
        again = self.client.get('/api/books', params={'q': query, 'search_by': 'title'}).json()
        self.assertEqual(again['items'][0]['id'], item['id'])
        self.assertEqual(again['warning'], data['warning'])

    def test_old_cached_failure_message_is_deduplicated_without_db_rewrite(self):
        from datetime import datetime, timezone
        from app.modules.books.models import CatalogQuery
        query = self.volume['volumeInfo']['title']
        original = {'items': [], 'partial': True, 'error_code': 'external_unavailable',
                    'warning': 'La búsqueda externa está temporalmente limitada. Mostramos los resultados disponibles; pueden faltar libros.'}
        self.db.add(CatalogQuery(query='es-only-v4:title:' + query.casefold() + ':google_books:0',
                                 payload=original, fetched_at=datetime.now(timezone.utc)))
        self.db.flush()
        response = self.client.get('/api/books', params={'q': query, 'search_by': 'title'}).json()
        self.assertEqual(response['warning'].count('temporalmente limitada'), 1)
        self.assertNotIn('pueden faltar libros', response['warning'])
        stored = self.db.get(CatalogQuery, 'es-only-v4:title:' + query.casefold() + ':google_books:0')
        self.assertEqual(stored.payload, original)

    def test_select_add_read_and_review_use_existing_internal_relationships(self):
        item = self.item(isbn=None)
        self.fallback.return_value = self.search_result(item)
        self.client.get('/api/books', params={'q': self.volume['volumeInfo']['title']})
        with patch('app.modules.books.open_library.detail', return_value=item):
            detail = self.client.get('/api/books/' + item['id']).json()
        account = self.client.post('/api/auth/register', json={'email': uuid.uuid4().hex + '@example.com', 'password': 'test-password', 'display_name': 'OL reader'}).json()
        headers = {'Authorization': 'Bearer ' + account['access_token']}
        reading = self.client.post('/api/readings/library', headers=headers, json={'book_ref': item['id'], 'book_title': item['volumeInfo']['title'], 'page_count': 200})
        self.assertEqual(reading.status_code, 200, reading.text)
        self.assertEqual(reading.json()['work_id'], detail['libria']['workId'])
        restored = self.client.get('/api/readings/me', headers=headers).json()[0]
        self.assertEqual(restored['catalog_volume']['id'], item['id'])
        self.assertEqual(restored['catalog_volume']['volumeInfo']['authors'], ['Test Author'])
        event = {'book_ref': item['id'], 'book_title': item['volumeInfo']['title'], 'page_count': 200, 'event': 'start'}
        started = self.client.post('/api/readings/events', headers=headers, json=event)
        self.assertEqual(started.status_code, 201, started.text)
        finished = self.client.post('/api/readings/events', headers=headers, json={**event, 'event': 'finish', 'reading_id': started.json()['reading_id']})
        self.assertEqual(finished.status_code, 201, finished.text)
        review = self.client.post('/api/reviews', headers=headers, json={'work_id': detail['libria']['workId'], 'edition_id': detail['libria']['editionId'], 'body': 'A review after discovery', 'rating': 4.5})
        self.assertEqual(review.status_code, 201, review.text)
        fresh = self.client.get('/api/books/' + detail['id']).json()
        self.assertEqual(fresh['libria']['averageRating'], 4.5)
        self.assertEqual(fresh['libria']['ratingsCount'], 1)
        self.assertEqual(fresh['libria']['readingStats']['finished'], 1)
