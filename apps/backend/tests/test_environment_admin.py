import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core import environment_admin as env


class EnvironmentAdminTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        for target in ('backend', 'web'):
            (self.root / target).mkdir()
        (self.root / 'backend' / '.env').write_text('# keep comment\nJWT_SECRET=private-value\nCATALOG_DISCOVERY_ENABLED=false\n', encoding='utf-8')
        self.paths = patch.object(env, 'APPS', self.root)
        self.paths.start()
        self.app = FastAPI()
        self.app.include_router(env.router)
        self.app.dependency_overrides[env.get_admin] = lambda: object()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.paths.stop()
        self.directory.cleanup()

    def test_secrets_are_hidden_and_preserved_on_edit(self):
        response = self.client.get('/admin/environment/backend')
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertNotIn('private-value', response.text)
        result = self.client.patch('/admin/environment/backend', json={
            'revision': response.json()['revision'], 'values': {'APP_NAME': 'My app'}})
        self.assertEqual(result.status_code, 200, result.text)
        raw = (self.root / 'backend' / '.env').read_text()
        self.assertIn('JWT_SECRET=private-value', raw)
        self.assertIn('# keep comment', raw)

    def test_rejects_stale_revision_unknown_keys_and_invalid_bundle(self):
        revision = env.snapshot('backend')['revision']
        for values, token, status in [({'APP_NAME': 'x'}, 'stale', 409),
                                      ({'UNKNOWN': 'x'}, revision, 422),
                                      ({'CATALOG_CANONICAL_ENABLED': 'true'}, revision, 422),
                                      ({'APP_NAME': 'a\nb'}, revision, 422)]:
            result = self.client.patch('/admin/environment/backend', json={'revision': token, 'values': values})
            self.assertEqual(result.status_code, status, result.text)

    def test_web_url_validation_and_write(self):
        revision = env.snapshot('web')['revision']
        for value, expected in [('javascript:alert(1)', 422), ('https://example.com/api', 200)]:
            result = self.client.patch('/admin/environment/web', json={'revision': revision, 'values': {'VITE_API_URL': value}})
            self.assertEqual(result.status_code, expected, result.text)

    def test_all_routes_require_admin(self):
        def deny():
            raise HTTPException(403, 'Se requiere una cuenta administradora')
        self.app.dependency_overrides[env.get_admin] = deny
        for target in ('backend', 'web'):
            self.assertEqual(self.client.get('/admin/environment/' + target).status_code, 403)
            self.assertEqual(self.client.patch('/admin/environment/' + target, json={'revision': '', 'values': {}}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
