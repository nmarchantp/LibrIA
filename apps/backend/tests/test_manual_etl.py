"""Exercise web-triggered extraction, atomic loading, and daily isolation."""
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine, SessionLocal
from app.main import app
from app.modules.analytics.etl import LOCK_KEY, run_manual, resume_manual_pending
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from scripts.seed_demo import stable_id


class ManualEtlTest(unittest.TestCase):
    def setUp(self):
        self.ids = []
        with SessionLocal() as db:
            self.admin = db.get(User, stable_id("user:admin"))
        app.dependency_overrides[get_current_user] = lambda: self.admin
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        with engine.begin() as connection:
            for run_id in self.ids:
                for table in ("evidencia_lectora_personal", "hechos_reflexiones", "validaciones_etl", "indicadores_personales", "hechos_publicaciones",
                              "hechos_lectura", "hechos_resenas", "preparacion_valoraciones_obras", "catalogo_obras"):
                    connection.execute(text(f"DELETE FROM analytics.{table} WHERE etl_run_id=:id"), {"id": run_id})
                connection.execute(text("DELETE FROM analytics.ejecuciones_etl WHERE id=:id"), {"id": run_id})

    def request(self):
        run_id = uuid.uuid4()
        self.ids.append(run_id)
        with patch("app.modules.analytics.router.run_manual") as worker:
            response = self.client.post("/api/analytics/admin/etl/run", json={"request_id": str(run_id)})
        self.assertEqual(response.status_code, 202, response.text)
        worker.assert_called_once_with(run_id)
        return run_id

    def test_web_request_is_idempotent_and_rejects_overlap(self):
        run_id = self.request()
        with patch("app.modules.analytics.router.run_manual") as worker:
            repeat = self.client.post("/api/analytics/admin/etl/run", json={"request_id": str(run_id)})
            self.assertEqual(repeat.status_code, 202)
            worker.assert_not_called()
            overlap = self.client.post("/api/analytics/admin/etl/run", json={"request_id": str(uuid.uuid4())})
            self.assertEqual(overlap.status_code, 409)

    def test_real_load_is_visible_and_does_not_change_daily_indicators(self):
        before = self.client.get("/api/analytics/me").json()
        run_id = self.request()
        run_manual(run_id)
        overview = self.client.get("/api/analytics/admin/etl").json()
        row = next(row for row in overview["runs"] if row["id"] == str(run_id))
        self.assertEqual((row["status"], row["phase"], row["business_date"]), ("succeeded", "completed", None))
        self.assertGreater(row["summary"]["loaded_events"], 0)
        self.assertGreater(row["summary"]["loaded_reviews"], 0)
        self.assertGreater(row["summary"]["excluded_rows"], 0)
        with engine.connect() as connection:
            for table, count_key in (("hechos_lectura", "loaded_events"), ("hechos_resenas", "loaded_reviews"),
                                     ("hechos_publicaciones", "loaded_posts"), ("indicadores_personales", "indicator_rows")):
                count = connection.execute(text(f"SELECT count(*) FROM analytics.{table} WHERE etl_run_id=:id"), {"id": run_id}).scalar_one()
                self.assertEqual(count, row["summary"][count_key])
        self.assertEqual(self.client.get("/api/analytics/me").json(), before)
        validations = self.client.get(f"/api/analytics/admin/etl/{run_id}/validations")
        self.assertEqual(validations.status_code, 200)
        self.assertIn("reconciliation", [rule["rule_code"] for rule in validations.json()])
        run_manual(run_id)
        self.assertEqual(self.client.get("/api/analytics/admin/etl").json()["counts"], overview["counts"])

    def test_failed_load_rolls_back_all_rows(self):
        run_id = self.request()

        def fail(connection, identifier, prepared, personal=None):
            connection.execute(text("INSERT INTO analytics.catalogo_obras (etl_run_id, work_id, title) VALUES (:id, :work, 'Failure test')"),
                               {"id": identifier, "work": uuid.uuid4()})
            raise RuntimeError("Expected test failure")

        with patch("app.modules.analytics.etl.publish", side_effect=fail):
            run_manual(run_id)
        with engine.connect() as connection:
            row = connection.execute(text("SELECT status, phase FROM analytics.ejecuciones_etl WHERE id=:id"), {"id": run_id}).one()
            count = connection.execute(text("SELECT count(*) FROM analytics.catalogo_obras WHERE etl_run_id=:id"), {"id": run_id}).scalar_one()
        self.assertEqual(tuple(row), ("failed", "failed"))
        self.assertEqual(count, 0)

    def test_daily_lock_prevents_web_request(self):
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
            connection.commit()
            try:
                response = self.client.post("/api/analytics/admin/etl/run", json={"request_id": str(uuid.uuid4())})
                self.assertEqual(response.status_code, 409)
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                connection.commit()

    def test_interrupted_request_resumes_after_lock_release(self):
        run_id = self.request()
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
            connection.commit()
            try:
                run_manual(run_id)
                with engine.connect() as check:
                    self.assertEqual(check.execute(text("SELECT status FROM analytics.ejecuciones_etl WHERE id=:id"),
                                                   {"id": run_id}).scalar_one(), "running")
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                connection.commit()
        resume_manual_pending()
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT status FROM analytics.ejecuciones_etl WHERE id=:id"),
                                               {"id": run_id}).scalar_one(), "succeeded")

    def test_permission_required_even_with_admin_role(self):
        with SessionLocal() as db:
            reader = db.get(User, stable_id("user:lector"))
        reader.role = "admin"
        app.dependency_overrides[get_current_user] = lambda: reader
        self.assertEqual(self.client.post("/api/analytics/admin/etl/run", json={"request_id": str(uuid.uuid4())}).status_code, 403)
        del app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.post("/api/analytics/admin/etl/run", json={"request_id": str(uuid.uuid4())}).status_code, 401)
