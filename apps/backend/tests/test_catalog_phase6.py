"""HTTP and transactional integration on owned disposable PostgreSQL only."""
from datetime import datetime, timedelta, timezone
import json
import uuid
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.books.models import Work
from app.modules.books.merge_preview import preview_merge,validate_preview,fingerprint
from app.modules.users.identity_models import AccountPermission
from tests import test_catalog_phase5 as phase5


class Phase6HTTP(phase5.Phase5HTTP):
    # Reuse fixture methods, not inherited test methods (removed below).
    def setUp(self):
        super().setUp()
        flag=patch.object(get_settings(),'catalog_admin_preview_enabled',True)
        flag.start(); self.addCleanup(flag.stop)
        with Session(self.engine) as db,db.begin():
            db.add(AccountPermission(user_id=uuid.UUID(self.actor),permission='admin'))

    def request(self, route='/merge-previews', **payload):
        return self.client.post('/api/admin/catalog'+route,json=payload or dict(source_work_id=self.work_id,target_work_id=self.other_id))

    def test_permission_is_effective_not_role(self):
        self.assertTrue(self.client.get('/api/roles/access').json()['admin'])
        reader=self.new_actor()
        response=self.client.post('/api/admin/catalog/compare',headers={'X-Test-Actor':reader},json=dict(source_work_id=self.work_id,target_work_id=self.other_id))
        self.assertEqual(response.status_code,403)

    def test_independent_comparison_and_no_bibliographic_writes(self):
        before=self.counts()
        with Session(self.engine) as db: digest=fingerprint(db)
        response=self.request()
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        from pathlib import Path
        (Path(__file__).resolve().parents[3]/'docs'/'catalog-canonical-phase6-example.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        self.assertFalse(result['execution_available'])
        self.assertIn('matching_title_not_identity',result['evidence']['candidates'])
        self.assertEqual(self.counts(),before)
        with Session(self.engine) as db: self.assertEqual(fingerprint(db),digest)
        self.assertEqual(self.request('/merge-previews/'+result['preview_id']+'/validate').status_code,200)

    def test_shared_libraries_reviews_privacy_and_invalidation(self):
        self.reading(self.work_id); self.reading(self.other_id)
        self.review(self.work_id,status='published'); self.review(self.other_id,status='draft')
        result=self.request().json()
        self.assertEqual(result['impact']['shared_libraries'],1)
        self.assertEqual(result['impact']['reading_attempts'],2)
        self.assertEqual(result['impact']['rereads'],0)
        self.assertEqual(result['expected_effects']['projected_rereads'],1)
        self.assertEqual(result['impact']['review_states'],{'published':1,'draft':1})
        self.assertEqual(len(result['conflicts']),1)
        self.assertNotIn('Synthetic review',json.dumps(result))
        self.assertIn('etl',result['impact']['invalidation'])

    def test_changed_data_rejects_validation(self):
        result=self.request().json()
        with Session(self.engine) as db,db.begin(): db.get(Work,uuid.UUID(self.work_id)).title+=' changed'
        self.assertEqual(self.request('/merge-previews/'+result['preview_id']+'/validate').status_code,409)

    def test_expiry(self):
        result=self.request().json()
        with Session(self.engine) as db:
            db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            with self.assertRaises(HTTPException) as error:
                validate_preview(db,uuid.UUID(self.actor),uuid.UUID(result['preview_id']),datetime.now(timezone.utc)+timedelta(hours=1))
            self.assertEqual(error.exception.status_code,409)

    def test_same_canonical_root_rejected(self):
        self.redirect()
        self.assertEqual(self.request().status_code,409)

    def test_historical_source_resolves(self):
        with Session(self.engine) as db,db.begin():
            third=Work(title='Independent third'); db.add(third); db.flush(); third_id=str(third.id)
        self.redirect()
        result=self.request(source_work_id=self.work_id,target_work_id=third_id)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['source']['canonical_id'],self.other_id)

    def test_failure_rolls_back_preview(self):
        with Session(self.engine) as db:
            before=db.scalar(text('SELECT count(*) FROM app.simulaciones_fusion'));db.rollback()
            with self.assertRaises(RuntimeError):
                with db.begin():
                    db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
                    preview_merge(db,uuid.UUID(self.actor),uuid.UUID(self.work_id),uuid.UUID(self.other_id))
                    raise RuntimeError('injected')
            self.assertEqual(db.scalar(text('SELECT count(*) FROM app.simulaciones_fusion')),before)

    def test_flag_disabled(self):
        with patch.object(get_settings(),'catalog_admin_preview_enabled',False):
            self.assertEqual(self.request().status_code,404)

    def test_concurrent_snapshot_detects_later_commit(self):
        with Session(self.engine) as db:
            db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            result=preview_merge(db,uuid.UUID(self.actor),uuid.UUID(self.work_id),uuid.UUID(self.other_id))
            def update():
                with Session(self.engine) as other,other.begin(): other.get(Work,uuid.UUID(self.other_id)).title+=' concurrent'
            with ThreadPoolExecutor(max_workers=1) as pool: pool.submit(update).result(timeout=10)
            db.commit()
        self.assertEqual(self.request('/merge-previews/'+result['preview_id']+'/validate').status_code,409)

    def test_selected_target_is_preserved_and_reversible_direction(self):
        result=self.request(source_work_id=self.other_id,target_work_id=self.work_id).json()
        self.assertEqual(result['target']['canonical_id'],self.work_id)
        self.assertEqual(result['expected_effects']['physical_work_count_delta'],0)

    def test_hidden_reviews_remain_hidden(self):
        self.review(self.work_id,status='hidden')
        before=self.request().json()['impact']['review_states']
        self.assertEqual(before,{'hidden':1})
        self.assertEqual(self.request('/compare').json()['impact']['review_states'],before)

    def test_different_editions_authors_and_isbn_are_not_merge_evidence(self):
        from app.modules.books.models import Edition,Author,WorkAuthor
        from tests.test_catalog_phase3 import unique_isbn
        with Session(self.engine) as db,db.begin():
            db.get(Edition,uuid.UUID(self.edition_id)).isbn13=unique_isbn()
            db.get(Edition,uuid.UUID(self.other_edition)).isbn13=unique_isbn()
            author=Author(name='Other bibliographic author');db.add(author);db.flush()
            db.add(WorkAuthor(work_id=uuid.UUID(self.other_id),author_id=author.id,position=2))
        result=self.request().json()
        self.assertEqual(len(result['evidence']['contradictions']),2)
        self.assertFalse(result['evidence']['automatic_merge_allowed'])

    def test_cycle_errors_fail_closed(self):
        from app.modules.books.canonical import CanonicalIdentityError
        with patch('app.modules.books.merge_preview.identity_snapshot',side_effect=CanonicalIdentityError('cycle')):
            self.assertEqual(self.request().status_code,409)

    def test_revoked_permission_and_role_only_denied(self):
        from app.modules.users.models import User
        with Session(self.engine) as db,db.begin():
            db.delete(db.get(AccountPermission,(uuid.UUID(self.actor),'admin')))
            db.get(User,uuid.UUID(self.actor)).role='admin'
        self.assertFalse(self.client.get('/api/roles/access').json()['admin'])
        self.assertEqual(self.request().status_code,403)

    def test_preview_audit_is_immutable(self):
        from sqlalchemy.exc import IntegrityError,DBAPIError
        result=self.request().json()
        with Session(self.engine) as db:
            with self.assertRaises(DBAPIError):
                db.execute(text('DELETE FROM app.simulaciones_fusion WHERE id=:id'),dict(id=uuid.UUID(result['preview_id'])))
            db.rollback()
        self.assertEqual(self.request('/merge-previews/'+result['preview_id']+'/validate').status_code,200)

    def test_unknown_work_and_search(self):
        self.assertEqual(self.request(source_work_id=str(uuid.uuid4()),target_work_id=self.other_id).status_code,404)
        result=self.client.get('/api/admin/catalog/works',params={'q':'%'} )
        self.assertEqual(result.status_code,200)
        self.assertIsInstance(result.json(),list)

    def test_admin_metadata_only_and_no_gemini(self):
        with Session(self.engine) as db: before=fingerprint(db)
        result=self.request().json()
        with Session(self.engine) as db:
            self.assertEqual(fingerprint(db),before)
            from app.modules.books.merge_preview import VERSION
            self.assertEqual(db.scalar(text('SELECT version FROM app.simulaciones_fusion WHERE id=:id'),dict(id=uuid.UUID(result['preview_id']))),VERSION)

    def test_service_rejects_unsafe_transaction(self):
        with Session(self.engine) as db:
            with self.assertRaises(HTTPException) as error:
                preview_merge(db,uuid.UUID(self.actor),uuid.UUID(self.work_id),uuid.UUID(self.other_id))
            self.assertEqual(error.exception.status_code,409)

    def test_confirmed_external_reference_provenance_is_displayed(self):
        from app.modules.books.catalog_models import CatalogOperation,WorkReference
        with Session(self.engine) as db,db.begin():
            op=CatalogOperation(actor_user_id=uuid.UUID(self.actor),operation_type='admin_import',request_key=str(uuid.uuid4()),
                request_hash='b'*64,target_work_id=uuid.UUID(self.work_id),reason='Synthetic provenance fixture',evidence={'synthetic':True},context={})
            db.add(op);db.flush()
            db.add(WorkReference(work_id=uuid.UUID(self.work_id),operation_id=op.id,provider='open-library',reference_type='work',
                external_id='OL'+str(uuid.uuid4().int)+'W',verification_status='confirmed',verified_by='open-library-detail',
                verified_at=datetime.now(timezone.utc),evidence={'transport':'server_detail','snapshot_sha256':'a'*64}))
        result=self.request().json()
        reference=result['source']['references'][0]
        self.assertEqual(reference['verification_status'],'confirmed')
        self.assertEqual(reference['provenance']['transport'],'server_detail')

    def test_invalid_legacy_isbn_is_exposed_without_repair(self):
        from app.modules.books.models import Edition
        with Session(self.engine) as db,db.begin(): db.get(Edition,uuid.UUID(self.edition_id)).isbn13='0000000000000'
        result=self.request().json()
        self.assertEqual(result['source']['editions'][0]['isbn_status'],'invalid_or_contradictory_requires_review')
        with Session(self.engine) as db:self.assertEqual(db.get(Edition,uuid.UUID(self.edition_id)).isbn13,'0000000000000')


# Fixture inheritance without rerunning all phase-5 tests under an admin account.
for _name in dir(phase5.Phase5HTTP):
    if _name.startswith('test_') and _name not in Phase6HTTP.__dict__:
        setattr(Phase6HTTP,_name,None)
