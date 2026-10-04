import unittest
import uuid

from app.modules.social.schemas import PostCreate
from scripts.generate_posts import make_post


class GeneratePostsTest(unittest.TestCase):
    def test_reader_payload_is_a_valid_review_shape(self):
        profile_id = str(uuid.uuid4())
        post = make_post({"key": "lector"}, profile_id, 0)
        PostCreate.model_validate(post)

        self.assertEqual(post["source"], "review")
        self.assertEqual(post["kind"], "reviews")
        self.assertEqual(post["author_profile_id"], profile_id)
        self.assertTrue(post["book_ref"])
        self.assertTrue(post["book_title"])
        self.assertGreaterEqual(post["rating"], 1)
        self.assertLessEqual(post["rating"], 5)
        self.assertTrue(post["body"])

    def test_organization_payload_uses_promotion_type(self):
        profile_id = str(uuid.uuid4())
        post = make_post({"key": "libreria", "organization": "Libreria Demo"},
                         profile_id, 1)
        PostCreate.model_validate(post)

        self.assertEqual(post["source"], "community")
        self.assertEqual(post["kind"], "community")
        self.assertEqual(post["publication_type"], "promotion")
        self.assertEqual(post["author_profile_id"], profile_id)

    def test_publisher_event_payload_matches_event_contract(self):
        post = make_post({"key": "autor"}, str(uuid.uuid4()), 0)
        PostCreate.model_validate(post)

        self.assertEqual(post["source"], "event")
        self.assertEqual(post["kind"], "community")
        self.assertEqual(post["publication_type"], "event")
