import copy
import os
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import Response
from sqlalchemy import text
from app.core.config import Settings
from app.modules.analytics.gemini_context import profile_evidence_units
from app.modules.analytics.gemini_contracts import ProfileInterpretation, ReaderDnaInterpretation, reader_dna_transport_json_schema
from app.modules.analytics.reader_dna import assess_evidence, evolution_context, validate_dna, read_current_dna
from app.modules.analytics import adaptive_router
from tests import test_stage5_gemini_worker as fixtures
from app.modules.analytics.gemini_context import canonical_json, content_hash
from app.modules.analytics.providers.base import StructuredGenerationResult, TokenUsage


SUMMARY = (
    'En tus reflexiones valoras las historias que permiten comprender las decisiones de los personajes desde '
    'varias perspectivas. Pareces conectar con protagonistas que cambian a partir de conflictos concretos y '
    'cuyas dudas conservan una relación reconocible con lo que ocurre en la narración. Tus comentarios '
    'destacan las consecuencias de sus elecciones, más allá de que el desenlace resulte feliz o doloroso. '
    'Como lector, buscas motivos que hagan creíble esa transformación y que mantengan tu interés durante la historia.\n\n'
    'También tiendes a valorar los relatos que dejan espacio para interpretar sus preguntas. En tus reseñas '
    'se relacionan la evolución de los vínculos y la manera en que el ritmo permite conocerlos. Disfrutas '
    'cuando esas conexiones se desarrollan con claridad, mientras expresas reservas ante soluciones que '
    'parecen apresuradas. Estas preferencias describen tu experiencia literaria registrada y pueden ampliarse '
    'a medida que compartas nuevas lecturas y reflexiones.'
)


def payload(count=2):
    return {'books': [{'reading_id': str(uuid.uuid4()), 'work_id': str(uuid.uuid4()),
                       'review_id': str(uuid.uuid4()), 'review': SUMMARY, 'rating': 5,
                       'metadata': {'title': 'Historia'}, 'finish_reflection': ''} for _ in range(count)]}


def content(units, level='sufficient'):
    ids = [unit.evidence_id for unit in units]
    value = ProfileInterpretation(evidence_ids=ids, narrative_preferences=['Personajes con decisiones complejas']).model_dump()
    value.update(reader_essence={'archetype': 'El explorador de las decisiones' if level == 'sufficient' else None,
                                'summary': SUMMARY if level == 'sufficient' else 'Tus comentarios permiten explorar tendencias iniciales.' if level == 'partial' else None,
                                'traits': ['Explorador de conflictos', 'Atento a los vínculos', 'Reflexivo en tus lecturas'] if level == 'sufficient' else [],
                                'evidence_level': level, 'evidence_ids': ids},
                 evolution={'reference_version_id': None, 'has_meaningful_changes': False, 'summary': None,
                            'stable_patterns': [], 'emerging_interests': [], 'changing_preferences': []})
    return value


class EssenceGemini(fixtures.MockGemini):
    def __init__(self, units, *, changed=False):
        super().__init__()
        self.units = units
        self.changed = changed

    def generate_structured(self, request):
        import json
        if 'reader_essence' not in request.response_schema.get('properties', {}):
            return super().generate_structured(request)
        self.calls.append(request)
        context = json.loads(request.user_content)
        value = content(self.units)
        value['evolution']['reference_version_id'] = context['reference_version_id']
        if context['previous'] and context['previous']['reader_essence']['evidence_level'] == 'sufficient':
            value['evolution']['summary'] = 'Tus preferencias literarias se mantienen estables en las experiencias registradas.'
            if self.changed:
                key = context['changed_personal_evidence_ids'][0]
                value['evolution'].update(has_meaningful_changes=True, summary='Tus reflexiones dan mayor importancia a los dilemas.',
                    changing_preferences=[{'dimension': 'themes_and_conflicts', 'text': 'Mayor atención a los dilemas frente al combate.',
                                           'evidence_ids': [key], 'reference_evidence_ids': context['previous']['evidence_ids'][:1]}])
        return StructuredGenerationResult(content=request.validate(value), provider='gemini', model=request.model or 'mock',
                                          usage=TokenUsage(input_tokens=100, output_tokens=20, total_tokens=120))


