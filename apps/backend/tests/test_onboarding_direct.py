"""Immediate HTTP generation against disposable PostgreSQL; never calls Gemini."""
import json
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.database import SessionLocal, engine, get_db
from app.main import app
from app.modules.analytics.providers.base import AIProviderTimeoutError, StructuredGenerationResult, TokenUsage
from app.modules.books.models import Author, Edition, Work, WorkAuthor
from app.modules.users.preference_models import Genre, Trope


class FakeOnboardingGemini:
    def __init__(self, *, error=None, invented=False):
        self.calls = []
        self.error = error
        self.invented = invented
        self.short = False

    def generate_structured(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        context = json.loads(request.user_content)
        preferences = context['declared_preferences']
        candidates = context['candidates']
        content = {'profile_name': 'Explorador de universos', 'profile_description': 'Disfrutas explorar historias según tus preferencias declaradas.',
            'preferred_genres': preferences['genres'], 'narrative_preferences': preferences['narrative_preferences'],
            'reading_motivations': preferences['emotions'], 'explanation': 'Interpretación del cuestionario, sin atribuir lecturas.',
            'analysis_version': 'onboarding-v1', 'recommendations': [
                {'work_id': str(uuid.uuid4()) if self.invented else item['work_id'], 'explanation': 'Comparte uno de tus géneros declarados.'}
                for item in candidates[:1 if self.short else 10]]}
        return StructuredGenerationResult(content=request.validate(content), provider='gemini', model=request.model,
            usage=TokenUsage(input_tokens=300, output_tokens=120, total_tokens=420))


class DirectOnboardingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {'localhost', '127.0.0.1'} or not engine.url.database.startswith('libria_nightly_test_'):
            raise unittest.SkipTest('Requires an explicitly disposable onboarding database')

    def setUp(self):
        with engine.begin() as connection:
            connection.execute(text('TRUNCATE app.usuarios,app.obras,app.autores,analytics.ejecuciones_etl CASCADE'))
            connection.execute(text('TRUNCATE ia.provider_cooldowns'))
        self.db = SessionLocal()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.account = self.register()
        self.owner = uuid.UUID(self.account['user']['id'])
        self.headers = {'Authorization': 'Bearer ' + self.account['access_token']}
        self.genre = self.db.scalar(select(Genre).where(Genre.active.is_(True)))
        self.trope = self.db.scalar(select(Trope).where(Trope.active.is_(True)))
        work = Work(title='Obra real del catálogo de prueba', categories=[self.genre.name])
        author = Author(name='Autora del catálogo de prueba')
        self.db.add_all([work, author]); self.db.flush()
        self.db.add_all([WorkAuthor(work_id=work.id, author_id=author.id, position=1),
                         Edition(work_id=work.id, title=work.title, language='es')])
        self.db.commit()
        self.work_id = str(work.id)
        self.data = {'step': 7, 'complete': True, 'answers': {'genre_ids': [self.genre.id], 'trope_ids': [self.trope.id],
            'emotions': ['Intriga'], 'habit': 'Leo ocasionalmente', 'favorite_work_ids': [], 'theme': 'lavanda'}}
        self.settings = Settings(_env_file=None, app_env='test', database_url=engine.url.render_as_string(hide_password=False),
            gemini_api_key='fake-test-key', gemini_free_test_mode=True, gemini_worker_enabled=False,
            ai_timeout_seconds=30, onboarding_ai_timeout_seconds=5, ai_requests_per_minute=600,
            ai_max_concurrent_requests=1)
        self.provider = FakeOnboardingGemini()
        self.settings_patch = patch('app.modules.users.onboarding.get_settings', return_value=self.settings)
        self.provider_patch = patch('app.modules.analytics.gemini_worker.build_ai_provider', return_value=self.provider)
        self.settings_patch.start(); self.provider_factory = self.provider_patch.start()

    def tearDown(self):
        self.provider_patch.stop(); self.settings_patch.stop()
        self.client.close(); app.dependency_overrides.clear(); self.db.close()

    def register(self):
        response = self.client.post('/api/auth/register', json={'email': f'{uuid.uuid4()}@example.com',
            'password': 'test-password', 'display_name': 'Prueba de consulta inmediata'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def complete(self):
        response = self.client.patch('/api/profiles/me/onboarding', headers=self.headers, json=self.data)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_same_response_contains_gemini_recommendations_without_etl_or_worker(self):
        with patch('app.modules.analytics.etl.run_pending', side_effect=AssertionError('Onboarding must not invoke ETL')):
            result = self.complete()
        self.assertFalse(self.settings.gemini_worker_enabled)
        self.assertEqual(result['ai_status'], 'completed')
        self.assertEqual(result['recommendation_source'], 'gemini')
        self.assertEqual(result['dna']['profile_name'], 'Explorador de universos')
        self.assertEqual([item['work_id'] for item in result['recommendations']], [self.work_id])
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.provider.calls[0].timeout_seconds, 5)
        self.assertNotIn(self.account['user']['email'], self.provider.calls[0].user_content)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM analytics.ejecuciones_etl')).scalar(), 0)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.reader_profile_versions')).scalar(), 0)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.call_ledger')).scalar(), 1)

    def test_repeated_confirmation_reuses_result_and_never_calls_twice(self):
        first = self.complete()
        second = self.complete()
        self.assertEqual(first['target'], second['target'])
        self.assertEqual(second['ai_status'], 'completed')
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE job_kind='onboarding'")).scalar(), 1)

    def seed_more_candidates(self):
        author = Author(name='Autora de otras obras reales')
        self.db.add(author); self.db.flush()
        for number in range(4):
            work = Work(title=f'Otra obra real {number}', categories=['Otra categoría'])
            self.db.add(work); self.db.flush()
            self.db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=1))
            self.db.add(Edition(work_id=work.id, title=work.title, language='es'))
        self.db.commit()

    def test_prompt_and_schema_require_five_real_recommendations(self):
        self.seed_more_candidates()
        result = self.complete()
        self.assertEqual(result['recommendation_source'], 'gemini')
        self.assertEqual(len(result['recommendations']), 5)
        self.assertEqual(len({item['work_id'] for item in result['recommendations']}), 5)
        request = self.provider.calls[0]
        self.assertEqual(json.loads(request.user_content)['minimum_recommendations'], 5)
        self.assertEqual(request.response_schema['properties']['recommendations']['minItems'], 5)
        self.assertIn('entre 5 y 10', request.system_instruction)

    def test_one_recommendation_is_rejected_when_five_candidates_exist(self):
        self.seed_more_candidates()
        self.provider.short = True
        result = self.complete()
        self.assertNotEqual(result['ai_status'], 'completed')
        self.assertEqual(result['recommendation_source'], 'catalog')
        self.assertEqual(len(result['recommendations']), 5)
        self.assertEqual(len(self.provider.calls), 1)

    def test_old_short_result_uses_current_catalog_without_another_ai_call(self):
        self.assertEqual(len(self.complete()['recommendations']), 1)
        self.seed_more_candidates()
        result = self.client.get('/api/profiles/me/onboarding', headers=self.headers).json()
        self.assertEqual(result['recommendation_source'], 'catalog')
        self.assertEqual(len(result['recommendations']), 5)
        self.assertEqual(len(self.provider.calls), 1)

    def test_request_never_processes_another_accounts_older_job(self):
        other = self.register()
        self.db.execute(text('''INSERT INTO ia.jobs(owner_id,target,job_kind,provider,model,prompt_version,created_at)
            VALUES (:owner,'onboarding:another-reader','onboarding','gemini',:model,'onboarding-v1',now()-interval '1 day')'''),
            {'owner': uuid.UUID(other['user']['id']), 'model': self.settings.gemini_model})
        self.db.commit()
        self.assertEqual(self.complete()['ai_status'], 'completed')
        row = self.db.execute(text("SELECT status,attempts FROM ia.jobs WHERE target='onboarding:another-reader'")).one()
        self.assertEqual(tuple(row), ('pending', 0))

    def test_timeout_returns_catalog_fallback_and_preserves_completion_and_backoff(self):
        self.provider.error = AIProviderTimeoutError('Simulated timeout')
        result = self.complete()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['required'])
        self.assertEqual(result['ai_error_code'], 'provider_timeout')
        self.assertEqual(result['recommendation_source'], 'catalog')
        self.assertEqual([item['work_id'] for item in result['recommendations']], [self.work_id])
        self.complete()
        self.assertEqual(len(self.provider.calls), 1, 'A repeated click cannot bypass retry backoff')

    def test_invalid_ids_are_not_shown_as_gemini_recommendations(self):
        self.provider.invented = True
        result = self.complete()
        self.assertEqual(result['ai_status'], 'failed')
        self.assertIsNone(result['dna'])
        self.assertEqual(result['recommendation_source'], 'catalog')
        self.assertEqual([item['work_id'] for item in result['recommendations']], [self.work_id])

    def test_missing_provider_configuration_does_not_block_or_invoke_sdk(self):
        disabled = self.settings.model_copy(update={'gemini_free_test_mode': False, 'gemini_paid_service_confirmed': False})
        with patch('app.modules.users.onboarding.get_settings', return_value=disabled):
            result = self.complete()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['ai_available'])
        self.provider_factory.assert_not_called()

    def test_busy_provider_defers_without_waiting_for_a_slot(self):
        with engine.connect() as holder:
            holder.execute(text('SELECT pg_advisory_lock(1947322051,0)')); holder.commit()
            try:
                with patch('app.modules.analytics.gemini_worker.time.sleep') as sleep:
                    result = self.complete()
                    sleep.assert_not_called()
                self.assertEqual(result['ai_error_code'], 'provider_busy')
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(len(self.provider.calls), 0)
            finally:
                holder.execute(text('SELECT pg_advisory_unlock(1947322051,0)')); holder.commit()
