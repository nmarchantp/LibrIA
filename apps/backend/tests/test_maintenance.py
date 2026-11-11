import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.exceptions import EmailAlreadyRegisteredError
from app.core.maintenance import maintenance_guard
from app.core.security import verify_password
from app.modules.auth.router import router, get_auth_service
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import RegisterRequest


class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(maintenance_mode=True, api_prefix='/api',
                                        session_refresh_cookie_name='libria_refresh', secure_session_cookie=False)
        for target in ('app.core.maintenance.get_settings', 'app.modules.auth.router.get_settings'):
            mocked = patch(target, return_value=self.settings)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.service = MagicMock()
        app = FastAPI()
        app.middleware('http')(maintenance_guard)
        app.add_middleware(CORSMiddleware, allow_origins=['https://libriaverse.cl'], allow_methods=['*'], allow_headers=['*'], allow_credentials=True)
        app.include_router(router, prefix='/api')
        app.dependency_overrides[get_auth_service] = lambda: self.service
        @app.get('/health')
        def health():
            return {'status': 'ok'}
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.data = {'display_name': 'Lector', 'email': 'lector@example.com', 'password': 'password123'}

    def test_status_normal_mode_and_health(self):
        result = self.client.get('/api/status')
        self.assertEqual(result.json(), {'maintenance_mode': True})
        self.assertEqual(result.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.settings.maintenance_mode = False
        self.assertEqual(self.client.get('/api/status').json(), {'maintenance_mode': False})
        self.assertEqual(self.client.post('/api/auth/login', json={}).status_code, 422)

    def test_all_access_paths_are_closed(self):
        for method, path in [('POST', '/auth/login'), ('POST', '/auth/refresh'),
                             ('GET', '/auth/google/login'), ('GET', '/auth/google/callback'),
                             ('POST', '/auth/google/session'), ('GET', '/auth/me'),
                             ('GET', '/books'), ('GET', '/auth/me/')]:
            with self.subTest(path=path):
                result = self.client.request(method, '/api' + path, headers={'Authorization': 'Bearer existing-token'})
                self.assertEqual(result.status_code, 503)
                self.assertEqual(result.json()['detail']['code'], 'maintenance_mode')

    def test_registration_does_not_issue_session(self):
        self.client.cookies.set('libria_refresh', 'previous-token', path='/api/auth')
        result = self.client.post('/api/auth/register', json=self.data)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['status'], 'registered')
        self.assertNotIn('access_token', result.json())
        self.assertIn('Max-Age=0', result.headers['set-cookie'])
        self.service.create_account.assert_called_once()
        self.service.register.assert_not_called()

    def test_duplicate_registration_and_invalid_data(self):
        self.service.create_account.side_effect = EmailAlreadyRegisteredError
        self.assertEqual(self.client.post('/api/auth/register', json=self.data).status_code, 409)
        self.assertEqual(self.client.post('/api/auth/register', json={**self.data, 'password': 'short'}).status_code, 422)

    def test_cors_is_available_on_blocked_responses(self):
        result = self.client.get('/api/auth/me', headers={'Origin': 'https://libriaverse.cl'})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.headers['access-control-allow-origin'], 'https://libriaverse.cl')
        result = self.client.options('/api/auth/register', headers={
            'Origin': 'https://libriaverse.cl', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type'})
        self.assertEqual(result.status_code, 200)

    def test_account_creation_hashes_password_without_creating_session(self):
        repository = MagicMock()
        repository.get_account_by_email.return_value = None
        service = AuthService(repository)
        data = RegisterRequest(**self.data)
        with patch.object(service, '_token_response') as tokens:
            user = service.create_account(data)
        self.assertIs(user, repository.create_account.return_value)
        self.assertTrue(verify_password(data.password, repository.create_account.call_args.args[1]))
        tokens.assert_not_called()
        with patch.object(service, '_token_response', return_value='normal-session') as tokens:
            self.assertEqual(service.register(data), 'normal-session')
        tokens.assert_called_once_with(user)