class ReaderDnaV2Test(unittest.TestCase):
    def setUp(self):
        self.payload = payload()
        self.units = profile_evidence_units(self.payload)
        self.context = evolution_context(None, self.units)

    def test_complete_second_person_essence_preserves_seven_dimensions(self):
        result = validate_dna(content(self.units), self.units, self.context)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['reader_essence']['evidence_level'], 'sufficient')
        self.assertEqual(len(set(ProfileInterpretation.model_fields) - {'evidence_ids'}), 7)
        self.assertTrue(set(ProfileInterpretation.model_fields).issubset(result))
        self.assertEqual(result['evolution']['summary'], None)

    def test_provider_schema_is_compact_but_local_bounds_remain_strict(self):
        schema = canonical_json(reader_dna_transport_json_schema())
        self.assertNotIn('maxItems', schema)
        value = content(self.units)
        value['reader_essence']['traits'] = ['rasgo'] * 6
        with self.assertRaises(ValueError):
            ReaderDnaInterpretation.model_validate(value)

    def test_only_global_synthesis_gets_the_larger_output_allowance(self):
        from app.modules.analytics.gemini_worker import _summary_request
        from app.modules.analytics.gemini_prompts import DNA_SYSTEM, CHUNK_SYSTEM
        settings = Settings(_env_file=None)
        dna = _summary_request(DNA_SYSTEM, {}, settings, set(), dna_units=self.units, dna_context=self.context)
        book = _summary_request(CHUNK_SYSTEM, {}, settings, set(), event=True)
        self.assertEqual(dna.max_output_tokens, 4096)
        self.assertEqual(book.max_output_tokens, settings.ai_output_token_budget)

    def test_synthesis_reduction_measures_schema_and_previous_version_not_just_summaries(self):
        from app.modules.analytics.gemini_worker import _summarize_profile, AttemptBudget
        from app.modules.analytics.gemini_prompts import REDUCE_SYSTEM, DNA_SYSTEM
        previous = {'id': uuid.uuid4(), 'source_payload': self.payload, 'content': content(self.units)}
        context = evolution_context(previous, self.units)
        context['previous']['narrative_preferences'] = ['Preferencia literaria respaldada. ' * 80]
        settings = Settings(_env_file=None, ai_context_token_budget=12000)
        verbose = ProfileInterpretation(evidence_ids=[unit.evidence_id for unit in self.units],
                                       narrative_preferences=['Relación narrativa respaldada. ' * 25]).model_dump()
        calls = []
        def invoke(db, provider, request, budget, settings):
            calls.append(request.system_instruction)
            if request.system_instruction == REDUCE_SYSTEM:
                return ProfileInterpretation(evidence_ids=[unit.evidence_id for unit in self.units], narrative_preferences=['Decisiones complejas']).model_dump()
            if request.system_instruction == DNA_SYSTEM:
                return content(self.units)
            return verbose
        # Cached chunks can each fit, while their aggregate plus the reference
        # and response schema no longer fits the final request.
        chunks = [{'hash': str(index), 'index': index, 'total': 3, 'evidence': [unit.wire() for unit in self.units]} for index in range(3)]
        with patch('app.modules.analytics.gemini_worker.chunk_evidence', return_value=chunks), \
             patch('app.modules.analytics.gemini_worker._chunk_cache', return_value=None), \
             patch('app.modules.analytics.gemini_worker._save_chunk'), \
             patch('app.modules.analytics.gemini_worker._invoke', side_effect=invoke):
            result, _, _ = _summarize_profile(MagicMock(), None, {'owner_id': uuid.uuid4(), 'model': settings.gemini_model,
                'prompt_version': settings.reader_dna_prompt_version}, self.payload, settings, AttemptBudget(24,100000), dna_context=context)
        self.assertIn('content', result)
        self.assertIn(REDUCE_SYSTEM, calls)
        self.assertEqual(calls[-1], DNA_SYSTEM)

    def test_metadata_and_ratings_cannot_create_an_essence(self):
        data = payload()
        for book in data['books']:
            book['review'] = ''
            book['metadata']['description'] = SUMMARY * 10
        units = profile_evidence_units(data)
        self.assertEqual(assess_evidence(units)['evidence_level'], 'insufficient')
        with self.assertRaises(ValueError):
            validate_dna(content(units), units, evolution_context(None, units))
        self.assertEqual(validate_dna(content(units, 'insufficient'), units, evolution_context(None, units))['reader_essence']['traits'], [])

    def test_one_book_never_defines_a_complete_identity(self):
        units = profile_evidence_units(payload(1))
        self.assertEqual(assess_evidence(units)['evidence_level'], 'partial')
        with self.assertRaises(ValueError):
            validate_dna(content(units), units, evolution_context(None, units))
        self.assertEqual(validate_dna(content(units, 'partial'), units, evolution_context(None, units))['reader_essence']['archetype'], None)

    def test_rejects_short_or_third_person_complete_narrative(self):
        for summary in ('El lector busca emociones.', SUMMARY.replace('tus', 'sus').replace('Tus', 'Sus').replace('valoras', 'valora').replace('Pareces', 'Parece').replace('buscas', 'busca').replace('tu ', 'su ').replace('tiendes', 'tiende').replace('Disfrutas', 'Disfruta')):
            value = content(self.units)
            value['reader_essence']['summary'] = summary
            with self.assertRaises(ValueError):
                ReaderDnaInterpretation.model_validate(value)

    def test_archetype_and_traits_require_cited_personal_evidence_across_works(self):
        value = content(self.units)
        value['reader_essence']['evidence_ids'] = [self.units[0].evidence_id]
        with self.assertRaises(ValueError):
            validate_dna(value, self.units, self.context)

    def test_unknown_evidence_and_version_are_rejected(self):
        value = content(self.units)
        value['reader_essence']['evidence_ids'] = ['invented']
        with self.assertRaises(ValueError):
            validate_dna(value, self.units, self.context)
        value = content(self.units)
        value['evolution']['reference_version_id'] = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            validate_dna(value, self.units, self.context)

    def test_rewording_and_metadata_edits_are_not_new_personal_evidence(self):
        previous = {'id': uuid.uuid4(), 'source_payload': self.payload, 'content': content(self.units)}
        changed = copy.deepcopy(self.payload)
        changed['books'][0]['metadata']['title'] = 'Título corregido'
        context = evolution_context(previous, profile_evidence_units(changed))
        self.assertEqual(context['changed_personal_evidence_ids'], [])
        value = content(self.units)
        value['evolution'].update(reference_version_id=context['reference_version_id'], has_meaningful_changes=True,
                                  summary='Tus preferencias han cambiado.', emerging_interests=[{'dimension':'narrative_preferences', 'text':'Un interés nuevo',
                                  'evidence_ids':[self.units[1].evidence_id], 'reference_evidence_ids':[self.units[1].evidence_id]}])
        with self.assertRaises(ValueError):
            validate_dna(value, self.units, context)

    def test_supported_changes_need_current_and_reference_citations(self):
        previous = {'id': uuid.uuid4(), 'source_payload': copy.deepcopy(self.payload), 'content': content(self.units)}
        self.payload['books'][0]['review'] += ' Ahora valoro más los dilemas que los combates.'
        units = profile_evidence_units(self.payload)
        context = evolution_context(previous, units)
        value = content(units)
        value['evolution'].update(reference_version_id=context['reference_version_id'], has_meaningful_changes=True,
                                  summary='Tus reflexiones dan mayor importancia a los dilemas.',
                                  changing_preferences=[{'dimension':'themes_and_conflicts', 'text':'Mayor atención a dilemas frente al combate.',
                                  'evidence_ids':[units[1].evidence_id], 'reference_evidence_ids':[self.units[1].evidence_id]}])
        self.assertTrue(validate_dna(value, units, context)['evolution']['has_meaningful_changes'])
        value['evolution']['changing_preferences'][0]['reference_evidence_ids'] = ['invented']
        with self.assertRaises(ValueError):
            validate_dna(value, units, context)

    def test_old_analysis_is_not_falsely_comparable(self):
        previous = {'id': uuid.uuid4(), 'source_payload': self.payload, 'content': ProfileInterpretation().model_dump()}
        context = evolution_context(previous, self.units)
        value = content(self.units)
        value['evolution'].update(reference_version_id=context['reference_version_id'], summary='Tus preferencias cambian.', has_meaningful_changes=True)
        result = validate_dna(value, self.units, context)
        self.assertFalse(result['evolution']['has_meaningful_changes'])
        self.assertIsNone(result['evolution']['summary'])

    def test_last_valid_dna_survives_missing_current_result(self):
        db = MagicMock()
        previous = {'id': uuid.uuid4(), 'content': content(self.units)}
        db.execute.return_value.mappings.return_value.first.return_value = previous
        with patch('app.modules.analytics.recommendation_sync._latest_state', return_value=None):
            self.assertFalse(read_current_dna(db, uuid.uuid4(), Settings(_env_file=None))['is_current'])
            self.assertIsNone(read_current_dna(db, uuid.uuid4(), Settings(_env_file=None), allow_stale=False))
        db.commit.assert_not_called()


