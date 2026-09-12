import unittest
from urllib.parse import parse_qs, urlparse

from app.core.config import Settings
from app.modules.auth.router import build_google_authorization_url


class GoogleIntegrationTest(unittest.TestCase):
    def test_google_settings_load_from_env(self):
        settings = Settings(
            google_client_id="cliente.test.apps.googleusercontent.com",
            google_client_secret="secret-value",
            google_redirect_uri="http://localhost:8000/api/auth/google/callback",
            google_books_api_key="api-key-value",
        )

        self.assertEqual(settings.google_client_id, "cliente.test.apps.googleusercontent.com")
        self.assertEqual(settings.google_client_secret, "secret-value")
        self.assertEqual(settings.google_redirect_uri, "http://localhost:8000/api/auth/google/callback")
        self.assertEqual(settings.google_books_api_key, "api-key-value")

    def test_build_google_authorization_url_includes_books_scope(self):
        url = build_google_authorization_url(
            "cliente.test.apps.googleusercontent.com",
            "http://localhost:8000/api/auth/google/callback",
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme + "://" + parsed.netloc, "https://accounts.google.com")
        self.assertEqual(params["client_id"][0], "cliente.test.apps.googleusercontent.com")
        self.assertEqual(params["redirect_uri"][0], "http://localhost:8000/api/auth/google/callback")
        self.assertIn("https://www.googleapis.com/auth/books", params["scope"][0])
        self.assertEqual(params["response_type"][0], "code")


if __name__ == "__main__":
    unittest.main()
