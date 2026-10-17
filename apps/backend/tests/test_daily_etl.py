"""Cortes, limpieza, atomicidad, exclusividad y permisos contra PostgreSQL."""
import unittest
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.analytics.etl import LOCK_KEY, day_bounds, extract, last_closed_day, publish, run_day, transform
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission
from scripts.seed_analytics_demo import MANIFEST, seed_scenarios
from scripts.seed_demo import stable_id


class CalendarTest(unittest.TestCase):
    def test_closed_day_uses_santiago_not_utc(self):
        self.assertEqual(last_closed_day(datetime(2026, 10, 10, 2, tzinfo=timezone.utc)), date(2026, 10, 8))
        self.assertEqual(last_closed_day(datetime(2026, 10, 10, 3, tzinfo=timezone.utc)), date(2026, 10, 9))

    def test_dst_day_and_exclusive_end(self):
        start, end = day_bounds(date(2026, 9, 6))
        self.assertEqual((end - start).total_seconds(), 23 * 3600)
        self.assertEqual(end, day_bounds(date(2026, 9, 7))[0])

    def test_current_day_is_rejected(self):
        with self.assertRaises(ValueError):
            run_day(date(2026, 10, 10), now=datetime(2026, 10, 10, 15, tzinfo=timezone.utc))

    def test_repeated_last_hour_belongs_to_same_25_hour_day(self):
        day = date(2026, 4, 4)
        start, cutoff = day_bounds(day)
        self.assertEqual((cutoff - start).total_seconds(), 25 * 3600)
        self.assertEqual(cutoff, day_bounds(date(2026, 4, 5))[0])
        # Antes y después de volver de 23:59 a 23:00, el día sigue abierto.
        for instant in (datetime(2026, 4, 5, 2, 59, 59, tzinfo=timezone.utc),
                        datetime(2026, 4, 5, 3, 0, tzinfo=timezone.utc),
                        datetime(2026, 4, 5, 3, 59, 59, tzinfo=timezone.utc)):
            self.assertEqual(last_closed_day(instant), date(2026, 4, 3))
        self.assertEqual(last_closed_day(cutoff), day)

    def test_etl_rejects_premature_trigger_during_repeated_hour(self):
        # Un disparo anticipado de Windows no debe abrir siquiera la conexión.
        with patch.object(engine, "connect") as connect, self.assertRaises(ValueError):
            run_day(date(2026, 4, 4), now=datetime(2026, 4, 5, 3, 30, tzinfo=timezone.utc))
        connect.assert_not_called()


class ScenarioTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")

    def tearDown(self):
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_repeatable_fixture_and_expected_indicators(self):
        first = seed_scenarios(self.db, "test-password")
        second = seed_scenarios(self.db, "test-password")
        self.assertEqual(first, second)
        self.db.flush()
        for day_string, expected in MANIFEST["expected"].items():
            prepared = transform(*extract(self.connection, *day_bounds(date.fromisoformat(day_string))))
            catalog, events, posts, indicators, rules, summary, *_ = prepared
            simulated = [event for event in events if event["provenance"] == "simulated"]
            self.assertEqual(len(simulated), expected["loaded_events"])
            for role, account in (("reader", "lector"), ("author", "autor")):
                if role not in expected:
                    continue
                actual = {i["indicator_code"]: i["value"] for i in indicators
                          if i["user_id"] == stable_id(f"user:{account}") and i["provenance"] == "simulated"}
                for code, value in expected[role].items():
                    self.assertEqual(actual[code], value, (day_string, role, code))
            if "excluded_reviews" in expected:
                self.assertGreaterEqual(rules["review_model_pending"], expected["excluded_reviews"])
                self.assertEqual(len([p for p in posts if p["provenance"] == "simulated"]), expected["loaded_posts"])

    def test_invalid_event_is_excluded_without_private_text(self):
        seed_scenarios(self.db, "test-password")
        works, events, posts, entries, _ = extract(self.connection, *day_bounds(date(2026, 10, 9)))
        event = dict(next(e for e in events if e["provenance"] == "simulated"))
        event["actor_user_id"] = uuid.uuid4()
        result = transform(works, [event], [], [])
        self.assertEqual(result[4]["event_identity_mismatch"], 1)
        self.assertEqual(result[1], [])
        event["actor_user_id"] = event["user_id"]
        event["page"] = event["total_pages"] + 1
        self.assertEqual(transform(works, [event], [], [])[4]["event_invalid_pages"], 1)


