"""One synthetic ETL-to-REST journey with an injected, network-free Gemini."""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.main import app
from app.modules.analytics.etl import day_bounds, last_closed_day, run_day
from app.modules.analytics.gemini_worker import process_one
from tests.test_stage5_gemini_worker import MockGemini


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.getenv("LIBRIA_STAGE7_TEST") == "1",
    "requires disposable PostgreSQL with LIBRIA_STAGE7_TEST=1",
)
class Stage7IntegralTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_url = os.environ["DATABASE_URL"]
        url = make_url(cls.database_url)
        if url.host not in {"localhost", "127.0.0.1", "::1"} or url.database == "libria":
            raise RuntimeError("Stage 7 requires a disposable loopback PostgreSQL database")
        cls.engine = create_engine(cls.database_url)
        command.upgrade(Config("alembic.ini"), "head")
        cls.factory = sessionmaker(bind=cls.engine, expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.client = TestClient(app)
        self.email = f"stage7-{uuid.uuid4()}@example.com"
        self.password = "fictitious-password-123"
        registered = self.client.post("/api/auth/register", json={
            "email": self.email, "password": self.password, "display_name": "Lectora ficticia",
        })
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertNotIn("refresh_token", registered.json())
        self.owner = uuid.UUID(registered.json()["user"]["id"])
        self.headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    def tearDown(self):
        self.client.close()

    def _event(self, reference: str, title: str, terminal: str):
        book = {"book_ref": reference, "book_title": title, "page_count": 100}
        started = self.client.post("/api/readings/events", headers=self.headers,
                                   json={**book, "event": "start"})
        self.assertEqual(started.status_code, 201, started.text)
        reading_id = started.json()["reading_id"]
        notebook = self.client.patch(
            f"/api/readings/{reading_id}/notebook", headers=self.headers,
            json={"characters": "Personajes contradictorios", "places": "Ciudad ficticia",
                  "summary": "Resumen ficticio sin instrucciones"},
        )
        self.assertEqual(notebook.status_code, 200, notebook.text)
        payload = {**book, "reading_id": reading_id, "event": terminal}
        if terminal == "abandon":
            payload["abandonment_reason"] = "Ritmo ficticio incompatible"
        closed = self.client.post("/api/readings/events", headers=self.headers, json=payload)
        self.assertEqual(closed.status_code, 201, closed.text)
        return uuid.UUID(reading_id), uuid.UUID(closed.json()["event_id"])

    def _work(self, reference: str):
        with self.engine.connect() as connection:
            return connection.execute(text("""SELECT ed.work_id,ed.id FROM app.ediciones ed
              JOIN app.fuentes_catalogo s ON s.edition_id=ed.id
              WHERE s.external_id=:reference ORDER BY s.provider LIMIT 1"""),
              {"reference": reference}).one()

    def _review(self, work_id, edition_id, rating, body):
        response = self.client.post("/api/reviews", headers=self.headers, json={
            "work_id": str(work_id), "edition_id": str(edition_id), "body": body,
            "rating": rating, "dimension_ratings": {"pace": rating}, "status": "published",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return uuid.UUID(response.json()["id"])

    def _place_initial_data_inside(self, day):
        start, _ = day_bounds(day)
        base = start + timedelta(hours=2)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE app.usuarios SET created_at=:at WHERE id=:owner"),
                               {"at": base, "owner": self.owner})
            connection.execute(text("""UPDATE app.obras SET created_at=:at,updated_at=:at
              WHERE id IN (SELECT work_id FROM app.entradas_biblioteca WHERE user_id=:owner)"""),
              {"at": base, "owner": self.owner})
            connection.execute(text("""UPDATE app.ediciones SET created_at=:at,updated_at=:at
              WHERE work_id IN (SELECT work_id FROM app.entradas_biblioteca WHERE user_id=:owner)"""),
              {"at": base, "owner": self.owner})
            connection.execute(text("UPDATE app.entradas_biblioteca SET created_at=:at WHERE user_id=:owner"),
                               {"at": base, "owner": self.owner})
            readings = connection.execute(text("""SELECT r.id,r.status FROM app.lecturas r
              JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
              WHERE le.user_id=:owner ORDER BY r.created_at,r.id"""), {"owner": self.owner}).all()
            for index, reading in enumerate(readings):
                opened = base + timedelta(minutes=index * 10)
                events = connection.execute(text("""SELECT id,kind FROM app.eventos_lectura
                  WHERE reading_id=:reading ORDER BY created_at,id"""), {"reading": reading.id}).all()
                for position, event in enumerate(events):
                    occurred = opened + timedelta(minutes=position)
                    connection.execute(text("UPDATE app.eventos_lectura SET created_at=:at WHERE id=:id"),
                                       {"at": occurred, "id": event.id})
                    if event.kind == "start":
                        connection.execute(text("UPDATE app.lecturas SET started_at=:at WHERE id=:id"),
                                           {"at": occurred, "id": reading.id})
                    elif event.kind == "finish":
                        connection.execute(text("UPDATE app.lecturas SET finished_at=:at WHERE id=:id"),
                                           {"at": occurred, "id": reading.id})
                    elif event.kind == "abandon":
                        connection.execute(text("UPDATE app.lecturas SET abandoned_at=:at WHERE id=:id"),
                                           {"at": occurred, "id": reading.id})
                connection.execute(text("UPDATE app.lecturas SET created_at=:at,updated_at=:updated WHERE id=:id"),
                                   {"at": opened, "updated": opened + timedelta(minutes=5), "id": reading.id})
            # The test moves API-created fixtures into a closed historical day;
            # production immutability remains enabled before and after this update.
            connection.execute(text("ALTER TABLE app.resenas DISABLE TRIGGER validate_review_identity"))
            connection.execute(text("""UPDATE app.resenas SET created_at=:at,updated_at=:at,
              published_at=:at WHERE created_by_user_id=:owner"""), {"at": base, "owner": self.owner})
            connection.execute(text("ALTER TABLE app.resenas ENABLE TRIGGER validate_review_identity"))
            connection.execute(text("""UPDATE app.revisiones_resena SET recorded_at=:at
              WHERE recorded_by_user_id=:owner"""), {"at": base, "owner": self.owner})
            connection.execute(text("UPDATE app.publicaciones SET created_at=:at WHERE user_id=:owner"),
                               {"at": base, "owner": self.owner})

    def _login(self):
        response = self.client.post("/api/auth/login", json={"email": self.email, "password": self.password})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("refresh_token", response.json())
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _job_count(self, kind):
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind=:kind"),
                                      {"owner": self.owner, "kind": kind}).scalar_one()

    def test_synthetic_etl_login_worker_persistence_and_frontend_contract(self):
        high_ref, low_ref, abandoned_ref = (f"stage7:{uuid.uuid4()}" for _ in range(3))
        first_reading, first_finish = self._event(high_ref, "Favorita ficticia", "finish")
        low_reading, low_finish = self._event(low_ref, "Lectura baja ficticia", "finish")
        abandoned_reading, abandoned_event = self._event(abandoned_ref, "Abandono ficticio", "abandon")
        reread, reread_finish = self._event(high_ref, "Favorita ficticia", "finish")
        for index in range(7):
            response = self.client.post("/api/readings/library", headers=self.headers, json={
                "book_ref": f"stage7-pending:{uuid.uuid4()}", "book_title": f"Pendiente ficticio {index}",
                "page_count": 100,
            })
            self.assertEqual(response.status_code, 200, response.text)

        high_work, high_edition = self._work(high_ref)
        low_work, low_edition = self._work(low_ref)
        high_review = self._review(high_work, high_edition, 5, "Reseña ficticia original")
        self._review(low_work, low_edition, 3.75, "Reseña ficticia bajo el umbral")
        for kind, body in (("note", "Nota interna ficticia"), ("theory", "Teoría privada ficticia")):
            response = self.client.post("/api/posts", headers=self.headers, json={
                "source": "community", "kind": "community", "publication_type": kind,
                "body": body, "book_ref": high_ref, "book_title": "Favorita ficticia",
            })
            self.assertEqual(response.status_code, 201, response.text)

        # Adding ten distinct library works created no broad AI work. Only four
        # explicit terminal events have one delayed individual job each.
        self.assertEqual(self._job_count("recommendation"), 0)
        self.assertEqual(self._job_count("reading_event_analysis"), 4)

        first_day = last_closed_day() - timedelta(days=2)
        self._place_initial_data_inside(first_day)
        first_etl = run_day(first_day, db_engine=self.engine)
        self.assertEqual(first_etl["status"], "succeeded")
        with self.engine.connect() as connection:
            profile = connection.execute(text("""SELECT p.id,p.payload FROM ia.reader_profile_versions p
              WHERE p.owner_id=:owner ORDER BY p.version DESC LIMIT 1"""), {"owner": self.owner}).mappings().one()
            self.assertEqual(len(profile["payload"]["books"]), 2)  # finish + reread, rating 5
            wire = str(profile["payload"])
            self.assertIn("Nota interna ficticia", wire)
            self.assertIn("Teoría privada ficticia", wire)
            self.assertNotIn("bajo el umbral", wire)

        candidate, author, edition, source = (uuid.uuid4() for _ in range(4))
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO app.obras(id,title,identity_key,description,categories)
              VALUES (:id,'Candidata ficticia',:identity,'Catálogo ficticio','[\"novela\"]'::jsonb)"""),
              {"id": candidate, "identity": f"stage7:{candidate}"})
            connection.execute(text("INSERT INTO app.autores(id,name) VALUES (:id,'Autora ficticia')"),
                               {"id": author})
            connection.execute(text("INSERT INTO app.obras_autores(work_id,author_id,position) VALUES (:work,:author,1)"),
                               {"work": candidate, "author": author})
            connection.execute(text("""INSERT INTO app.ediciones(id,work_id,title,language,page_count)
              VALUES (:id,:work,'Candidata ficticia','es',200)"""),
              {"id": edition, "work": candidate})
            connection.execute(text("""INSERT INTO app.fuentes_catalogo
              (id,edition_id,provider,external_id,fetched_at,validation_status,consolidation_status)
              VALUES (:id,:edition,'google-books',:external,now(),'validated','automatic')"""),
              {"id": source, "edition": edition, "external": f"stage7-candidate:{candidate}"})

        self.headers = self._login()
        self.assertEqual(self._job_count("recommendation"), 1)
        settings = Settings(_env_file=None, database_url=self.database_url,
                            ai_requests_per_minute=600, ai_retry_base_seconds=.1)
        fake = MockGemini()
        self.assertTrue(process_one(provider=fake, settings=settings, session_factory=self.factory))
        state = self.client.get("/api/analytics/me/recommendations/state", headers=self.headers)
        self.assertEqual(state.status_code, 200, state.text)
        self.assertEqual(state.json()["status"], "ready")
        self.assertTrue(state.json()["items"])

        # A second authenticated session and an unchanged nightly cut reuse the
        # same version, persisted result and unique recommendation job.
        self.headers = self._login()
        self.assertEqual(self._job_count("recommendation"), 1)
        unchanged = run_day(first_day + timedelta(days=1), db_engine=self.engine)
        self.assertEqual(unchanged["status"], "succeeded")
        self.headers = self._login()
        self.assertEqual(self._job_count("recommendation"), 1)
        self.assertEqual(self.client.get("/api/analytics/me/recommendations/state",
                                        headers=self.headers).json()["status"], "ready")

        # A review revision enters only the following closed ETL and produces a
        # new profile/job while the previous result remains explicitly outdated.
        edited = self.client.put(f"/api/reviews/{high_review}", headers=self.headers, json={
            "body": "Reseña ficticia editada para el siguiente ETL", "rating": 5,
            "dimension_ratings": {"pace": 5}, "status": "published", "edition_id": str(high_edition),
        })
        self.assertEqual(edited.status_code, 200, edited.text)
        edit_at = day_bounds(first_day + timedelta(days=2))[0] + timedelta(hours=2)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE app.resenas SET updated_at=:at WHERE id=:id"),
                               {"at": edit_at, "id": high_review})
            connection.execute(text("""UPDATE app.revisiones_resena SET recorded_at=:at
              WHERE review_id=:id AND revision_number=2"""), {"at": edit_at, "id": high_review})
        changed = run_day(first_day + timedelta(days=2), db_engine=self.engine)
        self.assertEqual(changed["status"], "succeeded")
        self.headers = self._login()
        self.assertEqual(self._job_count("recommendation"), 2)
        outdated = self.client.get("/api/analytics/me/recommendations/state", headers=self.headers).json()
        self.assertEqual(outdated["status"], "outdated")
        self.assertTrue(outdated["items"])
        with self.engine.connect() as connection:
            latest = connection.execute(text("""SELECT payload FROM ia.reader_profile_versions
              WHERE owner_id=:owner ORDER BY version DESC LIMIT 1"""), {"owner": self.owner}).scalar_one()
            self.assertIn("editada para el siguiente ETL", str(latest))
        self.assertTrue(process_one(provider=fake, settings=settings, session_factory=self.factory))
        self.assertEqual(self.client.get("/api/analytics/me/recommendations/state",
                                        headers=self.headers).json()["status"], "ready")

        # Consolidation delay is bypassed only inside this isolated test. Each
        # terminal event is processed once and PostgreSQL serves the results.
        with self.engine.begin() as connection:
            connection.execute(text("""UPDATE ia.jobs SET not_before=now()
              WHERE owner_id=:owner AND job_kind='reading_event_analysis'"""), {"owner": self.owner})
        for _ in range(4):
            self.assertTrue(process_one(provider=fake, settings=settings, session_factory=self.factory))
        self.assertEqual(sum(1 for call in fake.calls
                             if "event_kind" in call.response_schema.get("properties", {})), 4)
        with self.engine.connect() as connection:
            rows = connection.execute(text("""SELECT reading_event_id,count(*) FROM ia.analyses
              WHERE owner_id=:owner AND reading_event_id IS NOT NULL
              GROUP BY reading_event_id"""), {"owner": self.owner}).all()
            self.assertEqual({row[0] for row in rows},
                             {first_finish, low_finish, abandoned_event, reread_finish})
            self.assertTrue(all(row[1] == 1 for row in rows))
        for work in (high_work, low_work):
            response = self.client.get(f"/api/me/ai/books/{work}", headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "ready")

        frontend = (ROOT / "web/src/pages/RecommendationsPage.jsx").read_text(encoding="utf-8")
        self.assertIn("/analytics/me/recommendations/state", frontend)
        self.assertNotIn("method: 'POST'", frontend)


if __name__ == "__main__":
    unittest.main()
