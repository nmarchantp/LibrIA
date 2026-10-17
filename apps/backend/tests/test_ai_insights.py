"""Owner isolation, aggregate suppression, provenance and grounded AI cache."""
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch
from contextlib import contextmanager
import httpx
from app.modules.analytics.fast_profile import request_json

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.core.database import engine, get_db
from app.main import app
from app.modules.analytics.insights import aggregate_evidence, group_access, group_evidence
from app.modules.analytics.interpretation_provider import generate_interpretation, validate_interpretation, ProviderError
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry
from app.modules.users.identity_models import AccountPermission, Profile, ProfileCapability, ProfileMember
from scripts.seed_group_demo import seed_group


def narrative(metric="L02"):
    return {"title": "Tu actividad registrada", "summary": "Este escenario ficticio muestra actividad registrada.",
            "observations": [{"metric": metric, "interpretation": "Hay registros de actividad en el período."}],
            "suggestions": ["Puedes seguir registrando tus avances."],
            "limitations": ["Los datos disponibles no describen toda tu actividad."]}


@contextmanager
def provider_stream(response):
    async def read(payload):
        transport=httpx.MockTransport(lambda request:httpx.Response(200,content=response.getvalue()))
        return await request_json(payload,1,transport=transport)
    with patch('app.modules.analytics.interpretation_provider.request_book',side_effect=read) as transport:
        yield transport


class AggregateTest(unittest.TestCase):
    def population(self, count):
        return [{"user_id": uuid.uuid4(), "event_kind": "start"} for _ in range(count)]

    def test_small_group_never_releases_counts(self):
        self.assertIsNone(aggregate_evidence(self.population(9), [], {}, "unclassified"))

    def test_thresholds_caps_rounding_and_no_identity(self):
        events = self.population(12)
        events += [{"user_id": events[0]["user_id"], "event_kind": "finish"}] * 100
        reviews = [{"user_id": events[i]["user_id"], "rating": 4} for i in range(4)]
        result = aggregate_evidence(events, reviews, {}, "unclassified")
        self.assertEqual(result["metrics"]["G_READERS"]["value"], 10)
        self.assertNotIn("G_FINISHES", result["metrics"])
        self.assertNotIn("G_RATING", result["metrics"])
        self.assertNotIn("G_REVIEWS", result["metrics"])
        self.assertNotIn("user_id", json.dumps(result))
        for index in range(1, 5):
            events.append({"user_id": events[index]["user_id"], "event_kind": "finish"})
        result = aggregate_evidence(events, reviews, {}, "unclassified")
        self.assertEqual(result["metrics"]["G_FINISHES"]["value"], 15)

    def test_invalid_model_evidence_and_numbers_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_interpretation(narrative("NON_EXISTENT"), ["L02"])
        invalid = narrative()
        invalid["summary"] = "Registraste 999 libros."
        with self.assertRaises(ValueError):
            validate_interpretation(invalid, ["L02"])

    def test_narrative_can_repeat_only_numbers_from_verified_metrics(self):
        content = narrative()
        content["summary"] = "El escenario ficticio registra 2 incorporaciones."
        metrics = {"L02": {"value": 2, "label": "Libros incorporados"}}
        self.assertEqual(validate_interpretation(content, metrics)["summary"], content["summary"])
        content["summary"] = "El escenario ficticio registra 3 incorporaciones."
        with self.assertRaises(ValueError):
            validate_interpretation(content, metrics)

    def test_provider_is_local_and_schema_constrained(self):
        response = BytesIO(json.dumps({"done": True, "done_reason": "stop", "message": {"content": json.dumps(narrative())}}).encode())
        with provider_stream(response) as transport:
            result = generate_interpretation({"metrics": {"L02": {"value": 2}}}, "personal")
        self.assertEqual(result["title"], narrative()["title"])
        body = transport.call_args.args[0]
        self.assertTrue(body["stream"])
        self.assertFalse(body["think"])
        self.assertEqual(body["format"]["properties"]["observations"]["items"]["properties"]["metric"]["enum"], ["L02"])

    def test_remote_ollama_address_is_rejected(self):
        with self.assertRaises(ValueError):
            Settings(ollama_base_url="http://example.com", _env_file=None)

    def test_personal_contributions_are_required_in_schema_and_response(self):
        evidence = {"metrics": {"L02": {"value": 11}, "Q02": {"value": 2}},
                    "reader_contributions": [{"kind": "review", "body": "Mi lectura"}]}
        response = BytesIO(json.dumps({"done": True, "message": {"content": json.dumps(narrative("Q02"))}}).encode())
        with provider_stream(response) as transport:
            self.assertEqual(generate_interpretation(evidence, "personal")["observations"][0]["metric"], "Q02")
        schema = transport.call_args.args[0]["format"]["properties"]["observations"]
        self.assertEqual(schema["items"]["properties"]["metric"]["enum"], ["Q02"])
        invalid = BytesIO(json.dumps({"done": True, "message": {"content": json.dumps(narrative("L02"))}}).encode())
        with provider_stream(invalid), self.assertRaises(ProviderError):
            generate_interpretation(evidence, "personal")

    def test_reflections_and_contributions_must_both_be_covered(self):
        evidence = {"metrics": {"Q01": {"value": 1}, "Q02": {"value": 2}},
                    "qualitative": [{"reflection": "Mi experiencia"}],
                    "reader_contributions": [{"kind": "review", "body": "Mi lectura"}]}
        content = narrative("Q01")
        content["observations"].append({"metric": "Q02", "interpretation": "Has expresado opiniones sobre tus libros."})
        response = BytesIO(json.dumps({"done": True, "message": {"content": json.dumps(content)}}).encode())
        with provider_stream(response) as transport:
            self.assertEqual(len(generate_interpretation(evidence, "personal")["observations"]), 2)
        schema = transport.call_args.args[0]["format"]["properties"]["observations"]
        self.assertEqual(schema["minItems"], 2)
        self.assertEqual(schema["items"]["properties"]["metric"]["enum"], ["Q01", "Q02"])

    def test_complete_json_at_token_limit_is_valid_but_partial_json_is_not(self):
        valid = BytesIO(json.dumps({"done": True, "done_reason": "length", "message": {"content": json.dumps(narrative())}}).encode())
        with provider_stream(valid):
            self.assertEqual(generate_interpretation({"metrics": {"L02": {"value": 2}}}, "personal")["title"], narrative()["title"])
        partial = BytesIO(json.dumps({"done": True, "done_reason": "length", "message": {"content": '{"title":'}}).encode())
        with provider_stream(partial), self.assertRaises(ProviderError):
            generate_interpretation({"metrics": {"L02": {"value": 2}}}, "personal")

    def test_stream_stops_after_complete_validated_object(self):
        content = json.dumps(narrative())
        lines = [json.dumps({"message": {"content": content[:30]}, "done": False}),
                 json.dumps({"message": {"content": content[30:]}, "done": False}), "invalid trailing padding"]
        response = BytesIO("\n".join(lines).encode())
        with provider_stream(response):
            self.assertEqual(generate_interpretation({"metrics": {"L02": {"value": 2}}}, "personal")["title"], narrative()["title"])


class InsightApiTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Test insight owner", role="lector")
        self.db.add(self.user)
        self.db.flush()
        self.profile = Profile(kind="personal", owner_user_id=self.user.id, display_name=self.user.display_name)
        for index in range(10):
            work = Work(title=f"ADN prerequisite {index}")
            self.db.add(work)
            self.db.flush()
            self.db.add(LibraryEntry(user_id=self.user.id, work_id=work.id))
        self.db.add(self.profile)
        self.db.flush()
        self.run_id = uuid.uuid4()
        cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
        self.db.execute(text("""INSERT INTO analytics.ejecuciones_etl
            (id, status, started_at, source_cutoff_at, transform_version, run_kind, requested_by, period_start)
            VALUES (:id, 'succeeded', now(), :cutoff, 'test-insights', 'manual', :owner, :start)"""),
            {"id": self.run_id, "cutoff": cutoff, "owner": self.user.id, "start": cutoff - timedelta(days=30)})
        for owner, value in ((self.user.id, 2), (uuid.uuid4(), 999)):
            self.db.execute(text("""INSERT INTO analytics.indicadores_personales
                (etl_run_id,user_id,indicator_code,value,definition_version,provenance)
                VALUES (:id,:owner,'L02',:value,'test-insights','unclassified')"""),
                {"id": self.run_id, "owner": owner, "value": value})
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.ready = patch("app.modules.analytics.insights_router.provider_ready", return_value=True)
        self.ready.start()

    def tearDown(self):
        self.ready.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_personal_isolation_and_provenance(self):
        response = self.client.get("/api/analytics/me/insights")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["evidence"]["metrics"]["L02"]["value"], 2)
        self.assertNotIn("999", response.text)
        self.assertNotIn("owner_user_id", response.text)
        self.assertEqual(self.client.get("/api/analytics/me/insights?provenance=operational").json()["status"], "no_data")
        self.assertEqual(self.client.post("/api/analytics/me/interpretation", json={"user_id": str(uuid.uuid4())}).status_code, 422)

    def test_manual_activity_days_are_distinct_local_dates(self):
        work_id = uuid.uuid4()
        self.db.execute(text("INSERT INTO analytics.catalogo_obras (etl_run_id, work_id, title) VALUES (:run,:work,'Activity days test')"),
                        {"run": self.run_id, "work": work_id})
        for day, kind, previous, page in ((1, "start", 0, 0), (2, "progress", 0, 5), (3, "correction", 5, 2)):
            self.db.execute(text("""INSERT INTO analytics.hechos_lectura
                (etl_run_id,source_id,user_id,work_id,edition_id,event_kind,occurred_at,previous_page,page,total_pages,provenance)
                VALUES (:run,:id,:owner,:work,:edition,:kind,:at,:previous,:page,10,'unclassified')"""),
                {"run": self.run_id, "id": uuid.uuid4(), "owner": self.user.id, "work": work_id,
                 "edition": uuid.uuid4(), "kind": kind, "at": datetime.now(timezone.utc) - timedelta(days=day),
                 "previous": previous, "page": page})
        self.db.execute(text("""INSERT INTO analytics.indicadores_personales
            (etl_run_id,user_id,indicator_code,value,definition_version,provenance)
            VALUES (:id,:owner,'L09',1,'test-insights','unclassified')"""), {"id": self.run_id, "owner": self.user.id})
        result = self.client.get("/api/analytics/me/insights").json()
        self.assertEqual(result["evidence"]["metrics"]["L09"]["value"], 2)

    def test_admin_label_and_permission_do_not_grant_group_access(self):
        self.user.role = "admin"
        self.db.add(AccountPermission(user_id=self.user.id, permission="admin"))
        self.db.flush()
        self.assertFalse(self.client.get("/api/analytics/access").json()["group"])
        self.assertEqual(self.client.get("/api/analytics/group/insights").status_code, 403)
        self.assertEqual(self.client.post("/api/analytics/group/interpretation", json={}).status_code, 403)

    def test_author_capability_and_organization_membership_grant_access(self):
        self.db.add(ProfileCapability(profile_id=self.profile.id, capability="autor"))
        self.db.flush()
        self.assertTrue(group_access(self.db, self.user.id))
        self.db.delete(self.db.get(ProfileCapability, (self.profile.id, "autor")))
        self.db.flush()
        for kind in ("editorial", "libreria"):
            organization = Profile(kind="organization", organization_type=kind, display_name="Test professional")
            self.db.add(organization)
            self.db.flush()
            self.db.add(ProfileMember(profile_id=organization.id, user_id=self.user.id, permission="editor"))
            self.db.flush()
            self.assertTrue(group_access(self.db, self.user.id))
            organization.verification_status = "suspended"
            self.db.flush()
        self.assertFalse(group_access(self.db, self.user.id))

    def test_generation_is_cached_and_invalid_output_is_not_saved(self):
        with patch("app.modules.analytics.insights.provider_ready", return_value=True), patch("app.modules.analytics.insights.generate_interpretation", return_value=narrative()) as provider:
            first = self.client.post("/api/analytics/me/interpretation", json={})
            second = self.client.post("/api/analytics/me/interpretation", json={})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        provider.assert_called_once()
        evidence = provider.call_args.args[0]
        self.assertNotIn(str(self.user.id), json.dumps(evidence))
        self.assertEqual(self.client.get("/api/analytics/me/insights").json()["interpretation"]["id"], first.json()["id"])

    def test_provider_unavailable_has_no_fabricated_interpretation(self):
        with patch("app.modules.analytics.insights.provider_ready", return_value=False):
            response = self.client.post("/api/analytics/me/interpretation", json={})
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(self.client.get("/api/analytics/me/insights").json()["interpretation"])

    def test_bad_response_is_rejected_without_saving(self):
        with patch("app.modules.analytics.insights.provider_ready", return_value=True), patch("app.modules.analytics.insights.generate_interpretation", side_effect=ProviderError("test")):
            response = self.client.post("/api/analytics/me/interpretation", json={})
        self.assertEqual(response.status_code, 502)
        count = self.db.execute(text("SELECT count(*) FROM analytics.interpretaciones_ia WHERE owner_user_id=:id"), {"id": self.user.id}).scalar_one()
        self.assertEqual(count, 0)

    def test_daily_group_release_is_fixed_and_contains_only_aggregates(self):
        events = [{"user_id": uuid.uuid4(), "event_kind": "start"} for _ in range(12)]
        source = {"latest_id": self.run_id, "period": {"start": "test", "cutoff": "test", "source": "manual"}}
        with patch("app.modules.analytics.insights.source_runs", return_value=([self.run_id], source)), patch("app.modules.analytics.insights.facts", return_value=(events, [])):
            first = group_evidence(self.db, "operational")
        with patch("app.modules.analytics.insights.source_runs") as extractor:
            second = group_evidence(self.db, "operational")
        self.assertEqual(first, second)
        extractor.assert_not_called()
        for event in events:
            self.assertNotIn(str(event["user_id"]), json.dumps(first))

    def test_demo_cohort_is_repeatable(self):
        self.assertEqual(seed_group(self.db, "test-password"), seed_group(self.db, "test-password"))
