"""RF-INF-001..004 integration tests; refuse non-disposable databases."""
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import get_settings
from app.core.database import engine, get_db
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission, ProfileCapability
from app.modules.users.identities import personal_profile
from app.modules.users.verification_models import VerificationRequest
from app.modules.users.account_models import AccountAudit
from app.modules.users.profile_models import ProfileRoleChange
from app.modules.books.models import Work, Edition, CatalogSource
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent
from app.modules.social.models import Post, Review, ProfileFollow, PostLike


APPLICATION = {'requested_role': 'influencer', 'activity_description': 'Comparto reseñas literarias en mi canal.',
    'topics': ['Fantasía', 'Ciencia ficción'], 'motivation': 'Quiero conectar con lectores y compartir recomendaciones.',
    'evidence_links': ['https://www.youtube.com/@lecturas']}
OBSERVATION = 'Actividad literaria comprobada por administración.'


def require_isolated_database():
    if engine.url.database != 'libria_influencer_access_test' or get_settings().app_env != 'test':
        raise RuntimeError('Use compose.influencer-test.yaml; never run against development data')


class InfluencerAccessTest(unittest.TestCase):
    def setUp(self):
        require_isolated_database()
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode='create_savepoint')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.reader, self.admin = self.register(), self.register()
        administrator = self.user(self.admin)
        administrator.role = 'admin'
        self.db.add(AccountPermission(user_id=administrator.id, permission='admin'))
        self.db.commit()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def register(self):
        response = self.client.post('/api/auth/register', json={'email': uuid.uuid4().hex + '@example.com',
            'password': 'password123', 'display_name': 'Literary account'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def user(self, account):
        return self.db.get(User, uuid.UUID(account['user']['id']))

    def headers(self, account=None):
        return {'Authorization': 'Bearer ' + (account or self.reader)['access_token']}

    def submit(self, payload=None, account=None):
        return self.client.post('/api/roles/requests', headers=self.headers(account), json=payload or APPLICATION)

    def decide(self, identifier, action='approve', account=None, reason=OBSERVATION):
        return self.client.post(f'/api/roles/requests/{identifier}/{action}', headers=self.headers(account or self.admin), json={'reason': reason})

    def promote(self):
        request = self.submit()
        self.assertEqual(request.status_code, 201, request.text)
        result = self.decide(request.json()['id'])
        self.assertEqual(result.status_code, 200, result.text)
        self.reader = self.client.post('/api/auth/login', json={'email': self.reader['user']['email'], 'password': 'password123'}).json()
        return result.json()

    def suspend(self, account=None, until=None, reason='Suspensión temporal de permisos por revisión.'):
        return self.client.post(f"/api/roles/profiles/{self.reader['user']['id']}/influencer-suspension",
            headers=self.headers(account or self.admin), json={'reason': reason,
                'until': until or (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()})

    def post(self, body='Una novedad para la comunidad.'):
        return self.client.post('/api/posts', headers=self.headers(), json={'source': 'community', 'kind': 'community', 'publication_type': 'news', 'body': body})

    def test_application_fields_pending_uniqueness_and_private_history(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.text)
        for key in APPLICATION:
            self.assertEqual(response.json()[key], APPLICATION[key])
        self.assertEqual(response.json()['status'], 'pending')
        self.assertEqual(self.submit().status_code, 409)
        self.assertEqual(self.client.get('/api/roles/requests/me', headers=self.headers(self.admin)).json(), [])
        self.assertEqual(self.client.get('/api/roles/requests/pending', headers=self.headers()).status_code, 403)
        self.assertEqual(self.client.post('/api/roles/requests', json=APPLICATION).status_code, 401)

    def test_application_requires_all_fields_and_valid_public_links(self):
        for field in ('activity_description', 'topics', 'motivation', 'evidence_links'):
            for bad in (None, '' if field in ('activity_description', 'motivation') else []):
                response = self.submit({**APPLICATION, field: bad})
                self.assertEqual(response.status_code, 422, response.text)
        for link in ('javascript:alert(1)', 'file:///etc/passwd', 'http://localhost',
                     'http://127.0.0.1', 'https://user:password@example.com', 'https://example.com:8443'):
            response = self.submit({**APPLICATION, 'evidence_links': [link]})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.submit({**APPLICATION, 'user_id': self.admin['user']['id']}).status_code, 422)

    def test_other_profiles_cannot_request_and_role_label_does_not_grant_admin(self):
        owner = self.user(self.reader)
        for role in ('autor', 'influencer', 'libreria', 'admin'):
            owner.role = role; self.db.flush()
            self.assertEqual(self.submit().status_code, 403)
        owner.role = 'lector'; self.db.flush()
        self.assertEqual(self.submit({'requested_role': 'autor', 'note': 'Solicitud de escritor.'}).status_code, 403)
        request = self.submit().json()
        owner.role = 'admin'; self.db.flush()
        self.assertEqual(self.decide(request['id'], account=self.reader).status_code, 403)

    def test_rejection_records_observation_responsible_date_audit_and_allows_retry(self):
        request = self.submit().json()
        response = self.decide(request['id'], 'reject', reason='Falta evidencia de actividad literaria verificable.')
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['decided_by_user_id'], self.admin['user']['id'])
        self.assertIsNotNone(result['decided_by_name'])
        self.assertIsNotNone(result['decided_at'])
        self.assertNotEqual(result['decision_reason'], result['motivation'])
        history = self.client.get('/api/roles/requests/me', headers=self.headers()).json()
        self.assertEqual(history[0], result)
        event = self.db.scalar(select(AccountAudit).where(AccountAudit.user_id == self.user(self.reader).id,
            AccountAudit.action == 'professional_verification_rejected'))
        self.assertEqual(event.reason, result['decision_reason'])
        self.assertEqual(self.decide(request['id']).status_code, 409)
        self.assertEqual(self.submit().status_code, 201)

    def test_decision_requires_observation_admin_and_no_self_decision(self):
        identifier = self.submit().json()['id']
        self.assertEqual(self.decide(identifier, reason='').status_code, 422)
        self.assertEqual(self.client.post(f'/api/roles/requests/{identifier}/approve', headers=self.headers(self.admin)).status_code, 422)
        self.assertEqual(self.decide(identifier, account=self.reader).status_code, 403)
        self.db.add(AccountPermission(user_id=self.user(self.reader).id, permission='admin')); self.db.flush()
        for action in ('approve', 'reject'):
            self.assertEqual(self.decide(identifier, action, account=self.reader).status_code, 403)
        self.assertEqual(self.db.get(VerificationRequest, uuid.UUID(identifier)).status, 'pending')

    def fixture_activity(self):
        owner = self.user(self.reader)
        profile = personal_profile(self.db, owner)
        work = Work(title='Canonical fixture'); self.db.add(work); self.db.flush()
        edition = Edition(work_id=work.id, title=work.title, language='es', page_count=100); self.db.add(edition); self.db.flush()
        self.db.add(CatalogSource(edition_id=edition.id, provider='libria-feed', external_id=str(work.id), fetched_at=datetime.now(timezone.utc)))
        entry = LibraryEntry(user_id=owner.id, work_id=work.id); self.db.add(entry); self.db.flush()
        reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=edition.id, status='reading',
            current_page=10, total_pages=100, started_at=datetime.now(timezone.utc)); self.db.add(reading); self.db.flush()
        event = ReadingEvent(reading_id=reading.id, actor_user_id=owner.id, kind='progress', previous_page=0, page=10, total_pages=100, is_public=True)
        review = Review(author_profile_id=profile.id, created_by_user_id=owner.id, work_id=work.id, body='Mi reseña original', status='draft')
        note = Post(user_id=owner.id, author_profile_id=profile.id, author_role=owner.role, source='community', kind='community', publication_type='note', body='Mi nota original', work_id=work.id, book_ref=str(work.id), book_title=work.title)
        follow = ProfileFollow(profile_id=profile.id, user_id=self.user(self.admin).id)
        self.db.add_all([event, review, note, follow]); self.db.flush()
        self.db.add(PostLike(post_id=note.id, user_id=self.user(self.admin).id)); self.db.commit()
        return profile, work, reading, review, note, event

    def test_activation_preserves_reading_data_identity_followers_activity_and_invalidates_old_session(self):
        profile, work, reading, review, note, event = self.fixture_activity()
        old_id, old_token = self.reader['user']['id'], self.reader['access_token']
        self.promote()
        self.assertEqual(self.reader['user']['id'], old_id)
        self.assertEqual(self.reader['user']['role'], 'influencer')
        self.assertEqual(personal_profile(self.db, self.user(self.reader)).id, profile.id)
        for model, identifier in ((Work, work.id), (Reading, reading.id), (Review, review.id), (Post, note.id), (ReadingEvent, event.id)):
            self.assertIsNotNone(self.db.get(model, identifier))
        self.assertIsNotNone(self.db.get(ProfileFollow, (profile.id, self.user(self.admin).id)))
        self.assertIsNotNone(self.db.get(PostLike, (note.id, self.user(self.admin).id)))
        self.assertEqual(note.author_role, 'lector')
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + old_token}).status_code, 401)
        self.assertEqual(self.post().status_code, 201)

    def test_suspension_blocks_professional_create_edit_and_events_but_keeps_reader_functions(self):
        self.promote()
        profile, work, reading, review, note, event = self.fixture_activity()
        post = self.post().json()
        response = self.suspend()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['influencer_permissions_suspended'])
        self.assertEqual(self.post().status_code, 403)
        payload = {'source': 'community', 'kind': 'community', 'publication_type': 'news', 'body': 'Contenido editado.'}
        self.assertEqual(self.client.put(f"/api/posts/{post['id']}", headers=self.headers(), json=payload).status_code, 403)
        self.assertEqual(self.client.post('/api/posts', headers=self.headers(), json={**payload, 'source': 'event', 'publication_type': 'event'}).status_code, 403)
        self.assertEqual(self.client.get('/api/readings/me', headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.put('/api/me/reading-challenge', headers=self.headers(), json={'target': 12}).status_code, 200)
        self.assertEqual(self.client.put(f"/api/activities/publication/{post['id']}/like", headers=self.headers(self.admin)).status_code, 200)
        response = self.client.put(f'/api/posts/{note.id}', headers=self.headers(), json={**payload, 'publication_type': 'note', 'work_id': str(work.id), 'book_ref': str(work.id), 'book_title': work.title})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.get(Post, uuid.UUID(post['id'])).author_role, 'influencer')
        state = self.client.get('/api/roles/me/influencer-permissions', headers=self.headers()).json()
        self.assertTrue(state['suspended']); self.assertIn('revisión', state['reason'])
        permissions = self.client.get('/api/profiles/me', headers=self.headers()).json()
        self.assertFalse(permissions[0]['can_publish'])

    def test_temporary_expiry_manual_resume_and_audit(self):
        self.promote()
        self.assertEqual(self.suspend().status_code, 200)
        owner = self.user(self.reader)
        owner.influencer_suspended_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.suspend().status_code, 200)
        path = f'/api/roles/profiles/{owner.id}/influencer-resume'
        response = self.client.post(path, headers=self.headers(self.admin), json={'reason': 'Revisión concluida y permisos restituidos.'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['influencer_permissions_suspended'])
        self.assertEqual(self.post().status_code, 201)
        audit = self.db.scalar(select(AccountAudit).where(AccountAudit.user_id == owner.id, AccountAudit.action == 'influencer_resumed'))
        self.assertEqual(audit.actor_user_id, self.user(self.admin).id)
        self.assertIsNotNone(audit.created_at)
        self.assertIsNone(audit.after_state['influencer_suspended_until'])

    def test_revoke_with_professional_history_preserves_publications_and_reading_data(self):
        self.promote()
        profile, work, reading, review, note, event = self.fixture_activity()
        post = self.post().json()
        self.suspend()
        response = self.client.post(f'/api/roles/profiles/{profile.owner_user_id}/revoke', headers=self.headers(self.admin), json={'reason': 'Revocación administrativa de perfil Influencer.'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['role'], 'lector')
        self.assertIsNone(self.user(self.reader).influencer_suspended_until)
        self.reader = self.client.post('/api/auth/login', json={'email': self.reader['user']['email'], 'password': 'password123'}).json()
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.get(f"/api/posts/{post['id']}", headers=self.headers()).json()['author_role'], 'influencer')
        from app.modules.social.post_covers import require_cover_editor
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            require_cover_editor(self.db, self.user(self.reader), uuid.UUID(post['id']))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIsNotNone(self.db.get(Reading, reading.id))
        self.assertIsNotNone(self.db.get(Review, review.id))
        payload = {'source': 'community', 'kind': 'community', 'publication_type': 'note', 'body': 'Nota editada como lector', 'work_id': str(work.id), 'book_ref': str(work.id), 'book_title': work.title}
        edited = self.client.put(f'/api/posts/{note.id}', headers=self.headers(), json=payload)
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()['author_role'], 'influencer')
        self.assertIsNone(self.db.get(ProfileCapability, (profile.id, 'influencer')))
        change = self.db.scalar(select(ProfileRoleChange).where(ProfileRoleChange.user_id == profile.owner_user_id, ProfileRoleChange.new_role == 'lector'))
        self.assertEqual(change.admin_user_id, self.user(self.admin).id)

    def test_permissions_require_admin_motive_future_date_and_influencer_target(self):
        self.assertEqual(self.suspend().status_code, 409)
        self.promote()
        self.assertEqual(self.suspend(account=self.reader).status_code, 403)
        self.assertEqual(self.suspend(reason='').status_code, 422)
        self.assertEqual(self.suspend(until='2020-01-01T00:00:00Z').status_code, 422)
        self.assertEqual(self.suspend(until='2099-01-01T00:00:00').status_code, 422)
        owner = self.user(self.reader)
        self.db.add(AccountPermission(user_id=owner.id, permission='admin')); self.db.flush()
        self.assertEqual(self.suspend(account=self.reader).status_code, 403)
        self.assertEqual(self.client.post(f'/api/roles/profiles/{owner.id}/revoke', headers=self.headers(self.reader), json={'reason': OBSERVATION}).status_code, 403)

    def test_pending_moderation_cannot_bypass_suspension_or_revocation(self):
        self.promote()
        pending = self.post('Te voy a matar').json()
        self.assertEqual(pending['moderation_status'], 'pending_review')
        self.suspend()
        from app.modules.social.moderation_decisions import decide
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            decide(self.db, self.user(self.admin), uuid.UUID(pending['pending_revision_id']), 'approved', OBSERVATION, pending['moderation_version'])
        self.assertEqual(caught.exception.status_code, 409)
        self.db.rollback()
        revoked = self.client.post(f"/api/roles/profiles/{self.reader['user']['id']}/revoke", headers=self.headers(self.admin), json={'reason': 'Revocación tras revisión de permisos.'})
        self.assertEqual(revoked.status_code, 200, revoked.text)
        with self.assertRaises(HTTPException) as caught:
            decide(self.db, self.user(self.admin), uuid.UUID(pending['pending_revision_id']), 'approved', OBSERVATION, pending['moderation_version'])
        self.assertEqual(caught.exception.status_code, 409)
        self.db.rollback()

    def test_author_revocation_policy_is_unchanged(self):
        owner = self.user(self.reader)
        owner.role = 'autor'
        profile = personal_profile(self.db, owner)
        self.db.add(Post(user_id=owner.id, author_profile_id=profile.id, author_role='autor', source='community',
                         kind='community', publication_type='news', body='Publicación profesional histórica'))
        self.db.commit()
        response = self.client.post(f'/api/roles/profiles/{owner.id}/revoke', headers=self.headers(self.admin), json={'reason': OBSERVATION})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.suspend().status_code, 409)
        self.assertEqual(owner.role, 'autor')


