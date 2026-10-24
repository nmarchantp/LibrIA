"""Rating dimensions remain optional and share create/update validation."""
import unittest
import uuid

from pydantic import ValidationError

from app.modules.social.schemas import ReviewCreate, ReviewUpdate


class RatingDimensionsTest(unittest.TestCase):
    def test_every_quarter_round_trips_without_rounding(self):
        for step in range(1, 21):
            value = step / 4
            created = ReviewCreate(work_id=uuid.uuid4(), body='Quarter rating', rating=value,
                                   dimension_ratings={'spicy': value, 'world_building': value})
            restored = ReviewCreate.model_validate_json(created.model_dump_json())
            self.assertEqual(restored.rating, value)
            self.assertEqual(restored.dimension_ratings['spicy'], value)
            self.assertEqual(ReviewUpdate(body='Quarter rating', rating=value).rating, value)

    def test_non_quarters_and_zero_are_not_valid_scores(self):
        for value in (0, -0.25, 0.1, 1.33, 5.25, float('inf'), float('nan')):
            for field in ({'rating': value}, {'dimension_ratings': {'romance': value}}):
                with self.subTest(value=value, field=field):
                    with self.assertRaises(ValidationError):
                        ReviewCreate(work_id=uuid.uuid4(), body='Invalid rating', **field)

    def test_new_dimensions_round_trip_with_existing_ratings(self):
        values = {'plot_twist': 2, 'pace': 4, 'battles': 5, 'horror': 1,
                  'boring_moments': 3, 'comedy': 4}
        created = ReviewCreate(work_id=uuid.uuid4(), body='Reseña', rating=4,
                               dimension_ratings=values)
        restored = ReviewCreate.model_validate_json(created.model_dump_json())
        updated = ReviewUpdate(**{key: value for key, value in restored.model_dump().items()
                                  if key not in ('work_id', 'author_profile_id')})
        self.assertEqual(updated.dimension_ratings, values)
        self.assertEqual(updated.rating, 4)

    def test_old_reviews_do_not_gain_default_scores(self):
        for schema, extra in [(ReviewCreate, {'work_id': uuid.uuid4()}), (ReviewUpdate, {})]:
            old = schema(body='Reseña antigua', rating=3, dimension_ratings={'romance': 5}, **extra)
            self.assertEqual(old.dimension_ratings, {'romance': 5})
            self.assertEqual(schema(body='Sin dimensiones', **extra).dimension_ratings, {})

    def test_new_dimensions_only_accept_one_to_five(self):
        for schema, extra in [(ReviewCreate, {'work_id': uuid.uuid4()}), (ReviewUpdate, {})]:
            for key in ('battles', 'horror', 'boring_moments', 'comedy'):
                for score in (0, 6, None):
                    with self.subTest(schema=schema.__name__, key=key, score=score):
                        with self.assertRaises(ValidationError):
                            schema(body='Reseña', dimension_ratings={key: score}, **extra)


if __name__ == '__main__':
    unittest.main()
