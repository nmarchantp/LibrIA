"""Optional edition/progress integration on the validator-owned PostgreSQL only."""
from datetime import datetime, timedelta, timezone
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.books.models import Work, Edition
from app.modules.library.models import Reading, ReadingEditionSelection
from tests import test_catalog_phase3 as phase3


class Phase4HTTP(unittest.TestCase):
    setUpClass = classmethod(phase3.Phase3HTTP.setUpClass.__func__)
    tearDownClass = classmethod(phase3.Phase3HTTP.tearDownClass.__func__)
    new_actor = phase3.Phase3HTTP.new_actor
    counts = phase3.Phase3HTTP.counts

    def setUp(self):
        phase3.Phase3HTTP.setUp(self)
        flag = patch.object(get_settings(), "catalog_editionless_enabled", True)
        flag.start()
        self.addCleanup(flag.stop)
        from app.modules.users.identities import create_personal_profile
        from app.modules.users.models import User
        with Session(self.engine) as db, db.begin():
            create_personal_profile(db, db.get(User, uuid.UUID(self.actor)))
            work = Work(title="Optional edition " + uuid.uuid4().hex, categories=["Fiction"])
            db.add(work)
            db.flush()
            self.work_id = str(work.id)
            edition = Edition(work_id=work.id, title=work.title, language="es", page_count=237)
            db.add(edition)
            db.flush()
            self.edition_id = str(edition.id)

    def add_work(self, **changes):
        payload = {"book_ref": self.work_id, "book_title": "Display only", "page_count": 999,
                   "edition_selected": False, **changes}
        return self.client.post("/api/readings/library", json=payload, headers={"Idempotency-Key": str(uuid.uuid4())})

    def event(self, kind, state=None, **extra):
        payload = {"book_ref": self.work_id, "book_title": "Display only", "event": kind,
            "reading_id": None if kind == "start" else state["reading_id"], **extra}
        response = self.client.post("/api/readings/events", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def start(self):
        response = self.add_work()
        self.assertEqual(response.status_code, 200, response.text)
        return self.event("start")

    def test_flags_default_disabled_and_dependency_required(self):
        self.assertFalse(Settings(_env_file=None).catalog_editionless_enabled)
        with self.assertRaises(ValueError):
            Settings(_env_file=None, catalog_editionless_enabled=True)
        self.assertTrue(Settings(_env_file=None, catalog_discovery_enabled=True, catalog_editionless_enabled=True).catalog_editionless_enabled)

    def test_add_without_edition_never_selects_existing_edition_or_client_pages(self):
        before = self.counts()
        response = self.add_work()
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        for key in ("edition_id", "total_pages", "progress_percent"):
            self.assertIsNone(value[key])
        self.assertEqual(value["work_id"], self.work_id)
        self.assertNotIn("pageCount", value["catalog_volume"]["volumeInfo"])
        self.assertEqual(self.counts(), before)

    def test_explicit_edition_is_preserved_without_copying_pages(self):
        response = self.add_work(edition_id=self.edition_id, edition_selected=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["edition_id"], self.edition_id)
        state = self.event("start", edition_id=self.edition_id)
        self.assertEqual(state["edition_id"], self.edition_id)
        self.assertIsNone(state["total_pages"])

    def test_start_progress_finish_unknown_total_and_reload(self):
        state = self.start()
        state = self.event("progress", state, current_page=42)
        self.assertIsNone(state["progress_percent"])
        self.assertIn("página 42", state["post"]["body"])
        finished = self.event("finish", state)
        self.assertEqual(finished["current_page"], 42)
        self.assertIsNone(finished["total_pages"])
        library = self.client.get("/api/readings/me").json()
        self.assertEqual(library[0]["status"], "finished")
        self.assertIsNone(library[0]["edition_id"])
        history = self.client.get(f'/api/readings/{state["reading_id"]}/history').json()
        self.assertEqual([e["event"] for e in history], ["start", "progress", "finish"])
        self.assertTrue(all(e["total_pages"] is None for e in history))

    def test_declared_total_belongs_only_to_attempt_and_old_events_stay_unknown(self):
        state = self.start()
        state = self.event("progress", state, current_page=12)
        response = self.client.patch(f'/api/readings/{state["reading_id"]}/total-pages', json={"total_pages": 80})
        self.assertEqual(response.status_code, 200, response.text)
        finished = self.event("finish", state)
        self.assertEqual(finished["current_page"], 80)
        with Session(self.engine) as db:
            self.assertEqual(db.get(Edition, uuid.UUID(self.edition_id)).page_count, 237)
        history = self.client.get(f'/api/readings/{state["reading_id"]}/history').json()
        self.assertEqual([e["total_pages"] for e in history], [None, None, 80])

    def test_select_later_preserves_attempt_progress_history_and_audits_once(self):
        state = self.event("progress", self.start(), current_page=17)
        url = f'/api/readings/{state["reading_id"]}/edition'
        history = self.client.get(f'/api/readings/{state["reading_id"]}/history').json()
        for _ in range(2):
            response = self.client.patch(url, json={"edition_id": self.edition_id})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["current_page"], 17)
            self.assertIsNone(response.json()["total_pages"])
        self.assertEqual(self.client.get(f'/api/readings/{state["reading_id"]}/history').json(), history)
        with Session(self.engine) as db:
            audit = db.scalars(select(ReadingEditionSelection).where(ReadingEditionSelection.reading_id == uuid.UUID(state["reading_id"]))).all()
            self.assertEqual(len(audit), 1)
            self.assertIsNone(audit[0].before_state["edition_id"])
            self.assertEqual(audit[0].after_state["edition_id"], self.edition_id)

    def test_foreign_edition_rejected_on_add_and_selection_with_no_mutation(self):
        with Session(self.engine) as db, db.begin():
            work = Work(title="Other " + uuid.uuid4().hex)
            db.add(work)
            db.flush()
            edition = Edition(work_id=work.id, title=work.title, language="es")
            db.add(edition)
            db.flush()
            foreign = str(edition.id)
        self.assertEqual(self.add_work(edition_id=foreign, edition_selected=True).status_code, 409)
        state = self.start()
        response = self.client.patch(f'/api/readings/{state["reading_id"]}/edition', json={"edition_id": foreign})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIsNone(self.client.get("/api/readings/me").json()[0]["edition_id"])

    def test_existing_selected_edition_cannot_be_replaced(self):
        self.assertEqual(self.add_work(edition_id=self.edition_id, edition_selected=True).status_code, 200)
        state = self.event("start")
        with Session(self.engine) as db, db.begin():
            other = Edition(work_id=uuid.UUID(self.work_id), title="Other edition", language="en")
            db.add(other)
            db.flush()
            other_id = str(other.id)
        response = self.client.patch(f'/api/readings/{state["reading_id"]}/edition', json={"edition_id": other_id})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/api/readings/me").json()[0]["edition_id"], self.edition_id)

    def test_external_work_incorporation_catalogs_edition_without_selecting_it_for_reading(self):
        item = phase3.volume()
        before = self.counts()
        data = {"book_ref": item["id"], "book_title": "Display", "edition_selected": False,
            "external_reference": {"provider": "google-books", "reference_type": "volume", "external_id": item["id"]}}
        key = str(uuid.uuid4())
        with patch("app.modules.books.evidence.google_request", return_value=item):
            response = self.client.post("/api/readings/library", json=data, headers={"Idempotency-Key": key})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["edition_id"])
        after = self.counts()
        self.assertEqual(after["obras"], before["obras"] + 1)
        self.assertEqual(after["ediciones"], before["ediciones"] + 1)
        self.assertEqual(after["fuentes_catalogo"], before["fuentes_catalogo"] + 2)
        with patch("app.modules.books.evidence.google_request", side_effect=AssertionError("Replay must not fetch")):
            replay = self.client.post("/api/readings/library", json=data, headers={"Idempotency-Key": key})
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(self.counts(), after)

    def test_work_detail_and_search_without_edition_metadata(self):
        detail = self.client.get("/api/books/" + self.work_id)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertIsNone(detail.json()["libria"]["editionId"])
        self.assertNotIn("pageCount", detail.json()["volumeInfo"])
        with patch("app.modules.books.discovery.google_request", return_value={"items": []}):
            result = self.client.get("/api/books", params={"q": detail.json()["volumeInfo"]["title"]})
        self.assertIn(self.work_id, [i["id"] for i in result.json()["items"]])

    def test_review_rating_statistics_etl_profile_and_individual_context(self):
        from app.modules.analytics.etl import extract, transform, publish
        from app.modules.analytics.reader_evidence import extract_personal
        from app.modules.analytics.recommendation_profiles import _finished_readings, _reader_books
        from app.modules.analytics.gemini_worker import _individual_context
        from app.modules.users.reading_statistics import most_read_genres
        state = self.event("progress", self.start(), current_page=31)
        state = self.event("finish", state)
        response = self.client.post("/api/reviews", json={"work_id": self.work_id, "edition_id": None,
            "body": "Reader authored review", "rating": 4.5, "status": "published"})
        self.assertEqual(response.status_code, 201, response.text)
        cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)
        with self.engine.begin() as conn:
            prepared = transform(*extract(conn, cutoff - timedelta(days=1), cutoff))
            events = [e for e in prepared[1] if str(e["work_id"]) == self.work_id]
            self.assertEqual(len(events), 3)
            self.assertTrue(all(e["edition_id"] is None and e["total_pages"] is None for e in events))
            indicators = {i["indicator_code"]: i["value"] for i in prepared[3] if str(i["user_id"]) == self.actor}
            self.assertEqual(indicators["L05"], 1)
            self.assertEqual(indicators["L10"], 31)
            evidence = extract_personal(conn, cutoff)
            books = _reader_books(uuid.UUID(self.actor), _finished_readings(conn, cutoff), evidence, cutoff)
            self.assertEqual(len(books), 1)
            for key in ("edition_id", "pages", "format", "publisher_name"):
                self.assertIsNone(books[0]["metadata"][key])
            run_id = uuid.uuid4()
            conn.execute(text("""INSERT INTO analytics.ejecuciones_etl
                (id,status,started_at,source_cutoff_at,transform_version,business_date,period_start,run_kind,phase)
                VALUES (:id,'running',now(),:cutoff,'phase4-test','2091-01-01',:start,'daily','running')"""),
                {"id": run_id, "cutoff": cutoff, "start": cutoff - timedelta(days=1)})
            publish(conn, run_id, prepared, personal=evidence)
            facts = conn.execute(text("SELECT edition_id,total_pages FROM analytics.hechos_lectura WHERE etl_run_id=:run AND work_id=:work"),
                {"run": run_id, "work": self.work_id}).all()
            self.assertEqual(len(facts), 3)
            self.assertTrue(all(row == (None, None) for row in facts))
            profile = conn.execute(text("SELECT payload FROM ia.reader_profile_versions WHERE owner_id=:owner AND etl_run_id=:run"),
                {"owner": self.actor, "run": run_id}).scalar_one()
            self.assertEqual(len(profile["books"]), 1)
            self.assertIsNone(profile["books"][0]["metadata"]["edition_id"])
            conn.rollback()  # isolate the synthetic ETL run from monitoring regression fixtures
        with Session(self.engine) as db:
            stats = most_read_genres(db, uuid.UUID(self.actor))
            self.assertEqual(stats["finished_books"], 1)
            context, units = _individual_context(db, {"reading_event_id": uuid.UUID(state["event_id"]), "owner_id": uuid.UUID(self.actor)})
            self.assertTrue(units)
        detail = self.client.get("/api/books/" + self.work_id).json()["libria"]
        self.assertEqual(detail["ratingsCount"], 1)
        self.assertEqual(detail["readingStats"]["finished"], 1)
        feed = self.client.get("/api/posts").json()
        self.assertTrue(any(str(i["id"]) == state["event_id"] for i in feed))

    def test_later_edition_selection_does_not_rewrite_earlier_profile_cutoff(self):
        from app.modules.analytics.recommendation_profiles import _finished_readings
        state = self.event("finish", self.start())
        cutoff = datetime.now(timezone.utc)
        response = self.client.patch(f'/api/readings/{state["reading_id"]}/edition', json={"edition_id": self.edition_id})
        self.assertEqual(response.status_code, 200, response.text)
        with self.engine.connect() as conn:
            row = next(r for r in _finished_readings(conn, cutoff) if str(r["reading_id"]) == state["reading_id"])
            self.assertIsNone(row["edition_id"])
            self.assertIsNone(row["pages"])

    def test_abandon_correction_and_reread_without_edition(self):
        state = self.event("progress", self.start(), current_page=20)
        state = self.event("correction", state, current_page=10, correction_reason="Reader correction")
        state = self.event("abandon", state)
        self.assertEqual((state["status"], state["current_page"]), ("abandoned", 10))
        old = state["reading_id"]
        state = self.event("start")
        self.assertNotEqual(state["reading_id"], old)
        self.assertIsNone(state["edition_id"])
        self.assertEqual(len(self.client.get(f'/api/readings/{old}/history').json()), 4)
        attempts = self.client.get(f'/api/readings/library/{self.work_id}/attempts')
        self.assertEqual(attempts.status_code, 200, attempts.text)
        self.assertEqual({row["reading_id"] for row in attempts.json()}, {old, state["reading_id"]})
        self.assertTrue(all(row["edition_id"] is None for row in attempts.json()))
        other = self.new_actor()
        self.assertEqual(self.client.get(f'/api/readings/library/{self.work_id}/attempts', headers={"X-Test-Actor": other}).json(), [])

    def test_selection_permission_and_append_only_audit(self):
        state = self.start()
        url = f'/api/readings/{state["reading_id"]}/edition'
        other = self.new_actor()
        self.assertEqual(self.client.patch(url, json={"edition_id": self.edition_id}, headers={"X-Test-Actor": other}).status_code, 404)
        self.assertEqual(self.client.patch(url, json={"edition_id": self.edition_id}).status_code, 200)
        from sqlalchemy.exc import DBAPIError
        with self.engine.connect() as conn:
            with self.assertRaises(DBAPIError):
                conn.execute(text("DELETE FROM app.selecciones_edicion_lectura WHERE reading_id=:id"), {"id": state["reading_id"]})
            conn.rollback()

    def test_phase4_commands_remain_disabled_without_flag(self):
        with patch.object(get_settings(), "catalog_editionless_enabled", False):
            self.assertEqual(self.add_work().status_code, 422)
            response = self.client.patch(f'/api/readings/{uuid.uuid4()}/edition', json={"edition_id": self.edition_id})
            self.assertEqual(response.status_code, 404)

    def test_concurrent_selection_and_progress_preserve_both_results(self):
        from concurrent.futures import ThreadPoolExecutor
        state = self.event("progress", self.start(), current_page=17)
        def select():
            return self.client.patch(f'/api/readings/{state["reading_id"]}/edition', json={"edition_id": self.edition_id})
        def progress():
            return self.client.post("/api/readings/events", json={"book_ref": self.work_id, "book_title": "Display",
                "event": "progress", "reading_id": state["reading_id"], "current_page": 30})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda fn: fn(), [select, progress]))
        self.assertEqual([r.status_code for r in results], [200, 201], [r.text for r in results])
        saved = self.client.get("/api/readings/me").json()[0]
        self.assertEqual((saved["edition_id"], saved["current_page"], saved["total_pages"]), (self.edition_id, 30, None))

    def test_intermediate_failure_rolls_back_event_progress_and_selection(self):
        state = self.start()
        with patch("app.modules.analytics.persistence.enqueue_reading_event_analysis", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                self.client.post("/api/readings/events", json={"book_ref": self.work_id, "book_title": "Display",
                    "event": "finish", "reading_id": state["reading_id"], "current_page": 50})
        library = self.client.get("/api/readings/me").json()[0]
        self.assertEqual((library["status"], library["current_page"]), ("reading", 0))
        with patch("app.modules.books.library_view.reading_state", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                self.client.patch(f'/api/readings/{state["reading_id"]}/edition', json={"edition_id": self.edition_id})
        with Session(self.engine) as db:
            self.assertIsNone(db.get(Reading, uuid.UUID(state["reading_id"])).edition_id)
            self.assertIsNone(db.scalar(select(ReadingEditionSelection).where(ReadingEditionSelection.reading_id == uuid.UUID(state["reading_id"]))))

    def test_database_rejects_missing_work_and_foreign_edition(self):
        state = self.start()
        with self.engine.connect() as conn:
            with self.assertRaises(IntegrityError):
                conn.execute(text("UPDATE app.lecturas SET work_id=NULL WHERE id=:id"), {"id": state["reading_id"]})
            conn.rollback()
            with self.assertRaises(IntegrityError):
                conn.execute(text("UPDATE app.lecturas SET edition_id=:ed WHERE id=:id"), {"id": state["reading_id"], "ed": self.ids["edition"]})
            conn.rollback()