class DailyRunTest(unittest.TestCase):
    def setUp(self):
        self.day = date(1998, 1, 15)
        with engine.connect() as connection:
            exists = connection.execute(text("SELECT id FROM analytics.ejecuciones_etl WHERE business_date=:day"), {"day": self.day}).first()
        if exists:
            self.skipTest("La fecha reservada para esta prueba ya tiene una carga; no se altera")

    def tearDown(self):
        with engine.begin() as connection:
            params = {"day": self.day}
            for table in ("validaciones_etl", "indicadores_personales", "hechos_publicaciones", "hechos_lectura", "hechos_resenas", "preparacion_valoraciones_obras", "catalogo_obras"):
                connection.execute(text(f"DELETE FROM analytics.{table} WHERE etl_run_id IN (SELECT id FROM analytics.ejecuciones_etl WHERE business_date=:day)"), params)
            connection.execute(text("DELETE FROM analytics.ejecuciones_etl WHERE business_date=:day"), params)

    def test_second_successful_call_does_not_reload(self):
        first = run_day(self.day)
        second = run_day(self.day)
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(second["status"], "already_completed")
        self.assertEqual(first["id"], second["id"])
        with engine.connect() as connection:
            count = connection.execute(text("SELECT attempt_count FROM analytics.ejecuciones_etl WHERE id=:id"), {"id": first["id"]}).scalar_one()
        self.assertEqual(count, 1)

    def test_failure_rolls_back_and_retry_reuses_run(self):
        def failing_publish(connection, run_id, prepared, personal=None):
            connection.execute(text("INSERT INTO analytics.catalogo_obras (etl_run_id, work_id, title) VALUES (:run, :work, 'Atomicidad')"),
                               {"run": run_id, "work": uuid.uuid4()})
            raise RuntimeError("Fallo de prueba")
        with patch("app.modules.analytics.etl.publish", side_effect=failing_publish), self.assertRaises(RuntimeError):
            run_day(self.day)
        with engine.connect() as connection:
            failed = connection.execute(text("SELECT id, status FROM analytics.ejecuciones_etl WHERE business_date=:day"), {"day": self.day}).mappings().one()
            count = connection.execute(text("SELECT count(*) FROM analytics.catalogo_obras WHERE etl_run_id=:id"), {"id": failed["id"]}).scalar_one()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(count, 0)
        result = run_day(self.day)
        self.assertEqual(result["id"], str(failed["id"]))
        self.assertEqual(result["status"], "succeeded")

    def test_another_process_cannot_load_while_lock_is_held(self):
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
            connection.commit()
            try:
                self.assertEqual(run_day(self.day)["status"], "busy")
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                connection.commit()


class AnalyticsPermissionTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Prueba de permisos ETL", role="admin")
        self.db.add(self.user)
        self.db.flush()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_role_label_does_not_grant_admin_permission(self):
        self.assertEqual(self.client.get("/api/analytics/admin/etl").status_code, 403)
        self.assertEqual(self.client.get(f"/api/analytics/admin/etl/{uuid.uuid4()}/validations").status_code, 403)

    def test_admin_sees_only_monitoring_and_own_analysis(self):
        self.db.add(AccountPermission(user_id=self.user.id, permission="admin"))
        self.db.flush()
        response = self.client.get("/api/analytics/admin/etl")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        for secret in ('"user_id"', '"source_id"', '"body"', '"reason"'):
            self.assertNotIn(secret, response.text)
        self.assertEqual(self.client.get("/api/analytics/me").json()["items"], [])
        # No existe una ruta para consultar a otro titular, aunque sea administrador.
        self.assertEqual(self.client.get(f"/api/analytics/users/{stable_id('user:lector')}").status_code, 404)

    def test_without_session_is_rejected(self):
        del app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.get("/api/analytics/admin/etl").status_code, 401)

    def test_monitor_detects_a_gap_even_if_latest_day_succeeded(self):
        self.db.add(AccountPermission(user_id=self.user.id, permission="admin"))
        self.db.flush()
        self.db.execute(text("UPDATE analytics.ejecuciones_etl SET status='failed' WHERE business_date='2026-09-22'"))
        result = self.client.get("/api/analytics/admin/etl").json()
        self.assertFalse(result["up_to_date"])
        self.assertGreaterEqual(result["pending_days"], 1)
