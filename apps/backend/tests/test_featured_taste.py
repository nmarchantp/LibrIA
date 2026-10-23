"""One optional selected taste is displayed; the other ratings remain stored."""
import unittest
from unittest.mock import patch

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from tests import test_literary_preferences as preferences
from app.modules.users.preference_models import FavoriteIntensity


class FeaturedTasteTest(unittest.TestCase):
    setUpClass = classmethod(lambda cls: preferences.LiteraryPreferencesTest.setUpClass())
    setUp = preferences.LiteraryPreferencesTest.setUp
    tearDown = preferences.LiteraryPreferencesTest.tearDown
    register = preferences.LiteraryPreferencesTest.register
    auth = staticmethod(preferences.LiteraryPreferencesTest.auth)
    save = preferences.LiteraryPreferencesTest.save
    mine = preferences.LiteraryPreferencesTest.mine

    def configure(self):
        result = self.save({'intensities': [{'category_id': key, 'level': i}
            for i, key in enumerate(['romance', 'spicy', 'terror', 'humor', 'accion'], 1)]})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_optional_feature_switch_clear_and_reload_preserve_five_ratings(self):
        self.assertIsNone(self.configure()['featured_category_id'])
        for key in ['spicy', 'romance', 'humor', None]:
            self.assertEqual(self.save({'featured_category_id': key}).status_code, 200)
            self.db.expire_all()
            mine = self.mine()
            self.assertEqual(mine['featured_category_id'], key)
            self.assertEqual(len(mine['intensities']), 5)
            rows = self.db.scalars(select(FavoriteIntensity).where(FavoriteIntensity.user_id == self.owner['user']['id'])).all()
            self.assertEqual(sum(row.featured for row in rows), int(key is not None))

    def test_only_configured_category_can_be_featured_atomically(self):
        for key in ['spicy', 'unknown']:
            self.assertEqual(self.save({'featured_category_id': key, 'biography': 'Must not persist'}).status_code, 422)
            self.assertIsNone(self.mine()['biography'])
        self.configure()
        self.assertEqual(self.save({'featured_category_id': 'fantasia'}).status_code, 422)
        self.assertEqual(self.save({'featured_category_id': ['spicy', 'romance']}).status_code, 422)

    def test_updated_intensity_and_order_keep_feature_when_field_omitted(self):
        self.configure()
        self.save({'featured_category_id': 'spicy'})
        self.assertEqual(self.save({'intensities': [{'category_id': 'spicy', 'level': 5}, {'category_id': 'romance', 'level': 1}]}).status_code, 200)
        mine = self.mine()
        self.assertEqual(mine['featured_category_id'], 'spicy')
        self.assertEqual(mine['intensities'][0]['level'], 5)
        self.save({'biography': 'Only biography'})
        self.assertEqual(self.mine()['featured_category_id'], 'spicy')

    def test_removing_featured_category_clears_without_selecting_another(self):
        self.configure()
        self.save({'featured_category_id': 'spicy'})
        self.assertEqual(self.save({'intensities': [{'category_id': 'romance', 'level': 2}]}).status_code, 200)
        self.assertIsNone(self.mine()['featured_category_id'])
        self.assertEqual(len(self.mine()['intensities']), 1)
        self.save({'featured_category_id': 'romance'})
        self.assertEqual(self.save({'intensities': []}).status_code, 200)
        self.assertIsNone(self.mine()['featured_category_id'])

    def test_database_rejects_second_feature_and_delete_has_no_orphan(self):
        self.configure()
        self.save({'featured_category_id': 'spicy'})
        with self.assertRaises(IntegrityError) as error:
            with self.db.begin_nested():
                self.db.execute(update(FavoriteIntensity).where(FavoriteIntensity.user_id == self.owner['user']['id'],
                    FavoriteIntensity.category_id == 'romance').values(featured=True))
        self.assertEqual(error.exception.orig.diag.constraint_name, 'uq_gustos_intensidades_featured')
        self.db.execute(delete(FavoriteIntensity).where(FavoriteIntensity.user_id == self.owner['user']['id'],
            FavoriteIntensity.category_id == 'spicy'))
        self.db.commit()
        self.assertIsNone(self.mine()['featured_category_id'])

    def test_public_visibility_session_ownership_and_rollback(self):
        mine = self.configure()
        self.save({'featured_category_id': 'spicy'})
        route = '/api/profiles/' + mine['profile_id']
        public = self.client.get(route, headers=self.auth(self.other))
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()['featured_category_id'], 'spicy')
        self.assertNotIn('email', public.json())
        self.assertEqual(self.client.patch(route, headers=self.auth(self.other), json={'featured_category_id': None}).status_code, 405)
        self.assertEqual(self.client.patch(self.path, json={'featured_category_id': None}).status_code, 401)
        self.assertEqual(self.save({'featured_category_id': None, 'user_id': self.other['user']['id']}).status_code, 422)
        with patch('app.modules.users.preferences_router.own_response', side_effect=RuntimeError('save failed')):
            self.assertEqual(self.save({'featured_category_id': 'romance'}).status_code, 500)
        self.assertEqual(self.mine()['featured_category_id'], 'spicy')


if __name__ == '__main__':
    unittest.main()
