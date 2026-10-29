"""Stage 4 session, recommendation synchronization and trigger contracts.

Writing cases are opt-in and refuse the developer's ``libria`` database.
"""

from __future__ import annotations

import inspect
import os
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token_claims
from app.main import app
from app.modules.analytics import adaptive_ai
from app.modules.analytics.persistence import enqueue_reading_event_analysis
from app.modules.analytics.recommendation_sync import recommendation_state
from app.modules.auth.models import AuthSession
from app.modules.auth.sessions import (SessionValidationError, create_session, record_activity,
                                       rotate_refresh_token, validate_access_session)


ROOT = Path(__file__).resolve().parents[2]


class Stage4StaticContractTest(unittest.TestCase):
    def test_access_jwt_is_short_and_bound_to_session(self):
        user_id, session_id = uuid.uuid4(), uuid.uuid4()
        claims = decode_token_claims(create_access_token(str(user_id), session_id), "access")
        self.assertEqual((claims["sub"], claims["sid"], claims["typ"]),
                         (str(user_id), str(session_id), "access"))

    def test_access_jwt_expiration_is_enforced(self):
        expired = create_access_token(str(uuid.uuid4()), uuid.uuid4(),
                                      now=datetime.now(timezone.utc) - timedelta(hours=1))
        self.assertIsNone(decode_token_claims(expired, "access"))

    def test_inactivity_and_absolute_lifetimes_are_separate(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.session_inactivity_hours, 24)
        self.assertGreaterEqual(settings.session_absolute_hours, settings.session_inactivity_hours)

    def test_refresh_is_cookie_only_in_frontend(self):
        source = (ROOT / "web/src/context/AuthContext.jsx").read_text(encoding="utf-8")
        self.assertNotIn("refresh_token", source)
        self.assertIn("credentials: 'include'", (ROOT / "web/src/services/authService.js").read_text(encoding="utf-8"))

    def test_real_activity_excludes_mouse_movement_and_polling(self):
        source = (ROOT / "web/src/context/AuthContext.jsx").read_text(encoding="utf-8")
        self.assertNotIn("mousemove", source)
        self.assertIn("event.isTrusted", source)
        self.assertNotIn("setInterval(() => sendActivity", source)

    def test_suspended_tab_is_checked_on_return(self):
        source = (ROOT / "web/src/context/AuthContext.jsx").read_text(encoding="utf-8")
        self.assertIn("visibilitychange", source)
        self.assertIn("authService.session", source)

    def test_tabs_share_logout_and_expiration(self):
        source = (ROOT / "web/src/context/AuthContext.jsx").read_text(encoding="utf-8")
        self.assertIn("BroadcastChannel", source)
        self.assertIn("window.addEventListener('storage'", source)

    def test_unsaved_reviews_notes_and_theories_are_registered(self):
        hook = (ROOT / "web/src/hooks/useUnsavedSessionWarning.js").read_text(encoding="utf-8")
        reading = (ROOT / "web/src/pages/ReadingPage.jsx").read_text(encoding="utf-8")
        library = (ROOT / "web/src/pages/LibraryBookPage.jsx").read_text(encoding="utf-8")
        self.assertIn("beforeunload", hook)
        self.assertIn("useUnsavedSessionWarning", reading)
        self.assertGreaterEqual(library.count("useUnsavedSessionWarning"), 3)

    def test_refresh_does_not_record_activity(self):
        self.assertNotIn("record_activity", inspect.getsource(rotate_refresh_token))

    def test_legacy_worker_is_disabled(self):
        source = inspect.getsource(adaptive_ai.process_one)
        self.assertIn("LegacyAIFlowDisabled", source)
        self.assertNotIn("SessionLocal", source)

    def test_recommendation_get_is_read_only(self):
        source = (ROOT / "backend/app/modules/analytics/insights_router.py").read_text(encoding="utf-8")
        self.assertIn("recommendation_state(db, user.id, enqueue=False)", source)
        self.assertIn("recommendation_state(db, user.id, enqueue=True)", source)

    def test_all_recommendation_states_are_prepared(self):
        source = (ROOT / "backend/app/modules/analytics/recommendation_sync.py").read_text(encoding="utf-8")
        for state in ("waiting_for_etl", "insufficient_data", "pending", "processing", "ready", "outdated", "failed", "budget_exhausted"):
            self.assertIn(state, source)

    def test_register_does_not_sync_recommendations(self):
        source = inspect.getsource(__import__("app.modules.auth.router", fromlist=["register"]).register)
        self.assertNotIn("safe_sync_recommendations", source)

    def test_both_login_flows_use_the_same_session_issuer(self):
        source = inspect.getsource(__import__("app.modules.auth.service", fromlist=["AuthService"]).AuthService)
        self.assertIn("return self._token_response(account.user)", source)
        self.assertIn("return self._token_response(self.authenticate_google(claims))", source)

    def test_no_gemini_execution_is_imported_by_sync(self):
        source = inspect.getsource(__import__("app.modules.analytics.recommendation_sync", fromlist=["*"]))
        self.assertNotIn("GeminiProvider", source)
        self.assertNotIn("generate_structured", source)

    def test_individual_job_has_reading_and_event_identity_and_delay(self):
        source = inspect.getsource(enqueue_reading_event_analysis)
        self.assertIn("ev.id::text", source)
        self.assertIn(":provider", source)
        self.assertIn(":prompt", source)
        self.assertIn("interval '1 minute'", source)

    def test_forward_migration_preserves_projection_triggers(self):
        source = (ROOT / "backend/migrations/versions/0051_sessions_and_controlled_ai_triggers.py").read_text(encoding="utf-8")
        self.assertNotIn("projection_business_dirty", source)
        self.assertNotIn("projection_social_dirty", source)
        self.assertIn("never creates AI jobs", source)


