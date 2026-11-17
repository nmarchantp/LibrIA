"""Real PostgreSQL transactions; Gemini calls are always mocked."""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.core.config import get_settings
from app.main import app
from app.modules.users.models import User
from app.modules.users.preference_models import Genre, Trope, OnboardingFavorite
from app.modules.users.onboarding import Answers, InitialDNA, process_generation, rank_candidates
from app.modules.books.models import Work


class OnboardingTest(unittest.TestCase):
    def setUp(self):
        if get_settings().app_env != 'test':
            self.skipTest('Requires an isolated test database and APP_ENV=test')
        generation = patch('app.modules.users.onboarding.generate_immediately', return_value=False)
        generation.start()
        self.addCleanup(generation.stop)
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode='create_savepoint', expire_on_commit=False)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        response = self.client.post('/api/auth/register', json={'email': f'{uuid.uuid4()}@example.com',
            'display_name': 'Lector de prueba', 'password': 'test-password'})
        self.assertEqual(response.status_code, 201, response.text)
        self.account = response.json()
        self.user = self.db.get(User, uuid.UUID(self.account['user']['id']))
        self.headers = {'Authorization': 'Bearer ' + self.account['access_token']}
        self.path = '/api/profiles/me/onboarding'
        self.genre = self.db.scalar(select(Genre).where(Genre.active.is_(True)))
        self.trope = self.db.scalar(select(Trope).where(Trope.active.is_(True)))
        self.answers = {'genre_ids': [self.genre.id], 'trope_ids': [self.trope.id],
            'emotions': ['Intriga'], 'habit': 'Leo ocasionalmente', 'favorite_work_ids': [], 'theme': 'dark'}

    def tearDown(self):
        if not hasattr(self, 'client'):
            return
        self.client.close(); app.dependency_overrides.clear(); self.db.close()
        self.transaction.rollback(); self.connection.close()

    def save(self, step=7, complete=False, **answers):
        return self.client.patch(self.path, headers=self.headers, json={
            'step': step, 'answers': {**self.answers, **answers}, 'complete': complete})

    def get(self):
        return self.client.get(self.path, headers=self.headers).json()

    def test_registration_gate_and_session_restore(self):
        self.assertTrue(self.account['user']['onboarding_required'])
        self.assertTrue(self.client.get('/api/auth/me', headers=self.headers).json()['onboarding_required'])
        self.assertEqual(self.client.get('/api/readings/me', headers=self.headers).status_code, 403)
        self.assertEqual(self.client.get('/api/profiles/preference-catalogs', headers=self.headers).status_code, 200)
        result = self.save(step=3)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.get()['step'], 3)
        self.assertEqual(self.get()['answers'], self.answers)

    def test_existing_and_other_roles_are_optional(self):
        for role in ['lector', 'autor', 'influencer', 'libreria', 'admin', 'editorial']:
            self.user.onboarding = {} if role == 'lector' else {'required': True, 'status': 'pending'}
            self.user.role = role
            self.db.commit()
            self.assertFalse(self.user.onboarding_required)
            self.assertEqual(self.client.get('/api/readings/me', headers=self.headers).status_code, 200)

    def test_minimums_limits_and_invalid_taxonomy(self):
        for change in [{'genre_ids': []}, {'trope_ids': []}, {'emotions': []}, {'habit': None},
                       {'genre_ids': ['unknown']}, {'genre_ids': [self.genre.id] * 2},
                       {'emotions': ['Intriga'] * 4}, {'habit': 'inventado'}, {'theme': '<script>'}]:
            self.assertEqual(self.save(complete=True, **change).status_code, 422, change)
        self.assertEqual(self.save(step=1, genre_ids=[], trope_ids=[], emotions=[], habit=None).status_code, 200)

    def test_favorites_zero_five_duplicates_and_unknown(self):
        works = [Work(title=f'Favorito {i}') for i in range(6)]
        self.db.add_all(works); self.db.flush()
        ids = [str(work.id) for work in works]
        self.assertEqual(self.save(favorite_work_ids=[]).status_code, 200)
        self.assertEqual(self.save(favorite_work_ids=ids[:5]).status_code, 200)
        self.assertEqual(len(self.db.scalars(select(OnboardingFavorite).where(OnboardingFavorite.user_id == self.user.id)).all()), 5)
        for values in [ids, ids[:1] * 2]:
            self.assertEqual(self.save(favorite_work_ids=values).status_code, 422)
        # Unknown UUIDs are rejected by canonical identity validation.
        self.assertEqual(self.save(favorite_work_ids=[str(uuid.uuid4())]).status_code, 404)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM app.entradas_biblioteca WHERE user_id=:id'), {'id': self.user.id}).scalar(), 0)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM app.lecturas r JOIN app.entradas_biblioteca e ON e.id=r.library_entry_id WHERE e.user_id=:id'), {'id': self.user.id}).scalar(), 0)

    def test_complete_idempotent_immediate_job_and_theme(self):
        for _ in range(2):
            result = self.save(complete=True)
            self.assertEqual(result.status_code, 200, result.text)
        jobs = self.db.execute(text("SELECT * FROM ia.jobs WHERE owner_id=:id AND job_kind='onboarding'"), {'id': self.user.id}).mappings().all()
        self.assertEqual(len(jobs), 1)
        self.assertLessEqual(jobs[0]['not_before'], jobs[0]['created_at'])
        self.assertEqual(self.user.visual_theme, 'dark')
        self.assertFalse(self.get()['required'])
        self.assertEqual(self.client.get('/api/readings/me', headers=self.headers).status_code, 200)

    def test_completed_favorites_are_pending_and_idempotent(self):
        from app.modules.library.models import LibraryEntry, Reading
        works = [Work(title=f'Favorito pendiente {i}') for i in range(3)]
        self.db.add_all(works); self.db.flush()
        ids = [str(work.id) for work in works]
        self.assertEqual(self.save(favorite_work_ids=ids).status_code, 200)
        self.assertEqual(list(self.db.scalars(select(LibraryEntry).where(LibraryEntry.user_id == self.user.id))), [])
        for _ in range(2):
            self.assertEqual(self.save(complete=True, favorite_work_ids=ids).status_code, 200)
            self.assertEqual(self.client.post(self.path + '/library', headers=self.headers).status_code, 200)
        rows = list(self.db.scalars(select(Reading).join(LibraryEntry).where(LibraryEntry.user_id == self.user.id)))
        self.assertEqual(len(rows), 3)
        self.assertEqual({str(row.work_id) for row in rows}, set(ids))
        self.assertTrue(all(row.status == 'pending' and row.current_page == 0 and row.started_at is None for row in rows))
        listed = self.client.get('/api/readings/me', headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual({row['work_id'] for row in listed.json()}, set(ids))

    def test_favorites_preserve_existing_reading_and_archive(self):
        from datetime import datetime, timezone
        from app.modules.library.models import LibraryEntry, Reading
        works = [Work(title=f'Favorito existente {i}') for i in range(2)]
        self.db.add_all(works); self.db.flush()
        active = LibraryEntry(user_id=self.user.id, work_id=works[0].id)
        archived = LibraryEntry(user_id=self.user.id, work_id=works[1].id, archived_at=datetime.now(timezone.utc))
        self.db.add_all([active, archived]); self.db.flush()
        reading = Reading(library_entry_id=active.id, work_id=works[0].id, status='reading',
                          current_page=12, total_pages=100, started_at=datetime.now(timezone.utc))
        self.db.add(reading); self.db.commit()
        self.assertEqual(self.save(complete=True, favorite_work_ids=[str(work.id) for work in works]).status_code, 200)
        self.assertEqual(self.client.post(self.path + '/library', headers=self.headers).status_code, 200)
        self.db.refresh(reading); self.db.refresh(archived)
        self.assertEqual((reading.status, reading.current_page), ('reading', 12))
        self.assertIsNotNone(archived.archived_at)
        self.assertEqual(len(list(self.db.scalars(select(Reading).join(LibraryEntry).where(LibraryEntry.user_id == self.user.id)))), 1)

    def test_sync_favorites_requires_completed_questionnaire(self):
        self.assertEqual(self.client.post(self.path + '/library', headers=self.headers).status_code, 409)

    def test_first_completion_starts_persistent_guide_without_resetting_it(self):
        self.assertNotIn('guide', self.get())
        self.assertEqual(self.save(complete=True).json()['guide']['step'], 'analysis')
        route = self.path + '/guide'
        self.assertEqual(self.client.patch(route, headers=self.headers, json={'step': 'search'}).status_code, 200)
        self.assertEqual(self.get()['guide']['step'], 'search')
        self.assertEqual(self.save(complete=True).json()['guide']['step'], 'search')
        book = str(uuid.uuid4())
        self.client.patch(route, headers=self.headers, json={'step': 'library', 'book_ref': book})
        self.assertEqual(self.get()['guide']['book_ref'], book)
        self.client.patch(route, headers=self.headers, json={'step': 'completed'})
        self.assertEqual(self.save(complete=True).json()['guide']['step'], 'completed')

    def test_guide_can_be_skipped_restarted_and_requires_completed_questionnaire(self):
        route = self.path + '/guide'
        self.assertEqual(self.client.patch(route, headers=self.headers, json={'step': 'analysis'}).status_code, 409)
        self.save(complete=True)
        self.assertEqual(self.client.patch(route, headers=self.headers, json={'step': 'invalid'}).status_code, 422)
        self.client.patch(route, headers=self.headers, json={'step': 'dismissed'})
        self.assertEqual(self.get()['guide']['step'], 'dismissed')
        self.assertIn('finished_at', self.get()['guide'])
        self.client.patch(route, headers=self.headers, json={'step': 'analysis'})
        self.assertEqual(self.get()['guide']['step'], 'analysis')
        self.assertNotIn('finished_at', self.get()['guide'])

    def test_sync_imports_favorites_from_previously_completed_onboarding(self):
        from app.modules.library.models import LibraryEntry, Reading
        work = Work(title='Favorito de un registro anterior')
        self.db.add(work); self.db.flush()
        self.assertEqual(self.save(complete=True).status_code, 200)
        self.user.onboarding = {**self.user.onboarding, 'answers': {**self.answers, 'favorite_work_ids': [str(work.id)]}}
        self.db.commit()
        self.assertEqual(self.client.post(self.path + '/library', headers=self.headers).status_code, 200)
        reading = self.db.scalar(select(Reading).join(LibraryEntry).where(LibraryEntry.user_id == self.user.id))
        self.assertEqual((reading.work_id, reading.status), (work.id, 'pending'))

    def test_ai_failure_does_not_block_and_empty_catalog_fallback(self):
        result = self.save(complete=True)
        self.assertEqual(result.json()['recommendations'], [])
        self.db.execute(text("UPDATE ia.jobs SET status='failed' WHERE owner_id=:id"), {'id': self.user.id}); self.db.commit()
        self.assertEqual(self.get()['ai_status'], 'failed')
        self.assertEqual(self.get()['status'], 'completed')
        self.assertEqual(self.client.get('/api/readings/me', headers=self.headers).status_code, 200)

    def test_dna_validation_and_previous_analysis_during_regeneration(self):
        self.save(complete=True)
        job = dict(self.db.execute(text("SELECT * FROM ia.jobs WHERE owner_id=:id AND job_kind='onboarding'"), {'id': self.user.id}).mappings().one())
        self.db.execute(text("UPDATE ia.jobs SET status='processing',attempts=1 WHERE id=:id"), {'id': job['id']})
        job['attempts'] = 1
        self.db.commit()
        payload = {'profile_name': 'Explorador de historias', 'profile_description': 'Declaras interés en la intriga.',
            'preferred_genres': [self.genre.name], 'narrative_preferences': [self.trope.name],
            'reading_motivations': ['Intriga'], 'explanation': 'Basado en preferencias declaradas.',
            'analysis_version': 'onboarding-v1', 'recommendations': []}
        with patch('app.modules.analytics.gemini_worker._invoke', return_value=payload):
            process_generation(self.db, None, job, get_settings(), SimpleNamespace())
            self.db.commit()
        self.assertEqual(self.get()['dna']['profile_name'], payload['profile_name'])
        self.save(complete=True, emotions=['Ternura'])
        self.assertEqual(self.get()['dna']['profile_name'], payload['profile_name'])
        self.assertEqual(self.get()['ai_status'], 'pending')
        with self.assertRaises(ValidationError):
            InitialDNA.model_validate({**payload, 'analysis_version': 'unknown'})

    def test_edit_draft_does_not_regenerate_until_confirmation(self):
        self.save(complete=True)
        self.assertEqual(self.save(step=2, emotions=['Ternura']).status_code, 200)
        self.assertEqual(self.get()['answers']['emotions'], ['Intriga'])
        self.assertEqual(self.get()['draft_answers']['emotions'], ['Ternura'])
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:id AND job_kind='onboarding'"), {'id': self.user.id}).scalar(), 1)
        self.save(complete=True, emotions=['Ternura'])
        self.assertEqual(self.get()['answers']['emotions'], ['Ternura'])

    def test_privacy_defaults_and_explicit_consent(self):
        from app.modules.users.identity_models import Profile
        profile = self.db.scalar(select(Profile).where(Profile.owner_user_id == self.user.id))
        self.save(complete=True)
        self.assertFalse(self.get().get('shared', False))
        self.assertEqual(self.client.patch(self.path + '/sharing', headers=self.headers, json={'shared': True}).status_code, 200)
        self.assertTrue(self.get()['shared'])
        self.client.patch(self.path + '/sharing', headers=self.headers, json={'shared': False})
        self.assertFalse(self.get()['shared'])
        self.assertEqual(self.client.get(f'/api/profiles/{profile.id}/literary-dna').status_code, 401)

    def test_deterministic_ranking_filters_favorites_and_unrelated_metadata(self):
        candidates = [{'work_id': 'one', 'categories': ['Fantasía']}, {'work_id': 'two', 'categories': ['Fantasia']},
                      {'work_id': 'three', 'categories': ['Historia']}, {'work_id': 'four', 'categories': ['Fantasy']}]
        ranked = rank_candidates(candidates, {'genres': ['Fantasía']}, {'one'})
        self.assertEqual([item['work_id'] for item in ranked], ['four', 'two'])

    def test_structured_contract_rejects_duplicate_answers(self):
        for key in ['genre_ids', 'trope_ids', 'emotions', 'favorite_work_ids']:
            values = [str(uuid.uuid4())] if key == 'favorite_work_ids' else ['Intriga']
            with self.assertRaises(ValidationError):
                Answers.model_validate({key: values * 2})

    def test_real_candidates_fallback_and_gemini_ids(self):
        from app.modules.books.models import Author, Edition, WorkAuthor
        author = Author(name='Autor del catálogo')
        work = Work(title='Obra del catálogo', categories=[self.genre.name])
        self.db.add_all([author, work]); self.db.flush()
        self.db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=1))
        self.db.add(Edition(work_id=work.id, title=work.title, language='es', cover_url='https://example.com/cover.jpg'))
        self.db.commit()
        result = self.save(complete=True).json()
        self.assertEqual([item['work_id'] for item in result['recommendations']], [str(work.id)])
        job = dict(self.db.execute(text("SELECT * FROM ia.jobs WHERE owner_id=:id AND job_kind='onboarding'"), {'id': self.user.id}).mappings().one())
        self.db.execute(text("UPDATE ia.jobs SET status='processing',attempts=1,locked_at=now() WHERE id=:id"), {'id': job['id']})
        self.db.commit()
        job['attempts'] = 1
        from app.modules.analytics.gemini_worker import AttemptBudget, _finish_attempt
        from app.modules.analytics.providers.base import StructuredGenerationResult, TokenUsage
        import time
        class FakeGemini:
            def generate_structured(fake, request):
                payload = {'profile_name': 'Explorador', 'profile_description': 'Prefieres estos géneros.',
                    'preferred_genres': [self.genre.name], 'narrative_preferences': [], 'reading_motivations': ['Intriga'],
                    'explanation': 'Preferencias declaradas.', 'analysis_version': 'onboarding-v1',
                    'recommendations': [{'work_id': str(work.id), 'explanation': 'Comparte tu género declarado.'}]}
                return StructuredGenerationResult(content=request.validate(payload), provider='gemini', model=get_settings().gemini_model,
                    usage=TokenUsage(input_tokens=100, output_tokens=30, total_tokens=130))
        budget = AttemptBudget(3, 100000, job_id=job['id'], attempt=1)
        process_generation(self.db, FakeGemini(), job, get_settings(), budget)
        _finish_attempt(self.db, job, budget, time.monotonic(), get_settings(), status='completed')
        self.assertEqual(self.get()['ai_status'], 'completed')
        self.assertEqual(self.get()['recommendations'][0]['work_id'], str(work.id))
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.call_ledger WHERE job_id=:id'), {'id': job['id']}).scalar(), 1)

    def test_hallucinated_and_duplicate_recommendations_rejected(self):
        self.save(complete=True)
        job = dict(self.db.execute(text("SELECT * FROM ia.jobs WHERE owner_id=:id AND job_kind='onboarding'"), {'id': self.user.id}).mappings().one())
        item = {'work_id': str(uuid.uuid4()), 'explanation': 'Sin evidencia'}
        payload = {'profile_name': 'Perfil', 'profile_description': 'Descripción', 'preferred_genres': [],
            'narrative_preferences': [], 'reading_motivations': [], 'explanation': 'Declaradas',
            'analysis_version': 'onboarding-v1'}
        for selections in [[item], [item, item]]:
            with patch('app.modules.analytics.gemini_worker._invoke', return_value={**payload, 'recommendations': selections}):
                with self.assertRaises(ValueError):
                    process_generation(self.db, None, job, get_settings(), SimpleNamespace())
        self.assertIsNone(self.get()['dna'])

    def test_worker_backoff_and_final_failure_preserve_completion(self):
        import time
        from app.modules.analytics.gemini_worker import AttemptBudget, _retry_attempt
        self.save(complete=True)
        job = dict(self.db.execute(text("SELECT * FROM ia.jobs WHERE owner_id=:id AND job_kind='onboarding'"), {'id': self.user.id}).mappings().one())
        for attempt in [1, get_settings().ai_job_max_attempts]:
            self.db.execute(text("UPDATE ia.jobs SET status='processing',attempts=:attempt WHERE id=:id"), {'id': job['id'], 'attempt': attempt})
            self.db.commit(); job['attempts'] = attempt
            _retry_attempt(self.db, job, AttemptBudget(3, 10000), time.monotonic(), get_settings(), 'provider_timeout')
            current = self.db.execute(text('SELECT status,not_before>now() AS delayed FROM ia.jobs WHERE id=:id'), {'id': job['id']}).mappings().one()
            self.assertEqual(current['status'], 'pending' if attempt == 1 else 'failed')
            if attempt == 1:
                self.assertTrue(current['delayed'])
        self.assertEqual(self.get()['status'], 'completed')
        self.assertFalse(self.get()['required'])

    def test_queue_prevents_parallel_onboarding_for_one_owner(self):
        from app.modules.analytics.gemini_worker import claim_next_job
        self.save(complete=True)
        self.db.execute(text("UPDATE ia.jobs SET status='completed' WHERE owner_id<>:id"), {'id': self.user.id})
        self.db.execute(text('''INSERT INTO ia.jobs(owner_id,target,job_kind,provider,model,prompt_version)
            VALUES (:owner,'onboarding:second','onboarding','gemini',:model,'onboarding-v1')'''),
            {'owner': self.user.id, 'model': get_settings().gemini_model})
        self.db.commit()
        first = claim_next_job(self.db, get_settings())
        self.assertEqual(first['owner_id'], self.user.id)
        self.assertEqual(first['job_kind'], 'onboarding')
        self.assertIsNone(claim_next_job(self.db, get_settings()))

    def test_returning_to_cancelled_preferences_reuses_the_same_job(self):
        self.save(complete=True)
        target = self.get()['target']
        self.save(complete=True, emotions=['Ternura'])
        self.save(complete=True)
        self.assertEqual(self.get()['target'], target)
        self.assertEqual(self.get()['ai_status'], 'pending')
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner AND job_kind='onboarding'"), {'owner': self.user.id}).scalar(), 2)

    def test_public_dna_requires_consent_and_has_a_restricted_projection(self):
        import json
        from app.modules.users.identity_models import Profile
        from tests.onboarding_support import existing_account
        self.save(complete=True)
        original_sections = list(self.user.public_sections)
        profile = self.db.scalar(select(Profile).where(Profile.owner_user_id == self.user.id))
        payload = {'profile_name': 'Perfil declarado', 'profile_description': 'Basado en preferencias.',
                   'preferred_genres': [self.genre.name], 'explanation': 'Preferencias declaradas.',
                   'recommendations': [], 'answers': 'No publicar'}
        self.db.execute(text('''INSERT INTO ia.analyses(owner_id,target,version,data_hash,content,model,prompt_version,provider)
            VALUES (:owner,:target,1,'test',CAST(:content AS jsonb),'mock','onboarding-v1','gemini')'''),
            {'owner': self.user.id, 'target': self.get()['target'], 'content': json.dumps(payload)})
        self.db.commit()
        response = self.client.post('/api/auth/register', json={'email': f'{uuid.uuid4()}@example.com',
            'password': 'test-password', 'display_name': 'Visitante'})
        other = existing_account(self.db, response)
        headers = {'Authorization': 'Bearer ' + other['access_token']}
        path = f'/api/profiles/{profile.id}/literary-dna'
        self.assertIsNone(self.client.get(path, headers=headers).json()['dna'])
        self.client.patch(self.path + '/sharing', headers=self.headers, json={'shared': True})
        public = self.client.get(path, headers=headers).json()['dna']
        self.assertEqual(set(public), {'profile_name', 'profile_description', 'preferred_genres', 'explanation'})
        self.assertEqual(self.user.public_sections, original_sections)
        self.user.profile_visibility = 'private'; self.db.commit()
        self.assertEqual(self.client.get(path, headers=headers).status_code, 404)
