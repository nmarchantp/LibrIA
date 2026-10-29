"""Real merge/recovery transactions, with distinct connections for races."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import time
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.modules.books.models import Work,Edition
from app.modules.books.catalog_models import CatalogOperation,WorkRedirect
from app.modules.books.canonical import resolve_canonical_work,identity_snapshot
from app.modules.books.merge_execution import execute_merge
from app.modules.books.merge_scope import scope_fingerprint
from app.modules.books.consistency import current_reviews
from tests import test_catalog_phase6 as phase6


class Phase7HTTP(phase6.Phase6HTTP):
    def setUp(self):
        super().setUp()
        flag=patch.object(get_settings(),'catalog_admin_merge_enabled',True);flag.start();self.addCleanup(flag.stop)

    def simulate(self):
        result=self.request()
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def merge(self,preview=None,key=None,selected=None,**extra):
        preview=preview or self.simulate()
        body=dict(confirmation='FUSIONAR',reason='Reviewed synthetic bibliographic evidence',metadata_policy='preserve_destination',library_policy='preserve_all',review_ids=selected or [])
        body.update(extra)
        return self.client.post('/api/admin/catalog/merge-previews/'+preview['preview_id']+'/execute',json=body,headers={'Idempotency-Key':key or str(uuid.uuid4())})

    def reverse_preview(self,operation):
        result=self.client.post('/api/admin/catalog/merges/'+operation+'/reversal-preview')
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def reverse(self,preview,preserve=None,key=None):
        return self.client.post('/api/admin/catalog/reversal-previews/'+preview['preview_id']+'/execute',
            json=dict(confirmation='REVERTIR',reason='Controlled synthetic recovery',preserve_physical=preserve or []),headers={'Idempotency-Key':key or str(uuid.uuid4())})

    def test_merge_and_reversal_preserve_physical_history(self):
        a=self.reading(self.work_id,self.edition_id);b=self.reading(self.other_id,self.other_edition)
        before=self.counts()
        op=self.merge();self.assertEqual(op.status_code,200,op.text)
        self.assertEqual(self.counts(),before)
        with Session(self.engine) as db:
            self.assertEqual(str(resolve_canonical_work(db,uuid.UUID(self.work_id)).canonical_work_id),self.other_id)
        preview=self.reverse_preview(op.json()['operation_id'])
        self.assertEqual(preview['changes'],[])
        result=self.reverse(preview);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.counts(),before)
        with Session(self.engine) as db:self.assertEqual(str(resolve_canonical_work(db,uuid.UUID(self.work_id)).canonical_work_id),self.work_id)
        (Path(__file__).resolve().parents[3]/'docs'/'catalog-canonical-phase7-example.json').write_text(json.dumps(dict(merge=op.json(),reversal_preview=preview,reversal=result.json(),reading_ids=[a,b]),indent=2)+'\n',encoding='utf-8')

    def test_explicit_older_public_review_is_selected(self):
        older=self.review(self.work_id,5);newer=self.review(self.other_id,1)
        preview=self.simulate()
        self.assertEqual(self.merge(preview).status_code,422)
        result=self.merge(preview,selected=[older]);self.assertEqual(result.status_code,200,result.text)
        rows=self.client.get('/api/reviews/by-book/'+self.work_id).json()['items']
        self.assertEqual([r['id'] for r in rows],[older])
        from app.modules.books.community import public_rating
        with Session(self.engine) as db:
            rating,count=public_rating(db,{uuid.UUID(self.other_id)})
            self.assertEqual(float(rating),5);self.assertEqual(count,1)

    def test_private_choice_never_publishes_and_other_review_survives(self):
        self.review(self.work_id,5)
        hidden=self.review(self.other_id,1,status='hidden')
        result=self.merge(selected=[hidden]);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/reviews/by-book/'+self.work_id).json()['items'],[])
        with Session(self.engine) as db:
            rows=current_reviews(db,{uuid.UUID(self.work_id)})
            self.assertEqual(rows[0].status,'hidden')

    def test_scoped_fingerprint_ignores_unrelated_work(self):
        preview=self.simulate()
        with Session(self.engine) as db,db.begin():db.add(Work(title='Unrelated synthetic work '+str(uuid.uuid4())))
        result=self.merge(preview);self.assertEqual(result.status_code,200,result.text)

    def test_relevant_change_rejects_execution(self):
        preview=self.simulate()
        with Session(self.engine) as db,db.begin():db.get(Edition,uuid.UUID(self.edition_id)).language='fr'
        self.assertEqual(self.merge(preview).status_code,409)

    def test_idempotent_confirmation_and_payload_conflict(self):
        preview=self.simulate();key=str(uuid.uuid4())
        first=self.merge(preview,key);second=self.merge(preview,key)
        self.assertEqual(first.status_code,200,first.text);self.assertEqual(first.json(),second.json())
        self.assertEqual(self.merge(preview,key,reason='Different command').status_code,409)

    def test_concurrent_confirmations_same_key(self):
        preview=self.simulate();key=str(uuid.uuid4())
        body=dict(confirmation='FUSIONAR',reason='Concurrent synthetic confirmation',metadata_policy='preserve_destination',library_policy='preserve_all',review_ids=[])
        def run():
            with Session(self.engine) as db,db.begin():
                return execute_merge(db,uuid.UUID(self.actor),uuid.UUID(preview['preview_id']),key,body)
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual(results[0],results[1])

    def test_complete_rollback_after_redirect_insert(self):
        from app.modules.books import merge_execution
        original=merge_execution.scope_state;calls=[]
        def fail(*args):
            calls.append(1)
            if len(calls)==2:raise RuntimeError('injected post redirect failure')
            return original(*args)
        preview=self.simulate()
        with patch.object(merge_execution,'scope_state',side_effect=fail),self.assertRaises(RuntimeError):self.merge(preview)
        with Session(self.engine) as db:self.assertEqual(str(resolve_canonical_work(db,uuid.UUID(self.work_id)).canonical_work_id),self.work_id)
        self.assertEqual(self.merge(preview).status_code,200)

    def test_reversal_with_later_reading_requires_explicit_attribution(self):
        op=self.merge().json()
        self.reading(self.other_id,self.other_edition)
        preview=self.reverse_preview(op['operation_id'])
        self.assertTrue(preview['changes']);self.assertTrue(preview['can_execute'])
        self.assertEqual(self.reverse(preview).status_code,422)
        result=self.reverse(preview,[r['entity'] for r in preview['changes']]);self.assertEqual(result.status_code,200,result.text)

    def test_later_merge_dependency_blocks_reversal(self):
        op=self.merge().json()
        with Session(self.engine) as db,db.begin():
            third=Work(title='Later synthetic target');db.add(third);db.flush();third_id=str(third.id)
        preview=self.request(source_work_id=self.other_id,target_work_id=third_id).json()
        second=self.merge(preview);self.assertEqual(second.status_code,200,second.text)
        recovery=self.reverse_preview(op['operation_id'])
        self.assertTrue(recovery['blockers']);self.assertFalse(recovery['can_execute'])
        self.assertEqual(self.reverse(recovery,[r['entity'] for r in recovery['changes']]).status_code,409)

    def test_reversal_idempotent_and_version_changes(self):
        with Session(self.engine) as db:before=identity_snapshot(db).version
        op=self.merge().json();preview=self.reverse_preview(op['operation_id']);key=str(uuid.uuid4())
        first=self.reverse(preview,key=key);second=self.reverse(preview,key=key)
        self.assertEqual(first.status_code,200,first.text);self.assertEqual(first.json(),second.json())
        with Session(self.engine) as db:self.assertNotEqual(identity_snapshot(db).version,before)

    def test_search_library_reviews_and_etl_use_same_selection(self):
        self.reading(self.work_id,self.edition_id);self.reading(self.other_id,self.other_edition)
        selected=self.review(self.work_id,5);self.review(self.other_id,1)
        self.assertEqual(self.merge(selected=[selected]).status_code,200)
        library=self.client.get('/api/readings/me').json()
        self.assertEqual(len(library),1)
        detail=self.client.get('/api/books/'+self.work_id)
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()['libria']['workId'],self.other_id)
        from app.modules.analytics.etl import extract,transform
        from app.modules.analytics.reader_evidence import extract_personal
        cutoff=datetime.now(timezone.utc)+timedelta(seconds=1)
        with self.engine.connect() as connection:
            extracted=extract(connection,datetime(2020,1,1,tzinfo=timezone.utc),cutoff)
            rows=[r for r in extracted[-1] if r['owner_user_id']==uuid.UUID(self.actor)]
            self.assertEqual([str(r['id']) for r in rows],[selected])
            evidence=[r for r in extract_personal(connection,cutoff) if r['user_id']==uuid.UUID(self.actor) and r['source_kind']=='review']
            self.assertEqual([str(r['source_id']) for r in evidence],[selected])

    def test_admin_permissions_and_execution_flag(self):
        preview=self.simulate()
        with patch.object(get_settings(),'catalog_admin_merge_enabled',False):self.assertEqual(self.merge(preview).status_code,404)
        with Session(self.engine) as db,db.begin():
            from app.modules.users.identity_models import AccountPermission
            db.delete(db.get(AccountPermission,(uuid.UUID(self.actor),'admin')))
        self.assertEqual(self.merge(preview).status_code,403)

    def test_invalid_confirmation_and_unknown_review_choice(self):
        preview=self.simulate()
        self.assertEqual(self.merge(preview,confirmation='yes').status_code,422)
        self.assertEqual(self.merge(preview,selected=[str(uuid.uuid4())]).status_code,422)

    def test_simulation_and_execution_volume_measurements(self):
        results=[]
        for count in (0,100,1000):
            with Session(self.engine) as db,db.begin():
                db.add_all([Work(title='Unrelated benchmark '+str(uuid.uuid4())) for _ in range(count)])
                a=Work(title='Benchmark source');b=Work(title='Benchmark target');db.add_all([a,b]);db.flush();source,target=str(a.id),str(b.id)
            start=time.perf_counter();preview=self.request(source_work_id=source,target_work_id=target).json();preview_ms=(time.perf_counter()-start)*1000
            start=time.perf_counter();result=self.merge(preview);execute_ms=(time.perf_counter()-start)*1000
            self.assertEqual(result.status_code,200,result.text)
            results.append(dict(additional_unrelated_works=count,preview_ms=round(preview_ms,3),execute_ms=round(execute_ms,3)))
        (Path(__file__).resolve().parents[3]/'docs'/'catalog-canonical-phase7-performance.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')

    def test_expired_preview_cannot_execute(self):
        preview=self.simulate()
        with patch('app.modules.books.merge_execution.datetime') as clock:
            clock.now.return_value=datetime.now(timezone.utc)+timedelta(hours=1)
            self.assertEqual(self.merge(preview).status_code,409)

    def test_public_search_reflects_merge_without_importing(self):
        with Session(self.engine) as db:title=db.get(Work,uuid.UUID(self.work_id)).title
        before=self.counts()
        with patch('app.modules.books.discovery.google_request',return_value={'items':[]}),patch('app.modules.books.discovery.open_library.search',return_value={'items':[]}):
            original=self.client.get('/api/books',params={'q':title}).json()
            self.assertEqual(len(original['items']),2)
            self.assertEqual(self.merge().status_code,200)
            merged=self.client.get('/api/books',params={'q':title}).json()
            self.assertEqual([r['libria']['workId'] for r in merged['items']],[self.other_id])
        self.assertEqual(self.counts(),before)

    def test_post_merge_incorporation_exposes_ambiguous_requested_attribution(self):
        from app.modules.books.resolution import AdditionCommand,incorporate_book
        operation=self.merge().json()
        with Session(self.engine) as db,db.begin():
            added=incorporate_book(db,AdditionCommand(actor_user_id=uuid.UUID(self.actor),request_key=str(uuid.uuid4()),
                internal_work_id=uuid.UUID(self.work_id),requested_reference=self.work_id))
            self.assertEqual(added.physical_work_id,self.other_id)
        preview=self.reverse_preview(operation['operation_id'])
        self.assertTrue(preview['ambiguous_attributions'])
        self.assertEqual(self.reverse(preview).status_code,422)
        decision=[r['entity'] for r in preview['changes']]
        result=self.reverse(preview,decision)
        self.assertEqual(result.status_code,200,result.text)
        with Session(self.engine) as db:
            from app.modules.library.models import Reading
            self.assertEqual(str(db.get(Reading,uuid.UUID(added.reading_id)).work_id),self.other_id)

    def test_writer_barrier_waits_for_an_independent_transaction(self):
        preview=self.simulate()
        body=dict(confirmation='FUSIONAR',reason='Independent writer race',metadata_policy='preserve_destination',library_policy='preserve_all',review_ids=[])
        def attempt():
            with Session(self.engine) as db:
                try:
                    with db.begin():return execute_merge(db,uuid.UUID(self.actor),uuid.UUID(preview['preview_id']),str(uuid.uuid4()),body)
                except HTTPException as error:return error.status_code
        with Session(self.engine) as writer:
            work=writer.scalar(select(Work).where(Work.id==uuid.UUID(self.work_id)).with_for_update())
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(attempt)
                deadline=time.monotonic()+5
                waiting=False
                while time.monotonic()<deadline:
                    with self.engine.connect() as observer:
                        waiting=bool(observer.scalar(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND classid=73155 AND objid=1 AND NOT granted")))
                    if waiting:break
                    time.sleep(.01)
                self.assertTrue(waiting,'Merger must wait behind the source writer')
                work.title+=' committed after simulation';writer.commit()
                self.assertEqual(future.result(timeout=10),409)


for _name in dir(phase6.Phase6HTTP):
    if _name.startswith('test_') and _name not in Phase7HTTP.__dict__:setattr(Phase7HTTP,_name,None)
