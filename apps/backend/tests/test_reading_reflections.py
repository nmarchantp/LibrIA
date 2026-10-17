"""Completion -> private experience -> ETL -> owner-only Ollama evidence."""
from datetime import datetime, timedelta, timezone
import json
import unittest
import uuid
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.analytics.etl import extract, transform, publish
from app.modules.analytics.insights import personal_evidence
from app.modules.analytics.interpretation_provider import generate_interpretation
from app.modules.users.models import User
from app.modules.users.identities import create_personal_profile


class ReadingReflectionTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Reflection reader")
        self.other = User(display_name="Other reader")
        self.db.add_all([self.user, self.other])
        self.db.flush()
        create_personal_profile(self.db, self.user)
        create_personal_profile(self.db, self.other)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.book = {"book_ref": "reflection-" + uuid.uuid4().hex, "book_title": "Reflection book", "page_count": 100}
        started = self.client.post("/api/readings/events", json={**self.book, "event": "start"})
        self.assertEqual(started.status_code, 201, started.text)
        self.reading_id = started.json()["reading_id"]
        self.reflection = {"emotions": ["esperanza", "nostalgia", "esperanza"], "aspects": ["personajes"],
                           "sentiment": "mixto", "reflection": "  PRIVATE: me conmovió el final, aunque el ritmo fue lento.  "}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def finish(self):
        result = self.client.post("/api/readings/events", json={**self.book, "reading_id": self.reading_id,
            "event": "finish", "reflection": self.reflection})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def sources(self):
        now = datetime.now(timezone.utc)
        return extract(self.connection, now - timedelta(hours=1), now + timedelta(minutes=1))

    def test_reading_feed_includes_book_reference_and_cover(self):
        from app.modules.library.models import Reading
        from app.modules.books.models import Edition
        reading = self.db.get(Reading, uuid.UUID(self.reading_id))
        edition = self.db.get(Edition, reading.edition_id)
        edition.cover_url = "https://example.com/reading-cover.jpg"
        self.db.flush()
        response = self.client.get("/api/posts")
        self.assertEqual(response.status_code, 200, response.text)
        item = next(row for row in response.json() if row["book_title"] == self.book["book_title"])
        self.assertEqual(item["book_ref"], self.book["book_ref"])
        self.assertEqual(item["book_cover_url"], edition.cover_url)

    def test_finish_reflection_remains_private_and_is_cleaned_loaded_repeatably(self):
        result = self.finish()
        self.assertEqual(result["reflection"]["emotions"], ["esperanza", "nostalgia"])
        self.assertEqual(result["reflection"]["reflection"], self.reflection["reflection"].strip())
        self.assertNotIn("PRIVATE", json.dumps(result["post"]))
        self.assertNotIn("PRIVATE", self.client.get("/api/posts").text)
        self.assertEqual(self.client.get("/api/readings/me").json()[0]["reflection"], result["reflection"])
        sources = self.sources()
        prepared = transform(*sources)
        self.assertEqual(prepared, transform(*sources))
        personal_rows = [r for r in prepared[-1] if r["user_id"] == self.user.id]
        self.assertEqual(len(personal_rows), 1)
        for _ in range(2):
            run_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            self.connection.execute(text("""INSERT INTO analytics.ejecuciones_etl
                (id,status,started_at,run_kind,requested_by,period_start,source_cutoff_at,transform_version)
                VALUES (:id,'running',now(),'manual',:owner,:start,:cutoff,'daily-v3')"""),
                {"id": run_id, "owner": self.user.id, "start": now - timedelta(hours=1), "cutoff": now + timedelta(minutes=1)})
            summary = publish(self.connection, run_id, prepared)
            self.assertGreaterEqual(summary["loaded_reflections"], 1)
            self.assertEqual(self.connection.execute(text("SELECT count(*) FROM analytics.hechos_reflexiones WHERE etl_run_id=:run AND user_id=:owner"), {"run": run_id, "owner": self.user.id}).scalar_one(), 1)
        evidence = personal_evidence(self.db, self.user.id, "unclassified")
        self.assertEqual(evidence["qualitative"], [result["reflection"]])
        self.assertEqual(evidence["metrics"]["Q01"]["value"], 1)
        self.assertIsNone(personal_evidence(self.db, self.other.id, "unclassified"))
        self.assertNotIn(str(self.user.id), json.dumps(evidence))

    def test_non_finish_unknown_emotion_and_empty_reflections_are_rejected(self):
        for payload in ({"event": "progress", "current_page": 30, "reflection": self.reflection},
                        {"event": "finish", "reflection": {"emotions": ["inventada"]}},
                        {"event": "finish", "reflection": {}}):
            response = self.client.post("/api/readings/events", json={**self.book, "reading_id": self.reading_id, **payload})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get("/api/readings/me").json()[0]["status"], "reading")

    def test_invalid_legacy_reflection_is_excluded_without_losing_completion(self):
        self.finish()
        sources = list(self.sources())
        sources[1] = [dict(event) for event in sources[1]]
        for event in sources[1]:
            if event["user_id"] == self.user.id and event["kind"] == "finish":
                event["reflection"] = {"emotions": ["unknown"]}
        prepared = transform(*sources)
        self.assertEqual(prepared[4]["reflection_invalid_contract"], 1)
        self.assertFalse(any(r["user_id"] == self.user.id for r in prepared[-1]))
        self.assertTrue(any(r["user_id"] == self.user.id and r["event_kind"] == "finish" for r in prepared[1]))

    def test_ollama_receives_self_reports_only_for_individual_analysis(self):
        evidence = {"metrics": {"Q01": {"value": 1}}, "qualitative": [self.reflection]}
        narrative = {"title": "Experiencias declaradas", "summary": "Tu reflexión expresa emociones sobre la lectura.",
            "observations": [{"metric": "Q01", "interpretation": "Declaraste esperanza y nostalgia ante este libro."}],
            "suggestions": [], "limitations": ["Una experiencia no define tu personalidad."]}
        from unittest.mock import AsyncMock
        with patch("app.modules.analytics.interpretation_provider.request_book", new_callable=AsyncMock, return_value=narrative) as provider:
            generate_interpretation(evidence, "personal")
            payload = provider.call_args.args[0]
            self.assertIn("PRIVATE", payload["messages"][1]["content"])
        with patch("app.modules.analytics.interpretation_provider.request_book", new_callable=AsyncMock, return_value=narrative) as provider:
            generate_interpretation(evidence, "group")
            payload = provider.call_args.args[0]
            self.assertNotIn("PRIVATE", payload["messages"][1]["content"])
