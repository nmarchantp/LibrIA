"""Nightly book policy; all inference uses an in-memory provider."""
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import Settings
from app.core.database import engine
from app.modules.analytics import reading_analysis as policy
from app.modules.analytics.adaptive_router import book_analysis, refresh_book
from app.modules.analytics.gemini_context import EvidenceUnit
from app.modules.analytics.gemini_worker import process_one
from app.modules.analytics.providers.base import StructuredGenerationResult, TokenUsage


class FakeGemini:
    name = 'gemini'

    def __init__(self, callback=None, error=None):
        self.calls = 0
        self.callback, self.error = callback, error

    def generate_structured(self, request):
        self.calls += 1
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        payload = json.loads(request.user_content)
        ids = [item['evidence_id'] for item in payload['evidence'] if item['source_kind'] == 'review']
        raw = {'event_kind': payload['event_kind'],
               'experience_summary': {'text':'Disfrutaste la voz narrativa según tu reseña.','evidence_ids':ids},
               'valued_elements': [{'text':'La voz narrativa','evidence_ids':ids}]}
        return StructuredGenerationResult(content=request.validate(raw), provider='gemini',
            model='mock', usage=TokenUsage(input_tokens=100, output_tokens=30, total_tokens=130))


class PolicyUnitTest(unittest.TestCase):
    def test_reading_transport_is_inline_and_business_bounds_remain_strict(self):
        from app.modules.analytics.gemini_contracts import reading_transport_json_schema, ReadingAnalysis
        schema=reading_transport_json_schema()
        serialized=json.dumps(schema)
        self.assertNotIn('$ref',serialized)
        self.assertNotIn('$defs',serialized)
        self.assertNotIn('maxItems',serialized)
        self.assertIn('experience_summary',schema['required'])
        self.assertEqual(schema['properties']['experience_summary']['type'],'object')
        self.assertEqual(ReadingAnalysis.model_json_schema()['properties']['observation_evidence']['maxItems'],61)

    def test_claim_attached_citations_build_exact_indices_without_model_guessing(self):
        from app.modules.analytics.gemini_contracts import normalize_reading_transport, ReadingAnalysis
        raw={'event_kind':'finish','experience_summary':{'text':'Una lectura interesante.','evidence_ids':['review:own']},
             'valued_elements':[{'text':'La voz narrativa.','evidence_ids':['note:own']}]}
        value=ReadingAnalysis.model_validate(normalize_reading_transport(raw)).model_dump()
        self.assertEqual([(r['field'],r['index']) for r in value['observation_evidence']],
                         [('experience_summary',0),('valued_elements',0)])
        self.assertEqual(value['evidence_ids'],['note:own','review:own'])

    def test_normalization_preserves_meaning_and_nested_ratings(self):
        self.assertEqual(policy.normalize({'body': '  Me\n gusta  ', 'dimensions': {'plot': 4}}),
                         {'body': 'Me gusta', 'dimensions': {'plot': 4}})

    def test_fingerprint_ignores_global_catalog_version_only(self):
        self.assertEqual(policy.fingerprint({'identity_version': 'a', 'work_id': 'same'}),
                         policy.fingerprint({'identity_version': 'b', 'work_id': 'same'}))
        self.assertNotEqual(policy.fingerprint({'work_id': 'a'}), policy.fingerprint({'work_id': 'b'}))

    def test_context_sorts_units_and_ignores_review_revision(self):
        owner, event, work, review = [uuid.uuid4() for _ in range(4)]
        reading = EvidenceUnit(f'reading:{event}', 'reading', event, work, {'status': 'finished'})
        unit = EvidenceUnit(f'review:{review}:1', 'review', review, work, {'body': '  Me gusta ', 'status': 'draft'})
        db = MagicMock(); db.execute.return_value.scalar.return_value = True
        with patch('app.modules.analytics.gemini_worker._individual_context', return_value=({'work_id': str(work)}, [unit, reading])):
            first, _ = policy.context(db, owner, event)
        unit2 = EvidenceUnit(f'review:{review}:8', 'review', review, work, {'body': 'Me gusta', 'status': 'draft'})
        with patch('app.modules.analytics.gemini_worker._individual_context', return_value=({'work_id': str(work)}, [reading, unit2])):
            second, _ = policy.context(db, owner, event)
        self.assertEqual(policy.fingerprint(first), policy.fingerprint(second))

    def test_whitespace_review_and_numeric_rating_are_insufficient(self):
        key = uuid.uuid4(); db = MagicMock(); db.execute.return_value.scalar.return_value = True
        for body in ('', ' \n\t '):
            units = [EvidenceUnit(f'reading:{key}', 'reading', key, key, {'status': 'finished'}),
                     EvidenceUnit(f'review:{key}', 'review', key, key, {'body': body, 'rating': 5})]
            with self.subTest(body=body), patch('app.modules.analytics.gemini_worker._individual_context', return_value=({}, units)):
                with self.assertRaisesRegex(policy.IneligibleReading, 'requires_review'):
                    policy.context(db, key, key)

    def test_refresh_including_force_is_only_a_read(self):
        owner = SimpleNamespace(id=uuid.uuid4()); db = MagicMock()
        with patch('app.modules.analytics.adaptive_router.book_analysis', return_value={'status': 'waiting_nightly_processing'}) as read:
            refresh_book(uuid.uuid4(), Response(), owner, db, force=True)
        read.assert_called_once(); db.commit.assert_not_called(); db.execute.assert_not_called()


