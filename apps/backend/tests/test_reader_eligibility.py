"""Minimum library size blocks reads, cached results and model generation."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry
from app.modules.users.models import User
from app.modules.users.identities import create_personal_profile


class ReaderEligibilityTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Threshold reader")
        self.other = User(display_name="Other reader")
        self.db.add_all([self.user, self.other])
        self.db.flush()
        create_personal_profile(self.db, self.user)
        create_personal_profile(self.db, self.other)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def add_book(self, user=None):
        work = Work(title="Threshold book")
        self.db.add(work)
        self.db.flush()
        entry = LibraryEntry(user_id=(user or self.user).id, work_id=work.id)
        self.db.add(entry)
        self.db.flush()
        return entry

    def test_nine_books_block_both_reads_and_generations_before_model_or_cache_access(self):
        for _ in range(9):
            self.add_book()
        for _ in range(10):
            self.add_book(self.other)
        with patch("app.modules.analytics.insights_router.personal_evidence") as evidence, \
             patch("app.modules.analytics.insights_router.recommendation_state") as recommend:
            for path in ("/api/analytics/me/insights", "/api/analytics/me/recommendations"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "locked")
                self.assertEqual(response.json()["book_count"], 9)
                self.assertEqual(response.json()["missing_books"], 1)
            response = self.client.post("/api/analytics/me/interpretation", json={})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"]["code"], "minimum_reader_books")
            # Stage 6 retires the manual recommendation trigger for every user.
            self.assertEqual(
                self.client.post("/api/analytics/me/recommendations", json={}).status_code,
                405,
            )
            evidence.assert_not_called()
            recommend.assert_not_called()

    def test_tenth_book_unlocks_and_archiving_revokes_access(self):
        entries = [self.add_book() for _ in range(10)]
        access = self.client.get("/api/analytics/access").json()
        self.assertTrue(access["personal"])
        self.assertEqual(access["reader_eligibility"]["book_count"], 10)
        self.assertNotEqual(self.client.get("/api/analytics/me/insights").json()["status"], "locked")
        self.assertNotEqual(self.client.get("/api/analytics/me/recommendations").json()["status"], "locked")
        entries[-1].archived_at = datetime.now(timezone.utc)
        self.db.flush()
        self.assertFalse(self.client.get("/api/analytics/access").json()["personal"])
        self.assertEqual(self.client.get("/api/analytics/me/recommendations").json()["status"], "locked")