@unittest.skipUnless(os.getenv('LIBRIA_STAGE5_TEST') == '1', 'requires disposable PostgreSQL')
class ReaderDnaV2DatabaseTest(unittest.TestCase):
    run_counter = 3000
    setUpClass = classmethod(fixtures.Stage5DatabaseTest.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.Stage5DatabaseTest.tearDownClass.__func__)
    setUp = fixtures.Stage5DatabaseTest.setUp
    tearDown = fixtures.Stage5DatabaseTest.tearDown
    register = fixtures.Stage5DatabaseTest.register
    auth = staticmethod(fixtures.Stage5DatabaseTest.auth)
    seed_candidate = fixtures.Stage5DatabaseTest.seed_candidate
    seed_profile_job = fixtures.Stage5DatabaseTest.seed_profile_job
    run_mock = fixtures.Stage5DatabaseTest.run_mock

    def test_requested_global_dna_precedes_older_batch_work(self):
        from app.modules.analytics.reader_dna import enqueue_dna
        from app.modules.analytics.gemini_worker import claim_next_job
        owner = uuid.UUID(self.register()['user']['id'])
        _, profile = self.seed_profile_job(owner)
        self.db.execute(text("UPDATE ia.jobs SET not_before=now()-interval '1 day' WHERE owner_id=:owner"), {'owner': owner})
        enqueue_dna(self.db, owner, profile, self.settings.gemini_model, self.settings.reader_dna_prompt_version)
        self.db.commit()
        job = claim_next_job(self.db, self.settings)
        self.assertEqual(job['job_kind'], 'reader_profile')
        self.assertEqual(job['attempts'], 1)

    def seed_dna(self, owner, source):
        from app.modules.analytics.reader_dna import enqueue_dna
        job, profile = self.seed_profile_job(owner)
        self.db.execute(text('DELETE FROM ia.jobs WHERE id=:id'), {'id':job['id']})
        self.db.execute(text('UPDATE ia.reader_profile_versions SET payload=CAST(:payload AS jsonb),data_hash=:hash WHERE id=:id'),
                        {'id': profile, 'payload': canonical_json(source), 'hash': content_hash(source)})
        enqueue_dna(self.db, owner, profile, self.settings.gemini_model, self.settings.reader_dna_prompt_version)
        self.db.commit()
        return profile

    def test_complete_essence_and_supported_evolution_persist_without_extra_calls(self):
        account = self.register()
        owner = uuid.UUID(account['user']['id'])
        source = payload()
        self.seed_dna(owner, source)
        provider = EssenceGemini(profile_evidence_units(source))
        self.assertTrue(self.run_mock(provider))
        self.assertEqual(len(provider.calls), 1)
        first = self.client.get('/api/me/ai/profile', headers=self.auth(account)).json()
        self.assertEqual(first['analysis']['content']['reader_essence']['summary'], SUMMARY)
        public_profile = self.db.execute(text("SELECT id FROM app.perfiles WHERE owner_user_id=:owner AND kind='personal'"), {'owner': owner}).scalar_one()
        public = self.client.get(f'/api/profiles/{public_profile}/literary-dna', headers=self.auth(account))
        self.assertEqual(public.status_code, 200, public.text)
        self.assertNotIn('reader_essence', public.text)
        self.assertNotIn('evolution', public.text)
        first_id = first['dna_version_id']
        source['books'][0]['review'] += ' Ahora doy mayor importancia a los dilemas que al combate.'
        self.seed_dna(owner, source)
        provider = EssenceGemini(profile_evidence_units(source), changed=True)
        self.assertTrue(self.run_mock(provider))
        second = self.client.get('/api/me/ai/profile', headers=self.auth(account)).json()
        evolution = second['analysis']['content']['evolution']
        self.assertTrue(evolution['has_meaningful_changes'])
        self.assertEqual(evolution['reference_version_id'], first_id)
        self.assertEqual(len(provider.calls), 1)

    def test_large_profile_synthesizes_in_existing_worker_and_accounts_for_calls(self):
        account = self.register()
        owner = uuid.UUID(account['user']['id'])
        source = payload(5)
        self.seed_dna(owner, source)
        provider = EssenceGemini(profile_evidence_units(source))
        self.assertTrue(self.run_mock(provider))
        row = self.db.execute(text('SELECT content FROM ia.reader_dna WHERE owner_id=:owner'), {'owner':owner}).scalar_one()
        self.assertEqual(row['reader_essence']['evidence_level'], 'sufficient')
        synthesis = [request for request in provider.calls if request.accounting_phase == 'dna_synthesis']
        self.assertEqual(len(synthesis), 1)
        self.assertGreater(len(provider.calls), 1)
        count = self.db.execute(text('SELECT count(*) FROM ia.call_ledger')).scalar_one()
        self.assertEqual(count, len(provider.calls))

    def test_history_deduplicates_recommendations_has_stable_order_and_is_private(self):
        account = self.register()
        owner = uuid.UUID(account['user']['id'])
        job, profile = self.seed_profile_job(owner)
        first = fixtures.MockGemini()
        self.assertTrue(self.run_mock(first))
        result = self.client.get('/api/me/ai/profile/history', headers=self.auth(account))
        self.assertEqual(result.status_code, 200, result.text)
        versions = result.json()['items']
        self.assertEqual(len(versions), 1, 'Recommendation output must not duplicate the DNA version')
        self.assertEqual(versions[0]['version'], 1)
        self.assertEqual(versions[0]['content']['schema_version'], 2)
        self.assertEqual(versions[0]['source_profile_id'], str(profile))
        self.db.execute(text("UPDATE ia.jobs SET status='pending',not_before=now() WHERE id=:id"), {'id':job['id']})
        self.db.commit()
        cached = fixtures.MockGemini()
        self.assertTrue(self.run_mock(cached))
        self.assertEqual(cached.calls, [])
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.reader_dna WHERE owner_id=:owner'), {'owner':owner}).scalar_one(), 1)
        self.seed_profile_job(owner, text_body='Una nueva experiencia con otro libro.')
        self.assertTrue(self.run_mock(fixtures.MockGemini()))
        versions = self.client.get('/api/me/ai/profile/history', headers=self.auth(account)).json()['items']
        self.assertEqual([version['version'] for version in versions], [2, 1])
        self.assertEqual(versions[0]['content']['evolution']['reference_version_id'], versions[1]['dna_version_id'])
        page = self.client.get('/api/me/ai/profile/history?before=2', headers=self.auth(account)).json()['items']
        self.assertEqual([version['version'] for version in page], [1])
        other = self.register()
        self.assertEqual(self.client.get('/api/me/ai/profile/history', headers=self.auth(other)).json()['items'], [])
        self.assertEqual(self.client.get('/api/me/ai/profile/history').status_code, 401)

    def test_failed_new_generation_preserves_previous_valid_analysis_and_history(self):
        from app.modules.analytics.providers.base import AIProviderInvalidResponseError
        account = self.register()
        owner = uuid.UUID(account['user']['id'])
        self.seed_profile_job(owner)
        self.assertTrue(self.run_mock(fixtures.MockGemini()))
        previous = self.client.get('/api/me/ai/profile', headers=self.auth(account)).json()['analysis']
        self.seed_profile_job(owner, text_body='Otra reseña distinta para preparar la actualización.')
        self.assertTrue(self.run_mock(fixtures.MockGemini(AIProviderInvalidResponseError('incomplete'))))
        current = self.client.get('/api/me/ai/profile', headers=self.auth(account))
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()['analysis']['id'], previous['id'])
        self.assertEqual(current.json()['analysis']['content'], previous['content'])
        self.assertTrue(current.json()['needs_refresh'])
        self.assertEqual(len(self.client.get('/api/me/ai/profile/history', headers=self.auth(account)).json()['items']), 1)

    def test_history_is_owner_scoped_read_only_and_globally_numbered(self):
        db = MagicMock()
        owner = uuid.uuid4()
        db.execute.return_value.mappings.return_value.all.return_value = []
        response = Response()
        adaptive_router.history(response, SimpleNamespace(id=owner), db, 20, None)
        sql, params = db.execute.call_args.args
        self.assertIn('row_number()', str(sql))
        self.assertIn('a.owner_id=:owner', str(sql))
        self.assertEqual(params['owner'], owner)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        db.commit.assert_not_called()
