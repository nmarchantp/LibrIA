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
from scripts.generate_posts import PEOPLE, TEMPLATES


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
        bookstore = self.client.post("/api/roles/bookstores", headers=self.auth(admin), json={
            "email": f"{uuid.uuid4()}@example.com", "password": "test-password", "display_name": "Librería prueba"})
        self.assertEqual(bookstore.status_code, 201, bookstore.text)
        self.assertEqual(bookstore.json()["role"], "libreria")
        edited = self.client.patch(f"/api/roles/profiles/{bookstore.json()['id']}", headers=self.auth(admin),
                                   json={"display_name": "Librería renovada", "biography": "Libros de fantasía"})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["role"], "libreria")
        self.assertEqual(edited.json()["display_name"], "Librería renovada")
        self.assertEqual(self.client.post(f"/api/roles/profiles/{bookstore.json()['id']}/revoke",
                                          headers=self.auth(admin), json={"reason": "Motivo de prueba suficiente"}).status_code, 409)

    def test_reading_progress_creates_feed_posts(self):
        reader = self.register()
        book = {"book_ref": f"test:{uuid.uuid4()}", "book_title": "Mistborn", "page_count": 600}
        for event, extra, expected_percent in [
            ("start", {}, 0), ("progress", {"current_page": 300}, 50),
            ("finish", {}, 100),
        ]:
            response = self.client.post("/api/readings/events", headers=self.auth(reader),
                                        json={**book, "event": event, **extra})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["post"]["progress_percent"], expected_percent)
            self.assertEqual(response.json()["post"]["reading_event"], event)
        self.assertEqual(self.client.post("/api/readings/events", headers=self.auth(reader),
            json={**book, "event": "progress", "current_page": 350}).status_code, 409)
        states = self.client.get("/api/readings/me", headers=self.auth(reader))
        self.assertEqual(states.status_code, 200, states.text)
        self.assertEqual(next(item for item in states.json() if item["book_ref"] == book["book_ref"])["status"], "finished")
        abandon = self.client.post("/api/readings/events", headers=self.auth(reader), json={
            "book_ref": f"test:{uuid.uuid4()}", "book_title": "Otro libro", "page_count": 100,
            "event": "abandon", "abandonment_reason": "No me atrapó la historia"})
        self.assertEqual(abandon.status_code, 201, abandon.text)
        self.assertEqual(abandon.json()["post"]["reading_event"], "abandon")

    def test_admin_profile_maintenance_and_revocation(self):
        author = self.register("Autora verificable")
        admin = self.register("Administrador de perfiles")
        self.db.get(User, uuid.UUID(admin["user"]["id"])).role = "admin"
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

    def test_publishing_permissions_for_professional_profiles(self):
        for role in ("influencer", "autor", "libreria"):
            with self.subTest(role=role):
                session = self.register(f"Cuenta {role}")
                self.db.get(User, uuid.UUID(session["user"]["id"])).role = role
                self.db.flush()
                headers = self.auth(session)
                publication = self.client.post("/api/posts", headers=headers,
                                               json={"source": "community", "kind": "community", "body": "Una novedad"})
                self.assertEqual(publication.status_code, 201, publication.text)
                self.assertEqual(publication.json()["author_role"], role)
                event = self.client.post("/api/posts", headers=headers,
                                         json={"source": "event", "kind": "community", "body": "Encuentro de lectores"})
                self.assertEqual(event.status_code, 403 if role == "influencer" else 201, event.text)

    def test_demo_examples_match_permissions(self):
        self.assertEqual({role for _, role in PEOPLE}, set(TEMPLATES))
        for role, templates in TEMPLATES.items():
            self.assertGreaterEqual(len(templates), 2, role)
            for template in templates:
                if "reading_event" in template:
                    self.assertEqual(role, "lector")
                else:
                    PostCreate(**template)
                    if role == "lector":
                        self.assertEqual(template["source"], "review")


if __name__ == "__main__":
    unittest.main()