@unittest.skipUnless(os.getenv("LIBRIA_STAGE4_TEST") == "1",
                     "requires isolated PostgreSQL with LIBRIA_STAGE4_TEST=1")
class Stage4DatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_url = os.environ["DATABASE_URL"]
        url = make_url(cls.database_url)
        if url.host not in {"localhost", "127.0.0.1", "::1"} or url.database == "libria":
            raise RuntimeError("Stage 4 tests require disposable loopback PostgreSQL")
        cls.engine = create_engine(cls.database_url)
        command.upgrade(Config("alembic.ini"), "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def register(self):
        email = f"{uuid.uuid4()}@example.com"
        response = self.client.post("/api/auth/register", json={
            "email": email, "password": "password123", "display_name": "Lectora etapa 4",
        })
        self.assertEqual(response.status_code, 201, response.text)
        return email, response.json()

    @staticmethod
    def auth(result):
        return {"Authorization": f"Bearer {result['access_token']}"}

    def expire_inactivity(self, result):
        session = self.db.get(AuthSession, uuid.UUID(result["session_id"]))
        current = datetime.now(timezone.utc)
        session.created_at = current - timedelta(hours=26)
        session.last_activity_at = current - timedelta(hours=25)
        session.inactivity_expires_at = current - timedelta(hours=1)
        self.db.commit()

    def seed_profile_state(self, owner_id, *, empty=False, day=date(2050, 1, 1), version=1):
        run_id, profile_id = uuid.uuid4(), uuid.uuid4()
        cutoff = datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc)
        self.db.execute(text("""INSERT INTO analytics.ejecuciones_etl
            (id,status,started_at,finished_at,source_cutoff_at,transform_version,business_date,
             period_start,run_kind,phase)
            VALUES (:id,'succeeded',:cutoff,:cutoff,:cutoff,'stage4',:day,:start,'daily','completed')"""),
            {"id": run_id, "cutoff": cutoff, "day": day, "start": cutoff - timedelta(days=1)})
        if not empty:
            self.db.execute(text("""INSERT INTO ia.reader_profile_versions
                (id,owner_id,etl_run_id,data_hash,version,status,payload)
                VALUES (:id,:owner,:run,:hash,:version,'pending',
                        '{"hash_version":"recommendation-profile-v1","books":[{}]}'::jsonb)"""),
                {"id": profile_id, "owner": owner_id, "run": run_id,
                 "hash": uuid.uuid4().hex + uuid.uuid4().hex, "version": version})
        self.db.execute(text("""INSERT INTO ia.reader_profile_etl_states
            (owner_id,etl_run_id,profile_version_id,outcome,eligible_books_count,context_bytes,estimated_tokens)
            VALUES (:owner,:run,:profile,:outcome,:count,0,0)"""),
            {"owner": owner_id, "run": run_id, "profile": None if empty else profile_id,
             "outcome": "empty" if empty else "eligible_pending", "count": 0 if empty else 1})
        self.db.commit()
        return profile_id

    def start_and_close(self, result, kind="finish", book_ref=None):
        book_ref = book_ref or f"test:{uuid.uuid4()}"
        base = {"book_ref": book_ref, "book_title": "Obra etapa 4", "page_count": 100}
        started = self.client.post("/api/readings/events", headers=self.auth(result), json={**base, "event": "start"})
        self.assertEqual(started.status_code, 201, started.text)
        closed = self.client.post("/api/readings/events", headers=self.auth(result), json={
            **base, "reading_id": started.json()["reading_id"], "event": kind,
            **({"abandonment_reason": "No conectó"} if kind == "abandon" else {}),
        })
        self.assertEqual(closed.status_code, 201, closed.text)
        return started.json(), closed.json(), book_ref

    def test_password_login_creates_server_session(self):
        email, registered = self.register()
        logged = self.client.post("/api/auth/login", json={"email": email, "password": "password123"})
        self.assertEqual(logged.status_code, 200)
        self.assertNotEqual(logged.json()["session_id"], registered["session_id"])

    def test_inactivity_expires_after_24_hours(self):
        _, result = self.register(); self.expire_inactivity(result)
        response = self.client.get("/api/auth/me", headers=self.auth(result))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "session_inactive")

    def test_valid_activity_extends_inactivity(self):
        _, result = self.register()
        session = self.db.get(AuthSession, uuid.UUID(result["session_id"]))
        old_expiry = session.inactivity_expires_at
        session.created_at -= timedelta(hours=1)
        session.last_activity_at -= timedelta(hours=1)
        self.db.commit()
        response = self.client.post("/api/auth/activity", headers=self.auth(result))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreater(datetime.fromisoformat(response.json()["inactivity_expires_at"]), old_expiry)

    def test_refresh_rotates_without_extending_activity(self):
        _, result = self.register()
        before = self.db.get(AuthSession, uuid.UUID(result["session_id"])).last_activity_at
        refreshed = self.client.post("/api/auth/refresh", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        current = self.db.get(AuthSession, uuid.UUID(result["session_id"]))
        self.assertEqual(current.last_activity_at, before)
        self.assertEqual(current.refresh_generation, 2)

    def test_expired_session_cannot_refresh(self):
        _, result = self.register(); self.expire_inactivity(result)
        response = self.client.post("/api/auth/refresh", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_access(self):
        _, result = self.register()
        self.assertEqual(self.client.post("/api/auth/logout", headers=self.auth(result)).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth(result)).status_code, 401)

    def test_passive_session_check_does_not_extend_inactivity(self):
        _, result = self.register()
        before = self.db.get(AuthSession, uuid.UUID(result["session_id"])).last_activity_at
        self.assertEqual(self.client.get("/api/auth/session", headers=self.auth(result)).status_code, 200)
        self.assertEqual(self.db.get(AuthSession, uuid.UUID(result["session_id"])).last_activity_at, before)

    def test_register_does_not_create_recommendation_job(self):
        _, result = self.register()
        count = self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner"),
                                {"owner": uuid.UUID(result["user"]["id"])}).scalar_one()
        self.assertEqual(count, 0)

    def test_login_after_etl_enqueues_one_recommendation(self):
        email, result = self.register()
        self.seed_profile_state(uuid.UUID(result["user"]["id"]))
        logged = self.client.post("/api/auth/login", json={"email": email, "password": "password123"})
        self.assertEqual(logged.status_code, 200)
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind='recommendation'"),
                                         {"owner": uuid.UUID(result["user"]["id"])}).scalar_one(), 1)

    def test_five_logins_still_create_one_recommendation(self):
        email, result = self.register(); owner = uuid.UUID(result["user"]["id"])
        self.seed_profile_state(owner)
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code, 200)
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind='recommendation'"),
                                         {"owner": owner}).scalar_one(), 1)

    def test_open_session_syncs_after_new_etl(self):
        _, result = self.register(); owner = uuid.UUID(result["user"]["id"])
        self.seed_profile_state(owner)
        synced = self.client.post("/api/analytics/me/recommendations/sync", headers=self.auth(result))
        self.assertEqual(synced.status_code, 200, synced.text)
        self.assertEqual(synced.json()["status"], "pending")

    def test_old_result_is_outdated_while_new_profile_job_is_pending(self):
        _, result = self.register(); owner = uuid.UUID(result["user"]["id"])
        first_profile = self.seed_profile_state(owner, day=date(2050, 1, 1), version=1)
        first = recommendation_state(self.db, owner, enqueue=True)
        self.db.execute(text("""INSERT INTO ia.recomendaciones_ia
            (id,owner_user_id,data_hash,model,version,content,provider,profile_version_id,job_id)
            VALUES (:id,:owner,:hash,'gemini-3.5-flash-lite','recommendations-v1',
                    '{"items":[{"id":"old"}]}'::jsonb,'gemini',:profile,:job)"""),
            {"id": uuid.uuid4(), "owner": owner, "hash": uuid.uuid4().hex, "profile": first_profile,
             "job": uuid.UUID(first["job_id"])})
        second_profile = self.seed_profile_state(owner, day=date(2050, 1, 2), version=2)
        new_run = self.db.execute(text("SELECT etl_run_id FROM ia.reader_profile_etl_states WHERE profile_version_id=:profile"),
                                  {"profile": second_profile}).scalar_one()
        self.db.execute(text("""UPDATE ia.recomendaciones_ia SET is_current=false,
            invalidated_at=now(),invalidated_by_etl_run_id=:run WHERE profile_version_id=:profile"""),
            {"run": new_run, "profile": first_profile})
        self.db.commit()
        state = recommendation_state(self.db, owner, enqueue=True)
        self.assertEqual((state["status"], state["generation_status"]), ("outdated", "pending"))
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind='recommendation'"),
                                         {"owner": owner}).scalar_one(), 2)

    def test_user_without_etl_waits_without_job(self):
        _, result = self.register()
        state = self.client.get("/api/analytics/me/recommendations/state", headers=self.auth(result))
        self.assertEqual(state.json()["status"], "waiting_for_etl")

    def test_empty_profile_is_insufficient_without_job(self):
        _, result = self.register(); owner = uuid.UUID(result["user"]["id"])
        self.seed_profile_state(owner, empty=True)
        state = recommendation_state(self.db, owner, enqueue=True)
        self.assertEqual(state["status"], "insufficient_data")

    def test_finish_creates_one_delayed_individual_job(self):
        _, result = self.register(); _, closed, _ = self.start_and_close(result)
        row = self.db.execute(text("SELECT * FROM ia.jobs WHERE reading_event_id=:event"),
                              {"event": uuid.UUID(closed["event_id"])}).mappings().one()
        self.assertEqual(row["job_kind"], "reading_event_analysis")
        event_at = self.db.execute(text("SELECT created_at FROM app.eventos_lectura WHERE id=:id"),
                                   {"id": uuid.UUID(closed["event_id"])}).scalar_one()
        self.assertEqual(row["not_before"] - event_at, timedelta(minutes=30))

    def test_abandon_creates_one_individual_job(self):
        _, result = self.register(); _, closed, _ = self.start_and_close(result, "abandon")
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE reading_event_id=:event"),
                                         {"event": uuid.UUID(closed["event_id"])}).scalar_one(), 1)

    def test_reread_has_distinct_job_identity(self):
        _, result = self.register(); _, first, ref = self.start_and_close(result)
        _, second, _ = self.start_and_close(result, book_ref=ref)
        rows = self.db.execute(text("SELECT target FROM ia.jobs WHERE reading_event_id IN (:one,:two) ORDER BY target"),
                               {"one": uuid.UUID(first["event_id"]), "two": uuid.UUID(second["event_id"])}).scalars().all()
        self.assertEqual(len(set(rows)), 2)

    def test_review_edit_does_not_duplicate_individual_analysis(self):
        _, result = self.register(); started, _, _ = self.start_and_close(result)
        created = self.client.post("/api/reviews", headers=self.auth(result), json={
            "work_id": started["work_id"], "edition_id": started["edition_id"],
            "rating": 4, "body": "Reseña inicial", "status": "draft",
        })
        self.assertEqual(created.status_code, 201, created.text)
        edited = self.client.put(f"/api/reviews/{created.json()['id']}", headers=self.auth(result), json={
            "edition_id": started["edition_id"], "rating": 4.5,
            "body": "Reseña editada", "status": "draft", "is_spoiler": False,
        })
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind='reading_event_analysis'"),
                                         {"owner": uuid.UUID(result["user"]["id"])}).scalar_one(), 1)

    def test_theory_edit_does_not_duplicate_individual_analysis(self):
        _, result = self.register(); _, _, ref = self.start_and_close(result)
        created = self.client.post("/api/posts", headers=self.auth(result), json={
            "source": "community", "kind": "community", "publication_type": "theory",
            "title": "Teoría", "body": "Hipótesis inicial", "book_ref": ref,
            "book_title": "Obra etapa 4",
        })
        self.assertEqual(created.status_code, 201, created.text)
        self.db.execute(text("UPDATE app.publicaciones SET body='Hipótesis editada' WHERE id=:id"),
                        {"id": uuid.UUID(created.json()["id"])})
        self.db.commit()
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind='reading_event_analysis'"),
                                         {"owner": uuid.UUID(result["user"]["id"])}).scalar_one(), 1)

    def test_job_survives_worker_restart_without_execution(self):
        _, result = self.register(); _, closed, _ = self.start_and_close(result)
        row = self.db.execute(text("SELECT status,attempts FROM ia.jobs WHERE reading_event_id=:event"),
                              {"event": uuid.UUID(closed["event_id"])}).one()
        self.assertEqual(tuple(row), ("pending", 0))

    def test_infrastructure_failure_never_blocks_login(self):
        email, _ = self.register()
        with patch("app.modules.analytics.recommendation_sync.recommendation_state", side_effect=RuntimeError("offline")):
            response = self.client.post("/api/auth/login", json={"email": email, "password": "password123"})
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()
