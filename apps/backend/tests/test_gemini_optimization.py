"""Network-free contracts and opt-in isolated PostgreSQL concurrency tests."""
import copy
import json
import os
import threading
import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import text
from app.core.config import Settings
from app.modules.analytics.call_accounting import (
    BudgetExhausted, LocalRateLimited, job_totals, monthly_snapshot, reserve_call, settle_call, usage_cost, reconcile_call,
)
from app.modules.analytics.providers.base import AIProviderInvalidResponseError, AIProviderQuotaError, TokenUsage
from app.modules.analytics.providers.gemini import GeminiProvider
from app.modules.analytics.reader_dna import dna_fingerprint, enqueue_dna, find_dna
from app.modules.analytics.gemini_worker import claim_next_job, process_one
from tests import test_gemini_provider as adapter_fixtures
from tests import test_stage5_gemini_worker as worker_fixtures
from tests.test_gemini_provider import FakeResponse
from tests.test_stage5_gemini_worker import MockGemini


def metadata(**changes):
    values = dict(prompt_token_count=100, candidates_token_count=20,
                  thoughts_token_count=10, total_token_count=130)
    values.update(changes)
    return SimpleNamespace(**values)


class OptimizationUnitTest(unittest.TestCase):
    def test_cost_includes_reasoning_once(self):
        usage = GeminiProvider._usage(SimpleNamespace(usage_metadata=metadata()))
        self.assertTrue(usage.verified)
        self.assertEqual(usage.accounted_tokens, 130)
        self.assertEqual(usage_cost(Settings(_env_file=None), usage), Decimal('.00010500'))

    def test_missing_metadata_is_not_verified_zero(self):
        usage = GeminiProvider._usage(SimpleNamespace())
        self.assertFalse(usage.verified)
        self.assertEqual(usage.present_fields, frozenset())

    def test_retry_after_http_date(self):
        error = SimpleNamespace(code=429, response=SimpleNamespace(headers={'Retry-After':'Wed, 28 Oct 2099 12:00:00 GMT'}),details='',message='')
        self.assertGreater(GeminiProvider._map_api_error(error).retry_after, 3600)

    def test_partial_metadata_is_not_verified(self):
        usage = GeminiProvider._usage(SimpleNamespace(usage_metadata=SimpleNamespace(prompt_token_count=100)))
        self.assertFalse(usage.verified)
        self.assertNotIn('candidates_token_count', usage.present_fields)

    def test_inconsistent_total_is_not_verified(self):
        self.assertFalse(GeminiProvider._usage(SimpleNamespace(usage_metadata=metadata(total_token_count=120))).verified)

    def test_invalid_json_preserves_metadata(self):
        fixture = adapter_fixtures.GeminiProviderTest()
        with self.assertRaises(AIProviderInvalidResponseError) as raised:
            fixture.provider(response=FakeResponse('broken', usage=metadata())).generate_structured(fixture.request())
        self.assertTrue(raised.exception.usage.verified)
        self.assertEqual(raised.exception.usage.reasoning_tokens, 10)
        self.assertEqual(raised.exception.request_id, 'gemini-response-1')

    def test_truncated_valid_json_is_rejected_with_usage(self):
        fixture = adapter_fixtures.GeminiProviderTest()
        response = FakeResponse('{"title":"partial","score":4}', usage=metadata())
        response.candidates = [SimpleNamespace(finish_reason='MAX_TOKENS')]
        with self.assertRaises(AIProviderInvalidResponseError) as raised:
            fixture.provider(response=response).generate_structured(fixture.request())
        self.assertEqual(raised.exception.finish_reason, 'MAX_TOKENS')
        self.assertEqual(raised.exception.usage.accounted_tokens, 130)

    def test_429_retry_after_and_daily_quota_are_distinct(self):
        error = SimpleNamespace(code=429, response=SimpleNamespace(headers={'Retry-After':'120'}),
                                details='requests per minute', message='')
        mapped = GeminiProvider._map_api_error(error)
        self.assertEqual(mapped.retry_after, 120)
        self.assertFalse(mapped.quota_exhausted)
        error.details = 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'
        self.assertTrue(GeminiProvider._map_api_error(error).quota_exhausted)

    def test_dna_identity_ignores_uninterpreted_fields_but_invalidates_notes(self):
        payload = {'books':[{'reading_id':str(uuid.uuid4()),'work_id':str(uuid.uuid4()),
                             'rating':5,'metadata':{'title':'Book'},'notebook':'Original'}]}
        baseline = dna_fingerprint(payload)
        self.assertEqual(baseline, dna_fingerprint({**payload,'etl_run_id':'different'}))
        changed = copy.deepcopy(payload); changed['books'][0]['notebook'] = 'Edited'
        self.assertNotEqual(baseline, dna_fingerprint(changed))


