"""Transactional PostgreSQL checks; all created accounts roll back after each test."""
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.core.config import get_settings
from app.main import app
from app.modules.users.identity_models import AccountPermission
from app.modules.users.models import User
from app.modules.users.preference_models import FavoriteGenre, FavoriteTrope, Genre, Trope


class LiteraryPreferencesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if get_settings().app_env not in {"development", "test"}:
            raise unittest.SkipTest("Las pruebas transaccionales solo se ejecutan en desarrollo/prueba")

    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, raise_server_exceptions=False)
        self.owner = self.register()
        self.other = self.register()
        self.headers = self.auth(self.owner)
        self.path = "/api/profiles/me/literary-preferences"

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def register(self):
        response = self.client.post("/api/auth/register", json={"email": f"{uuid.uuid4()}@example.com",
            "password": "test-password", "display_name": "Lector de prueba"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    @staticmethod
    def auth(account):
        return {"Authorization": f"Bearer {account['access_token']}"}

    def save(self, payload):
        return self.client.patch(self.path, headers=self.headers, json=payload)

    def mine(self):
        r = self.client.get(self.path, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_expanded_genres_keep_identity_and_five_selection_limit(self):
        import importlib.util
        from pathlib import Path
        import unicodedata
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        spec = importlib.util.spec_from_file_location('genres_migration', Path('migrations/versions/0045_genre_catalog_groups.py'))
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        catalog = self.client.get('/api/profiles/preference-catalogs', headers=self.headers).json()['genres']
        self.assertEqual(len({x['group'] for x in catalog}), 10)
        normalize = lambda name: unicodedata.normalize('NFC', name).casefold()
        self.assertEqual(len(catalog), len({normalize(x['name']) for x in catalog}))
        expected = {normalize(name) for values in migration.GROUPS.values() for _, name in values}
        self.assertTrue(expected <= {normalize(x['name']) for x in catalog})
        ids = ['fantasia', 'romantasy', 'cyberpunk', 'dark-romance', 'manga']
        self.assertEqual(self.save({'genre_ids': ids}).status_code, 200)
        self.assertEqual(self.save({'genre_ids': ids + ['romance']}).status_code, 422)
        self.db.close()
        before = self.connection.execute(select(Genre.id, Genre.name, Genre.active).order_by(Genre.id)).all()
        picks = self.connection.execute(select(FavoriteGenre.user_id, FavoriteGenre.genre_id, FavoriteGenre.position)).all()
        with Operations.context(MigrationContext.configure(self.connection)):
            migration.downgrade()
            migration.upgrade()
        self.assertEqual(before, self.connection.execute(select(Genre.id, Genre.name, Genre.active).order_by(Genre.id)).all())
        self.assertEqual(picks, self.connection.execute(select(FavoriteGenre.user_id, FavoriteGenre.genre_id, FavoriteGenre.position)).all())

    def test_catalogs_separate_and_new_accounts_empty(self):
        response = self.client.get("/api/profiles/preference-catalogs", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertGreaterEqual(len(data["genres"]), 6)
        self.assertIn("magia", {x["id"] for x in data["tropes"]})
        self.assertNotIn("magia", {x["id"] for x in data["genres"]})
        self.assertEqual(self.mine()["genres"], [])
        self.assertEqual(self.mine()["tropes"], [])

    def test_round_trip_public_projection_and_no_private_fields(self):
        r = self.save({"biography": "Entre libros", "genre_ids": ["fantasia", "romance"], "trope_ids": ["magia", "dragones"]})
        self.assertEqual(r.status_code, 200, r.text)
        mine = self.mine()
        # Force expiration to verify persisted DB state, not just an ORM response.
        self.db.expire_all()
        self.assertEqual(self.mine()["biography"], "Entre libros")
        public = self.client.get(f"/api/profiles/{mine['profile_id']}", headers=self.auth(self.other))
        self.assertEqual(public.status_code, 200, public.text)
        self.assertEqual(set(public.json()), {"id", "display_name", "avatar_url", "biography", "genres", "tropes", "intensities", "interests", "featured_category_id"})
        self.assertEqual(public.json()["genres"], mine["genres"])
        self.assertEqual(public.json()["tropes"], mine["tropes"])
        self.assertNotEqual(mine["profile_id"], self.owner["user"]["id"])

    def test_sixth_genre_duplicate_and_cross_catalog_rejected_atomically(self):
        self.save({"biography": "Original", "genre_ids": ["fantasia"], "trope_ids": ["magia"]})
        before = self.mine()
        for payload in (
            {"genre_ids": ["fantasia", "romance", "ciencia-ficcion", "misterio", "thriller", "terror"]},
            {"genre_ids": ["fantasia", "fantasia"]}, {"trope_ids": ["magia", "magia"]},
            {"biography": "No debe guardarse", "genre_ids": ["magia"]},
            {"genre_ids": ["romance"], "trope_ids": ["fantasia"]},
            {"trope_ids": ["no-existe"]}, {"genre_ids": None}, {"trope_ids": None},
        ):
            r = self.save(payload)
            self.assertEqual(r.status_code, 422, r.text)
            self.assertEqual(self.mine(), before)

    def test_omission_empty_null_and_maximum_biography(self):
        self.assertEqual(self.save({"biography": "x" * 70, "genre_ids": ["fantasia"], "trope_ids": ["magia"]}).status_code, 200)
        self.assertEqual(self.save({"biography": "x" * 71}).status_code, 422)
        self.save({"genre_ids": []})
        data = self.mine()
        self.assertEqual(data["genres"], [])
        self.assertEqual([x["id"] for x in data["tropes"]], ["magia"])
        self.assertEqual(data["biography"], "x" * 70)
        self.assertEqual(self.save({}).json(), data)
        self.save({"biography": None, "trope_ids": []})
        self.assertIsNone(self.mine()["biography"])
        self.assertEqual(self.mine()["tropes"], [])
        self.save({"biography": "  "})
        self.assertIsNone(self.mine()["biography"])

    def test_owner_from_session_and_other_account_untouched(self):
        for field in ("user_id", "owner_user_id", "profile_id"):
            self.assertEqual(self.save({field: self.other["user"]["id"], "biography": "No"}).status_code, 422)
        self.save({"biography": "Solo yo", "trope_ids": ["vampiros"]})
        other = self.client.get(self.path, headers=self.auth(self.other)).json()
        self.assertIsNone(other["biography"])
        self.assertEqual(other["tropes"], [])
        profile_id = self.mine()["profile_id"]
        self.assertEqual(self.client.patch(f"/api/profiles/{profile_id}", headers=self.auth(self.other), json={"biography": "No"}).status_code, 405)

    def test_all_endpoints_require_authentication(self):
        for path in (self.path, "/api/profiles/preference-catalogs", f"/api/profiles/{uuid.uuid4()}"):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.patch(self.path, json={"biography": "No"}).status_code, 401)
        self.assertEqual(self.client.get(f"/api/profiles/{uuid.uuid4()}", headers=self.headers).status_code, 404)

    def test_admin_biography_workflow_requires_reason_and_seventy_characters(self):
        admin_id = uuid.UUID(self.other["user"]["id"])
        self.db.get(User, admin_id).role = "admin"
        self.db.add(AccountPermission(user_id=admin_id, permission="admin"))
        self.db.commit()
        biography = "a" * 70
        r = self.client.patch(f"/api/roles/profiles/{self.owner['user']['id']}", headers=self.auth(self.other),
            json={"display_name": "Nombre administrativo", "biography": biography, "reason": "Corrección administrativa solicitada"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.mine()["biography"], biography)
        # Saving only tastes must preserve the existing longer administrator biography.
        self.save({"genre_ids": ["romance"]})
        self.assertEqual(self.mine()["biography"], biography)

    def test_database_rejects_sixth_slot_and_duplicate_trope(self):
        owner_id = uuid.UUID(self.owner["user"]["id"])
        genres = list(self.db.scalars(select(Genre.id).order_by(Genre.sort_order).limit(6)))
        self.assertEqual(self.save({"genre_ids": genres[:5]}).status_code, 200)
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.add(FavoriteGenre(user_id=owner_id, genre_id=genres[5], position=6))
            self.db.flush()
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.add(FavoriteGenre(user_id=owner_id, genre_id=genres[5], position=1))
            self.db.flush()
        self.save({"trope_ids": ["magia"]})
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.add(FavoriteTrope(user_id=owner_id, trope_id="magia"))
            self.db.flush()

    def test_commit_failure_rolls_back_whole_patch(self):
        self.save({"biography": "Antes", "genre_ids": ["fantasia"], "trope_ids": ["magia"]})
        before = self.mine()
        with patch.object(self.db, "commit", side_effect=RuntimeError("forced test failure")):
            self.assertEqual(self.save({"biography": "Después", "genre_ids": [], "trope_ids": []}).status_code, 500)
        self.assertEqual(self.mine(), before)

    def test_inactive_catalog_options_cannot_be_newly_selected(self):
        self.save({"trope_ids": ["magia"]})
        self.db.get(Trope, "magia").active = False
        self.db.get(Genre, "fantasia").active = False
        self.db.commit()
        self.assertEqual(self.save({"trope_ids": ["magia"]}).status_code, 200)
        self.assertEqual(self.save({"genre_ids": ["fantasia"]}).status_code, 422)
        self.assertEqual(self.save({"trope_ids": []}).status_code, 200)
        self.assertEqual(self.save({"trope_ids": ["magia"]}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
