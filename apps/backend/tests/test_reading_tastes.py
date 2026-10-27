"""Real PostgreSQL/API checks; test accounts and writes roll back after each test."""
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from tests import test_literary_preferences as preferences
from app.modules.users.preference_models import FavoriteIntensity, IntensityCategory, Interest


class ReadingTastesTest(unittest.TestCase):
    setUpClass = classmethod(lambda cls: preferences.LiteraryPreferencesTest.setUpClass())
    setUp = preferences.LiteraryPreferencesTest.setUp
    tearDown = preferences.LiteraryPreferencesTest.tearDown
    register = preferences.LiteraryPreferencesTest.register
    auth = staticmethod(preferences.LiteraryPreferencesTest.auth)
    save = preferences.LiteraryPreferencesTest.save
    mine = preferences.LiteraryPreferencesTest.mine

    def test_controlled_catalog_and_empty_new_account(self):
        data = self.client.get('/api/profiles/preference-catalogs', headers=self.headers).json()
        self.assertEqual(len(data['intensities']), 10)
        self.assertEqual(len(data['interests']), 10)
        self.assertEqual(len({x['id'] for x in data['intensities']}), 10)
        self.assertTrue(all(len(x['levels']) == 5 for x in data['intensities']))
        self.assertEqual(len({x['group'] for x in data['interests']}), 4)
        self.assertEqual(self.mine()['intensities'], [])
        self.assertEqual(self.mine()['interests'], [])

    def test_persistence_levels_reorder_replace_and_public_visibility(self):
        items = [{'category_id': 'romance', 'level': 4}, {'category_id': 'spicy', 'level': 2}]
        self.assertEqual(self.save({'intensities': items, 'interest_ids': ['historia', 'ciencia']}).status_code, 200)
        self.db.expire_all()
        mine = self.mine()
        self.assertEqual([(x['id'], x['level']) for x in mine['intensities']], [('romance', 4), ('spicy', 2)])
        self.assertEqual(len(mine['interests']), 2)
        self.assertEqual(self.save({'intensities': items[::-1]}).status_code, 200)
        self.assertEqual([x['id'] for x in self.mine()['intensities']], ['spicy', 'romance'])
        self.assertEqual(self.save({'intensities': [{'category_id': 'humor', 'level': 5}]}).status_code, 200)
        mine = self.mine()
        public = self.client.get('/api/profiles/' + mine['profile_id'], headers=self.auth(self.other))
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()['intensities'], mine['intensities'])
        self.assertEqual(public.json()['interests'], mine['interests'])
        self.assertNotIn('email', public.json())

    def test_max_five_with_independent_interests(self):
        keys = ['romance', 'spicy', 'terror', 'humor', 'accion']
        items = [{'category_id': key, 'level': 1} for key in keys]
        interests = list(self.db.scalars(select(Interest.id)))
        self.assertEqual(self.save({'intensities': items, 'interest_ids': interests}).status_code, 200)
        self.assertEqual(len(self.mine()['interests']), 10)
        self.assertEqual(self.save({'intensities': items + [{'category_id': 'fantasia', 'level': 3}]}).status_code, 422)
        self.assertEqual(len(self.mine()['intensities']), 5)

    def test_invalid_values_duplicates_and_catalogs_are_rejected_atomically(self):
        for level in [0, 6, 1.5, True, '3', None]:
            with self.subTest(level=level):
                self.assertEqual(self.save({'intensities': [{'category_id': 'romance', 'level': level}]}).status_code, 422)
        duplicate = {'category_id': 'romance', 'level': 3}
        for payload in [
            {'intensities': [duplicate, duplicate]}, {'interest_ids': ['historia', 'historia']},
            {'intensities': [{'category_id': 'unknown', 'level': 2}]}, {'interest_ids': ['dragones']},
            {'intensities': None}, {'interest_ids': None},
            {'intensities': [dict(duplicate, owner_id=self.other['user']['id'])]},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.save({'biography': 'Must not persist', **payload}).status_code, 422)
                self.assertIsNone(self.mine()['biography'])

    def test_omission_clearing_and_existing_preferences_preserved(self):
        self.assertEqual(self.save({'biography': 'My story', 'genre_ids': ['romance'], 'trope_ids': ['magia'],
            'intensities': [{'category_id': 'romance', 'level': 1}], 'interest_ids': ['historia']}).status_code, 200)
        self.assertEqual(self.save({'biography': 'Updated'}).status_code, 200)
        self.assertEqual(len(self.mine()['intensities']), 1)
        self.assertEqual(self.save({'intensities': []}).status_code, 200)
        self.assertEqual(len(self.mine()['interests']), 1)
        self.assertEqual(self.save({'interest_ids': []}).status_code, 200)
        mine = self.mine()
        self.assertEqual(mine['intensities'], [])
        self.assertEqual(mine['interests'], [])
        self.assertEqual(mine['biography'], 'Updated')
        self.assertEqual([x['id'] for x in mine['genres']], ['romance'])
        self.assertEqual([x['id'] for x in mine['tropes']], ['magia'])

    def test_only_session_owner_can_write_and_public_requires_authentication(self):
        payload = {'intensities': [{'category_id': 'romance', 'level': 3}]}
        self.assertEqual(self.client.patch(self.path, json=payload).status_code, 401)
        self.assertEqual(self.save(dict(payload, user_id=self.other['user']['id'])).status_code, 422)
        own_id = self.mine()['profile_id']
        self.assertEqual(self.client.patch('/api/profiles/' + own_id, headers=self.auth(self.other), json=payload).status_code, 405)
        self.assertEqual(self.client.get('/api/profiles/' + own_id).status_code, 401)
        self.assertEqual(self.client.patch(self.path, headers=self.auth(self.other), json=payload).status_code, 200)
        self.assertEqual(self.mine()['intensities'], [])

    def test_database_counts_independently_from_position_constraints(self):
        keys = ['romance', 'spicy', 'terror', 'humor', 'accion']
        self.assertEqual(self.save({'intensities': [{'category_id': key, 'level': 2} for key in keys]}).status_code, 200)
        self.db.close()
        # Temporarily remove both position protections inside a rolled-back DDL
        # savepoint: the explicit total-count trigger must still reject a sixth.
        with self.connection.begin_nested() as ddl:
            self.connection.execute(text('ALTER TABLE app.gustos_intensidades DROP CONSTRAINT ck_gustos_intensidades_position'))
            self.connection.execute(text('ALTER TABLE app.gustos_intensidades DROP CONSTRAINT uq_gustos_intensidades_position'))
            with self.assertRaises(IntegrityError) as error:
                with self.connection.begin_nested():
                    self.connection.execute(text('INSERT INTO app.gustos_intensidades (user_id,category_id,level,position) VALUES (:user,\'fantasia\',2,6)'), {'user': self.owner['user']['id']})
            self.assertEqual(error.exception.orig.diag.constraint_name, 'ck_gustos_intensidades_count')
            ddl.rollback()

    def test_database_levels_and_duplicate_category(self):
        user_id = uuid.UUID(self.owner['user']['id'])
        for level in [0, 6]:
            with self.assertRaises(IntegrityError):
                with self.db.begin_nested():
                    self.db.add(FavoriteIntensity(user_id=user_id, category_id='romance', level=level, position=1))
                    self.db.flush()
        self.save({'intensities': [{'category_id': 'romance', 'level': 1}]})
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(FavoriteIntensity(user_id=user_id, category_id='romance', level=2, position=2))
                self.db.flush()

    def test_failure_rolls_back_new_and_old_fields_together(self):
        with patch('app.modules.users.preferences_router.own_response', side_effect=RuntimeError('forced failure')):
            response = self.save({'biography': 'Must roll back', 'intensities': [{'category_id': 'romance', 'level': 3}], 'interest_ids': ['historia']})
        self.assertEqual(response.status_code, 500)
        mine = self.mine()
        self.assertIsNone(mine['biography'])
        self.assertEqual(mine['intensities'], [])
        self.assertEqual(mine['interests'], [])

    def test_inactive_saved_options_can_be_retained_not_newly_chosen(self):
        self.save({'intensities': [{'category_id': 'romance', 'level': 3}]})
        self.db.get(IntensityCategory, 'romance').active = False
        self.db.commit()
        self.assertEqual(self.save({'intensities': [{'category_id': 'romance', 'level': 4}]}).status_code, 200)
        response = self.client.patch(self.path, headers=self.auth(self.other), json={'intensities': [{'category_id': 'romance', 'level': 4}]})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