@unittest.skipUnless(os.getenv('LIBRIA_GEMINI_FIX_TEST') == '1', 'requires isolated PostgreSQL')
class OptimizationDatabaseTest(unittest.TestCase):
    run_counter = 1000
    setUpClass = classmethod(worker_fixtures.Stage5DatabaseTest.setUpClass.__func__)
    tearDownClass = classmethod(worker_fixtures.Stage5DatabaseTest.tearDownClass.__func__)
    setUp = worker_fixtures.Stage5DatabaseTest.setUp
    tearDown = worker_fixtures.Stage5DatabaseTest.tearDown
    register = worker_fixtures.Stage5DatabaseTest.register
    auth = staticmethod(worker_fixtures.Stage5DatabaseTest.auth)
    seed_candidate = worker_fixtures.Stage5DatabaseTest.seed_candidate
    seed_profile_job = worker_fixtures.Stage5DatabaseTest.seed_profile_job
    seed_terminal_job = worker_fixtures.Stage5DatabaseTest.seed_terminal_job
    run_mock = worker_fixtures.Stage5DatabaseTest.run_mock

    def profile_job(self):
        owner = uuid.UUID(self.register()['user']['id'])
        job, profile = self.seed_profile_job(owner)
        return owner, job, profile

    def claim(self):
        self.db.commit()
        with self.factory() as db:
            return claim_next_job(db, self.settings)

    def test_invalid_json_consumption_is_measured_not_reserved(self):
        _, job, _ = self.profile_job()
        error = AIProviderInvalidResponseError('invalid', usage=GeminiProvider._usage(
            SimpleNamespace(usage_metadata=metadata())), finish_reason='MAX_TOKENS')
        self.run_mock(MockGemini(error))
        row = self.db.execute(text('SELECT * FROM ia.call_ledger WHERE job_id=:job'), {'job':job['id']}).mappings().one()
        self.assertEqual(row['state'], 'measured')
        self.assertEqual(row['measured_cost_usd'], Decimal('.00010500'))
        self.assertEqual(row['finish_reason'], 'MAX_TOKENS')
        snapshot = monthly_snapshot(self.db, self.settings)
        self.assertEqual(snapshot['pending_reconciliation'], 0)
        self.assertEqual(snapshot['committed'], Decimal('.00010500'))

    def test_unknown_and_partial_usage_hold_reservations(self):
        _, _, _ = self.profile_job(); job = self.claim()
        with self.factory() as db:
            call = reserve_call(db, job['id'], 1, 'test', 100, 100, self.settings)
            settle_call(db, call, self.settings, usage=GeminiProvider._usage(SimpleNamespace()))
            snapshot = monthly_snapshot(db, self.settings)
            self.assertGreater(snapshot['pending_reconciliation'], 0)
            self.assertEqual(snapshot['measured'], 0)
            self.assertEqual(job_totals(db, job['id'])[1], 200)

    def test_rejected_request_releases_reservation_and_keeps_call(self):
        self.profile_job(); job = self.claim()
        with self.factory() as db:
            call = reserve_call(db,job['id'],1,'test',100,100,self.settings)
            settle_call(db,call,self.settings,error=AIProviderQuotaError('quota',status_code=429))
            self.assertEqual(monthly_snapshot(db,self.settings)['committed'],0)
            self.assertEqual(job_totals(db,job['id'])[:2],(1,0))

    def test_unknown_reservation_requires_verified_reconciliation(self):
        self.profile_job();job=self.claim()
        with self.factory() as db:
            call=reserve_call(db,job['id'],1,'test',1000,100,self.settings)
            settle_call(db,call,self.settings)
            self.assertGreater(monthly_snapshot(db,self.settings)['pending_reconciliation'],0)
            reconcile_call(db,call,self.settings,usage=TokenUsage(input_tokens=100,output_tokens=20,total_tokens=120),
                           request_id='verified-fixture',verification_reference='fixture-audit-1')
            snapshot=monthly_snapshot(db,self.settings)
            self.assertEqual(snapshot['pending_reconciliation'],0)
            self.assertEqual(snapshot['committed'],Decimal('.00008000'))

    def test_crashed_worker_reservation_survives_reclaim(self):
        self.profile_job();job=self.claim()
        with self.factory() as db:
            call=reserve_call(db,job['id'],1,'test',1000,100,self.settings)
            db.execute(text("UPDATE ia.jobs SET locked_at=now()-interval '1 hour' WHERE id=:id"),{'id':job['id']});db.commit()
            reclaimed=claim_next_job(db,self.settings)
            self.assertEqual(reclaimed['attempts'],2)
            self.assertEqual(db.execute(text('SELECT state FROM ia.call_ledger WHERE id=:id'),{'id':call}).scalar_one(),'unknown')
            self.assertEqual(job_totals(db,job['id'])[:2],(1,1100))

    def test_rpm_is_shared_and_rejections_still_count_as_requests(self):
        self.profile_job();job=self.claim()
        settings=self.settings.model_copy(update={'ai_requests_per_minute':1})
        with self.factory() as db:
            call=reserve_call(db,job['id'],1,'test',100,100,settings)
            settle_call(db,call,settings,error=AIProviderQuotaError('quota',status_code=429))
            with self.assertRaises(LocalRateLimited):
                reserve_call(db,job['id'],1,'test',100,100,settings)

    def test_budget_accumulates_across_attempts(self):
        self.profile_job(); job = self.claim()
        settings = self.settings.model_copy(update={'ai_job_token_budget':1000})
        with self.factory() as db:
            call = reserve_call(db,job['id'],1,'test',500,100,settings)
            settle_call(db,call,settings,usage=TokenUsage(input_tokens=500,output_tokens=100,total_tokens=600))
            db.execute(text("UPDATE ia.jobs SET attempts=2 WHERE id=:id"),{'id':job['id']}); db.commit()
            with self.assertRaisesRegex(BudgetExhausted,'job_budget_exhausted'):
                reserve_call(db,job['id'],2,'test',400,100,settings)

    def test_call_limit_accumulates_across_attempts(self):
        self.profile_job(); job = self.claim()
        settings = self.settings.model_copy(update={'ai_max_calls_per_job':1})
        with self.factory() as db:
            call = reserve_call(db,job['id'],1,'test',100,100,settings)
            settle_call(db,call,settings,usage=TokenUsage(input_tokens=1,total_tokens=1))
            db.execute(text('UPDATE ia.jobs SET attempts=2 WHERE id=:id'),{'id':job['id']});db.commit()
            with self.assertRaises(BudgetExhausted):
                reserve_call(db,job['id'],2,'test',1,1,settings)

    def test_concurrent_reservations_cannot_exceed_monthly_budget(self):
        self.profile_job(); self.profile_job(); jobs=[self.claim(),self.claim()]
        settings=self.settings.model_copy(update={'ai_monthly_budget_usd':.0003})
        barrier=threading.Barrier(2); results=[]; errors=[]
        def reserve(job):
            try:
                with self.factory() as db:
                    barrier.wait(timeout=5)
                    try: reserve_call(db,job['id'],1,'test',100,100,settings); results.append('reserved')
                    except BudgetExhausted: results.append('blocked')
            except Exception as error: errors.append(error)
        threads=[threading.Thread(target=reserve,args=(job,)) for job in jobs]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertFalse(errors)
        self.assertEqual(sorted(results),['blocked','reserved'])

    def test_429_pauses_other_jobs_and_respects_retry_after(self):
        _,job,_=self.profile_job()
        self.run_mock(MockGemini(AIProviderQuotaError('quota',status_code=429,retry_after=3600)))
        self.profile_job()
        self.assertIsNone(self.claim())
        delay=self.db.execute(text("SELECT extract(epoch FROM not_before-now()) FROM ia.jobs WHERE id=:id"),{'id':job['id']}).scalar_one()
        self.assertGreater(delay,3500)

    def test_daily_quota_does_not_retry_immediately(self):
        _,job,_=self.profile_job()
        self.run_mock(MockGemini(AIProviderQuotaError('daily',status_code=429,quota_exhausted=True)))
        delay=self.db.execute(text("SELECT extract(epoch FROM not_before-now()) FROM ia.jobs WHERE id=:id"),{'id':job['id']}).scalar_one()
        self.assertGreater(delay,86000)

    def test_dna_and_recommendations_reuse_without_calls(self):
        owner,job,profile=self.profile_job(); first=MockGemini(); self.run_mock(first)
        self.assertEqual(len(first.calls),2)
        self.db.execute(text("UPDATE ia.jobs SET status='pending',not_before=now() WHERE id=:id"),{'id':job['id']})
        # Simulate a crash after cache commit, before final publication.
        self.db.execute(text('DELETE FROM ia.recomendaciones_ia WHERE job_id=:id'),{'id':job['id']})
        self.db.execute(text("DELETE FROM ia.evidence WHERE analysis_id IN (SELECT id FROM ia.analyses WHERE job_id=:id AND target NOT LIKE '%dna%')"),{'id':job['id']})
        self.db.execute(text("DELETE FROM ia.analyses WHERE job_id=:id AND target NOT LIKE '%dna%'"),{'id':job['id']}); self.db.commit()
        second=MockGemini(); self.run_mock(second)
        self.assertEqual(second.calls,[])
        payload=self.db.execute(text('SELECT payload FROM ia.reader_profile_versions WHERE id=:id'),{'id':profile}).scalar_one()
        self.assertIsNotNone(find_dna(self.db,owner,payload,self.settings.gemini_model,self.settings.reader_dna_prompt_version))
        changed=copy.deepcopy(payload);changed['books'][0]['notebook']={'characters':'Different'}
        self.assertIsNone(find_dna(self.db,owner,changed,self.settings.gemini_model,self.settings.reader_dna_prompt_version))
        self.assertIsNone(find_dna(self.db,owner,payload,self.settings.gemini_model,'new-prompt'))

    def test_two_workers_generate_same_dna_once(self):
        owner,_,profile=self.profile_job()
        enqueue_dna(self.db,owner,profile,self.settings.gemini_model,self.settings.reader_dna_prompt_version);self.db.commit()
        provider=MockGemini(); errors=[]; barrier=threading.Barrier(2)
        def work():
            try:
                barrier.wait(timeout=5)
                process_one(provider=provider,settings=self.settings,session_factory=self.factory)
            except Exception as error: errors.append(error)
        threads=[threading.Thread(target=work) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=15)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertFalse(errors)
        self.assertEqual(sum(c.prompt_kind.value=='reader_profile' for c in provider.calls),1)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.reader_dna')).scalar_one(),1)

    def test_recommendation_prompt_change_reuses_dna_fixture(self):
        from app.modules.analytics.persistence import enqueue_recommendation_job
        _,_,profile=self.profile_job(); cold=MockGemini();self.run_mock(cold)
        # Replay the legacy stages when recommendation prompt changes: its
        # chunk cache was namespaced by that recommendation prompt as well.
        legacy=MockGemini()
        legacy_usage=[legacy.generate_structured(request).usage for request in cold.calls]
        changed_settings=self.settings.model_copy(update={'recommendation_prompt_version':'recommendations-fixture-next'})
        enqueue_recommendation_job(self.db,profile_version_id=profile,provider='gemini',
          model=self.settings.gemini_model,prompt_version=changed_settings.recommendation_prompt_version)
        self.db.commit()
        warm=MockGemini()
        process_one(provider=warm,settings=changed_settings,session_factory=self.factory)
        self.assertEqual(len(cold.calls),2)
        self.assertEqual(len(legacy.calls),2)
        self.assertEqual(sum(u.accounted_tokens for u in legacy_usage),240)
        self.assertEqual(len(warm.calls),1)
        self.assertEqual(warm.calls[0].prompt_kind.value,'recommendations')
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.reader_dna')).scalar_one(),1)
        # The fake returns exactly 100 input + 20 visible output per call.
        self.assertEqual(usage_cost(self.settings,TokenUsage(input_tokens=200,output_tokens=40,total_tokens=240)),Decimal('.00016000'))
        self.assertEqual(usage_cost(self.settings,TokenUsage(input_tokens=100,output_tokens=20,total_tokens=120)),Decimal('.00008000'))

    def test_dna_only_job_does_not_generate_recommendations(self):
        result=self.register(); owner=uuid.UUID(result['user']['id']);job,profile=self.seed_profile_job(owner)
        self.db.execute(text('DELETE FROM ia.jobs WHERE id=:id'),{'id':job['id']})
        enqueue_dna(self.db,owner,profile,self.settings.gemini_model,self.settings.reader_dna_prompt_version);self.db.commit()
        provider=MockGemini();self.run_mock(provider)
        self.assertEqual(len(provider.calls),1)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.recomendaciones_ia')).scalar_one(),0)
        with patch('app.modules.analytics.providers.gemini.GeminiProvider.generate_structured',side_effect=AssertionError('network forbidden')):
            response=self.client.get('/api/me/ai/profile',headers=self.auth(result))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'ready')
        self.assertIn('narrative_preferences',response.json()['analysis']['content'])
        self.assertIsNone(response.json()['job'])

    def test_pending_notebook_edits_wait_for_new_nightly_snapshot(self):
        result,first=self.seed_terminal_job(); _,second=self.seed_terminal_job(result=result)
        self.db.execute(text("UPDATE ia.jobs SET not_before=now()-interval '1 second'"));self.db.commit()
        reading=self.db.execute(text('SELECT reading_id FROM app.eventos_lectura WHERE id=:id'),{'id':first['reading_event_id']}).scalar_one()
        for version in (1,2):
            self.db.execute(text('UPDATE app.lecturas SET notebook=CAST(:body AS jsonb) WHERE id=:id'),
                            {'id':reading,'body':json.dumps({'characters':str(version)})});self.db.commit()
        rows=self.db.execute(text('SELECT id,not_before>now() deferred FROM ia.jobs')).all()
        flags={r.id:r.deferred for r in rows}
        self.assertFalse(flags[first['id']]);self.assertFalse(flags[second['id']])

    def test_distinct_events_are_not_merged(self):
        result,first=self.seed_terminal_job();_,second=self.seed_terminal_job(result=result)
        provider=MockGemini();self.run_mock(provider);self.run_mock(provider)
        self.assertEqual(len(provider.calls),2)
        events=self.db.execute(text('SELECT reading_event_id FROM ia.analyses WHERE reading_event_id IS NOT NULL')).scalars().all()
        self.assertEqual(set(events),{first['reading_event_id'],second['reading_event_id']})

    def test_same_event_result_is_reused_even_after_revision_flag(self):
        _,job=self.seed_terminal_job();provider=MockGemini();self.run_mock(provider)
        self.db.execute(text("UPDATE ia.jobs SET status='pending',not_before=now() WHERE id=:id"),{'id':job['id']});self.db.commit()
        cached=MockGemini();self.run_mock(cached);self.assertEqual(cached.calls,[])
        self.db.execute(text("UPDATE ia.jobs SET status='pending',revision=2,not_before=now() WHERE id=:id"),{'id':job['id']});self.db.commit()
        forced=MockGemini();self.run_mock(forced);self.assertEqual(len(forced.calls),0)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.analyses WHERE reading_event_id=:id'),{'id':job['reading_event_id']}).scalar_one(),1)

    def test_force_endpoint_preserves_contract_and_attempt_budget(self):
        result,job=self.seed_terminal_job();self.run_mock(MockGemini())
        self.db.execute(text("INSERT INTO app.permisos_cuenta(user_id,permission) VALUES (:id,'admin')"),
                        {'id':uuid.UUID(result['user']['id'])});self.db.commit()
        work=self.db.execute(text('SELECT r.work_id FROM app.lecturas r JOIN app.eventos_lectura ev ON ev.reading_id=r.id WHERE ev.id=:id'),
                             {'id':job['reading_event_id']}).scalar_one()
        response=self.client.post(f'/api/me/ai/books/{work}/refresh?force=true',headers=self.auth(result))
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['status'],'completed')
        self.assertEqual(response.json()['job']['attempts'],1)
        self.db.execute(text('UPDATE ia.jobs SET attempts=3 WHERE id=:id'),{'id':job['id']});self.db.commit()
        blocked=self.client.post(f'/api/me/ai/books/{work}/refresh?force=true',headers=self.auth(result))
        self.assertEqual(blocked.status_code,202)
        self.assertEqual(blocked.json()['job']['attempts'],3)
