"""Global manual ETL regression, contained in a rolled-back transaction."""
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.modules.analytics.etl import publish, extract, transform
from app.modules.analytics.reader_evidence import extract_personal
from app.modules.analytics.recommendation_profiles import build_nightly_reader_profiles
from app.modules.analytics.recommendation_sync import _latest_state
from app.modules.analytics.gemini_worker import _latest_profile_is
from app.modules.analytics.adaptive_router import refresh_profile
from app.modules.books.canonical import identity_version
from tests.test_nightly_recommendation_profiles import profile_book
from types import SimpleNamespace


class ManualEtlReadersTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.addCleanup(self.connection.close)
        self.addCleanup(self.transaction.rollback)
        self.admin, self.reader, self.run = (uuid.uuid4() for _ in range(3))
        for owner in (self.admin, self.reader):
            self.connection.execute(text("INSERT INTO app.usuarios(id,display_name) VALUES (:id,'ETL regression')"), {'id':owner})
        self.connection.execute(text("INSERT INTO app.permisos_cuenta(user_id,permission) VALUES (:id,'admin')"), {'id':self.admin})
        self.cutoff = self.connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        self.start = self.cutoff - timedelta(days=30)
        self.connection.execute(text("""INSERT INTO analytics.ejecuciones_etl
            (id,status,started_at,source_cutoff_at,period_start,transform_version,run_kind,requested_by,phase)
            VALUES (:id,'running',now(),:cutoff,:start,'regression','manual',:admin,'queued')"""),
            {'id':self.run,'cutoff':self.cutoff,'start':self.start,'admin':self.admin})
        self.connection.execute(text('UPDATE analytics.ejecuciones_etl SET identity_version=:version WHERE id=:id'),
            {'id':self.run,'version':identity_version(self.connection)})

    def test_full_manual_publication_prepares_other_reader_without_gemini(self):
        with patch('app.modules.analytics.providers.factory.build_ai_provider', side_effect=AssertionError('ETL must not invoke AI')):
            summary = publish(self.connection, self.run,
                transform(*extract(self.connection, self.start, self.cutoff)),
                extract_personal(self.connection, self.cutoff))
        expected = self.connection.execute(text('SELECT count(*) FROM app.usuarios WHERE created_at<:cutoff'), {'cutoff':self.cutoff}).scalar_one()
        self.assertEqual(summary['recommendation_profiles']['readers'], expected)
        with Session(bind=self.connection, join_transaction_mode='create_savepoint') as db:
            state = _latest_state(db, self.reader)
            self.assertIsNotNone(state)
            self.assertEqual(state['etl_run_id'], self.run)
            self.assertEqual(state['outcome'], 'empty')
            from app.modules.analytics.recommendation_sync import recommendation_state
            result = recommendation_state(db, self.reader)
            self.assertEqual(result['status'], 'insufficient_data')
            self.assertEqual(result['source_cutoff_at'], self.cutoff)

    def test_other_reader_profile_is_saved_readable_and_can_queue_own_dna(self):
        book = profile_book(user_id=self.reader)
        with patch('app.modules.analytics.recommendation_profiles._reader_books',
                   side_effect=lambda owner, *args: [book] if owner == self.reader else []):
            summary = build_nightly_reader_profiles(self.connection, self.run)
        self.assertGreaterEqual(summary['readers'], 2)
        self.connection.execute(text("UPDATE analytics.ejecuciones_etl SET status='succeeded',finished_at=now() WHERE id=:id"), {'id':self.run})
        with Session(bind=self.connection, join_transaction_mode='create_savepoint') as db:
            state = _latest_state(db, self.reader)
            self.assertEqual(state['outcome'], 'eligible_pending')
            self.assertTrue(_latest_profile_is(db, self.reader, state['profile_version_id']))
            # The ordinary reader can prepare from another user's manual run
            # and queue only their own DNA, without any admin permission.
            with patch('app.modules.analytics.recommendation_profiles._reader_books',
                       side_effect=lambda owner, *args: [book] if owner == self.reader else []):
                result = refresh_profile(Response(), SimpleNamespace(id=self.reader), db)
            self.assertEqual(result['status'], 'pending')
            self.assertEqual(result['profile_preparation']['readers'], 1)
            owner = db.execute(text('SELECT owner_id FROM ia.jobs WHERE id=:id'), {'id':result['job_id']}).scalar_one()
            self.assertEqual(owner, self.reader)
