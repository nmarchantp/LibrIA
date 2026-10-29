"""HTTP, writer inventory, rollback and contention tests in owned disposable PG."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import statistics
import time
from typing import Annotated
import unittest
import uuid
from unittest.mock import patch, Mock

from fastapi import Depends, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
import psycopg

from app.main import app
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import CatalogQuery, CatalogSource, Edition, Work
from app.modules.books.evidence import ExternalReference
from app.modules.books.resolution import incorporate_book as real_incorporate
from app.modules.library.models import Reading
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission
from tests import test_catalog_phase1 as phase1_tests


def volume(title=None, identifier=None, isbn=None):
    return {"id": identifier or "discovery-" + uuid.uuid4().hex, "volumeInfo": {
        "title": title or "Discovery " + uuid.uuid4().hex, "authors": ["Discovery Author"],
        "language": "es", "pageCount": 123, "description": "Server synopsis", "publisher": "Server publisher",
        "industryIdentifiers": [{"type": "ISBN_13", "identifier": isbn}] if isbn else []}}


def unique_isbn():
    base = "978" + str(uuid.uuid4().int % 10**9).zfill(9)
    return base + str(-sum(int(c)*(1 if i % 2 == 0 else 3) for i, c in enumerate(base)) % 10)


class Phase3Policy(unittest.TestCase):
    def test_rollout_default_off_and_bundle_can_be_validated_without_other_features(self):
        self.assertFalse(Settings(_env_file=None).catalog_discovery_enabled)
        settings = Settings(_env_file=None, catalog_discovery_enabled=True)
        self.assertFalse(settings.catalog_admin_merge_enabled)
        self.assertFalse(settings.catalog_editionless_enabled)

    def test_scripts_delegate_before_legacy_writes(self):
        with patch.object(get_settings(), "catalog_discovery_enabled", True):
            for module in ("run_catalog_ingest", "load_popular_spanish_books", "load_popular_chile_books", "load_popular_argentina_books"):
                with self.subTest(module=module), patch("scripts.import_catalog.main", return_value="authorized") as replacement:
                    self.assertEqual(importlib.import_module("scripts." + module).main(), "authorized")
                    replacement.assert_called_once()

    def test_synthetic_catalog_seed_refuses_non_owned_database(self):
        from app.modules.books.policy import require_disposable_fixture
        with patch.dict("os.environ", {"CATALOG_PHASE1_DISPOSABLE_MARKER": ""}):
            with self.assertRaises(RuntimeError):
                require_disposable_fixture(Mock())

    def test_cli_requires_explicit_admin_reason_and_idempotency_prefix(self):
        from scripts.import_catalog import main
        with patch("sys.argv", ["import_catalog"]), self.assertRaises(SystemExit) as result:
            main()
        self.assertEqual(result.exception.code, 2)


class Phase3HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        phase1_tests.Phase1Postgres.setUpClass.__func__(cls)
        cls.engine = create_engine(cls.url.replace("postgresql://", "postgresql+psycopg://", 1), pool_size=8, max_overflow=8)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        enrichment = patch("app.modules.books.edition_discovery.discover_editions", return_value=())
        enrichment.start()
        self.addCleanup(enrichment.stop)
        self.flag = patch.object(get_settings(), "catalog_discovery_enabled", True)
        self.flag.start()
        self.addCleanup(self.flag.stop)
        self.actor = self.new_actor()
        self.sessions = []
        def database():
            with Session(self.engine) as db:
                self.sessions.append(db)
                yield db
        def authenticated(request: Request, db: Annotated[Session, Depends(get_db)]):
            return db.get(User, uuid.UUID(request.headers.get("X-Test-Actor", self.actor)))
        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user] = authenticated
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(app.dependency_overrides.clear)

    def new_actor(self, admin=False):
        with Session(self.engine) as db, db.begin():
            user = User(display_name="Discovery synthetic", role="lector")
            db.add(user)
            db.flush()
            if admin:
                db.add(AccountPermission(user_id=user.id, permission="admin"))
            return str(user.id)

    def counts(self):
        with self.engine.connect() as conn:
            return {table: conn.scalar(text("SELECT count(*) FROM app." + table)) for table in
                ("obras", "ediciones", "autores", "obras_autores", "fuentes_catalogo")}

    def payload(self, item, **updates):
        data = {"book_ref": item["id"], "book_title": "Untrusted client title", "page_count": 999,
            "edition_selected": True, "external_reference": {"provider": "google-books", "reference_type": "volume", "external_id": item["id"]}}
        return {**data, **updates}

    def add(self, item, key=None, actor=None, **updates):
        return self.client.post("/api/readings/library", json=self.payload(item, **updates),
            headers={"Idempotency-Key": key or str(uuid.uuid4()), "X-Test-Actor": actor or self.actor})

    def test_google_search_and_detail_do_not_change_definitive_counts(self):
        item, before = volume(), self.counts()
        with patch("app.modules.books.discovery.google_request", return_value={"items": [item]}):
            response = self.client.get("/api/books", params={"q": item["volumeInfo"]["title"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["items"][0]["libria"].get("workId"))
        with patch("app.modules.books.discovery.google_request", return_value=item):
            detail = self.client.get("/api/books/" + item["id"])
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(self.counts(), before)

    def test_open_library_search_and_detail_do_not_import(self):
        item = volume(identifier="openlibrary:OL" + str(uuid.uuid4().int % 10**12) + "M")
        item["openLibrary"] = {"editionKey": item["id"].split(":")[1], "workKey": "OL88001W"}
        before = self.counts()
        with patch("app.modules.books.discovery.open_library.search", return_value={"items": [item]}):
            result = self.client.get("/api/books", params={"q": item["volumeInfo"]["title"], "provider": "open_library"})
        with patch("app.modules.books.discovery.open_library.detail", return_value=item):
            detail = self.client.get("/api/books/" + item["id"])
        self.assertEqual((result.status_code, detail.status_code), (200, 200))
        self.assertEqual(self.counts(), before)

    def test_search_detail_add_reload_and_reading_work_without_prior_import(self):
        item, before = volume(), self.counts()
        with patch("app.modules.books.discovery.google_request", return_value={"items": [item]}):
            self.assertEqual(self.client.get("/api/books", params={"q": item["volumeInfo"]["title"]}).status_code, 200)
        with patch("app.modules.books.discovery.google_request", return_value=item):
            self.assertEqual(self.client.get("/api/books/" + item["id"]).status_code, 200)
        self.assertEqual(self.counts(), before)
        with patch("app.modules.books.evidence.google_request", return_value=item):
            added = self.add(item)
        self.assertEqual(added.status_code, 200, added.text)
        state = added.json()
        self.assertEqual(state["book_title"], item["volumeInfo"]["title"])
        self.assertIsNone(state["total_pages"])
        after = self.counts()
        self.assertEqual(after["obras"], before["obras"] + 1)
        self.assertEqual(after["ediciones"], before["ediciones"] + 1)
        library = self.client.get("/api/readings/me").json()
        self.assertEqual(len(library), 1)
        self.assertEqual(library[0]["edition_id"], state["edition_id"])
        self.assertIn(item["id"], library[0]["catalog_volume"]["libria"]["externalAliases"])
        detail = self.client.get("/api/books/" + state["work_id"])
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["volumeInfo"]["title"], item["volumeInfo"]["title"])
        event = self.client.post("/api/readings/events", json={"book_ref": state["work_id"], "book_title": state["book_title"],
            "edition_id": state["edition_id"], "page_count": 123, "event": "start"})
        self.assertEqual(event.status_code, 201, event.text)
        self.assertEqual(self.counts(), after)

    def test_replay_is_idempotent_without_provider_and_without_metadata_evidence(self):
        item, key = volume(), str(uuid.uuid4())
        with patch("app.modules.books.evidence.google_request", return_value=item) as provider:
            a = self.add(item, key=key)
        self.assertEqual(a.status_code, 200, a.text)
        before = self.counts()
        with patch("app.modules.books.evidence.google_request", side_effect=AssertionError("No provider on replay")):
            b = self.add(item, key=key, book_title="Changed display title", page_count=50)
        self.assertEqual(b.status_code, 200, b.text)
        self.assertEqual(a.json()["reading_id"], b.json()["reading_id"])
        self.assertEqual(self.counts(), before)

    def test_existing_uuid_and_legacy_external_reference_reuse_record(self):
        item = volume()
        with patch("app.modules.books.evidence.google_request", return_value=item):
            state = self.add(item).json()
        before = self.counts()
        other_actor = self.new_actor()
        result = self.client.post("/api/readings/library", json={"book_ref": state["work_id"], "book_title": "ignored",
            "edition_id": state["edition_id"]}, headers={"X-Test-Actor": other_actor})
        self.assertEqual(result.status_code, 200, result.text)
        legacy = self.client.post("/api/readings/library", json={"book_ref": item["id"], "book_title": "ignored"})
        self.assertEqual(legacy.status_code, 200, legacy.text)
        self.assertEqual(self.counts(), before)

    def test_historical_external_source_is_accessible_without_provider_or_metadata_rewrite(self):
        # The phase-1 fixture is an existing publication, not provider evidence to reimport.
        with self.engine.connect() as conn:
            source_ref = conn.scalar(text("SELECT external_id FROM app.fuentes_catalogo WHERE provider='google-books' AND edition_id=:id"), {"id": self.ids["edition"]})
        before = self.counts()
        with patch("app.modules.books.evidence.google_request", side_effect=AssertionError("Use stored identity")), patch("app.modules.books.discovery.google_request", side_effect=AssertionError("Use stored identity")):
            detail = self.client.get("/api/books/" + source_ref)
            result = self.client.post("/api/readings/library", json={"book_ref": source_ref, "book_title": "Untrusted replacement"})
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["edition_id"], self.ids["edition"])
        self.assertEqual(self.counts(), before)

    def test_fake_internal_identity_in_provider_cache_never_becomes_catalog_identity(self):
        item = volume()
        item["libria"] = {"workId": self.ids["work"], "editionId": self.ids["edition"]}
        before = self.counts()
        with patch("app.modules.books.discovery.google_request", return_value={"items": [item]}):
            result = self.client.get("/api/books", params={"q": item["volumeInfo"]["title"]})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn("workId", result.json()["items"][0]["libria"])
        self.assertEqual(self.counts(), before)

    def test_open_library_result_adds_via_server_detail_not_search_payload(self):
        identifier = "OL" + str(uuid.uuid4().int % 10**12) + "M"
        item = volume(identifier="openlibrary:" + identifier)
        item["openLibrary"] = {"editionKey": identifier, "workKey": "OL" + str(uuid.uuid4().int % 10**12) + "W"}
        payload = self.payload(item, external_reference={"provider": "open-library", "reference_type": "edition", "external_id": identifier})
        with patch("app.modules.books.evidence.open_library.detail", return_value=item):
            result = self.client.post("/api/readings/library", json=payload)
        self.assertEqual(result.status_code, 200, result.text)

    def test_isbn_conflict_is_409_without_partial_incorporation(self):
        isbn = unique_isbn()
        first = volume(isbn=isbn)
        with patch("app.modules.books.evidence.google_request", return_value=first):
            self.assertEqual(self.add(first).status_code, 200)
        second = volume(isbn=isbn)
        second["volumeInfo"]["authors"] = ["Conflicting Author"]
        before = self.counts()
        with patch("app.modules.books.evidence.google_request", return_value=second):
            result = self.add(second)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self.counts(), before)

    def test_same_title_author_different_provider_reuses_work(self):
        first = volume()
        second = volume(title=first["volumeInfo"]["title"], identifier="openlibrary:OL" + str(uuid.uuid4().int % 10**12) + "M")
        second["openLibrary"] = {"editionKey": second["id"].split(":")[1], "workKey": "OL" + str(uuid.uuid4().int % 10**12) + "W"}
        with patch("app.modules.books.evidence.google_request", return_value=first):
            a = self.add(first)
        with patch("app.modules.books.evidence.open_library.detail", return_value=second):
            b = self.add(second, actor=self.new_actor(), external_reference={"provider": "open-library", "reference_type": "edition", "external_id": second["openLibrary"]["editionKey"]})
        self.assertEqual((a.status_code, b.status_code), (200, 200), b.text)
        self.assertEqual(a.json()["work_id"], b.json()["work_id"])

    def test_cache_is_discovery_only_and_represented_from_current_catalog(self):
        item = volume()
        with patch("app.modules.books.discovery.google_request", return_value={"items": [item]}):
            self.client.get("/api/books", params={"q": item["volumeInfo"]["title"]})
        with self.engine.connect() as conn:
            cached = conn.scalar(text("SELECT payload FROM app.consultas_catalogo WHERE query LIKE :key"), {"key": "discovery-v1:all:"+item["volumeInfo"]["title"].casefold()+":%"})
        self.assertNotIn("workId", cached["items"][0].get("libria", {}))
        with patch("app.modules.books.evidence.google_request", return_value=item):
            added = self.add(item)
        with patch("app.modules.books.discovery.google_request", side_effect=AssertionError("Use discovery cache")):
            found = self.client.get("/api/books", params={"q": item["volumeInfo"]["title"]})
        self.assertEqual(found.status_code, 200, found.text)
        self.assertEqual([row["id"] for row in found.json()["items"]], [added.json()["work_id"]])

    def test_provider_failure_leaves_no_partial_catalog_or_operation(self):
        item, before = volume(), self.counts()
        with patch("app.modules.books.evidence.google_request", side_effect=HTTPException(502, "unavailable")):
            result = self.add(item)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(self.counts(), before)

    def test_remote_calls_do_not_hold_request_database_transactions(self):
        item = volume()
        def provider(*args, **kwargs):
            self.assertFalse(any(session.in_transaction() for session in self.sessions))
            return item
        with patch("app.modules.books.evidence.google_request", side_effect=provider):
            result = self.add(item)
        self.assertEqual(result.status_code, 200, result.text)

    def test_unknown_reading_start_cannot_bypass_incorporation(self):
        before = self.counts()
        response = self.client.post("/api/readings/events", json={"book_ref": "unknown-publication", "book_title": "No import",
            "event": "start", "page_count": 123})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.counts(), before)

    def test_old_writer_helpers_fail_closed_in_new_mode(self):
        from app.modules.books.router import store_volume
        from app.modules.books.open_library_catalog import ensure_edition, store_selected
        from app.modules.books.service import consolidate_equivalent_works
        with Session(self.engine) as db:
            for operation in (lambda: store_volume(db, volume()), lambda: ensure_edition(db, "openlibrary:OL100M"),
                              lambda: store_selected(db, {}), lambda: consolidate_equivalent_works(db, uuid.uuid4(), reviewed=True)):
                with self.assertRaises(HTTPException) as result:
                    operation()
                self.assertEqual(result.exception.status_code, 409)

    def test_admin_import_permission_provenance_and_no_personal_library(self):
        item = volume()
        data = {"reference": {"provider": "google-books", "reference_type": "volume", "external_id": item["id"]}, "reason": "Authorized synthetic batch"}
        with patch("app.modules.books.evidence.google_request", return_value=item) as provider:
            unauthorized = self.client.post("/api/admin/catalog/imports", json=data, headers={"Idempotency-Key": str(uuid.uuid4())})
            self.assertEqual(unauthorized.status_code, 403)
            provider.assert_not_called()
            admin = self.new_actor(admin=True)
            headers = {"Idempotency-Key": str(uuid.uuid4()), "X-Test-Actor": admin}
            authorized = self.client.post("/api/admin/catalog/imports", json=data, headers=headers)
            replay = self.client.post("/api/admin/catalog/imports", json=data, headers=headers)
        self.assertEqual(authorized.status_code, 200, authorized.text)
        self.assertEqual(replay.json(), authorized.json())
        with self.engine.connect() as conn:
            self.assertEqual(conn.scalar(text("SELECT count(*) FROM app.entradas_biblioteca WHERE user_id=:id"), {"id": admin}), 0)
            self.assertEqual(conn.scalar(text("SELECT origin FROM app.incorporaciones_catalogo WHERE id=:id"), {"id": authorized.json()["incorporation_id"]}), "admin_import")

    def test_retry_transient_transaction_once_without_refetching_provider(self):
        item = volume()
        calls = []
        def command(*args):
            calls.append(1)
            if len(calls) == 1:
                raise OperationalError(None, None, psycopg.errors.SerializationFailure("synthetic retry"))
            return real_incorporate(*args)
        with patch("app.modules.books.evidence.google_request", return_value=item) as provider, patch("app.modules.books.facade.incorporate_book", side_effect=command):
            result = self.add(item)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(provider.call_count, 1)

    def test_lock_timeout_returns_retryable_response_without_catalog_writes(self):
        item, before = volume(), self.counts()
        with self.engine.connect() as owner, owner.begin():
            owner.execute(text("SELECT pg_advisory_xact_lock(73155,1)"))
            with patch.object(get_settings(), "catalog_lock_timeout_ms", 50), patch.object(get_settings(), "catalog_write_attempts", 2), patch("app.modules.books.evidence.google_request", return_value=item):
                result = self.add(item)
        self.assertEqual(result.status_code, 503, result.text)
        self.assertEqual(result.headers["Retry-After"], "1")
        self.assertEqual(self.counts(), before)

    def test_concurrent_http_additions_reuse_single_reference(self):
        item = volume()
        actors = [self.new_actor(), self.new_actor()]
        with patch("app.modules.books.evidence.google_request", return_value=item):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda actor: self.add(item, actor=actor), actors))
        self.assertEqual([r.status_code for r in results], [200, 200], [r.text for r in results])
        self.assertEqual(results[0].json()["work_id"], results[1].json()["work_id"])
        self.assertEqual(results[0].json()["edition_id"], results[1].json()["edition_id"])

    def test_z_measure_global_lock_with_concurrent_http_commands(self):
        measurements = []
        for concurrency in (1, 2, 4):
            items = [volume() for _ in range(8)]
            snapshots = {item["id"]: item for item in items}
            def provider(path, **kwargs):
                return snapshots[path.removeprefix("/")]
            def add(item):
                started = time.perf_counter()
                response = self.add(item)
                self.assertEqual(response.status_code, 200, response.text)
                return time.perf_counter() - started
            started = time.perf_counter()
            with patch("app.modules.books.evidence.google_request", side_effect=provider), ThreadPoolExecutor(max_workers=concurrency) as pool:
                durations = list(pool.map(add, items))
            elapsed = time.perf_counter() - started
            measurements.append(dict(concurrency=concurrency, commands=8, elapsed_seconds=round(elapsed, 4),
                throughput_per_second=round(8/elapsed, 2), median_ms=round(statistics.median(durations)*1000, 2), max_ms=round(max(durations)*1000, 2)))
        artifact = Path(__file__).resolve().parents[3] / "docs" / ("catalog-canonical-" + os.environ.get("CATALOG_TEST_PHASE", "phase3") + "-benchmark.json")
        artifact.write_text(json.dumps({"scope": "synthetic_disposable_pg_mocked_providers_global_lock_preserved",
                                       "measurements": measurements}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
