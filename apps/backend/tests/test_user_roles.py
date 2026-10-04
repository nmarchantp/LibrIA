"""Reglas de registro, verificación y publicaciones por tipo de cuenta."""

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.social.models import Post
from app.modules.social.schemas import PostCreate
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission, ProfileCapability
from app.modules.users.identities import personal_profile
from scripts.seed_demo import MANIFEST, seed


class UserRolesTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")

        def test_db():
            yield self.db

        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def register(self, name="Lector de prueba"):
        payload = {"email": f"{uuid.uuid4()}@example.com", "password": "test-password", "display_name": name}
        response = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    @staticmethod
    def auth(session):
        return {"Authorization": f"Bearer {session['access_token']}"}

    def test_every_registration_starts_as_reader_and_cannot_post_freely(self):
        payload = {"email": f"{uuid.uuid4()}@example.com", "password": "test-password", "display_name": "Autor falso"}
        for role in ("autor", "influencer", "libreria", "admin"):
            self.assertEqual(self.client.post("/api/auth/register", json={**payload, "role": role}).status_code, 422)
        reader = self.register()
        self.assertEqual(reader["user"]["role"], "lector")
        self.assertEqual(self.client.post("/api/posts", headers=self.auth(reader),
            json={"source": "community", "kind": "community", "body": "Texto libre"}).status_code, 403)
        self.assertEqual(self.client.post("/api/posts", headers=self.auth(reader),
            json={"source": "event", "kind": "community", "body": "Evento"}).status_code, 403)
        review = self.client.post("/api/posts", headers=self.auth(reader), json={
            "source": "review", "kind": "reviews", "book_ref": "test:fourth-wing", "book_title": "Fourth Wing",
            "rating": 4, "body": "Me gustaron los personajes."})
        self.assertEqual(review.status_code, 201, review.text)
        self.assertEqual(review.json()["author_role"], "lector")
        self.assertEqual(review.json()["rating"], 4)
        legacy = Post(user_id=uuid.UUID(reader["user"]["id"]), author_role="lector", source="community", kind="community", body="Ejemplo antiguo")
        self.db.add(legacy)
        self.db.flush()
        listed = [item["id"] for item in self.client.get("/api/posts").json()]
        self.assertIn(review.json()["id"], listed)
        self.assertNotIn(str(legacy.id), listed)
        self.assertEqual(self.client.post("/api/posts", headers=self.auth(reader),
            json={"source": "review", "kind": "reviews", "body": "Sin libro"}).status_code, 422)

    def test_admin_verifies_profiles_and_creates_bookstores(self):
        reader = self.register("Persona aspirante")
        admin = self.register("Admin de prueba")
        self.db.get(User, uuid.UUID(admin["user"]["id"])).role = "admin"
        self.db.add(AccountPermission(user_id=uuid.UUID(admin["user"]["id"]), permission="admin"))
        self.db.flush()
        request = self.client.post("/api/roles/requests", headers=self.auth(reader),
            json={"requested_role": "autor", "note": "Publiqué una novela de ficción."})
        self.assertEqual(request.status_code, 201, request.text)
        request_id = request.json()["id"]
        self.assertEqual(self.client.post("/api/roles/requests", headers=self.auth(reader),
            json={"requested_role": "influencer", "note": "Tengo un canal de libros."}).status_code, 409)
        self.assertEqual(self.client.get("/api/roles/requests/pending", headers=self.auth(reader)).status_code, 403)
        self.assertEqual(self.client.post(f"/api/roles/requests/{request_id}/approve", headers=self.auth(reader)).status_code, 403)
        self.assertEqual(self.client.post("/api/roles/bookstores", headers=self.auth(reader), json={
            "email": f"{uuid.uuid4()}@example.com", "password": "test-password", "display_name": "Librería prueba"}).status_code, 403)
        approved = self.client.post(f"/api/roles/requests/{request_id}/approve", headers=self.auth(admin))
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth(reader)).json()["role"], "autor")
        post = self.client.post("/api/posts", headers=self.auth(reader),
            json={"source": "community", "kind": "community", "body": "Mi nueva novela"})
        self.assertEqual(post.status_code, 201, post.text)
        self.assertEqual(post.json()["author_role"], "autor")
        bookstore = self.client.post("/api/profiles/organizations", headers=self.auth(admin), json={
            "display_name": "Bookstore test", "administrator_user_id": reader["user"]["id"]})
        self.assertEqual(bookstore.status_code, 201, bookstore.text)
        self.assertEqual(bookstore.json()["organization_type"], "libreria")
        forged = self.client.post("/api/posts", headers=self.auth(admin), json={
            "source": "event", "kind": "community", "body": "Forbidden actor", "author_profile_id": bookstore.json()["id"]})
        self.assertEqual(forged.status_code, 403)

    def test_reading_progress_creates_feed_posts(self):
        reader = self.register()
        book = {"book_ref": f"test:{uuid.uuid4()}", "book_title": "Mistborn", "page_count": 600}
        reading_id = None
        for event, extra, expected_percent in [
            ("start", {}, 0), ("progress", {"current_page": 300}, 50),
            ("finish", {}, 100),
        ]:
            response = self.client.post("/api/readings/events", headers=self.auth(reader),
                                        json={**book, "event": event, "reading_id": reading_id, "share": True, **extra})
            self.assertEqual(response.status_code, 201, response.text)
            reading_id = response.json()["reading_id"]
            self.assertEqual(response.json()["post"]["progress_percent"], expected_percent)
            self.assertEqual(response.json()["post"]["reading_event"], event)
        self.assertEqual(self.client.post("/api/readings/events", headers=self.auth(reader),
            json={**book, "reading_id": reading_id, "event": "progress", "current_page": 350}).status_code, 409)
        states = self.client.get("/api/readings/me", headers=self.auth(reader))
        self.assertEqual(states.status_code, 200, states.text)
        self.assertEqual(next(item for item in states.json() if item["book_ref"] == book["book_ref"])["status"], "finished")
        abandon = self.client.post("/api/readings/events", headers=self.auth(reader), json={
            "book_ref": f"test:{uuid.uuid4()}", "book_title": "Otro libro", "page_count": 100,
            "event": "abandon", "abandonment_reason": "No me atrapó la historia"})
        self.assertEqual(abandon.status_code, 422, abandon.text)

    def test_admin_profile_maintenance_and_revocation(self):
        author = self.register("Autora verificable")
        admin = self.register("Administrador de perfiles")
        self.db.get(User, uuid.UUID(admin["user"]["id"])).role = "admin"
        self.db.add(AccountPermission(user_id=uuid.UUID(admin["user"]["id"]), permission="admin"))
        self.db.flush()
        author_headers = self.auth(author)
        admin_headers = self.auth(admin)
        request = self.client.post("/api/roles/requests", headers=author_headers,
                                   json={"requested_role": "autor", "note": "Tengo una novela publicada."})
        self.assertEqual(request.status_code, 201, request.text)

        for method, path in (("get", "/api/roles/profiles"),
                             ("get", f"/api/roles/profiles/{author['user']['id']}/requests"),
                             ("get", f"/api/roles/profiles/{author['user']['id']}/history")):
            self.assertEqual(getattr(self.client, method)(path, headers=author_headers).status_code, 403)
        results = self.client.get("/api/roles/profiles", headers=admin_headers,
                                  params={"q": "Autora verificable", "role": "lector", "limit": 1})
        self.assertEqual(results.status_code, 200, results.text)
        self.assertEqual(results.json()["total"], 1)
        self.assertEqual(results.json()["items"][0]["pending_role"], "autor")
        self.assertEqual(self.client.get("/api/roles/profiles", headers=admin_headers,
                                         params={"role": "administrador"}).status_code, 422)
        self.assertEqual(self.client.patch(f"/api/roles/profiles/{author['user']['id']}",
                                           headers=admin_headers, json={"display_name": "Nuevo nombre", "role": "admin"}).status_code, 422)
        edited = self.client.patch(f"/api/roles/profiles/{author['user']['id']}", headers=admin_headers,
                                   json={"display_name": "Autora actualizada", "biography": "Escribe ficción."})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["role"], "lector")
        self.assertEqual(len(self.client.get(f"/api/roles/profiles/{author['user']['id']}/requests",
                                             headers=admin_headers).json()), 1)

        approved = self.client.post(f"/api/roles/requests/{request.json()['id']}/approve", headers=admin_headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        post = self.client.post("/api/posts", headers=author_headers,
                                json={"source": "community", "kind": "community", "body": "Mi próximo libro"})
        self.assertEqual(post.status_code, 201, post.text)
        self.assertEqual(self.client.post(f"/api/roles/profiles/{author['user']['id']}/revoke",
                                          headers=author_headers, json={"reason": "No corresponde al perfil"}).status_code, 403)
        revoked = self.client.post(f"/api/roles/profiles/{author['user']['id']}/revoke", headers=admin_headers,
                                   json={"reason": "Se retiró la verificación del perfil."})
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["role"], "lector")
        self.assertEqual(self.client.post("/api/posts", headers=author_headers,
                                          json={"source": "community", "kind": "community", "body": "Otro libro"}).status_code, 403)
        listed = self.client.get("/api/posts").json()
        self.assertEqual(next(item for item in listed if item["id"] == post.json()["id"])["author_role"], "autor")
        history = self.client.get(f"/api/roles/profiles/{author['user']['id']}/history", headers=admin_headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["previous_role"], "autor")
        self.assertEqual(history.json()[0]["new_role"], "lector")

    def test_admin_profile_list_handles_legacy_invalid_email(self):
        admin = self.register("Administrador de perfiles")
        admin_user = self.db.get(User, uuid.UUID(admin["user"]["id"]))
        admin_user.role = "admin"
        self.db.add(AccountPermission(user_id=admin_user.id, permission="admin"))

        legacy_user = self.register("Perfil con correo legado")
        legacy_account = self.db.get(User, uuid.UUID(legacy_user["user"]["id"])).auth_account
        legacy_account.email = f"-{uuid.uuid4()}"
        self.db.flush()

        response = self.client.get(
            "/api/roles/profiles",
            headers=self.auth(admin),
            params={"q": "Perfil con correo legado"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["items"][0]["email"].startswith("-"))

    def test_reading_ownership_transitions_and_privacy(self):
        owner, other = self.register(), self.register()
        book = {"book_ref": f"test:{uuid.uuid4()}", "book_title": "Private book", "page_count": 100}
        url = "/api/readings/events"
        headers = self.auth(owner)
        for action in ("progress", "finish", "abandon"):
            result = self.client.post(url, headers=headers, json={**book, "event": action, "current_page": 20,
                                                                "abandonment_reason": "Private reason"})
            self.assertEqual(result.status_code, 422)
        started = self.client.post(url, headers=headers, json={**book, "event": "start"})
        self.assertEqual(started.status_code, 201, started.text)
        self.assertIsNotNone(started.json()["post"])
        reading_id = started.json()["reading_id"]
        payload = {**book, "reading_id": reading_id, "event": "progress", "current_page": 20}
        self.assertEqual(self.client.post(url, headers=self.auth(other), json=payload).status_code, 404)
        self.assertEqual(self.client.post(url, headers=headers, json={**payload, "page_count": 200}).status_code, 409)
        self.assertEqual(self.client.post(url, headers=headers, json=payload).status_code, 201)
        self.assertEqual(self.client.post(url, headers=headers, json=payload).status_code, 422)
        closed = self.client.post(url, headers=headers, json={**payload, "event": "abandon", "abandonment_reason": "Private reason"})
        self.assertEqual(closed.status_code, 201, closed.text)
        self.assertIsNone(closed.json()["post"])
        self.assertEqual(self.client.post(url, headers=headers, json={**payload, "event": "finish"}).status_code, 409)
        self.assertFalse(any(item["book_ref"] == book["book_ref"] for item in self.client.get("/api/posts").json()))
        self.assertFalse(any(item["book_ref"] == book["book_ref"] for item in self.client.get("/api/readings/me", headers=self.auth(other)).json()))

    def test_hidden_post_cannot_be_commented(self):
        reader = self.register()
        post = Post(user_id=uuid.UUID(reader["user"]["id"]), author_role="lector", source="community", kind="community", body="Legacy")
        self.db.add(post)
        self.db.flush()
        url = f"/api/posts/{post.id}/comments"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, headers=self.auth(reader), json={"body": "Hello"}).status_code, 404)

    def test_library_persists_pending_without_duplicates(self):
        reader = self.register()
        headers = self.auth(reader)
        book = {"book_ref": f"test:{uuid.uuid4()}", "book_title": "Pending book"}
        first = self.client.post("/api/readings/library", headers=headers, json=book)
        second = self.client.post("/api/readings/library", headers=headers, json=book)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.json()["reading_id"], first.json()["reading_id"])
        states = self.client.get("/api/readings/me", headers=headers).json()
        matches = [item for item in states if item["book_ref"] == book["book_ref"]]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "pending")
        self.assertIsNone(matches[0]["total_pages"])
        started = self.client.post("/api/readings/events", headers=headers, json={**book, "page_count": 100, "event": "start"})
        self.assertEqual(started.status_code, 201, started.text)
        self.assertEqual(started.json()["reading_id"], first.json()["reading_id"])

    def test_publishing_permissions_for_professional_profiles(self):
        for role in ("influencer", "autor"):
            session = self.register(f"Account {role}")
            user = self.db.get(User, uuid.UUID(session["user"]["id"]))
            profile = personal_profile(self.db, user)
            self.db.add(ProfileCapability(profile_id=profile.id, capability=role))
            self.db.flush()
            for source in ("community", "event"):
                publication = self.client.post("/api/posts", headers=self.auth(session), json={
                    "source": source, "kind": "community", "body": "News"})
                self.assertEqual(publication.status_code, 201, publication.text)
                self.assertEqual(publication.json()["author_role"], role)

    def test_demo_accounts_are_repeatable(self):
        first = seed(self.db, "test-password")
        self.db.flush()
        second = seed(self.db, "test-password")
        self.db.flush()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual({item["key"] for item in MANIFEST["accounts"]},
                         {"lector", "autor", "influencer", "libreria", "editorial", "admin"})


if __name__ == "__main__":
    unittest.main()