@unittest.skipUnless(os.getenv('LIBRIA_NIGHTLY_TEST') == '1', 'requires isolated nightly test database')
class NightlyDatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not engine.url.database.startswith('libria_nightly_test_') or engine.url.host not in {'localhost', '127.0.0.1'}:
            raise RuntimeError('Refusing non-disposable PostgreSQL')
        cls.factory = sessionmaker(engine, expire_on_commit=False)

    def setUp(self):
        with engine.begin() as c:
            c.execute(text('TRUNCATE app.usuarios,app.obras,app.autores,analytics.ejecuciones_etl CASCADE'))
            c.execute(text('TRUNCATE ia.provider_cooldowns'))
        self.db = self.factory()
        self.settings = Settings(_env_file=None, database_url=engine.url.render_as_string(hide_password=False),
            ai_requests_per_minute=600, catalog_canonical_enabled=False)
        self.owner, self.profile, self.work, self.entry, self.reading, self.event, self.review, self.run = [uuid.uuid4() for _ in range(8)]
        self.db.execute(text("INSERT INTO app.usuarios(id,username,display_name) VALUES(:id,:username,'Lector nocturno')"),
                        {'id': self.owner, 'username': uuid.uuid4().hex})
        self.db.execute(text("INSERT INTO app.perfiles(id,kind,owner_user_id,display_name) VALUES(:id,'personal',:owner,'Lector nocturno')"),
                        {'id': self.profile, 'owner': self.owner})
        self.db.execute(text("INSERT INTO app.obras(id,title,identity_key) VALUES(:id,'Obra nocturna',:key)"), {'id': self.work, 'key': uuid.uuid4().hex})
        self.db.execute(text('INSERT INTO app.entradas_biblioteca(id,user_id,work_id) VALUES(:id,:owner,:work)'),
                        {'id': self.entry, 'owner': self.owner, 'work': self.work})
        self.db.execute(text("""INSERT INTO app.lecturas(id,library_entry_id,work_id,status,current_page,total_pages,started_at,finished_at)
          VALUES(:id,:entry,:work,'finished',100,100,now()-interval '1 day',now())"""),
          {'id': self.reading, 'entry': self.entry, 'work': self.work})
        self.db.execute(text("""INSERT INTO app.eventos_lectura(id,reading_id,actor_user_id,kind,previous_page,page,total_pages,is_public)
          VALUES(:id,:reading,:owner,'finish',0,100,100,false)"""), {'id': self.event, 'reading': self.reading, 'owner': self.owner})
        self.db.execute(text("""INSERT INTO analytics.ejecuciones_etl(id,status,business_date,started_at,period_start,source_cutoff_at,transform_version)
          VALUES(:id,'running','2026-10-28',now(),now()-interval '1 day',now(),'nightly-test')"""), {'id': self.run})
        self.db.commit()
        self.canonical = patch('app.modules.books.canonical.enabled', return_value=False); self.canonical.start()

    def tearDown(self):
        self.canonical.stop(); self.db.close()

    def add_review(self, body='Me gustó la voz narrativa y el conflicto de los personajes.'):
        self.db.execute(text("""INSERT INTO app.resenas(id,author_profile_id,created_by_user_id,work_id,body,rating,status)
          VALUES(:id,:profile,:owner,:work,:body,5,'draft')"""),
          {'id': self.review, 'profile': self.profile, 'owner': self.owner, 'work': self.work, 'body': body})
        self.db.commit()

    def state(self):
        return policy.book_state(self.db, self.owner, [self.work], self.settings)

    def prepare(self, cutoff=None):
        result = policy.prepare_nightly(self.db, cutoff or datetime.now(timezone.utc) + timedelta(seconds=1), self.run, self.settings)
        self.db.commit(); return result

    def infer(self, provider=None):
        self.db.commit()
        fake = provider or FakeGemini()
        process_one(provider=fake, settings=self.settings, session_factory=self.factory)
        self.db.expire_all()
        return fake

    def edit_review(self, body):
        self.db.execute(text('UPDATE app.resenas SET body=:body,revision_number=revision_number+1 WHERE id=:id'), {'body': body, 'id': self.review})
        self.db.commit()

    def test_finish_and_abandon_require_review(self):
        self.assertEqual(self.state()['status'], 'requires_review')
        self.assertEqual(self.prepare()['prepared'], 0)
        self.db.execute(text("UPDATE app.lecturas SET status='abandoned',finished_at=NULL,abandoned_at=now() WHERE id=:id"), {'id': self.reading})
        self.db.execute(text("UPDATE app.eventos_lectura SET kind='abandon' WHERE id=:id"), {'id': self.event}); self.db.commit()
        self.assertEqual(self.state()['status'], 'requires_review')
        self.add_review(); self.assertEqual(self.prepare()['prepared'], 1)
        self.infer(); self.assertEqual(self.state()['analysis']['content']['event_kind'], 'abandon')

    def test_pending_and_reading_are_ineligible_even_with_review(self):
        self.add_review()
        for status in ('reading', 'pending'):
            self.db.execute(text("""UPDATE app.lecturas SET status=:status,finished_at=NULL,current_page=0,
              started_at=CASE WHEN :status='pending' THEN NULL ELSE now() END WHERE id=:id"""), {'status': status, 'id': self.reading})
            self.db.commit()
            self.assertEqual(self.state()['status'], 'not_eligible'); self.assertEqual(self.prepare()['prepared'], 0)

    def test_one_book_request_survives_reconnect_and_waits_for_cut(self):
        before = datetime.now(timezone.utc)
        self.add_review()
        self.assertEqual(self.state()['status'], 'waiting_nightly_processing')
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.jobs')).scalar(), 0)
        self.db.close(); self.db = self.factory()
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.reading_analysis_requests')).scalar(), 1)
        self.assertEqual(self.prepare(before)['prepared'], 0)
        self.assertEqual(self.prepare()['prepared'], 1)
        self.assertEqual(self.prepare()['prepared'], 0)
        self.assertEqual(self.state()['status'], 'queued')
        self.assertEqual(self.infer().calls, 1)
        self.assertEqual(self.state()['status'], 'completed')

    def test_repeated_reads_and_refresh_do_not_generate(self):
        self.add_review(); self.prepare(); self.infer()
        analysis = self.state()['analysis']['id']
        for _ in range(3):
            self.assertEqual(self.state()['analysis']['id'], analysis)
            self.assertEqual(refresh_book(self.work, Response(), SimpleNamespace(id=self.owner), self.db)['status'], 'completed')
        self.assertEqual(self.prepare()['reused'], 1)
        self.assertEqual(self.infer().calls, 0)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.jobs')).scalar(), 1)

    def test_edits_consolidate_keep_previous_and_preserve_history(self):
        self.add_review(); self.prepare(); self.infer(); previous = self.state()['analysis']['id']
        self.edit_review('Me interesa el conflicto.'); self.edit_review('Me interesa la voz narrativa.')
        state = self.state(); self.assertEqual(state['status'], 'update_pending'); self.assertEqual(state['analysis']['id'], previous)
        self.prepare(); self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.jobs')).scalar(), 2)
        self.infer(); self.assertEqual(self.state()['status'], 'completed'); self.assertNotEqual(self.state()['analysis']['id'], previous)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.analyses WHERE valid')).scalar(), 2)
        self.assertEqual(self.state()['analysis']['version'], 2)

    def test_reverting_review_reuses_exact_previous_content(self):
        original = 'Me gusta la voz narrativa.'
        self.add_review(original); self.prepare(); self.infer(); previous = self.state()['analysis']['id']
        self.edit_review('No me gusta.'); self.edit_review(original)
        self.assertEqual(self.state()['status'], 'completed'); self.assertEqual(self.state()['analysis']['id'], previous)
        self.assertEqual(self.prepare()['prepared'], 0)

    def test_relevant_evidence_changes_but_cover_does_not(self):
        self.add_review(); self.prepare(); self.infer()
        for sql in ("UPDATE app.resenas SET rating=4 WHERE id=:id", "UPDATE app.resenas SET dimension_ratings='{\"characters\": 4}' WHERE id=:id"):
            self.db.execute(text(sql), {'id': self.review}); self.db.commit(); self.assertEqual(self.state()['status'], 'update_pending')
            self.prepare(); self.infer()
        self.db.execute(text("UPDATE app.lecturas SET notebook='{\"summary\":\"Me gusta su voz\"}' WHERE id=:id"), {'id': self.reading})
        self.db.commit(); self.assertEqual(self.state()['status'], 'update_pending'); self.prepare(); self.infer()
        self.db.execute(text("UPDATE app.eventos_lectura SET reflection='{\"body\":\"Final emotivo\"}' WHERE id=:id"), {'id': self.event})
        self.db.commit(); self.assertEqual(self.state()['status'], 'update_pending')

    def test_edit_during_generation_keeps_history_and_waits_next_night(self):
        self.add_review(); self.prepare()
        self.infer(FakeGemini(callback=lambda: self.edit_review('La nueva reseña expresa otra experiencia.')))
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.analyses')).scalar(), 1)
        self.assertEqual(self.state()['status'], 'update_pending')
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM ia.jobs WHERE status='pending'")).scalar(), 0)
        self.prepare(); self.infer(); self.assertEqual(self.state()['status'], 'completed')

    def test_review_removed_during_generation_prevents_publication(self):
        self.add_review(); self.prepare()
        def remove():
            self.db.execute(text('DELETE FROM app.resenas WHERE id=:id'), {'id': self.review}); self.db.commit()
        self.infer(FakeGemini(callback=remove))
        self.assertEqual(self.state()['status'], 'requires_review')
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.analyses')).scalar(), 0)

    def test_review_removal_scrubs_derived_history_and_snapshot(self):
        self.add_review(); self.prepare(); self.infer()
        self.db.execute(text('DELETE FROM app.resenas WHERE id=:id'), {'id': self.review}); self.db.commit()
        self.assertIsNone(self.state()['analysis']); self.assertEqual(self.state()['status'], 'requires_review')
        self.assertEqual(self.db.execute(text('SELECT content FROM ia.analyses')).scalar(), {})
        self.assertEqual(self.db.execute(text('SELECT payload FROM ia.reading_analysis_snapshots')).scalar(), {})

    def test_review_and_reading_belong_to_authenticated_owner(self):
        self.add_review(); self.prepare(); self.infer()
        with self.assertRaises(HTTPException) as error:
            book_analysis(self.work, Response(), SimpleNamespace(id=uuid.uuid4()), self.db)
        self.assertEqual(error.exception.status_code, 404)

    def test_obsolete_snapshot_is_not_sent_to_provider(self):
        self.add_review(); self.prepare(); self.edit_review('Cambió antes de comenzar.')
        self.assertEqual(self.infer().calls, 0)
        self.assertEqual(self.state()['status'], 'waiting_nightly_processing')

    def test_failure_preserves_previous_and_usage_limits(self):
        from app.modules.analytics.providers.base import AIProviderAuthenticationError
        self.add_review(); self.prepare(); self.infer(); previous = self.state()['analysis']['id']
        self.edit_review('Me gusta el estilo.'); self.prepare()
        self.infer(FakeGemini(error=AIProviderAuthenticationError('mock authentication failure')))
        self.assertEqual(self.state()['status'], 'failed'); self.assertEqual(self.state()['analysis']['id'], previous)
        self.assertGreater(self.db.execute(text('SELECT count(*) FROM ia.usage_metrics')).scalar(), 0)

    def test_note_and_theory_edits_are_personal_evidence(self):
        self.add_review(); self.prepare(); self.infer()
        for kind in ('note', 'theory'):
            post = uuid.uuid4()
            self.db.execute(text("""INSERT INTO app.publicaciones(id,user_id,author_profile_id,publication_type,
              source,author_role,kind,body,work_id) VALUES(:id,:owner,:profile,:kind,'community','lector','community',
              'Me interesó la evolución del personaje.',:work)"""),
              {'id':post,'owner':self.owner,'profile':self.profile,'kind':kind,'work':self.work})
            self.db.commit(); self.assertEqual(self.state()['status'], 'update_pending')
            self.prepare(); self.infer()
            self.db.execute(text('UPDATE app.publicaciones SET body=:body WHERE id=:id'), {'id':post,'body':'La voz narrativa me emocionó.'})
            self.db.commit(); self.assertEqual(self.state()['status'], 'update_pending')
            self.prepare(); self.infer()
            self.db.execute(text('DELETE FROM app.publicaciones WHERE id=:id'), {'id':post}); self.db.commit()
            # Removing the added note restores the original, still permitted
            # evidence and therefore reuses its earlier interpretation.
            self.assertEqual(self.state()['status'], 'completed')
            self.prepare(); self.infer()

    def test_failed_retry_is_authorized_only_by_next_night_and_is_bounded(self):
        from app.modules.analytics.providers.base import AIProviderAuthenticationError
        from app.modules.analytics.adaptive_router import retry_book
        self.add_review(); self.prepare(); self.infer(FakeGemini(error=AIProviderAuthenticationError('mock')))
        state = retry_book(self.work, Response(), SimpleNamespace(id=self.owner), self.db)
        self.assertEqual(state['status'], 'waiting_nightly_processing')
        self.assertTrue(state['retry_scheduled'])
        self.assertEqual(self.infer().calls, 0)
        self.assertEqual(self.prepare()['prepared'], 1)
        self.infer(FakeGemini(error=AIProviderAuthenticationError('mock')))
        self.db.execute(text('UPDATE ia.jobs SET attempts=3')); self.db.commit()
        with self.assertRaises(HTTPException):
            retry_book(self.work, Response(), SimpleNamespace(id=self.owner), self.db)
        self.assertEqual(self.db.execute(text('SELECT attempts FROM ia.jobs')).scalar(), 3)

    def test_latest_terminal_event_does_not_borrow_previous_reading_analysis(self):
        self.add_review(); self.prepare(); self.infer(); first = self.state()['analysis']['id']
        reading, event = uuid.uuid4(), uuid.uuid4()
        self.db.execute(text("""INSERT INTO app.lecturas(id,library_entry_id,work_id,status,current_page,total_pages,started_at,finished_at)
          VALUES(:id,:entry,:work,'finished',100,100,now(),now())"""), {'id':reading,'entry':self.entry,'work':self.work})
        self.db.execute(text("""INSERT INTO app.eventos_lectura(id,reading_id,actor_user_id,kind,previous_page,page,total_pages,is_public)
          VALUES(:id,:reading,:owner,'finish',0,100,100,false)"""), {'id':event,'reading':reading,'owner':self.owner})
        self.db.commit()
        self.assertIsNone(self.state()['analysis']); self.assertEqual(self.state()['reading_event_id'], event)
        self.prepare(); self.infer(); self.assertNotEqual(self.state()['analysis']['id'], first)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.analyses')).scalar(), 2)

    def test_full_daily_etl_prepares_without_provider_and_is_idempotent(self):
        from app.modules.analytics.etl import run_day
        self.add_review()
        day = datetime.now(timezone.utc).date() + timedelta(days=1)
        with patch('app.modules.analytics.gemini_worker._invoke', side_effect=AssertionError('ETL cannot invoke provider')):
            result = run_day(day, db_engine=engine, now=datetime.now(timezone.utc)+timedelta(days=3))
            again = run_day(day, db_engine=engine, now=datetime.now(timezone.utc)+timedelta(days=3))
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['summary']['reading_analyses']['prepared'], 1)
        self.assertEqual(again['status'], 'already_completed')
        self.assertEqual(self.state()['status'], 'queued')

    def manual_run(self, cutoff=None):
        from app.modules.analytics.etl import run_manual
        run = uuid.uuid4()
        cutoff = cutoff or datetime.now(timezone.utc)
        self.db.execute(text("INSERT INTO app.permisos_cuenta(user_id,permission) VALUES(:owner,'admin') ON CONFLICT DO NOTHING"), {'owner':self.owner})
        self.db.execute(text('''INSERT INTO analytics.ejecuciones_etl
          (id,status,started_at,period_start,source_cutoff_at,transform_version,run_kind,requested_by)
          VALUES(:id,'running',now(),:start,:cutoff,'manual-test','manual',:owner)'''),
          {'id':run,'start':cutoff-timedelta(days=29),'cutoff':cutoff,'owner':self.owner})
        self.db.commit()
        with patch('app.modules.analytics.gemini_worker._invoke', side_effect=AssertionError('ETL cannot invoke provider')):
            run_manual(run, db_engine=engine)
        return run

    def test_manual_etl_prepares_and_worker_generates_without_waiting_midnight(self):
        from app.modules.analytics.etl import run_manual
        self.add_review()
        self.assertEqual(self.state()['status'],'waiting_nightly_processing')
        run = self.manual_run()
        result = self.db.execute(text('SELECT status,summary FROM analytics.ejecuciones_etl WHERE id=:id'),{'id':run}).mappings().one()
        self.assertEqual(result['status'],'succeeded')
        self.assertEqual(result['summary']['reading_analyses']['prepared'],1)
        self.assertEqual(self.state()['status'],'queued')
        self.db.commit()
        run_manual(run, db_engine=engine)
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.jobs')).scalar(),1)
        self.assertEqual(self.infer().calls,1)
        self.assertEqual(self.state()['status'],'completed')

    def test_manual_etl_respects_its_cutoff_and_later_run_picks_up_changes(self):
        self.add_review()
        cutoff = datetime.now(timezone.utc)
        self.edit_review('Me interesa el nuevo conflicto.')
        run = self.manual_run(cutoff)
        summary = self.db.execute(text('SELECT summary FROM analytics.ejecuciones_etl WHERE id=:id'),{'id':run}).scalar()
        self.assertEqual(summary['reading_analyses']['prepared'],0)
        self.assertEqual(self.state()['status'],'waiting_nightly_processing')
        self.manual_run()
        self.assertEqual(self.state()['status'],'queued')

    def test_manual_etl_keeps_previous_analysis_visible_during_update(self):
        self.add_review(); self.prepare(); self.infer()
        previous=self.state()['analysis']['id']
        self.edit_review('Prefiero el estilo de la narración.')
        self.manual_run()
        state=self.state()
        self.assertEqual(state['status'],'update_pending')
        self.assertEqual(state['job']['status'],'pending')
        self.assertEqual(state['analysis']['id'],previous)
        self.infer()
        self.assertEqual(self.state()['status'],'completed')
        self.assertNotEqual(self.state()['analysis']['id'],previous)

    def test_canonical_review_matches_only_resolved_work_with_optional_edition(self):
        root, operation = uuid.uuid4(), uuid.uuid4()
        self.db.execute(text("INSERT INTO app.obras(id,title,identity_key) VALUES(:id,'Obra raíz',:key)"), {'id':root,'key':uuid.uuid4().hex})
        self.db.execute(text("""INSERT INTO app.resenas(id,author_profile_id,created_by_user_id,work_id,body,rating,status)
          VALUES(:id,:profile,:owner,:work,'Me gustó la voz narrativa.',5,'draft')"""),
          {'id':self.review,'profile':self.profile,'owner':self.owner,'work':root})
        self.db.commit()
        with patch('app.modules.books.canonical.enabled', return_value=True):
            self.assertEqual(self.state()['status'], 'requires_review')
            self.db.execute(text("""INSERT INTO app.operaciones_catalogo(id,actor_user_id,operation_type,request_key,
              request_hash,source_work_id,target_work_id,reason,evidence,context)
              VALUES(:id,:owner,'merge',:key,:hash,:source,:target,'Prueba canónica','{}','{}')"""),
              {'id':operation,'owner':self.owner,'key':uuid.uuid4().hex,'hash':'0'*64,'source':self.work,'target':root})
            self.db.execute(text("""INSERT INTO app.redirecciones_obras(id,source_work_id,target_work_id,operation_id)
              VALUES(:id,:source,:target,:operation)"""), {'id':uuid.uuid4(),'source':self.work,'target':root,'operation':operation})
            self.db.commit()
            self.assertEqual(self.prepare()['prepared'], 1)
            self.infer(); self.assertEqual(self.state()['status'], 'completed')
            payload, _ = policy.context(self.db,self.owner,self.event)
            self.assertEqual(payload['work_id'],str(root))
            self.assertEqual(self.db.execute(text('SELECT edition_id FROM app.lecturas WHERE id=:id'),{'id':self.reading}).scalar(),None)

    def test_irrelevant_catalog_display_changes_do_not_regenerate(self):
        self.add_review(); self.prepare(); self.infer()
        self.db.execute(text("UPDATE app.obras SET updated_at=clock_timestamp() WHERE id=:id"), {'id':self.work})
        self.db.execute(text("UPDATE app.resenas SET is_spoiler=true WHERE id=:id"), {'id':self.review})
        self.db.commit(); self.assertEqual(self.state()['status'], 'completed'); self.assertEqual(self.prepare()['prepared'],0)

    def test_invalid_observation_citations_are_not_persisted(self):
        from app.modules.analytics.providers.base import AIProviderInvalidResponseError
        class BadCitation(FakeGemini):
            def generate_structured(self, request):
                payload=json.loads(request.user_content)
                raw={'event_kind':payload['event_kind'],'experience_summary':'Sin respaldo verificable.',
                     'evidence_ids':[payload['evidence'][0]['evidence_id']],
                     'observation_evidence':[{'field':'experience_summary','index':0,'evidence_ids':['foreign:wrong']}]}
                try:
                    request.validate(raw)
                except ValueError as error:
                    raise AIProviderInvalidResponseError('unsupported citations') from error
        self.add_review(); self.prepare(); self.infer(BadCitation())
        self.assertEqual(self.db.execute(text('SELECT count(*) FROM ia.analyses WHERE reading_event_id IS NOT NULL')).scalar(),0)
        self.assertEqual(self.state()['status'],'failed')

    def test_unrelated_book_change_does_not_postpone_this_request(self):
        self.add_review()
        before = self.db.execute(text('SELECT changed_at FROM ia.reading_analysis_requests WHERE reading_event_id=:id'), {'id':self.event}).scalar()
        other = uuid.uuid4()
        self.db.execute(text("INSERT INTO app.obras(id,title,identity_key) VALUES(:id,'Otra obra',:key)"), {'id':other,'key':uuid.uuid4().hex})
        self.db.execute(text("""INSERT INTO app.resenas(id,author_profile_id,created_by_user_id,work_id,body,status)
          VALUES(:id,:profile,:owner,:work,'Otra experiencia.','draft')"""),
          {'id':uuid.uuid4(),'profile':self.profile,'owner':self.owner,'work':other})
        self.db.commit()
        after = self.db.execute(text('SELECT changed_at FROM ia.reading_analysis_requests WHERE reading_event_id=:id'), {'id':self.event}).scalar()
        self.assertEqual(before,after)

    def test_private_review_remains_valid_when_hidden_from_community(self):
        self.add_review(); self.prepare(); self.infer(); original=self.state()['analysis']['id']
        for status in ('published','hidden'):
            self.db.execute(text('UPDATE app.resenas SET status=:status,published_at=COALESCE(published_at,now()) WHERE id=:id'),
                            {'id':self.review,'status':status}); self.db.commit()
            self.assertEqual(self.state()['status'],'completed')
            self.assertEqual(self.state()['analysis']['id'],original)
            self.assertEqual(self.prepare()['prepared'],0)
