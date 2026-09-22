"""Comprueba comentarios persistentes sin dejar datos de prueba en PostgreSQL."""

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post
from app.modules.users.models import User


class PostCommentsTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Lector de prueba")
        self.db.add(self.user)
        self.db.flush()
        self.post = Post(user_id=self.user.id, source="reading", kind="progress", body="Avance de prueba")
        self.db.add(self.post)
        self.db.flush()

        def test_db():
            yield self.db

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_create_and_list_comments(self):
        url = f"/api/posts/{self.post.id}/comments"
        created = self.client.post(url, json={"body": "  Me gustó este avance.  "})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["body"], "Me gustó este avance.")
        self.assertEqual(created.json()["author"], "Lector de prueba")
        self.assertEqual(created.json()["author_role"], "lector")

        listed = self.client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], [created.json()["id"]])

    def test_invalid_body_and_missing_post(self):
        url = f"/api/posts/{self.post.id}/comments"
        for body in ["   ", "a" * 1001]:
            with self.subTest(body_length=len(body)):
                self.assertEqual(self.client.post(url, json={"body": body}).status_code, 422)

        missing_url = f"/api/posts/{uuid.uuid4()}/comments"
        self.assertEqual(self.client.get(missing_url).status_code, 404)
        self.assertEqual(self.client.post(missing_url, json={"body": "Hola"}).status_code, 404)

    def test_comments_are_separate_for_each_post(self):
        review = Post(user_id=self.user.id, source="review", kind="reviews", body="Reseña de prueba")
        self.db.add(review)
        self.db.flush()
        first_url = f"/api/posts/{self.post.id}/comments"
        review_url = f"/api/posts/{review.id}/comments"

        self.assertEqual(self.client.post(first_url, json={"body": "Sobre el avance"}).status_code, 201)
        self.assertEqual(self.client.post(review_url, json={"body": "Sobre la reseña"}).status_code, 201)
        self.assertEqual([item["body"] for item in self.client.get(first_url).json()], ["Sobre el avance"])
        self.assertEqual([item["body"] for item in self.client.get(review_url).json()], ["Sobre la reseña"])

    def test_comment_requires_session(self):
        app.dependency_overrides.pop(get_current_user)
        response = self.client.post(f"/api/posts/{self.post.id}/comments", json={"body": "Hola"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
