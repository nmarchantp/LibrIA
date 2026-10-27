"""Reseñas normalizadas, privacidad, integridad e indicadores al corte."""
from datetime import date, datetime, timezone
import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import CatalogSource, Work, Edition
from app.modules.social.models import Post, PostComment, Review, ReviewImage, ReviewRevision
from app.modules.users.identities import create_personal_profile
from app.modules.users.models import User
from app.modules.analytics.etl import day_bounds, extract, transform, publish
from scripts.seed_reviews_demo import MANIFEST, seed_reviews, stable_id as review_id
from scripts.seed_demo import stable_id as account_id
from scripts.seed_analytics_demo import stable_id as source_id


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Autora de reseña")
        self.other = User(display_name="Otro administrador", role="admin")
        self.work = Work(title="Obra reseñada")
        self.db.add_all([self.user, self.other, self.work])
        self.db.flush()
        self.profile = create_personal_profile(self.db, self.user)
        create_personal_profile(self.db, self.other)
        self.edition = Edition(work_id=self.work.id, title="Edición", language="es", page_count=100)
        self.second_edition = Edition(work_id=self.work.id, title="Otra edición", language="en", page_count=150)
        self.db.add_all([self.edition, self.second_edition])
        self.db.flush()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def create(self, **values):
        payload = {"work_id": str(self.work.id), "edition_id": str(self.edition.id), "body": "Una reseña personal"}
        return self.client.post("/api/reviews", json={**payload, **values})

    def update(self, item, **values):
        payload = {"body": "Reseña editada", "rating": 4, "status": "published", "edition_id": str(self.edition.id)}
        return self.client.put(f"/api/reviews/{item['id']}", json={**payload, **values})

    def test_rating_optional_and_no_manual_post_created(self):
        result = self.create()
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        self.assertIsNone(item["rating"])
        self.assertEqual(item["feed_item_type"], "review")
        self.assertIsNone(self.db.get(Post, uuid.UUID(item["id"])))
        self.assertEqual(self.db.scalar(select(ReviewRevision.rating).where(ReviewRevision.review_id == uuid.UUID(item["id"]))), None)
        self.assertEqual(self.client.get(f"/api/reviews/{item['id']}").status_code, 200)

    def test_quarter_ratings_persist_in_review_revision_and_responses(self):
        from decimal import Decimal
        result = self.create(rating=0.25, dimension_ratings={'spicy': 1.5, 'world_building': 3.75})
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        self.assertEqual(item['rating'], 0.25)
        self.assertEqual(item['dimension_ratings'], {'spicy': 1.5, 'world_building': 3.75})
        review_id = uuid.UUID(item['id'])
        self.assertEqual(self.db.get(Review, review_id).rating, Decimal('0.25'))
        self.assertEqual(self.db.scalar(select(ReviewRevision.rating).where(ReviewRevision.review_id == review_id)), Decimal('0.25'))
        updated = self.update(item, rating=3.75, dimension_ratings={'comedy': 4.25})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(self.client.get(f"/api/reviews/{review_id}").json()['rating'], 3.75)
        self.assertEqual(self.db.scalars(select(ReviewRevision.rating).where(ReviewRevision.review_id == review_id)
                                         .order_by(ReviewRevision.revision_number)).all(), [Decimal('0.25'), Decimal('3.75')])
        self.assertEqual(self.update(item, rating=0.1).status_code, 422)
        cleared = self.update(item, rating=None, dimension_ratings={})
        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertIsNone(cleared.json()['rating'])
        self.assertEqual(cleared.json()['dimension_ratings'], {})

    def test_quarter_rating_is_included_in_etl_sum_average_and_distribution(self):
        import json
        from decimal import Decimal
        from datetime import timedelta
        created = self.create(rating=0.25)
        self.assertEqual(created.status_code, 201, created.text)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        prepared = transform(*extract(self.connection, today, today + timedelta(days=1)))
        valuations = prepared[7]
        item = next(row for row in valuations if row['work_id'] == self.work.id)
        self.assertEqual(item['rating_sum'], Decimal('0.25'))
        self.assertEqual(item['rating_average'], Decimal('0.25'))
        self.assertEqual(json.loads(item['distribution'])['0.25'], 1)
        run_id = uuid.uuid4()
        self.connection.execute(text('''INSERT INTO analytics.ejecuciones_etl
            (id,status,started_at,source_cutoff_at,transform_version)
            VALUES (:id,'running',now(),:cutoff,'quarter-rating-test')'''),
            {'id': run_id, 'cutoff': today + timedelta(days=1)})
        publish(self.connection, run_id, prepared)
        total = self.connection.execute(text('''SELECT rating_sum FROM analytics.preparacion_valoraciones_obras
            WHERE etl_run_id=:run AND work_id=:work'''), {'run': run_id, 'work': self.work.id}).scalar_one()
        self.assertEqual(total, Decimal('0.25'))

    def test_unique_per_profile_work_even_with_different_edition(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create(edition_id=str(self.second_edition.id)).status_code, 409)

    def test_feed_includes_edition_cover(self):
        self.edition.cover_url = "https://example.com/cover.jpg"
        self.db.flush()
        created = self.create().json()
        response = self.client.get("/api/posts")
        self.assertEqual(response.status_code, 200, response.text)
        item = next(row for row in response.json() if row["id"] == created["id"])
        self.assertEqual(item["book_cover_url"], self.edition.cover_url)

    def test_book_reviews_exclude_private_reviews_and_other_books(self):
        reference = "reviews-" + uuid.uuid4().hex
        self.db.add(CatalogSource(edition_id=self.edition.id, provider="google-books", external_id=reference,
                                  fetched_at=datetime.now(timezone.utc)))
        self.db.flush()
        public = self.create(rating=5, is_spoiler=True).json()
        app.dependency_overrides[get_current_user] = lambda: self.other
        private = self.create(status="draft").json()
        other_work = Work(title="Unrelated book")
        self.db.add(other_work)
        self.db.flush()
        self.assertEqual(self.client.post("/api/reviews", json={"work_id": str(other_work.id), "body": "Otro libro"}).status_code, 201)
        app.dependency_overrides.pop(get_current_user)
        response = self.client.get(f"/api/reviews/by-book/{reference}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual([item["id"] for item in response.json()["items"]], [public["id"]])
        self.assertTrue(response.json()["items"][0]["is_spoiler"])
        self.assertFalse(response.json()["has_more"])
        app.dependency_overrides[get_current_user] = lambda: self.other
        self.assertEqual(self.update(private).status_code, 200)
        self.assertEqual(self.update(private, status="hidden").status_code, 200)
        self.assertEqual([item["id"] for item in self.client.get(f"/api/reviews/by-book/{reference}").json()["items"]], [public["id"]])
        self.assertEqual(self.client.get("/api/reviews/by-book/unknown-reference").json(), {"items": [], "has_more": False})

    def test_book_reviews_include_other_editions_and_support_pagination(self):
        reference = "reviews-" + uuid.uuid4().hex
        self.db.add(CatalogSource(edition_id=self.edition.id, provider="libria-feed", external_id=reference,
                                  fetched_at=datetime.now(timezone.utc)))
        self.db.flush()
        first = self.create().json()
        app.dependency_overrides[get_current_user] = lambda: self.other
        second = self.create(edition_id=str(self.second_edition.id), rating=3).json()
        url = f"/api/reviews/by-book/{reference}?limit=1"
        page_one = self.client.get(url).json()
        page_two = self.client.get(url + "&offset=1").json()
        self.assertTrue(page_one["has_more"])
        self.assertFalse(page_two["has_more"])
        self.assertEqual({page_one["items"][0]["id"], page_two["items"][0]["id"]}, {first["id"], second["id"]})

    def test_alternate_volume_records_share_reviews_and_prevent_duplicates(self):
        self.edition.title = "Asesino de brujas"
        alternate = Edition(work_id=self.work.id,
                            title="Asesino de brujas - vol 1 La bruja blanca - ed coleccionista",
                            language="es", page_count=520)
        self.db.add(alternate)
        self.db.flush()
        reference = "collector-" + uuid.uuid4().hex
        self.db.add(CatalogSource(edition_id=alternate.id, provider="google-books",
                                  external_id=reference, fetched_at=datetime.now(timezone.utc)))
        self.db.flush()

        review = self.create(rating=5).json()
        shown = self.client.get(f"/api/reviews/by-book/{reference}").json()["items"]
        self.assertEqual([item["id"] for item in shown], [review["id"]])
        duplicate = self.create(edition_id=str(alternate.id))
        self.assertEqual(duplicate.status_code, 409)

    def test_database_rejects_duplicate_review_and_new_legacy_post(self):
        item = self.create().json()
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.execute(text("""INSERT INTO app.resenas
                (id,author_profile_id,created_by_user_id,work_id,edition_id,body,status,published_at,created_at,updated_at)
                SELECT :new_id,author_profile_id,created_by_user_id,work_id,:edition,'Duplicada',status,published_at,created_at,updated_at
                FROM app.resenas WHERE id=:id"""),
                {"new_id": uuid.uuid4(), "edition": self.second_edition.id, "id": item["id"]})
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.add(Post(user_id=self.user.id, author_role="lector", source="review", kind="reviews", body="Nueva reseña mezclada"))
            self.db.flush()

    def test_edit_hide_republish_preserves_identity_and_first_publication(self):
        item = self.create(rating=5).json()
        for state in ("published", "hidden", "published"):
            updated = self.update(item, status=state)
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(updated.json()["id"], item["id"])
            self.assertEqual(updated.json()["published_at"], item["published_at"])
        self.assertEqual(self.db.scalar(select(Review.revision_number).where(Review.id == uuid.UUID(item["id"]))), 4)
        self.assertEqual(len(list(self.db.scalars(select(ReviewRevision).where(ReviewRevision.review_id == uuid.UUID(item["id"]))))), 4)

    def test_draft_is_private_and_first_publish_sets_date_once(self):
        item = self.create(status="draft").json()
        self.assertIsNone(item["published_at"])
        self.assertEqual(self.client.get(f"/api/reviews/{item['id']}").status_code, 404)
        self.assertFalse(any(row["id"] == item["id"] for row in self.client.get("/api/posts").json()))
        self.assertEqual(self.client.get(f"/api/reviews/me?work_id={self.work.id}").json()[0]["id"], item["id"])
        self.assertEqual(self.update(item, status="hidden").status_code, 422)
        published = self.update(item).json()
        self.assertIsNotNone(published["published_at"])
        self.assertEqual(self.update(item, status="draft").status_code, 422)

    def test_other_user_including_admin_cannot_edit_or_read_private_review(self):
        item = self.create(status="draft").json()
        app.dependency_overrides[get_current_user] = lambda: self.other
        self.assertEqual(self.update(item).status_code, 404)
        self.assertEqual(self.client.get(f"/api/reviews/me?work_id={self.work.id}").json(), [])
        self.assertEqual(self.create(author_profile_id=str(self.profile.id)).status_code, 403)

    def test_hidden_review_blocks_feed_comments_likes_and_images(self):
        result = self.create(is_spoiler=True)
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        path = f"/api/posts/{item['id']}"
        self.assertEqual(self.client.put(path + "/like").json()["like_count"], 1)
        self.assertEqual(self.client.put(path + "/like").json()["like_count"], 1)
        comment = self.client.post(path + "/comments", json={"body": "Comentario de la reseña"})
        self.assertEqual(comment.status_code, 201, comment.text)
        stored = self.db.get(PostComment, uuid.UUID(comment.json()["id"]))
        self.assertEqual(str(stored.review_id), item["id"])
        self.assertIsNone(stored.post_id)
        # An attachment stored before the text-only policy must not be exposed.
        legacy = ReviewImage(review_id=uuid.UUID(item["id"]), content_type="image/png", data=b"\x89PNG\r\n\x1a\ntest")
        self.db.add(legacy)
        self.db.flush()
        image = f"/api/posts/{item['id']}/images/{legacy.id}"
        self.assertEqual(self.client.get(image).status_code, 404)
        self.assertEqual(self.client.get(f"/api/reviews/{item['id']}").json()["images"], [])
        self.assertEqual(self.update(item, status="hidden").status_code, 200)
        for url in (path + "/comments", image, f"/api/reviews/{item['id']}"):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(path + "/comments", json={"body": "No permitido"}).status_code, 404)
        self.assertEqual(self.client.put(path + "/like").status_code, 404)
        self.assertEqual(self.client.delete(path + "/like").status_code, 404)
        self.assertFalse(any(row["id"] == item["id"] for row in self.client.get("/api/posts").json()))

    def test_review_create_and_update_reject_files_and_image_fields(self):
        files = [("images", ("test.png", b"\x89PNG\r\n\x1a\ntest", "image/png"))]
        response = self.client.post("/api/reviews", data={"work_id": str(self.work.id), "body": "No guardar"}, files=files)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(list(self.db.scalars(select(Review).where(Review.work_id == self.work.id))), [])
        self.assertEqual(self.create(images=["https://example.com/image.png"]).status_code, 422)
        item = self.create().json()
        self.assertEqual(self.client.put(f"/api/reviews/{item['id']}", data={"body": "No cambiar"}, files=files).status_code, 422)
        self.assertEqual(self.update(item, replace_images=True).status_code, 422)
        unchanged = self.client.get(f"/api/reviews/{item['id']}").json()
        self.assertEqual(unchanged["body"], item["body"])
        self.assertEqual(unchanged["revision_number"], 1)
        self.assertEqual(unchanged["images"], [])

    def test_invalid_rating_work_edition_and_manual_route_are_rejected(self):
        for rating in (0, 6):
            self.assertEqual(self.create(rating=rating).status_code, 422)
        self.assertEqual(self.create(body="   ").status_code, 422)
        self.assertEqual(self.create(work_id=str(uuid.uuid4())).status_code, 404)
        self.assertEqual(self.create(edition_id=str(uuid.uuid4())).status_code, 422)
        self.assertEqual(self.client.post("/api/posts", json={"source": "review", "kind": "reviews", "body": "Prohibida"}).status_code, 422)

    def test_db_protects_first_publication_identity_and_comment_destination(self):
        item = self.create().json()
        for assignment in ("published_at=published_at + interval '1 day'", "work_id='" + str(uuid.uuid4()) + "'"):
            with self.assertRaises(IntegrityError), self.db.begin_nested():
                self.db.execute(text(f"UPDATE app.resenas SET {assignment} WHERE id=:id"), {"id": item["id"]})
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.add(PostComment(user_id=self.user.id, body="Sin destino"))
            self.db.flush()

    def test_repeatable_review_scenarios_and_indicators(self):
        first = seed_reviews(self.db, "test-password")
        self.assertEqual(first, seed_reviews(self.db, "test-password"))
        prepared = transform(*extract(self.connection, *day_bounds(date.fromisoformat(MANIFEST["reference_date"]))))
        for account, expected in MANIFEST["expected"]["new_reviews"].items():
            actual = next(i["value"] for i in prepared[3] if i["user_id"] == account_id(f"user:{account}")
                          and i["indicator_code"] == "S02" and i["provenance"] == "simulated")
            self.assertEqual(actual, expected)
        uncalibrated = next(row for row in prepared[7] if row["work_id"] == source_id("work:unknown") and row["provenance"] == "simulated")
        self.assertEqual(uncalibrated["rated_count"], 0)
        self.assertIsNone(uncalibrated["rating_average"])
        garden = next(row for row in prepared[7] if row["work_id"] == source_id("work:garden") and row["provenance"] == "simulated")
        self.assertEqual(garden["rating_average"], 4)
        self.assertNotIn(review_id("admin-hidden"), {row["source_id"] for row in prepared[6] if row["status"] == "published"})

    def test_etl_uses_revision_before_cutoff_not_current_rating(self):
        seed_reviews(self.db, "test-password")
        start, _ = day_bounds(date(2026, 10, 10))
        cutoff = datetime(2026, 10, 10, 11, 10, tzinfo=timezone.utc)  # 08:10 de Santiago
        prepared = transform(*extract(self.connection, start, cutoff))
        row = next(row for row in prepared[6] if row["source_id"] == review_id("reader-edited"))
        self.assertEqual(row["rating"], 5)
        self.assertEqual(row["revision_number"], 1)
        self.assertEqual(self.db.get(Review, review_id("reader-edited")).rating, 3)
        # Primera publicación exactamente al corte todavía no pertenece al intervalo.
        self.assertFalse(any(row["source_id"] == review_id("author-republished") for row in prepared[6]))

    def test_etl_publishes_reviews_and_conciles_prepared_rows(self):
        seed_reviews(self.db, "test-password")
        start, cutoff = day_bounds(date(2026, 10, 10))
        prepared = transform(*extract(self.connection, start, cutoff))
        run_id = uuid.uuid4()
        self.connection.execute(text("""INSERT INTO analytics.ejecuciones_etl
            (id,status,started_at,source_cutoff_at,transform_version) VALUES (:id,'running',now(),:cutoff,'daily-v2')"""),
            {"id": run_id, "cutoff": cutoff})
        summary = publish(self.connection, run_id, prepared)
        actual = self.connection.execute(text("SELECT count(*) FROM analytics.hechos_resenas WHERE etl_run_id=:id"), {"id": run_id}).scalar_one()
        self.assertEqual(actual, summary["loaded_reviews"])
        self.assertEqual(summary["group_analysis"], "protected_global_aggregates_only")
        average = self.connection.execute(text("""SELECT rating_average FROM analytics.preparacion_valoraciones_obras
            WHERE etl_run_id=:id AND work_id=:work AND provenance='simulated'"""),
            {"id": run_id, "work": source_id("work:unknown")}).scalar_one()
        self.assertIsNone(average)
        self.assertEqual(self.connection.execute(text("SELECT status FROM analytics.ejecuciones_etl WHERE id=:id"), {"id": run_id}).scalar_one(), "succeeded")
