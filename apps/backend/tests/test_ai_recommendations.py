"""Recommendation cutover keeps validation and removes manual batches."""
import unittest
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.analytics.recommendations import validate_selection
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.library.models import LibraryEntry
from app.modules.users.identities import create_personal_profile
from app.modules.users.models import User

ROOT = Path(__file__).resolve().parents[2]


class RecommendationsTest(unittest.TestCase):
    """Shared persisted-reader fixture; provider generation is deliberately absent."""

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
        self.client.post(
            "/api/readings/library",
            json={"book_ref": self.owned, "book_title": "Owned book", "page_count": 100},
        )
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
        reference = "recommend-" + uuid.uuid4().hex
        payload = {
            "id": reference,
            "volumeInfo": {
                "title": title,
                "authors": [author],
                "categories": ["Unique test category"],
                "pageCount": 100,
                "language": "es",
            },
        }
        for provider in ("google-books", "libria-feed"):
            self.db.add(
                CatalogSource(
                    edition_id=edition.id,
                    provider=provider,
                    external_id=reference,
                    fetched_at=datetime.now(timezone.utc),
                    payload=payload if provider == "google-books" else None,
                )
            )
        self.db.flush()
        return reference


class RecommendationCutoverTest(unittest.TestCase):
    def test_historical_selection_validator_rejects_invention(self):
        candidates=[{"metadata":{"id":"real"},"reasons":{"category":"Razón"},"volume":{"id":"real"}}]
        with self.assertRaises(ValueError):
            validate_selection({"recommendations":[{"id":"inventado","criterion":"category"}]},candidates)

    def test_frontend_reads_state_without_generation_post(self):
        source=(ROOT / "web/src/pages/RecommendationsPage.jsx").read_text(encoding="utf-8")
        self.assertIn("/analytics/me/recommendations/state",source)
        self.assertNotIn("method: 'POST'",source)
        self.assertNotIn("requestMore",source)

    def test_legacy_manual_endpoint_is_disabled(self):
        source=(ROOT / "backend/app/modules/analytics/insights_router.py").read_text(encoding="utf-8")
        block=source[source.index('def generate_recommendations'):source.index('@router.get("/access")')]
        self.assertIn("status_code=405",block)
