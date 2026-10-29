"""Private ETL evidence: authorship, snapshots, ratings and bounded AI input."""
from datetime import datetime, timedelta, timezone
import unittest
import uuid
from unittest.mock import MagicMock
from sqlalchemy import select, text
from tests import test_ai_recommendations as fixtures
from app.modules.analytics.reader_evidence import extract_personal, publish_personal, personal_samples
from app.modules.analytics.insights import personal_evidence
from app.modules.library.models import Reading
from app.modules.books.models import CatalogSource, Edition


class ReaderEvidenceTest(unittest.TestCase):
    setUp = fixtures.RecommendationsTest.setUp
    tearDown = fixtures.RecommendationsTest.tearDown
    book = fixtures.RecommendationsTest.book

    def test_snapshot_includes_own_text_and_private_ratings_but_excludes_demo(self):
        reading = self.db.scalar(select(Reading).join(Edition, Edition.id == Reading.edition_id)
            .join(CatalogSource, CatalogSource.edition_id == Edition.id)
            .where(CatalogSource.external_id == self.owned))
        reading.notebook = {'characters': 'Me interesa su evolución', 'places': 'Ciudad costera', 'summary': 'Una búsqueda'}
        self.db.flush()
        response = self.client.post('/api/reviews', json={'work_id': str(reading.work_id),
            'body': 'Me gustó el ritmo, pero no el desenlace', 'rating': 4,
            'dimension_ratings': {'pace': 5}, 'status': 'draft'})
        self.assertEqual(response.status_code, 201, response.text)
        for kind in ('note', 'theory'):
            response = self.client.post('/api/posts', json={'source': 'community', 'kind': 'community',
                'publication_type': kind, 'body': 'Mi aporte sobre este libro',
                'book_ref': self.owned, 'book_title': 'Owned book'})
            self.assertEqual(response.status_code, 201, response.text)
        cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)
        rows = extract_personal(self.db, cutoff)
        own = [row for row in rows if row['user_id'] == self.user.id]
        self.assertEqual({row['source_kind'] for row in own}, {'notebook', 'review', 'note', 'theory'})
        run = uuid.uuid4()
        self.db.execute(text("""INSERT INTO analytics.ejecuciones_etl
            (id,status,started_at,finished_at,period_start,source_cutoff_at,transform_version,run_kind,requested_by)
            VALUES (:id,'succeeded',now(),now(),now(),:cutoff,'test-personal','manual',:owner)"""),
            {'id': run, 'cutoff': cutoff, 'owner': self.user.id})
        publish_personal(self.db, run, rows)
        samples, truncated = personal_samples(self.db, run, self.user.id, 'unclassified')
        self.assertEqual(len(samples), 4)
        self.assertFalse(truncated)
        review = next(item for item in samples if item['kind'] == 'review')
        self.assertEqual(review['dimension_ratings'], {'pace': 5})
        self.assertEqual(review['rating'], 4)
        self.assertEqual(personal_samples(self.db, run, self.other.id, 'unclassified')[0], [])
        evidence = personal_evidence(self.db, self.user.id, 'unclassified')
        self.assertEqual(evidence['metrics']['Q02']['value'], 4)
        self.assertEqual(len(evidence['reader_contributions']), 4)
        self.assertNotIn('reader_contributions', evidence.get('group', {}))
        self.db.execute(text("INSERT INTO app.procedencia_demo VALUES ('lecturas',:id,'test')"), {'id': reading.id})
        self.assertFalse(any(row['source_id'] == reading.id for row in extract_personal(self.db, cutoff)))
        self.assertFalse(any(row['source_id'] == reading.id for row in extract_personal(self.db, cutoff - timedelta(days=1))))


class SamplingTest(unittest.TestCase):
    def test_text_budget_and_truncation_are_explicit(self):
        db = MagicMock()
        db.execute.return_value.mappings.return_value.all.return_value = [
            {'work_id': uuid.uuid4(), 'source_id': uuid.uuid4(), 'source_kind': 'notebook',
             'source_at': datetime.now(timezone.utc), 'total': 40,
             'payload': {'title': 'Book', 'notebook': {
                 'characters': 'a' * 3000, 'places': 'b' * 3000, 'summary': 'c' * 5000}}}
            for _ in range(8)]
        samples, truncated = personal_samples(db, uuid.uuid4(), uuid.uuid4(), 'unclassified')
        self.assertTrue(truncated)
        self.assertLessEqual(sum(len(item['title']) + sum(len(value) for value in item['notebook'].values())
                                 for item in samples), 18000)
        self.assertTrue(all(len(value) <= 1500 for item in samples for value in item['notebook'].values()))
