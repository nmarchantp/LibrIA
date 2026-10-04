"""La migración y sus rutas se prueban dentro de una transacción revertida."""

import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.users.identities import create_personal_profile
from app.modules.users.identity_models import AccountPermission, Profile, ProfileCapability
from app.modules.users.models import User


class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        migration_path = Path(__file__).parents[1] / "migrations/versions/0010_profile_identities.py"
        spec = importlib.util.spec_from_file_location("identity_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        if not inspect(self.connection).has_table("perfiles", schema="app"):
            with Operations.context(MigrationContext.configure(self.connection)):
                migration.upgrade()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.admin = self.person("Administrador")
        self.owner = self.person("Responsable")
        self.outsider = self.person("Otra persona")
        self.db.add(AccountPermission(user_id=self.admin.id, permission="admin"))
        self.db.flush()
        self.actor = self.admin
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.actor
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def person(self, name):
        user = User(display_name=name, role="lector")
        self.db.add(user)
        self.db.flush()
        create_personal_profile(self.db, user)
        self.db.flush()
        return user

    def organization(self):
        response = self.client.post("/api/profiles/organizations", json={
            "display_name": "Organización de prueba", "administrator_user_id": str(self.owner.id)})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def test_capabilities_are_multiple_and_verification_does_not_grant_admin(self):
        profile = self.db.scalar(select(Profile).where(Profile.owner_user_id == self.owner.id))
        profile.verification_status = "verified"
        self.db.add(ProfileCapability(profile_id=profile.id, capability="autor"))
        self.db.flush()
        self.actor = self.owner
        response = self.client.get("/api/profiles/me")
        self.assertEqual(response.json()[0]["capabilities"], ["autor", "lector"])
        self.assertEqual(self.client.post("/api/profiles/organizations", json={
            "display_name": "Sin permiso", "administrator_user_id": str(self.owner.id)}).status_code, 403)

    def test_organization_members_require_membership_even_for_system_admin(self):
        organization = self.organization()
        url = f"/api/profiles/{organization}/members/{self.outsider.id}"
        self.assertEqual(self.client.put(url, json={"permission": "editor"}).status_code, 403)
        self.actor = self.owner
        self.assertEqual(self.client.put(url, json={"permission": "editor"}).status_code, 200)
        self.actor = self.outsider
        self.assertEqual(len(self.client.get("/api/profiles/me").json()), 2)
        self.assertEqual(self.client.put(url, json={"permission": "admin"}).status_code, 403)

    def test_last_administrator_cannot_be_demoted(self):
        organization = self.organization()
        self.actor = self.owner
        url = f"/api/profiles/{organization}/members/{self.owner.id}"
        self.assertEqual(self.client.put(url, json={"permission": "editor"}).status_code, 409)

    def test_personal_profiles_cannot_have_members(self):
        profile = self.db.scalar(select(Profile).where(Profile.owner_user_id == self.owner.id))
        self.actor = self.owner
        self.assertEqual(self.client.put(f"/api/profiles/{profile.id}/members/{self.outsider.id}",
                                         json={"permission": "editor"}).status_code, 422)
