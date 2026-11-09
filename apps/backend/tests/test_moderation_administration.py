"""Stage 3 HTTP operations against PostgreSQL, fixtures always roll back."""
import json
import uuid
import unittest
from unittest.mock import patch
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.users.identity_models import AccountPermission
from app.modules.social.models import Post,PostImage,PostBookCover,Review,ReviewRevision,PostComment,EventAttendance,PublicationEvent
from app.modules.social.moderation_models import ModerationRevision,ModerationAudit,ContentReport
from app.modules.books.community import public_rating
from app.modules.social.interaction_service import batch_counts
from tests import test_moderation_integration as integration
png=integration.png


class ModerationAdministrationTest(unittest.TestCase):
    setUp=integration.ModerationIntegrationTest.setUp
    tearDown=integration.ModerationIntegrationTest.tearDown
    make_reading=integration.ModerationIntegrationTest.make_reading
    make_event=integration.ModerationIntegrationTest.make_event
    owner=integration.ModerationIntegrationTest.owner
    viewer_user=integration.ModerationIntegrationTest.viewer_user
    payload=integration.ModerationIntegrationTest.payload
    pending_post=integration.ModerationIntegrationTest.pending_post

    def admin(self):
        if not self.db.get(AccountPermission,(self.other.id,'admin')):
            self.db.add(AccountPermission(user_id=self.other.id,permission='admin'));self.db.flush()
        app.dependency_overrides[get_current_user]=lambda:self.other

    def decide(self,item,action='approved',reason='Revisado con contexto literario',version=1):
        return self.client.post('/api/admin/moderation/'+item['pending_revision_id']+'/decision',
                                json={'action':action,'reason':reason,'expected_version':version})

    def report(self,kind='publication',identifier=None):
        self.viewer_user()
        result=self.client.post(f'/api/content-reports/{kind}/{identifier or self.post.id}',json={'reason':'spam','detail':'Revisar contexto'})
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def resolve(self,item,action='hidden',version=1,reason='Revisión administrativa',headers=None):
        return self.client.post('/api/admin/moderation/reports/'+item['id']+'/resolution',
            json={'action':action,'reason':reason,'expected_version':version},headers=headers or {})

    def test_real_admin_permission_and_revocation(self):
        item=self.pending_post()
        # owner has role admin but no account permission
        self.assertEqual(self.client.get('/api/admin/moderation').status_code,403)
        self.assertEqual(self.decide(item).status_code,403)
        self.admin()
        result=self.client.get('/api/admin/moderation')
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn(item['pending_revision_id'],[r['id'] for r in result.json()['items']])
        self.db.delete(self.db.get(AccountPermission,(self.other.id,'admin')));self.db.flush()
        self.assertEqual(self.decide(item).status_code,403)

    def test_approve_new_publication_and_replay_not_twice(self):
        item=self.pending_post();self.admin()
        result=self.decide(item);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/posts/'+item['id']).json()['body'],'Te voy a matar')
        self.assertEqual(self.decide(item).json(),result.json())
        post=self.db.get(Post,uuid.UUID(item['id']));self.assertEqual(post.moderation_version,2)
        self.assertEqual(self.decide(item,'rejected').status_code,409)
        audits=self.db.scalar(select(func.count()).select_from(ModerationAudit).where(ModerationAudit.revision_id==uuid.UUID(item['pending_revision_id']),ModerationAudit.action=='approved'))
        self.assertEqual(audits,1)

    def test_reject_new_and_edit_preserve_public_version(self):
        item=self.pending_post();self.admin()
        self.assertEqual(self.decide(item,'rejected').status_code,200)
        self.assertEqual(self.client.get('/api/posts/'+item['id']).status_code,404)
        self.owner()
        value=self.payload('Te voy a matar');value['publication_type']='note'
        result=self.client.put('/api/posts/'+str(self.post.id),json=value)
        self.assertEqual(result.status_code,200,result.text)
        edit=result.json();self.admin()
        self.assertEqual(self.decide(edit,'rejected').status_code,200)
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).json()['body'],'Public note')
        self.owner()
        status=self.client.get('/api/me/moderation/'+edit['pending_revision_id']).json()
        self.assertEqual(status['status'],'rejected')
        self.assertEqual(status['decision_reason'],'Revisado con contexto literario')

    def test_approve_event_edit_media_cover_dates_and_attendance(self):
        self.owner();item=self.client.post('/api/posts',json=self.payload(kind='event')).json()
        identifier=uuid.UUID(item['id'])
        image=PostImage(post_id=identifier,content_type='image/png',data=png())
        self.db.add_all([image,EventAttendance(post_id=identifier,user_id=self.viewer.id)]);self.db.flush()
        value=self.payload('Te voy a matar','event')
        value['event_details'].update(start_date='2026-12-14',end_date='2026-12-15')
        value.update(existing_image_ids=[],cover_mode='custom')
        result=self.client.put('/api/posts/'+item['id'],data={k:json.dumps(v) if isinstance(v,(dict,list)) else str(v) for k,v in value.items()},
            files=[('images',('new.png',png(),'image/png')),('book_cover',('cover.png',png(),'image/png'))])
        self.assertEqual(result.status_code,200,result.text)
        edit=result.json();self.admin()
        detail=self.client.get('/api/admin/moderation/'+edit['pending_revision_id']).json()
        self.assertEqual(detail['public_version']['body'],'Una invitación literaria')
        self.assertEqual(len(detail['attachments']),2)
        self.assertEqual(self.client.get('/api'+detail['attachments'][0]['url']).status_code,200)
        approved=self.decide(edit);self.assertEqual(approved.status_code,200,approved.text)
        self.assertIsNone(self.db.get(PostImage,image.id))
        self.assertIsNotNone(self.db.get(PostBookCover,identifier))
        self.assertIsNotNone(self.db.get(EventAttendance,(identifier,self.viewer.id)))
        visible=self.client.get('/api/posts/'+item['id']).json()
        self.assertEqual(visible['event_details']['start_date'],'2026-12-14')
        self.assertEqual(len(visible['images']),1)

    def test_obsolete_deleted_and_superseded_revisions(self):
        for mode in ('changed','deleted','superseded'):
            item=self.pending_post();record=self.db.get(Post,uuid.UUID(item['id']))
            if mode=='changed':record.body='Un cambio posterior';self.db.flush()
            elif mode=='deleted':self.assertEqual(self.client.delete('/api/posts/'+item['id']).status_code,204)
            else:self.client.put('/api/posts/'+item['id'],json=self.payload('Texto corregido'))
            self.admin()
            self.assertEqual(self.decide(item).status_code,409)

    def test_new_review_approval_updates_rating_and_history_once(self):
        self.viewer_user();before=public_rating(self.db,{self.work.id})
        result=self.client.post('/api/reviews',json={'work_id':str(self.work.id),'body':'Te voy a matar','rating':1})
        item=result.json();self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(public_rating(self.db,{self.work.id}),before)
        self.admin();result=self.decide(item);self.assertEqual(result.status_code,200,result.text)
        record=self.db.get(Review,uuid.UUID(item['id']))
        self.assertIsNotNone(record.published_at)
        self.assertIsNotNone(self.db.get(ReviewRevision,(record.id,1)))
        self.assertEqual(public_rating(self.db,{self.work.id})[1],before[1]+1)
        self.decide(item)
        self.assertEqual(record.revision_number,1)

    def test_review_edit_approval_and_rejection_keep_canonical_id(self):
        self.owner()
        result=self.client.put('/api/reviews/'+str(self.review.id),json={'body':'Te voy a matar','rating':1,'status':'published'})
        self.assertEqual(result.status_code,200,result.text)
        item=result.json();self.admin()
        self.assertEqual(self.decide(item,'rejected').status_code,200)
        self.assertEqual(self.review.body,'Public review')
        self.owner();item=self.client.put('/api/reviews/'+str(self.review.id),json={'body':'Te voy a matar','rating':2,'status':'published'}).json()
        self.admin();result=self.decide(item);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.review.body,'Te voy a matar')
        self.assertEqual(float(self.review.rating),2)

    def test_comment_approval_and_edit_rejection_all_destinations(self):
        for kind,identifier in [('publication',self.post.id),('review',self.review.id),('reading_event',self.events[0].id)]:
            path=f'/api/activities/{kind}/{identifier}/comments';self.viewer_user()
            item=self.client.post(path,json={'body':'Te voy a matar'}).json()['comment']
            self.admin();approved=self.decide(item);self.assertEqual(approved.status_code,200,approved.text)
            self.assertIn(item['id'],[r['id'] for r in self.client.get(path).json()])
            self.viewer_user()
            edit=self.client.put(path+'/'+item['id'],json={'body':'Te voy a matar ahora'}).json()['comment']
            self.admin();self.assertEqual(self.decide(edit,'rejected',version=2).status_code,200)
            self.assertEqual(self.db.get(PostComment,uuid.UUID(item['id'])).body,'Te voy a matar')

    def test_unique_reports_and_no_automatic_hide(self):
        first=self.report();second=self.report()
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).status_code,200)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ContentReport).where(ContentReport.post_id==self.post.id)),1)
        self.admin();data=self.client.get('/api/admin/moderation/reports').json()
        self.assertIn(first['id'],[r['id'] for r in data['items']])
        self.assertEqual(self.client.get('/api/admin/moderation/reports/'+first['id']).json()['reported_content']['body'],'Public note')

    def test_inaccessible_missing_and_invalid_reports(self):
        item=self.pending_post();self.viewer_user()
        for kind,identifier in [('publication',item['id']),('publication',uuid.uuid4()),('comment',uuid.uuid4())]:
            self.assertEqual(self.client.post(f'/api/content-reports/{kind}/{identifier}',json={'reason':'spam'}).status_code,404)
        self.assertEqual(self.client.post(f'/api/content-reports/reading_event/{self.private.id}',json={'reason':'spam'}).status_code,422)
        self.assertEqual(self.client.post(f'/api/content-reports/publication/{self.post.id}',json={'reason':'invented'}).status_code,422)

    def test_hide_restore_access_assets_counters_and_author_cannot_unhide(self):
        image=PostImage(post_id=self.post.id,content_type='image/png',data=png());self.db.add(image);self.db.flush()
        item=self.report();self.admin()
        hidden=self.resolve(item);self.assertEqual(hidden.status_code,200,hidden.text)
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).status_code,404)
        self.assertEqual(self.client.get(f'/api/posts/{self.post.id}/images/{image.id}').status_code,404)
        self.assertEqual(self.client.put(f'/api/activities/publication/{self.post.id}/like').status_code,404)
        self.owner();edited=self.client.put('/api/posts/'+str(self.post.id),json={**self.payload('Una corrección'),'publication_type':'note'})
        self.assertEqual(edited.status_code,200,edited.text)
        self.assertTrue(self.post.moderation_hidden)
        self.admin();restored=self.resolve(item,'restored',version=3)
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).status_code,200)

    def test_hide_review_and_comment_excludes_ratings_and_counts(self):
        before=public_rating(self.db,{self.work.id})
        item=self.report('review',self.review.id);self.admin()
        self.assertEqual(self.resolve(item).status_code,200)
        self.assertEqual(public_rating(self.db,{self.work.id})[1],before[1]-1)
        self.viewer_user();comment=self.client.post(f'/api/activities/publication/{self.post.id}/comments',json={'body':'Un comentario'}).json()['comment']
        item=self.report('comment',comment['id']);self.admin();self.assertEqual(self.resolve(item).status_code,200)
        comments=self.client.get(f'/api/activities/publication/{self.post.id}/comments').json()
        self.assertNotIn(comment['id'],[r['id'] for r in comments])
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).json()['comment_count'],0)

    def test_dismissal_history_immutable_and_required_reason(self):
        item=self.report();self.admin()
        self.assertEqual(self.resolve(item,'dismissed',reason='  ').status_code,422)
        result=self.resolve(item,'dismissed');self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.resolve(item,'hidden').status_code,409)
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).status_code,200)
        history=self.client.get('/api/admin/moderation/history').json()
        self.assertTrue(any(row['report_id']==item['id'] and row['action']=='dismissed' for row in history['items']))
        with self.assertRaises(DBAPIError),self.db.begin_nested():
            self.db.execute(text('UPDATE app.auditoria_moderacion SET reason=:reason WHERE report_id=:id'),{'reason':'overwrite','id':uuid.UUID(item['id'])})
        with self.assertRaises(DBAPIError),self.db.begin_nested():
            self.db.execute(text('UPDATE app.reportes_contenido SET resolution_reason=:reason WHERE id=:id'),{'reason':'overwrite','id':uuid.UUID(item['id'])})

    def test_restore_deleted_or_private_content_is_denied_and_retry_key(self):
        item=self.report();self.admin();key={'Idempotency-Key':str(uuid.uuid4())}
        first=self.resolve(item,headers=key);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.resolve(item,headers=key).json(),first.json())
        self.owner();self.client.delete('/api/posts/'+str(self.post.id))
        self.admin();self.assertEqual(self.resolve(item,'restored',version=3).status_code,409)

    def test_hidden_event_not_in_calendar_attendance_and_no_unauthorized_admin_assets(self):
        self.owner();created=self.client.post('/api/posts',json=self.payload(kind='event')).json()
        item=self.report('publication',created['id']);self.admin();self.assertEqual(self.resolve(item).status_code,200)
        rows=self.client.get('/api/events?from_date=2026-11-01&to_date=2026-11-30').json()['items']
        self.assertNotIn(created['id'],[r['id'] for r in rows])
        self.assertEqual(self.client.put('/api/events/'+created['id']+'/attendance').status_code,404)
        self.viewer_user()
        for path in ['/api/admin/moderation/history','/api/admin/moderation/reports',f'/api/admin/moderation/content/publication/{self.post.id}/cover']:
            self.assertEqual(self.client.get(path).status_code,403)

    def test_old_report_cannot_restore_later_hold(self):
        first=self.report()
        self.owner()
        second=self.client.post(f'/api/content-reports/publication/{self.post.id}',json={'reason':'harassment'}).json()
        self.admin();self.assertEqual(self.resolve(first).status_code,200)
        self.assertEqual(self.resolve(first,'restored',version=2).status_code,200)
        self.assertEqual(self.resolve(second,'hidden',version=3).status_code,200)
        self.assertEqual(self.resolve(first,'restored',version=4).status_code,409)
        self.assertEqual(self.resolve(second,'restored',version=4).status_code,200)

    def test_decision_rolls_back_content_media_and_audit_together(self):
        from app.modules.social.moderation_decisions import decide
        item=self.pending_post();self.admin()
        revision_id=uuid.UUID(item['pending_revision_id']);identifier=uuid.UUID(item['id'])
        with self.assertRaises(RuntimeError),self.db.begin_nested():
            decide(self.db,self.other,revision_id,'approved','Contexto comprobado',1)
            raise RuntimeError('fallo antes de confirmar')
        self.assertEqual(self.db.get(Post,identifier).moderation_status,'pending_review')
        self.assertEqual(self.db.get(ModerationRevision,revision_id).status,'pending_review')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ModerationAudit).where(ModerationAudit.revision_id==revision_id,ModerationAudit.action=='approved')),0)

    def test_comment_parent_private_deleted_and_decision_immutable(self):
        path=f'/api/activities/publication/{self.post.id}/comments'
        item=self.client.post(path,json={'body':'Te voy a matar'}).json()['comment']
        self.owner();self.client.delete('/api/posts/'+str(self.post.id))
        self.admin();self.assertEqual(self.decide(item).status_code,404)
        fresh=self.pending_post();self.admin();self.assertEqual(self.decide(fresh).status_code,200)
        with self.assertRaises(DBAPIError),self.db.begin_nested():
            self.db.execute(text("UPDATE app.revisiones_moderacion SET decision_reason='alterado' WHERE id=:id"),{'id':uuid.UUID(fresh['pending_revision_id'])})
        audit=self.db.scalar(select(ModerationAudit).where(ModerationAudit.revision_id==uuid.UUID(fresh['pending_revision_id']),ModerationAudit.action=='approved'))
        self.assertEqual(audit.context['previous']['moderation_status'],'pending_review')
        self.assertEqual(audit.context['result']['moderation_status'],'approved')

    def test_report_snapshot_survives_edit_and_analytics_respects_hold(self):
        from app.modules.analytics.projections import extract_social
        item=self.report()
        self.owner();self.client.put('/api/posts/'+str(self.post.id),json={**self.payload('Texto nuevo'),'publication_type':'note'})
        self.admin()
        detail=self.client.get('/api/admin/moderation/reports/'+item['id']).json()
        self.assertEqual(detail['reported_content']['body'],'Public note')
        self.assertEqual(detail['current_content']['body'],'Texto nuevo')
        self.assertEqual(self.resolve(item,version=1).status_code,409)
        self.assertEqual(self.resolve(item,version=2).status_code,200)
        result=extract_social(self.db,self.author.id)
        self.assertNotIn(str(self.post.id),str(result))
