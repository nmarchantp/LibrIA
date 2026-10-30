"""Real PostgreSQL transactions; every test rolls back its generated accounts."""
import io
import unittest
import uuid
from datetime import timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.main import app as full_app
from app.core.database import engine, get_db
from app.modules.auth.router import router as auth_router
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.auth.models import AuthSession
from app.modules.users.account_router import router
from app.modules.users.account_models import AccountAudit, AccountChallenge, AccountAvatar
from app.modules.users.account_service import now, issue_challenge, request_deletion
from app.modules.users.account_lifecycle import process_expired_accounts
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission, Profile, ProfileMember
from app.modules.users.verification_models import VerificationRequest
from app.modules.users.identity_models import ProfileCapability


class AccountManagementTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.service = AuthService(AuthRepository(self.db))
        app = FastAPI()
        app.include_router(auth_router, prefix="/api")
        app.include_router(router, prefix="/api")
        from app.modules.users.roles_router import router as roles_router
        app.include_router(roles_router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.grant = self.register()
        self.user = self.db.get(User, self.grant.user.id)
        self.headers = {"Authorization": f"Bearer {self.grant.access_token}"}

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def register(self):
        return self.service.register(RegisterRequest(email=uuid.uuid4().hex + "@example.com",
            password="password123", display_name="Cuenta de prueba"))

    def post(self, path, data):
        return self.client.post('/api/accounts' + path, headers=self.headers, json=data)

    def admin(self):
        grant = self.register()
        self.db.add(AccountPermission(user_id=grant.user.id, permission="admin"))
        self.db.commit()
        return {"Authorization": f"Bearer {grant.access_token}"}

    def challenge(self, purpose):
        token = issue_challenge(self.db, self.user, purpose)
        self.db.commit()
        return token

    def pending(self):
        response = self.post('/me/deletion', {"current_password": "password123"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_registration_and_account_contract(self):
        account = self.client.get('/api/accounts/me', headers=self.headers).json()
        self.assertTrue(account['username'].startswith('reader_'))
        self.assertEqual(account['role'], 'lector')
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).json()['username'], account['username'])
        self.assertNotIn('password_hash', account)

    def test_public_updates_preserve_identity_and_profile(self):
        old_username = self.user.username
        response = self.client.patch('/api/accounts/me', headers=self.headers,
            json={"display_name": "Otro nombre", "biography": "📚" * 70})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['username'], old_username)
        self.assertEqual(response.json()['id'], str(self.user.id))
        self.assertEqual(self.db.scalar(select(Profile.display_name).where(Profile.owner_user_id == self.user.id)), "Otro nombre")
        for extra in ({"username": "otro"}, {"role": "admin"}, {"biography": "📚" * 71}):
            result = self.client.patch('/api/accounts/me', headers=self.headers, json={"display_name": "Otro nombre", **extra})
            self.assertEqual(result.status_code, 422)

    def test_password_verification_and_session_revocation(self):
        self.assertEqual(self.post('/me/password', {"current_password": "wrong", "new_password": "newpassword123"}).status_code, 400)
        self.assertEqual(self.post('/me/password', {"current_password": "password123", "new_password": "newpassword123"}).status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)
        result = self.client.post('/api/auth/login', json={"email": self.user.auth_account.email, "password": "newpassword123"})
        self.assertEqual(result.status_code, 200, result.text)

    def test_reset_challenge_hash_single_use_and_expiration(self):
        token = self.challenge('password_reset')
        saved = self.db.scalar(select(AccountChallenge).where(AccountChallenge.user_id == self.user.id))
        self.assertNotEqual(saved.token_hash, token)
        result = self.post('/recovery/password', {"token": token, "new_password": "newpassword123"})
        self.assertEqual(result.status_code, 204, result.text)
        self.assertEqual(self.post('/recovery/password', {"token": token, "new_password": "anotherpassword"}).status_code, 400)
        self.assertIsNotNone(self.user.auth_account.email_verified_at)

    def test_recovery_email_does_not_return_token(self):
        with patch('app.modules.users.account_router.send_account_email') as mail:
            response = self.post('/recovery/request?purpose=password_reset', {"email": self.user.auth_account.email})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mail.called)
            self.assertNotIn('token', response.json())
        unknown = self.post('/recovery/request?purpose=password_reset', {"email": uuid.uuid4().hex + '@example.com'})
        self.assertEqual(unknown.json(), response.json())

    def test_email_change_keeps_old_until_confirmation(self):
        old = self.user.auth_account.email
        new = uuid.uuid4().hex + '@example.com'
        with patch('app.modules.users.account_router.send_account_email') as mail:
            response = self.post('/me/email/request', {"current_password": "password123", "email": new})
            self.assertEqual(response.status_code, 200, response.text)
            token = mail.call_args.args[2].split('\n')[-1]
            self.assertEqual(self.user.auth_account.email, old)
            self.assertEqual(self.post('/me/email/confirm', {"token": token}).status_code, 204)
            self.assertEqual(mail.call_args.args[0], old)
        self.assertEqual(self.user.auth_account.email, new)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)

    def test_email_conflict_is_case_insensitive(self):
        other = self.register()
        result = self.post('/me/email/request', {"current_password": "password123", "email": other.user.email.upper()})
        self.assertEqual(result.status_code, 409)

    def test_google_unlink_requires_verified_alternative(self):
        self.user.auth_account.google_subject = uuid.uuid4().hex
        self.db.commit()
        self.assertEqual(self.post('/me/google/unlink', {"current_password": "password123"}).status_code, 409)
        self.user.auth_account.email_verified_at = now()
        self.db.commit()
        self.assertEqual(self.post('/me/google/unlink', {"current_password": "wrong"}).status_code, 400)
        self.assertEqual(self.post('/me/google/unlink', {"current_password": "password123"}).status_code, 204)
        self.assertIsNone(self.user.auth_account.google_subject)

    def test_deletion_exact_thirty_days_and_blocks_access(self):
        result = self.pending()
        self.assertEqual(self.user.deletion_scheduled_at - self.user.deletion_requested_at, timedelta(days=30))
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={"email": self.user.auth_account.email, "password": "password123"}).status_code, 403)
        self.assertEqual(self.db.scalar(select(func_count()).where(AuthSession.user_id == self.user.id, AuthSession.revoked_at.is_(None))), 0)

    def test_cancel_deletion_preserves_suspension(self):
        self.pending()
        self.user.suspended_at = now()
        self.db.commit()
        token = self.challenge('recover_deletion')
        response = self.post('/recovery/deletion', {"token": token})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['suspended'])
        self.assertEqual(self.user.account_status, 'active')
        self.assertIsNone(self.user.deletion_scheduled_at)
        self.assertEqual(process_expired_accounts(self.db), 0)

    def test_expired_cannot_recover_and_processing_is_idempotent(self):
        self.pending()
        token = self.challenge('recover_deletion')
        self.user.deletion_requested_at = now() - timedelta(days=31)
        self.user.deletion_scheduled_at = self.user.deletion_requested_at + timedelta(days=30)
        self.db.commit()
        self.assertEqual(self.post('/recovery/deletion', {"token": token}).status_code, 400)
        profile_id = self.db.scalar(select(Profile.id).where(Profile.owner_user_id == self.user.id))
        old_id = self.user.id
        self.assertEqual(process_expired_accounts(self.db), 1)
        self.db.commit()
        self.assertEqual(process_expired_accounts(self.db), 0)
        self.assertEqual(self.user.id, old_id)
        self.assertEqual(self.db.get(Profile, profile_id).display_name, 'Cuenta eliminada')
        self.assertEqual(self.user.account_status, 'anonymized')
        self.assertIsNone(self.user.biography)
        self.assertIsNone(self.user.auth_account.google_subject)

    def test_avatar_validated_reencoded_removed_and_audited(self):
        self.assertEqual(self.client.put('/api/accounts/me/avatar', headers=self.headers,
            files={"file": ('photo.png', b'<script>bad</script>', 'image/png')}).status_code, 422)
        output = io.BytesIO()
        Image.new('RGB', (5, 5)).save(output, 'PNG')
        response = self.client.put('/api/accounts/me/avatar', headers=self.headers,
            files={"file": ('photo.png', output.getvalue(), 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        avatar = self.db.get(AccountAvatar, self.user.id)
        self.assertEqual(avatar.content_type, 'image/jpeg')
        self.assertEqual(self.client.get(response.json()['avatar_url']).headers['x-content-type-options'], 'nosniff')
        self.assertEqual(self.client.delete('/api/accounts/me/avatar', headers=self.headers).status_code, 204)
        self.assertTrue(self.db.scalar(select(AccountAudit.id).where(AccountAudit.user_id == self.user.id, AccountAudit.action == 'avatar_updated')))

    def test_admin_permissions_suspension_and_reactivation(self):
        path = f'/api/accounts/admin/{self.user.id}/suspension'
        body = {"suspended": True, "reason": "Revisión administrativa"}
        self.assertEqual(self.client.patch(path, headers=self.headers, json=body).status_code, 403)
        admin = self.admin()
        self.assertEqual(self.client.patch(path, headers=admin, json=body).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)
        body['suspended'] = False
        self.assertEqual(self.client.patch(path, headers=admin, json=body).status_code, 200)
        self.assertIsNone(self.user.suspended_at)
        rows = self.client.get('/api/accounts/admin', params={"state": "active", "q": self.user.username}, headers=admin).json()
        self.assertIn(str(self.user.id), [u['id'] for u in rows['items']])

    def test_role_requires_verification_and_admin_cannot_self_change(self):
        admin = self.admin()
        response = self.client.patch(f'/api/accounts/admin/{self.user.id}/role', headers=admin,
            json={"role": "autor", "reason": "Cambio administrativo revisado"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.user.role, 'lector')
        admin_id = self.client.get('/api/auth/me', headers=admin).json()['id']
        self.assertEqual(self.client.patch(f'/api/accounts/admin/{admin_id}/role', headers=admin,
            json={"role": "admin", "reason": "Intento de modificación propia"}).status_code, 403)

    def test_only_admin_can_request_and_approve_exclusive_bookstore_role(self):
        self.assertEqual(self.client.post('/api/roles/requests', headers=self.headers,
            json={"requested_role": "autor", "note": "Solicitud del titular"}).status_code, 403)
        admin = self.admin()
        request = self.client.post(f'/api/accounts/admin/{self.user.id}/verification', headers=admin,
            json={"requested_role": "libreria", "note": "Evidencia comercial revisada"})
        self.assertEqual(request.status_code, 201, request.text)
        response = self.client.post(f"/api/roles/requests/{request.json()['id']}/approve", headers=admin)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.user.role, 'libreria')
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)
        new = self.client.post('/api/auth/login', json={"email": self.user.auth_account.email, "password": "password123"})
        self.assertEqual(new.json()['user']['role'], 'libreria')

    def test_admin_role_changes_require_reason_and_update_permission(self):
        admin = self.admin()
        path = f'/api/accounts/admin/{self.user.id}/role'
        self.assertEqual(self.client.patch(path, headers=admin, json={"role": "admin"}).status_code, 422)
        response = self.client.patch(path, headers=admin, json={"role": "admin", "reason": "Autorización administrativa expresa"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(self.db.get(AccountPermission, (self.user.id, 'admin')))

    def test_expired_and_wrong_purpose_tokens_rejected(self):
        token = self.challenge('password_reset')
        self.assertEqual(self.post('/recovery/deletion', {"token": token}).status_code, 400)
        self.db.execute(update(AccountChallenge).where(AccountChallenge.user_id == self.user.id).values(expires_at=now()-timedelta(seconds=1)))
        self.db.commit()
        self.assertEqual(self.post('/recovery/password', {"token": token, "new_password": "newpassword123"}).status_code, 400)

    def test_recovery_response_same_when_throttled(self):
        with patch('app.modules.users.account_router.send_account_email') as mail:
            one = self.post('/recovery/request?purpose=password_reset', {"email": self.user.auth_account.email})
            two = self.post('/recovery/request?purpose=password_reset', {"email": self.user.auth_account.email})
            self.assertEqual(one.json(), two.json())
            self.assertEqual(mail.call_count, 1)

    def test_sole_organization_administrator_cannot_be_orphaned(self):
        organization = Profile(kind='organization', organization_type='libreria', display_name='Organización histórica')
        self.db.add(organization)
        self.db.flush()
        self.db.add(ProfileMember(profile_id=organization.id, user_id=self.user.id, permission='admin'))
        self.db.commit()
        self.assertEqual(self.post('/me/deletion', {"current_password": "password123"}).status_code, 409)
        self.assertEqual(self.user.account_status, 'active')

    def test_session_revocation_is_owner_scoped(self):
        other = self.register()
        self.assertEqual(self.client.delete(f'/api/accounts/me/sessions/{other.session_id}', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/accounts/me/sessions/{self.grant.session_id}', headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)

    def test_rotating_refresh_reuse_still_revokes_the_session(self):
        from app.modules.auth.sessions import rotate_refresh_token, validate_access_session, SessionValidationError
        rotated = rotate_refresh_token(self.db, self.grant.refresh_token)
        self.assertNotEqual(rotated.refresh_token, self.grant.refresh_token)
        with self.assertRaises(SessionValidationError) as failure:
            rotate_refresh_token(self.db, self.grant.refresh_token)
        self.assertEqual(failure.exception.code, 'refresh_reuse')
        with self.assertRaises(SessionValidationError):
            validate_access_session(self.db, rotated.access_token)

    def test_password_change_invalidates_in_flight_google_handoff(self):
        import jwt
        from app.core.config import get_settings
        handoff = jwt.encode({"sub": str(self.user.id), "aud": "google-session", "sv": 0,
            "exp": now()+timedelta(seconds=60)}, get_settings().jwt_secret, algorithm='HS256')
        self.assertEqual(self.post('/me/password', {"current_password": "password123", "new_password": "newpassword123"}).status_code, 204)
        self.client.cookies.set('libria_google_session', handoff)
        self.assertEqual(self.client.post('/api/auth/google/session').status_code, 401)

    def test_restricted_owner_cannot_make_queued_ai_provider_calls(self):
        from unittest.mock import Mock
        from app.core.config import get_settings
        from app.modules.analytics.models import AIJob
        from app.modules.analytics.gemini_worker import _invoke, AttemptBudget, PermanentJobError
        job = AIJob(owner_id=self.user.id, target='account-test:'+uuid.uuid4().hex)
        self.db.add(job)
        self.user.suspended_at = now()
        self.db.commit()
        provider = Mock()
        with self.assertRaises(PermanentJobError) as failure:
            _invoke(self.db, provider, None, AttemptBudget(max_calls=1, max_tokens=1000, job_id=job.id), get_settings())
        self.assertEqual(str(failure.exception), 'account_restricted')
        provider.generate_structured.assert_not_called()

    def test_anonymization_preserves_library_reviews_posts_and_revisions(self):
        from app.modules.books.models import Work
        from app.modules.library.models import LibraryEntry, Reading
        from app.modules.social.models import Review, ReviewRevision, Post
        work = Work(title='Obra histórica de prueba')
        self.db.add(work)
        self.db.flush()
        entry = LibraryEntry(user_id=self.user.id, work_id=work.id)
        self.db.add(entry)
        self.db.flush()
        reading = Reading(library_entry_id=entry.id, work_id=work.id, status='pending')
        profile = self.db.scalar(select(Profile).where(Profile.owner_user_id == self.user.id))
        review = Review(author_profile_id=profile.id, created_by_user_id=self.user.id, work_id=work.id,
            body='Reseña histórica', status='published', published_at=now())
        post = Post(user_id=self.user.id, author_profile_id=profile.id, author_role='lector',
            source='community', kind='community', body='Contenido conservado')
        self.db.add_all([reading, review, post])
        self.db.flush()
        revision = ReviewRevision(review_id=review.id, revision_number=1, recorded_by_user_id=self.user.id,
            body=review.body, is_spoiler=False, status='published')
        self.db.add(revision)
        self.db.commit()
        self.client.patch('/api/accounts/me', headers=self.headers,
            json={"display_name": "Nombre que debe minimizarse", "biography": "Biografía privada al eliminar"})
        self.pending()
        self.user.deletion_requested_at = now() - timedelta(days=31)
        self.user.deletion_scheduled_at = self.user.deletion_requested_at + timedelta(days=30)
        self.db.commit()
        self.assertEqual(process_expired_accounts(self.db), 1)
        self.db.commit()
        self.assertEqual(self.db.get(LibraryEntry, entry.id).user_id, self.user.id)
        self.assertEqual(self.db.get(Reading, reading.id).library_entry_id, entry.id)
        self.assertEqual(self.db.get(Review, review.id).body, 'Reseña histórica')
        self.assertIsNotNone(self.db.get(ReviewRevision, (review.id, 1)))
        self.assertEqual(self.db.get(Post, post.id).body, 'Contenido conservado')
        for row in self.db.scalars(select(AccountAudit).where(AccountAudit.user_id == self.user.id)):
            self.db.refresh(row)
            self.assertNotIn('display_name', row.before_state)
            self.assertNotIn('biography', row.after_state)

    def test_avatar_size_limit(self):
        response = self.client.put('/api/accounts/me/avatar', headers=self.headers,
            files={"file": ('photo.jpg', b'x' * (2*1024*1024+1), 'image/jpeg')})
        self.assertEqual(response.status_code, 413)

    def test_audit_sanitization_admin_visibility_and_immutability(self):
        self.post('/me/password', {"current_password": "password123", "new_password": "newpassword123"})
        admin = self.admin()
        result = self.client.get(f'/api/accounts/admin/{self.user.id}/history', headers=admin)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('password123', result.text)
        self.assertNotIn('password_hash', result.text)
        self.assertTrue(all('correlation_id' in a for a in result.json()))
        with self.db.begin_nested():
            with self.assertRaises(Exception):
                self.db.execute(text('DELETE FROM app.auditoria_cuentas WHERE user_id=:id'), {'id': self.user.id})
            self.db.rollback()


def func_count():
    from sqlalchemy import func
    return func.count(AuthSession.id)
