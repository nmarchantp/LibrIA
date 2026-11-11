"""Exclusive demo logins, credential configuration and non-destructive reseeding."""
import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import Settings, get_settings
from app.core.database import engine, get_db
from app.core.security import verify_password
from app.modules.users.models import User
from app.modules.users.identities import personal_profile
from app.modules.users.identity_models import Profile, ProfileCapability, AccountPermission
from app.modules.users.account_models import AccountAudit
from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry, Reading
from app.modules.auth.models import AuthAccount
from scripts.seed_demo import seed, stable_id, configured_passwords, MANIFEST


class DemoProfileAccountsTest(unittest.TestCase):
    def setUp(self):
        if engine.url.database != 'libria_influencer_access_test' or get_settings().app_env != 'test':
            raise RuntimeError('Use the isolated compose.influencer-test.yaml database')
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode='create_savepoint')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear()
        self.db.close(); self.transaction.rollback(); self.connection.close()

    def test_optional_per_profile_passwords_fall_back_to_existing_common_key(self):
        settings = Settings(_env_file=None, libria_demo_password='common-password', libria_demo_admin_password='admin-password', libria_demo_editorial_password='editorial-password')
        passwords = configured_passwords(settings)
        self.assertEqual(passwords['admin'], 'admin-password')
        self.assertEqual(passwords['editorial'], 'editorial-password')
        self.assertEqual(passwords['lector'], 'common-password')
        self.assertEqual(len(passwords), 6)

    def test_six_distinct_accounts_can_login_with_correct_roles_and_permissions(self):
        passwords = {entry['key']: entry['key'] + '-private-password' for entry in MANIFEST['accounts']}
        seed(self.db, '', passwords=passwords); self.db.commit()
        for entry in MANIFEST['accounts']:
            key = entry['key']
            login = self.client.post('/api/auth/login', json={'email': entry['email'], 'password': passwords[key]})
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(login.json()['user']['role'], key)
            headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
            me = self.client.get('/api/auth/me', headers=headers)
            self.assertEqual(me.json()['role'], key)
            publish = self.client.post('/api/posts', headers=headers, json={'source': 'community', 'kind': 'community', 'body': 'Publicación de prueba demo.'})
            self.assertEqual(publish.status_code, 403 if key == 'lector' else 201, publish.text)
            admin = self.client.get('/api/roles/requests/pending', headers=headers)
            self.assertEqual(admin.status_code, 200 if key == 'admin' else 403, admin.text)
            wrong = self.client.post('/api/auth/login', json={'email': entry['email'], 'password': 'incorrect-password'})
            self.assertEqual(wrong.status_code, 401)
            self.assertEqual(self.db.get(User, stable_id('user:' + key)).role, key)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Profile).where(Profile.kind == 'organization')), 0)

    def test_reseed_is_idempotent_and_password_rotation_revokes_old_sessions(self):
        original = seed(self.db, 'initial-password'); self.db.commit()
        login = self.client.post('/api/auth/login', json={'email': 'demo.lector@example.com', 'password': 'initial-password'}).json()
        user = self.db.get(User, stable_id('user:lector'))
        profile_id = personal_profile(self.db, user).id
        work = Work(title='Existing personal book'); self.db.add(work); self.db.flush()
        entry = LibraryEntry(user_id=user.id, work_id=work.id); self.db.add(entry); self.db.flush()
        reading = Reading(library_entry_id=entry.id, work_id=work.id, status='reading', current_page=3, total_pages=100, started_at=datetime.now(timezone.utc))
        self.db.add(reading); self.db.commit()
        self.assertEqual(seed(self.db, 'rotated-password'), original); self.db.commit()
        self.assertEqual(personal_profile(self.db, user).id, profile_id)
        self.assertIsNotNone(self.db.get(Reading, reading.id))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(User)), 6)
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + login['access_token']}).status_code, 401)

    def test_legacy_reader_responsible_becomes_exclusive_editorial_without_data_loss(self):
        seed(self.db, 'initial-password'); self.db.commit()
        user = self.db.get(User, stable_id('user:editorial'))
        user.role = 'lector'; self.db.commit()
        profile_id = personal_profile(self.db, user).id
        seed(self.db, 'initial-password', keys={'editorial'}); self.db.commit()
        self.assertEqual(user.role, 'editorial')
        self.assertEqual(personal_profile(self.db, user).id, profile_id)
        self.assertIsNone(self.db.get(AccountPermission, (user.id, 'admin')))
        audit = self.db.scalar(select(AccountAudit).where(AccountAudit.user_id == user.id, AccountAudit.action == 'demo_role_synchronized'))
        self.assertEqual(audit.before_state['role'], 'lector')
        self.assertEqual(audit.after_state['role'], 'editorial')

    def test_invalid_credentials_fail_before_any_account_is_written(self):
        with self.assertRaises(ValueError):
            seed(self.db, 'common-password', passwords={'editorial': 'short'})
        self.assertEqual(self.db.scalar(select(func.count()).select_from(User)), 0)

    def test_selected_profile_does_not_reset_admin_password(self):
        seed(self.db, 'admin-original-password', keys={'admin'}); self.db.commit()
        seed(self.db, 'reader-password', keys={'lector'}); self.db.commit()
        admin = self.db.get(User, stable_id('user:admin'))
        self.assertTrue(verify_password('admin-original-password', admin.auth_account.password_hash))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(User)), 2)

    def test_email_collision_never_takes_over_an_existing_account(self):
        user = User(id=uuid.uuid4(), display_name='Existing person')
        user.auth_account = AuthAccount(email='demo.lector@example.com', password_hash='unchanged')
        self.db.add(user); self.db.commit()
        with self.assertRaises(ValueError):
            seed(self.db, 'common-password', keys={'lector'})
        self.assertEqual(user.auth_account.password_hash, 'unchanged')
