import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

import jwt
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.main import app


class SecurityTest(unittest.TestCase):
    def test_token_requires_expiration(self):
        settings = get_settings()
        token = jwt.encode({"sub": "someone"}, settings.jwt_secret, algorithm="HS256")
        self.assertIsNone(decode_access_token(token))

    def test_production_rejects_default_secret(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, app_env="production")

    def test_blank_registration_name(self):
        with TestClient(app) as client:
            result = client.post("/api/auth/register", json={"email": "test@example.com", "password": "password123", "display_name": "   "})
            self.assertEqual(result.status_code, 422)

    def test_oauth_state_and_no_token_disclosure(self):
        settings = Settings(_env_file=None, google_client_id="client", google_client_secret="secret")
        with patch("app.modules.auth.router.get_settings", return_value=settings), \
             patch("app.modules.auth.router.urllib.request.urlopen") as upstream, TestClient(app) as client:
            self.assertEqual(client.get("/api/auth/google/callback?code=test").status_code, 400)
            upstream.assert_not_called()
            login = client.get("/api/auth/google/login", follow_redirects=False)
            state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
            self.assertEqual(client.get("/api/auth/google/callback", params={"code": "test", "state": "wrong"}).status_code, 400)
            upstream.assert_not_called()
            response = MagicMock()
            response.read.return_value = b'{"access_token":"sensitive","refresh_token":"very-sensitive"}'
            upstream.return_value.__enter__.return_value = response
            result = client.get("/api/auth/google/callback", params={"code": "test", "state": state})
            self.assertEqual(result.status_code, 200)
            self.assertNotIn("sensitive", result.text)
            self.assertEqual(result.headers["cache-control"], "no-store")
            self.assertEqual(client.get("/api/auth/google/callback", params={"code": "test", "state": state}).status_code, 400)
