"""Community totals from persisted library attempts and public general ratings."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.router import store_volume
from app.modules.library.models import LibraryEntry, Reading
from app.modules.social.models import Review
from app.modules.users.identities import create_personal_profile
from app.modules.users.models import User


class BookCommunityTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Community test reader")
        self.other = User(display_name="Second community reader")
        self.db.add_all([self.user, self.other])
        self.db.flush()
        create_personal_profile(self.db, self.user)
        create_personal_profile(self.db, self.other)
        self.volume = {"id": "community-" + uuid.uuid4().hex, "volumeInfo": {
            "title": "Community work " + uuid.uuid4().hex, "authors": ["Community Author"],
            "language": "es", "pageCount": 100,
        }}
        self.source = store_volume(self.db, self.volume, complete=True)
        self.edition = self.db.get(Edition, self.source.edition_id)
        self.work_id = self.edition.work_id
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def stats(self, ref=None):
        response = self.client.get('/api/books/' + str(ref or self.volume['id']))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        return response.json()['libria']

    def event(self, kind, reading_id=None):
        payload = dict(book_ref=self.volume['id'], book_title=self.volume['volumeInfo']['title'],
                       edition_id=str(self.edition.id), page_count=100, event=kind)
        if reading_id:
            payload['reading_id'] = reading_id
        response = self.client.post('/api/readings/events', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['reading_id']

    def review(self, rating=4.5, status='published'):
        response = self.client.post('/api/reviews', json={
            'work_id': str(self.work_id), 'edition_id': str(self.edition.id),
            'body': 'A persisted review', 'rating': rating, 'status': status,
            'dimension_ratings': {'romance': 1, 'spicy': 5},
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def edit(self, review, rating, status='published'):
        response = self.client.put('/api/reviews/' + review['id'], json={
            'body': 'An edited review', 'rating': rating, 'status': status,
            'edition_id': str(self.edition.id), 'dimension_ratings': {'romance': 5},
        })
        self.assertEqual(response.status_code, 200, response.text)

    def assert_readers(self, finished=0, reading=0, abandoned=0):
        stats = self.stats()['readingStats']
        self.assertEqual({key: stats[key] for key in ('finished', 'reading', 'abandoned')},
                         dict(finished=finished, reading=reading, abandoned=abandoned))

    def test_reading_to_finished_and_fresh_reload(self):
        self.assert_readers()
        response = self.client.post('/api/readings/library', json={
            'book_ref': self.volume['id'], 'book_title': self.volume['volumeInfo']['title'], 'page_count': 100})
        self.assertEqual(response.status_code, 200, response.text)
        self.assert_readers()
        reading = self.event('start')
        self.assert_readers(reading=1)
        self.event('finish', reading)
        self.assert_readers(finished=1)
        self.db.expire_all()
        self.assert_readers(finished=1)

    def test_latest_attempt_only_and_removal(self):
        reading = self.event('start')
        self.event('finish', reading)
        self.assert_readers(finished=1)
        second = self.event('start')
        self.assert_readers(reading=1)
        self.event('abandon', second)
        self.assert_readers(abandoned=1)
        response = self.client.delete('/api/readings/library/' + str(self.work_id))
        self.assertEqual(response.status_code, 204, response.text)
        self.assert_readers()
        self.assertEqual(self.stats()['readingStats']['readerPreview'], [])

    def test_general_rating_edit_and_delete(self):
        review = self.review(4.5)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (4.5, 1))
        self.edit(review, 3.75)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (3.75, 1))
        self.assertEqual(self.client.delete('/api/reviews/' + review['id']).status_code, 204)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (None, 0))

    def test_two_users_and_private_or_missing_general_rating(self):
        first = self.review(4.25)
        self.user, self.other = self.other, self.user
        second = self.review(4.75)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (4.5, 2))
        self.edit(second, 5, 'hidden')
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (4.25, 1))
        public = self.client.get('/api/reviews/by-book/' + self.volume['id']).json()['items']
        self.assertEqual([item['id'] for item in public], [first['id']])
        self.edit(second, None)
        self.assertEqual(self.stats()['ratingsCount'], 1)
        self.user, self.other = self.other, self.user
        self.edit(first, None)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (None, 0))

    def test_draft_never_contributes(self):
        review = self.review(5, 'draft')
        self.assertEqual(self.stats()['ratingsCount'], 0)
        self.assertEqual(self.client.get('/api/reviews/by-book/' + self.volume['id']).json()['items'], [])
        self.edit(review, 0.25)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (0.25, 1))

    def test_internal_external_and_edition_identifiers_share_totals(self):
        self.event('finish', self.event('start'))
        self.review()
        with patch('app.modules.books.router.google_request') as provider:
            for ref in (self.volume['id'], self.work_id, self.edition.id):
                totals = self.stats(ref)
                self.assertEqual((totals['averageRating'], totals['ratingsCount']), (4.5, 1))
                self.assertEqual(totals['readingStats']['finished'], 1)
            provider.assert_not_called()
        self.assertEqual(self.source.payload, self.volume)

    def test_equivalent_works_deduplicate_users_without_merging_records(self):
        self.event('finish', self.event('start'))
        self.review(3)
        duplicate = Work(title=self.volume['volumeInfo']['title'])
        self.db.add(duplicate)
        self.db.flush()
        edition = Edition(work_id=duplicate.id, title=duplicate.title, language='es', page_count=100)
        self.db.add(edition)
        self.db.flush()
        entry = LibraryEntry(user_id=self.user.id, work_id=duplicate.id)
        self.db.add(entry)
        self.db.flush()
        now = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.db.add(Reading(library_entry_id=entry.id, work_id=duplicate.id, edition_id=edition.id,
                            status='reading', total_pages=100, current_page=0, started_at=now, created_at=now))
        original = self.db.scalar(select(Review).where(Review.work_id == self.work_id))
        self.db.add(Review(author_profile_id=original.author_profile_id, created_by_user_id=self.user.id,
                           work_id=duplicate.id, edition_id=edition.id, body='Newer review', rating=Decimal('5'),
                           status='published', published_at=now, created_at=now, updated_at=now))
        self.db.flush()
        self.assert_readers(reading=1)
        self.assertEqual((self.stats()['averageRating'], self.stats()['ratingsCount']), (5, 1))
        self.assertIsNotNone(self.db.get(Work, duplicate.id))

    def test_empty_native_work_and_other_work_are_not_mixed(self):
        self.event('finish', self.event('start'))
        self.review()
        work = Work(title='Unrelated work ' + uuid.uuid4().hex)
        self.db.add(work)
        self.db.flush()
        edition = Edition(work_id=work.id, title=work.title, language='es')
        self.db.add(edition)
        self.db.flush()
        self.db.add(CatalogSource(edition_id=edition.id, provider='libria-feed', external_id='native:' + str(work.id),
                                  fetched_at=datetime.now(timezone.utc)))
        self.db.flush()
        for ref in (work.id, 'native:' + str(work.id)):
            result = self.stats(ref)
            self.assertEqual((result['averageRating'], result['ratingsCount']), (None, 0))
            self.assertEqual(result['readingStats']['finished'], 0)
