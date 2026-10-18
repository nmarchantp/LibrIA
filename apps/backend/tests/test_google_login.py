"""Exercise real ID-token validation and transactional Google account creation."""
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import engine, get_db
from app.core.exceptions import InvalidCredentialsError
from app.modules.auth.repository import AuthRepository
from app.modules.auth.router import router, get_auth_service
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.auth.email_verification import send_verification_email


class GoogleLoginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.service = AuthService(AuthRepository(self.db))
        self.settings = Settings(_env_file=None, google_client_id="client", google_client_secret="secret")
        self.claims = {"sub": uuid.uuid4().hex, "email": uuid.uuid4().hex + "@gmail.com",
                       "email_verified": True, "name": "Lector Google", "iss": "https://accounts.google.com",
                       "aud": "client", "iat": datetime.now(timezone.utc),
                       "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_auth_service] = lambda: self.service
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.settings_patch = patch("app.modules.auth.router.get_settings", return_value=self.settings)
        self.settings_patch.start()

    def tearDown(self):
        self.settings_patch.stop()
        self.client.close()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def register(self, email=None):
        return self.service.register(RegisterRequest(email=email or self.claims["email"], password="password123", display_name="Mi perfil"))

    def verify(self, existing):
        headers = {"Authorization": f"Bearer {existing.access_token}"}
        with patch("app.modules.auth.email_verification.send_verification_email") as send:
            result = self.client.post("/api/auth/google/email/request", headers=headers, json={"email": self.claims["email"]})
            self.assertEqual(result.status_code, 200)
            code = send.call_args.args[1]
        result = self.client.post("/api/auth/google/email/confirm", headers=headers, json={"code": code})
        self.assertEqual(result.status_code, 200)
        return code

    def callback(self, signing_key=None, link_token=None, **changes):
        if link_token:
            login = self.client.post("/api/auth/google/link", headers={"Authorization": f"Bearer {link_token}"})
            self.assertEqual(login.status_code, 200)
            url = login.json()["url"]
        else:
            login = self.client.get("/api/auth/google/login", follow_redirects=False)
            url = login.headers["location"]
        params = parse_qs(urlparse(url).query)
        state = params["state"][0]
        self.assertEqual(params["nonce"][0], state)
        claims = {**self.claims, "nonce": state, **changes}
        token = jwt.encode(claims, signing_key or self.key, algorithm="RS256", headers={"kid": "test-key"})
        upstream = MagicMock()
        upstream.__enter__.return_value.read.return_value = json.dumps({"id_token": token}).encode()
        with patch("app.modules.auth.router.urllib.request.urlopen", return_value=upstream), \
             patch("app.modules.auth.router.google_keys.get_signing_key_from_jwt",
                   return_value=SimpleNamespace(key=self.key.public_key())):
            result = self.client.get("/api/auth/google/callback", params={"code": "code", "state": state}, follow_redirects=False)
        self.assertEqual(result.status_code, 303)
        self.assertNotIn(token, result.text)
        self.assertNotIn(token, result.headers["location"])
        return result

    def test_explicit_link_then_login_and_session_handoff(self):
        existing = self.register()
        self.verify(existing)
        linked = self.callback(link_token=existing.access_token)
        self.assertTrue(linked.headers["location"].endswith("/profile?tab=account&google_link=success"))
        self.assertIsNone(self.client.cookies.get("libria_google_session"))
        result = self.callback()
        self.assertTrue(result.headers["location"].endswith("/auth/google/callback"))
        self.assertIn("HttpOnly", result.headers.get("set-cookie"))
        session = self.client.post("/api/auth/google/session", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["user"]["email"], self.claims["email"])
        self.assertEqual(session.json()["user"]["role"], "lector")
        self.assertEqual(self.client.post("/api/auth/google/session", headers={"Origin": "http://localhost:5173"}).status_code, 401)
        same_user = self.service.google_login(self.claims)
        self.assertEqual(str(same_user.user.id), session.json()["user"]["id"])

    def test_unknown_google_account_cannot_register(self):
        result = self.callback()
        self.assertIn("google_error=account", result.headers["location"])
        self.assertIsNone(self.service.repository.get_account_by_email(self.claims["email"]))
        self.assertIsNone(self.client.cookies.get("libria_google_session"))

    def test_existing_password_account_keeps_both_methods(self):
        existing = self.service.register(RegisterRequest(email=self.claims["email"], password="password123", display_name="Mi perfil"))
        with self.assertRaises(InvalidCredentialsError):
            self.service.google_login(self.claims)
        self.verify(existing)
        self.service.google_link(existing.user.id, self.claims)
        google = self.service.google_login(self.claims)
        password = self.service.login(LoginRequest(email=self.claims["email"], password="password123"))
        self.assertEqual(existing.user.id, google.user.id)
        self.assertEqual(password.user.id, google.user.id)
        self.assertEqual(google.user.display_name, "Mi perfil")

    def test_rejects_invalid_identity_tokens(self):
        for changes in ({"aud": "another-client"}, {"iss": "https://attacker.test"},
                        {"exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
                        {"nonce": "wrong"}, {"email_verified": False}):
            with self.subTest(changes=changes):
                result = self.callback(**changes)
                self.assertIn("google_error=", result.headers["location"])
                self.assertIsNone(self.client.cookies.get("libria_google_session"))

    def test_rejects_untrusted_session_origin(self):
        existing = self.register()
        self.verify(existing)
        self.service.google_link(existing.user.id, self.claims)
        self.callback()
        self.assertEqual(self.client.post("/api/auth/google/session", headers={"Origin": "https://attacker.test"}).status_code, 403)

    def test_rejects_invalid_signature(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        result = self.callback(signing_key=other_key)
        self.assertIn("google_error=failed", result.headers["location"])
        self.assertIsNone(self.client.cookies.get("libria_google_session"))

    def test_expired_handoff_is_rejected(self):
        handoff = jwt.encode({"sub": str(uuid.uuid4()), "aud": "google-session",
                              "exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
                             self.settings.jwt_secret, algorithm="HS256")
        self.client.cookies.set("libria_google_session", handoff)
        self.assertEqual(self.client.post("/api/auth/google/session", headers={"Origin": "http://localhost:5173"}).status_code, 401)

    def test_third_party_email_does_not_automatically_link(self):
        self.claims["email"] = uuid.uuid4().hex + "@example.com"
        self.service.register(RegisterRequest(email=self.claims["email"], password="password123", display_name="Mi perfil"))
        with self.assertRaises(InvalidCredentialsError):
            self.service.google_login(self.claims)

    def test_link_requires_authentication(self):
        self.assertEqual(self.client.post("/api/auth/google/link").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/google/link").status_code, 401)

    def test_link_can_use_a_different_google_email(self):
        existing = self.register(email=uuid.uuid4().hex + "@example.com")
        self.verify(existing)
        self.service.google_link(existing.user.id, self.claims)
        self.assertEqual(self.service.google_login(self.claims).user.id, existing.user.id)

    def test_cannot_link_google_identity_to_two_users(self):
        first = self.register()
        second = self.register(email=uuid.uuid4().hex + "@example.com")
        self.verify(first)
        self.verify(second)
        self.service.google_link(first.user.id, self.claims)
        result = self.callback(link_token=second.access_token)
        self.assertIn("google_link=account", result.headers["location"])
        self.assertEqual(self.service.google_login(self.claims).user.id, first.user.id)

    def test_link_status(self):
        existing = self.register()
        headers = {"Authorization": f"Bearer {existing.access_token}"}
        self.assertFalse(self.client.get("/api/auth/google/link", headers=headers).json()["linked"])
        self.verify(existing)
        self.service.google_link(existing.user.id, self.claims)
        self.assertTrue(self.client.get("/api/auth/google/link", headers=headers).json()["linked"])

    def test_forged_link_intent_is_rejected_before_google_request(self):
        existing = self.register()
        state = "test-state"
        forged = jwt.encode({"sub": str(existing.user.id), "state": state, "aud": "google-link",
                             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                            "an-attacker-secret-with-enough-length", algorithm="HS256")
        self.client.cookies.set("libria_google_state", state)
        self.client.cookies.set("libria_google_link", forged)
        with patch("app.modules.auth.router.urllib.request.urlopen") as upstream:
            result = self.client.get("/api/auth/google/callback", params={"code": "code", "state": state}, follow_redirects=False)
            upstream.assert_not_called()
        self.assertIn("google_link=failed", result.headers["location"])
        self.assertIsNone(self.service.repository.get_user_by_id(existing.user.id).auth_account.google_subject)

    def test_login_clears_previous_link_intent(self):
        existing = self.register()
        self.verify(existing)
        self.client.post("/api/auth/google/link", headers={"Authorization": f"Bearer {existing.access_token}"})
        self.assertIsNotNone(self.client.cookies.get("libria_google_link"))
        self.client.get("/api/auth/google/login", follow_redirects=False)
        self.assertIsNone(self.client.cookies.get("libria_google_link"))

    def test_link_is_blocked_until_email_is_verified(self):
        existing = self.register()
        headers = {"Authorization": f"Bearer {existing.access_token}"}
        self.assertEqual(self.client.post("/api/auth/google/link", headers=headers).status_code, 409)
        with self.assertRaises(InvalidCredentialsError):
            self.service.google_link(existing.user.id, self.claims)

    def test_cannot_link_a_different_google_email_after_verification(self):
        existing = self.register()
        self.verify(existing)
        result = self.callback(link_token=existing.access_token, email="someoneelse@gmail.com")
        self.assertIn("google_link=account", result.headers["location"])
        self.assertIsNone(self.service.repository.get_user_by_id(existing.user.id).auth_account.google_subject)

    def test_verification_code_is_single_use(self):
        existing = self.register()
        code = self.verify(existing)
        result = self.client.post("/api/auth/google/email/confirm", headers={"Authorization": f"Bearer {existing.access_token}"}, json={"code": code})
        self.assertEqual(result.status_code, 400)

    def test_verification_rate_limit_attempts_and_expiration(self):
        existing = self.register()
        headers = {"Authorization": f"Bearer {existing.access_token}"}
        with patch("app.modules.auth.email_verification.send_verification_email") as send:
            result = self.client.post("/api/auth/google/email/request", headers=headers, json={"email": self.claims["email"]})
            self.assertEqual(result.status_code, 200)
            code = send.call_args.args[1]
            self.assertNotIn(code, result.text)
            expires_at = datetime.fromisoformat(result.json()["expires_at"])
            resend_at = datetime.fromisoformat(result.json()["resend_at"])
            self.assertEqual(expires_at - resend_at, timedelta(minutes=4))
            pending = self.client.get("/api/auth/google/link", headers=headers).json()
            self.assertEqual(datetime.fromisoformat(pending["expires_at"]), expires_at)
            self.assertEqual(self.client.post("/api/auth/google/email/request", headers=headers, json={"email": "other@gmail.com"}).status_code, 429)
            self.assertEqual(send.call_count, 1)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/google/email/confirm", headers=headers, json={"code": wrong}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/google/email/confirm", headers=headers, json={"code": code}).status_code, 400)
        account = self.service.repository.get_user_by_id(existing.user.id).auth_account
        self.assertNotEqual(account.google_email_code_hash, code)
        account.google_email_code_attempts = 0
        account.google_email_code_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.client.post("/api/auth/google/email/confirm", headers=headers, json={"code": code}).status_code, 400)
        self.assertIsNone(account.google_email_verified_at)

    def test_delivery_failure_does_not_save_pending_email(self):
        existing = self.register()
        with patch("app.modules.auth.email_verification.send_verification_email", side_effect=HTTPException(502, "Delivery failed")):
            result = self.client.post("/api/auth/google/email/request", headers={"Authorization": f"Bearer {existing.access_token}"}, json={"email": self.claims["email"]})
        self.assertEqual(result.status_code, 502)
        self.assertIsNone(self.service.repository.get_user_by_id(existing.user.id).auth_account.google_email)

    def test_new_code_invalidates_previous_verified_email(self):
        existing = self.register()
        self.verify(existing)
        account = self.service.repository.get_user_by_id(existing.user.id).auth_account
        account.google_email_code_sent_at -= timedelta(minutes=2)
        self.db.commit()
        headers = {"Authorization": f"Bearer {existing.access_token}"}
        with patch("app.modules.auth.email_verification.send_verification_email"):
            result = self.client.post("/api/auth/google/email/request", headers=headers, json={"email": "new@gmail.com"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.post("/api/auth/google/link", headers=headers).status_code, 409)

    def test_cancelled_consent_clears_state(self):
        login = self.client.get("/api/auth/google/login", follow_redirects=False)
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        result = self.client.get("/api/auth/google/callback", params={"error": "access_denied", "state": state}, follow_redirects=False)
        self.assertIn("google_error=cancelled", result.headers["location"])
        self.assertIsNone(self.client.cookies.get("libria_google_state"))


class VerificationMailTest(unittest.TestCase):
    def test_gmail_delivery_uses_tls_and_app_password(self):
        settings = Settings(_env_file=None, smtp_username="sender@gmail.com", smtp_password="abcd efgh ijkl mnop")
        with patch("app.modules.auth.email_verification.get_settings", return_value=settings), \
             patch("app.modules.auth.email_verification.smtplib.SMTP_SSL") as connection:
            smtp = connection.return_value.__enter__.return_value
            smtp.send_message.return_value = {}
            send_verification_email("recipient@gmail.com", "123456")
            smtp.login.assert_called_once_with("sender@gmail.com", "abcdefghijklmnop")
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message["To"], "recipient@gmail.com")
            self.assertIn("123456", message.get_body(preferencelist=("plain",)).get_content())
            html = message.get_body(preferencelist=("html",)).get_content()
            self.assertIn("123456", html)
            self.assertIn("5 minutos", html)
            self.assertIn('src="cid:libriaverse-logo"', html)
            logo = next(part for part in message.walk() if part.get_content_type() == "image/png")
            self.assertEqual(logo["Content-ID"], "<libriaverse-logo>")
            self.assertEqual(logo.get_content_disposition(), "inline")
            self.assertTrue(logo.get_payload(decode=True).startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(connection.call_args.args, ("smtp.gmail.com", 465))

    def test_missing_credentials_never_reports_delivery(self):
        settings = Settings(_env_file=None)
        with patch("app.modules.auth.email_verification.get_settings", return_value=settings), \
             patch("app.modules.auth.email_verification.smtplib.SMTP_SSL") as connection:
            with self.assertRaises(HTTPException) as error:
                send_verification_email("recipient@gmail.com", "123456")
            self.assertEqual(error.exception.status_code, 503)
            connection.assert_not_called()
