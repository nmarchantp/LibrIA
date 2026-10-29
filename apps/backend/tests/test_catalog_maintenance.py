"""Real administrator HTTP edits on the validator-owned PostgreSQL only."""
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.books.catalog_models import CatalogOperation, CatalogOperationEffect
from app.modules.books.models import CatalogSource
from app.modules.users.identity_models import AccountPermission
from tests import test_catalog_phase3 as phase3


class CatalogMaintenanceHTTP(unittest.TestCase):
    setUpClass = classmethod(phase3.Phase3HTTP.setUpClass.__func__)
    tearDownClass = classmethod(phase3.Phase3HTTP.tearDownClass.__func__)
    new_actor = phase3.Phase3HTTP.new_actor

    def setUp(self):
        phase3.Phase3HTTP.setUp(self)
        for flag in ("catalog_admin_preview_enabled", "catalog_editionless_enabled", "catalog_canonical_enabled"):
            change = patch.object(get_settings(), flag, True)
            change.start()
            self.addCleanup(change.stop)
        with Session(self.engine) as db, db.begin():
            db.add(AccountPermission(user_id=uuid.UUID(self.actor), permission="admin"))

    def write(self, path, data, key=None, actor=None, method="POST"):
        return self.client.request(method, "/api/admin/catalog" + path, json=data,
            headers={"Idempotency-Key": key or str(uuid.uuid4()), "X-Test-Actor": actor or self.actor})

    def create(self):
        data = {"title": "Mantenedor " + uuid.uuid4().hex, "authors": ["Autora del catálogo"],
                "description": "Sinopsis corregida", "categories": ["Novela"], "reason": "Registro administrativo"}
        response = self.write("/works", data)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def edition(self, work, **changes):
        data = {"title": work["title"] + " (NE)", "isbn": phase3.unique_isbn(), "language": "es",
                "page_count": 210, "publisher_name": "Editorial de prueba", "publication_date": "2020-02-29",
                "cover_url": "https://example.invalid/cover.jpg", "expected_version": work["version"],
                "reason": "Añadir edición verificada", **changes}
        return self.write(f'/works/{work["id"]}/editions', data)

    def test_create_edit_edition_and_replay_are_audited_and_public(self):
        work = self.create()
        response = self.edition(work)
        self.assertEqual(response.status_code, 200, response.text)
        current = response.json()
        self.assertEqual(current["edition_count"], 1)
        edition = current["editions"][0]
        key = str(uuid.uuid4())
        data = {"title": "Título de edición corregido", "isbn": edition["isbn13"], "language": "es",
                "page_count": 320, "expected_version": current["version"], "reason": "Corregir datos de edición"}
        path = f'/works/{work["id"]}/editions/{edition["id"]}'
        saved = self.write(path, data, key, method="PATCH")
        self.assertEqual(saved.status_code, 200, saved.text)
        replay = self.write(path, data, key, method="PATCH")
        self.assertEqual(replay.json(), saved.json())
        public = self.client.get('/api/books/' + edition["id"])
        self.assertEqual(public.status_code, 200, public.text)
        self.assertEqual(public.json()["volumeInfo"]["title"], data["title"])
        self.assertEqual(public.json()["volumeInfo"]["pageCount"], 320)
        self.assertEqual(public.json()["volumeInfo"]["imageLinks"], {})
        with Session(self.engine) as db:
            operations = db.scalars(select(CatalogOperation).where(CatalogOperation.target_work_id == uuid.UUID(work["id"]))).all()
            self.assertEqual(len(operations), 3)
            self.assertTrue(all(operation.context.get("result") for operation in operations))
            effects = db.scalars(select(CatalogOperationEffect).where(CatalogOperationEffect.operation_id.in_([row.id for row in operations]))).all()
            self.assertTrue(any(row.entity_table == 'app.ediciones' and row.before_state for row in effects))

    def test_stale_versions_invalid_isbn_and_duplicate_isbn_do_not_write(self):
        work = self.create()
        added = self.edition(work)
        self.assertEqual(added.status_code, 200, added.text)
        self.assertEqual(self.edition(work).status_code, 409)
        current = added.json()
        self.assertEqual(self.edition(current, isbn="9780306406158").status_code, 422)
        other = self.create()
        conflict = self.edition(other, isbn=current["editions"][0]["isbn13"])
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(self.client.get('/api/admin/catalog/works/' + other["id"]).json()["edition_count"], 0)

    def test_permissions_validation_and_foreign_edition(self):
        reader = self.new_actor()
        response = self.client.get('/api/admin/catalog/inventory', headers={"X-Test-Actor": reader})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.write('/works', {"title": "Test", "reason": "Test"}, actor=reader).status_code, 403)
        work = self.create()
        self.assertEqual(self.edition(work, publication_date="2023-02-29").status_code, 422)
        self.assertEqual(self.edition(work, cover_url="javascript:alert(1)").status_code, 422)
        other = self.create()
        added = self.edition(other).json()
        response = self.write(f'/works/{work["id"]}/editions/{added["editions"][0]["id"]}',
            {"title": "Foreign", "expected_version": work["version"], "reason": "No cambiar otra obra"}, method="PATCH")
        self.assertEqual(response.status_code, 404, response.text)

    def test_manual_creation_rejects_a_duplicate_work(self):
        work = self.create()
        response = self.write('/works', {"title": work["title"] + " (NE)", "authors": work["authors"], "reason": "Otra presentación"})
        self.assertEqual(response.status_code, 409, response.text)
        result = self.client.get('/api/admin/catalog/inventory', params={"q": work["title"]}).json()
        self.assertEqual(result["total"], 1)

    def test_inventory_search_by_author_isbn_and_pagination(self):
        work = self.create()
        current = self.edition(work).json()
        isbn = current["editions"][0]["isbn13"]
        for query in (work["title"], isbn):
            response = self.client.get('/api/admin/catalog/inventory', params={"q": query})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual([row["id"] for row in response.json()["items"]], [work["id"]])
        response = self.client.get('/api/admin/catalog/inventory', params={"q": "Autora del catalogo", "limit": 1})
        self.assertGreaterEqual(response.json()["total"], 1)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(self.client.get('/api/admin/catalog/inventory', params={"limit": 101}).status_code, 422)

    def test_editorial_correction_does_not_rewrite_provider_evidence(self):
        work = self.create()
        current = self.edition(work).json()
        edition_id = uuid.UUID(current["editions"][0]["id"])
        snapshot = {"id": "provider-" + uuid.uuid4().hex, "volumeInfo": {"title": "Ficha original", "authors": ["Autor original"]}}
        with Session(self.engine) as db, db.begin():
            db.add(CatalogSource(edition_id=edition_id, provider="google-books", external_id=snapshot["id"],
                                fetched_at=datetime.now(timezone.utc), payload=snapshot))
        current = self.client.get('/api/admin/catalog/works/' + work["id"]).json()
        data = {"title": "Nombre corregido " + uuid.uuid4().hex, "authors": ["Autora corregida"],
                "expected_version": current["version"], "reason": "Corregir autor y título"}
        response = self.write('/works/' + work["id"], data, method="PATCH")
        self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            source = db.scalar(select(CatalogSource).where(CatalogSource.external_id == snapshot["id"]))
            self.assertEqual(source.payload, snapshot)
        public = self.client.get('/api/books/' + snapshot["id"])
        self.assertEqual(public.json()["volumeInfo"]["authors"], ["Autora corregida"])
