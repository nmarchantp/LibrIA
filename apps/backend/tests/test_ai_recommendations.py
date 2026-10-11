"""Personalized candidates, owner isolation, validated selection and caching."""
from datetime import datetime, timezone
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.analytics.recommendations import prepare, validate_selection
from app.modules.books.models import Work, Edition, CatalogSource
from app.modules.library.models import LibraryEntry
from app.modules.users.models import User
from app.modules.users.identities import create_personal_profile


class RecommendationsTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Reader one")
        self.other = User(display_name="Reader two")
        self.db.add_all([self.user, self.other])
        self.db.flush()
        create_personal_profile(self.db, self.user)
        create_personal_profile(self.db, self.other)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.owned = self.book("Owned book", author="Unique reader author")
        self.candidate = self.book("New candidate", author="Unique reader author")
        self.foreign = self.book("Foreign history", author="Other author")
        self.client.post("/api/readings/library", json={"book_ref": self.owned, "book_title": "Owned book", "page_count": 100})
        for index in range(9):
            work = Work(title=f"Recommendation prerequisite {index}")
            self.db.add(work)
            self.db.flush()
            self.db.add(LibraryEntry(user_id=self.user.id, work_id=work.id))
        self.db.flush()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def book(self, title, author):
        work = Work(title=title)
        self.db.add(work)
        self.db.flush()
        edition = Edition(work_id=work.id, title=title, language="es", page_count=100)
        self.db.add(edition)
        self.db.flush()
        ref = "recommend-" + uuid.uuid4().hex
        payload = {"id": ref, "volumeInfo": {"title": title, "authors": [author], "categories": ["Unique test category"], "pageCount": 100, "language": "es"}}
        for provider in ("google-books", "libria-feed"):
            self.db.add(CatalogSource(edition_id=edition.id, provider=provider, external_id=ref,
                fetched_at=datetime.now(timezone.utc), payload=payload if provider == "google-books" else None))
        self.db.flush()
        return ref

    def test_history_is_owner_scoped_and_owned_books_excluded(self):
        app.dependency_overrides[get_current_user] = lambda: self.other
        self.client.post("/api/readings/library", json={"book_ref": self.foreign, "book_title": "Foreign history", "page_count": 100})
        context, candidates = prepare(self.db, self.user.id, "unclassified")
        self.assertEqual([item["id"] for item in context["history"]], [self.owned])
        self.assertNotIn(self.owned, [c["metadata"]["id"] for c in candidates])
        candidate = next(c for c in candidates if c["metadata"]["id"] == self.candidate)
        self.assertIn("author", candidate["reasons"])
        self.assertIn("category", candidate["reasons"])

    def test_model_cannot_invent_books_criteria_or_duplicate_choices(self):
        _, candidates = prepare(self.db, self.user.id, "unclassified")
        selection = {"id": self.candidate, "criterion": "author"}
        self.assertEqual(len(validate_selection({"recommendations": [selection]}, candidates)), 1)
        for selections in ([{"id": "imaginary", "criterion": "author"}],
                           [{"id": self.candidate, "criterion": "personality"}], [selection, selection], []):
            with self.assertRaises(ValueError):
                validate_selection({"recommendations": selections}, candidates)

    def test_generation_cached_and_never_shared_between_users(self):
        _, candidates = prepare(self.db, self.user.id, "unclassified")
        generated = validate_selection({"recommendations": [{"id": self.candidate, "criterion": "author"}]}, candidates)
        with patch("app.modules.analytics.recommendations.provider_ready", return_value=True), \
             patch("app.modules.analytics.recommendations.generate", return_value=generated) as provider:
            url = "/api/analytics/me/recommendations"
            self.assertEqual(self.client.get(url).json()["status"], "needs_generation")
            response = self.client.post(url, json={"provenance": "unclassified"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["items"], generated)
            self.assertEqual(self.client.get(url).json()["items"], generated)
            self.assertEqual(self.client.post(url, json={"provenance": "unclassified"}).status_code, 200)
            self.assertEqual(provider.call_count, 1)
            app.dependency_overrides[get_current_user] = lambda: self.other
            other = self.client.get(url).json()
            self.assertEqual(other["items"], [])
            self.assertEqual(other["status"], "locked")

    def test_authentication_required_and_missing_model_has_no_fake_results(self):
        with patch("app.modules.analytics.recommendations.provider_ready", return_value=False):
            self.assertEqual(self.client.post("/api/analytics/me/recommendations", json={"provenance": "unclassified"}).status_code, 503)
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get("/api/analytics/me/recommendations").status_code, 401)
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM analytics.recomendaciones_ia WHERE owner_user_id=:id"), {"id": self.user.id}).scalar_one(), 0)
