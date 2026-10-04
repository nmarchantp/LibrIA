"""Comprueba publicaciones con imágenes, permisos e interacciones del mural."""

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.social.models import Post
from app.modules.users.identity_models import Profile, ProfileCapability
from app.modules.users.models import User


class PostInteractionsTest(unittest.TestCase):
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

    def register(self, name):
        response = self.client.post("/api/auth/register", json={
            "email": f"{uuid.uuid4()}@example.com",
            "password": "test-password",
            "display_name": name,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    @staticmethod
    def auth(account):
        return {"Authorization": f"Bearer {account['access_token']}"}

    def test_reader_cannot_publish_freely_but_admin_can(self):
        reader = self.register("Lectora")
        response = self.client.post("/api/posts", headers=self.auth(reader), json={
            "source": "community", "kind": "community", "body": "Hola mural",
        })
        self.assertEqual(response.status_code, 403)

        admin = self.register("Administradora")
        admin_user = self.db.get(User, uuid.UUID(admin["user"]["id"]))
        admin_user.role = "admin"
        self.db.flush()
        published = self.client.post("/api/posts", headers=self.auth(admin), json={
            "source": "community", "kind": "community", "body": "Anuncio breve",
        })
        self.assertEqual(published.status_code, 201, published.text)
        self.assertEqual(published.json()["author_role"], "admin")

    def test_images_likes_follows_and_comments_work_for_reader(self):
        author = self.register("Autora")
        author_id = uuid.UUID(author["user"]["id"])
        author_profile = self.db.scalar(select(Profile).where(Profile.owner_user_id == author_id))
        self.db.add(ProfileCapability(profile_id=author_profile.id, capability="autor"))
        self.db.flush()
        reader = self.register("Lector")

        published = self.client.post(
            "/api/posts",
            headers=self.auth(author),
            data={"source": "community", "kind": "community", "body": "Una publicación corta"},
            files=[
                ("images", (f"imagen-{index}.png", b"\x89PNG\r\n\x1a\ncontenido", "image/png"))
                for index in range(10)
            ],
        )
        self.assertEqual(published.status_code, 201, published.text)
        post_id = published.json()["id"]
        self.assertEqual(len(published.json()["images"]), 10)
        image_url = published.json()["images"][0]
        image = self.client.get(f"/api{image_url}")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/png")

        headers = self.auth(reader)
        liked = self.client.put(f"/api/posts/{post_id}/like", headers=headers)
        self.assertEqual(liked.status_code, 200, liked.text)
        self.assertEqual(liked.json(), {"like_count": 1, "liked_by_me": True})
        self.assertEqual(self.client.put(f"/api/posts/{post_id}/like", headers=headers).json()["like_count"], 1)
        self.assertEqual(self.client.post(f"/api/profiles/{author_profile.id}/follow", headers=headers).status_code, 200)
        comment = self.client.post(f"/api/posts/{post_id}/comments", headers=headers, json={"body": "Me gustó"})
        self.assertEqual(comment.status_code, 201, comment.text)

        feed = self.client.get("/api/posts", headers=headers).json()
        item = next(post for post in feed if post["id"] == post_id)
        self.assertEqual(item["like_count"], 1)
        self.assertTrue(item["liked_by_me"])
        self.assertTrue(item["following_author"])
        self.assertEqual(len(item["images"]), 10)

        self.assertEqual(self.client.delete(f"/api/posts/{post_id}/like", headers=headers).json(),
                         {"like_count": 0, "liked_by_me": False})
        self.assertEqual(self.client.delete(f"/api/profiles/{author_profile.id}/follow", headers=headers).status_code, 204)

    def test_free_publication_is_brief_and_image_count_is_limited(self):
        author = self.register("Autora")
        self.db.add(ProfileCapability(
            profile_id=uuid.UUID(self.client.get("/api/profiles/me", headers=self.auth(author)).json()[0]["id"]),
            capability="influencer",
        ))
        self.db.flush()
        too_long = self.client.post("/api/posts", headers=self.auth(author), json={
            "source": "community", "kind": "community", "body": "x" * 501,
        })
        self.assertEqual(too_long.status_code, 422)
        files = [("images", (f"{index}.png", b"\x89PNG\r\n\x1a\n", "image/png")) for index in range(11)]
        too_many = self.client.post(
            "/api/posts", headers=self.auth(author),
            data={"source": "community", "kind": "community", "body": "Breve"},
            files=files,
        )
        self.assertEqual(too_many.status_code, 422)


if __name__ == "__main__":
    unittest.main()