class InfluencerConcurrencyTest(unittest.TestCase):
    def test_concurrent_requests_and_decisions(self):
        require_isolated_database()
        # No dependency overrides: each concurrent HTTP request gets a real connection.
        client = TestClient(app)
        def register():
            return client.post('/api/auth/register', json={'email': uuid.uuid4().hex + '@example.com',
                'password': 'password123', 'display_name': 'Concurrent creator'}).json()
        reader, admin = register(), register()
        with Session(engine) as db:
            db.get(User, uuid.UUID(admin['user']['id'])).role = 'admin'
            db.add(AccountPermission(user_id=uuid.UUID(admin['user']['id']), permission='admin')); db.commit()
        barrier = Barrier(2)
        # Use clients without lifespan: background demo workers are unrelated to these tests.
        def submit_without_lifespan(_):
            parallel = TestClient(app)
            try:
                barrier.wait(timeout=10)
                return parallel.post('/api/roles/requests', headers={'Authorization': 'Bearer ' + reader['access_token']}, json=APPLICATION)
            finally:
                parallel.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit_without_lifespan, range(2)))
        self.assertEqual(sorted(result.status_code for result in results), [201, 409])
        identifier = next(result.json()['id'] for result in results if result.status_code == 201)
        def decide(action):
            parallel = TestClient(app)
            try:
                barrier.wait(timeout=10)
                return parallel.post(f'/api/roles/requests/{identifier}/{action}', headers={'Authorization': 'Bearer ' + admin['access_token']}, json={'reason': OBSERVATION})
            finally:
                parallel.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, ('approve', 'reject')))
        self.assertEqual(sorted(result.status_code for result in results), [200, 409])
        with Session(engine) as db:
            count = db.scalar(select(func.count()).select_from(AccountAudit).where(AccountAudit.user_id == uuid.UUID(reader['user']['id']), AccountAudit.action.in_(('professional_verification_approved', 'professional_verification_rejected'))))
            self.assertEqual(count, 1)
        client.close()
