"""Demo credential migration without touching the application database."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import Settings
from app.modules.demo.service import prepare_actors
from scripts.seed_demo import configured_passwords


class DemoCredentialsTest(unittest.TestCase):
    def test_admin_key_is_the_fallback_and_profile_keys_are_preserved(self):
        settings = Settings(_env_file=None, libria_demo_admin_password='admin-password',
                            libria_demo_lector_password='reader-password')
        passwords = configured_passwords(settings)
        self.assertEqual(passwords['admin'], 'admin-password')
        self.assertEqual(passwords['lector'], 'reader-password')
        self.assertEqual(passwords['autor'], 'admin-password')
        self.assertNotIn('libria_demo_password', Settings.model_fields)

    @patch('app.modules.users.account_service.revoke_all')
    @patch('app.modules.demo.service.hash_password', return_value='new-hash')
    @patch('app.modules.demo.service.verify_password', return_value=False)
    @patch('app.modules.demo.service.SessionLocal')
    @patch('app.modules.demo.service.get_settings')
    def test_existing_showcase_credentials_follow_admin_key(self, settings, sessions, verify, hash_, revoke):
        from app.modules.demo.service import identifier
        settings.return_value = SimpleNamespace(libria_demo_admin_password='new-admin-password')
        db = sessions.begin.return_value.__enter__.return_value
        user_id = identifier('user:camila')
        account = SimpleNamespace(user_id=user_id, password_hash='old-hash')
        db.scalar.return_value = account
        db.get.return_value = SimpleNamespace(id=user_id, account_status='active', suspended_at=None)
        with patch('app.modules.demo.service.PERSONAS', [('camila', 'Camila Demo', 'lector')]):
            prepare_actors()
        verify.assert_called_once_with('new-admin-password', 'old-hash')
        hash_.assert_called_once_with('new-admin-password')
        self.assertEqual(account.password_hash, 'new-hash')
        revoke.assert_called_once_with(db, user_id, 'demo_credentials_changed')
