"""Private persistent inbox and stage-4 presentation metadata."""
import uuid
import unittest
from sqlalchemy import select,func
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.moderation_models import ModerationNotification
from app.modules.social.moderation_decisions import decide
from tests import test_moderation_administration as admin_fixtures


class ModerationNotificationTest(unittest.TestCase):
    setUp=admin_fixtures.ModerationAdministrationTest.setUp
    tearDown=admin_fixtures.ModerationAdministrationTest.tearDown
    make_reading=admin_fixtures.ModerationAdministrationTest.make_reading
    make_event=admin_fixtures.ModerationAdministrationTest.make_event
    owner=admin_fixtures.ModerationAdministrationTest.owner
    viewer_user=admin_fixtures.ModerationAdministrationTest.viewer_user
    payload=admin_fixtures.ModerationAdministrationTest.payload
    pending_post=admin_fixtures.ModerationAdministrationTest.pending_post
    admin=admin_fixtures.ModerationAdministrationTest.admin
    decide=admin_fixtures.ModerationAdministrationTest.decide

    def inbox(self):
        result=self.client.get('/api/me/notifications')
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn('no-store',result.headers['cache-control'])
        return result.json()

    def test_no_demo_or_historical_backfill_and_private_access(self):
        self.assertEqual(self.inbox()['items'],[])
        self.pending_post();own=self.inbox()
        self.assertEqual(own['unread_count'],1)
        self.assertEqual(own['items'][0]['kind'],'pending_review')
        self.viewer_user()
        self.assertEqual(self.inbox()['items'],[])
        self.assertEqual(self.client.put('/api/me/notifications/'+own['items'][0]['id']+'/read').status_code,404)

    def test_approved_decision_is_persistent_and_not_duplicated(self):
        item=self.pending_post();self.admin()
        self.assertEqual(self.decide(item).status_code,200)
        self.assertEqual(self.decide(item).status_code,200)
        self.owner();data=self.inbox()
        self.assertEqual(sorted(n['kind'] for n in data['items']),['approved','pending_review'])
        self.assertTrue(all(n['revision_id']==item['pending_revision_id'] for n in data['items']))
        self.db.expire_all()
        self.assertEqual(self.inbox()['unread_count'],2)

    def test_rejected_reason_is_author_only_and_mark_read_idempotent(self):
        item=self.pending_post();self.admin()
        self.assertEqual(self.decide(item,'rejected','Motivo privado comprobado').status_code,200)
        self.owner();data=self.inbox();rejected=next(n for n in data['items'] if n['kind']=='rejected')
        self.assertEqual(rejected['decision_reason'],'Motivo privado comprobado')
        path='/api/me/notifications/'+rejected['id']+'/read'
        self.assertEqual(self.client.put(path).status_code,200)
        self.assertEqual(self.client.put(path).status_code,200)
        self.assertEqual(self.inbox()['unread_count'],1)
        self.viewer_user();self.assertEqual(self.inbox()['unread_count'],0)

    def test_pending_retries_and_comments_all_destinations_notify_once(self):
        for kind,identifier in [('publication',self.post.id),('review',self.review.id),('reading_event',self.events[0].id)]:
            key={'Idempotency-Key':str(uuid.uuid4())}
            path=f'/api/activities/{kind}/{identifier}/comments'
            first=self.client.post(path,json={'body':'Te voy a matar'},headers=key)
            second=self.client.post(path,json={'body':'Te voy a matar'},headers=key)
            self.assertEqual(first.json()['comment']['pending_revision_id'],second.json()['comment']['pending_revision_id'])
        self.assertEqual(len(self.inbox()['items']),3)

    def test_notification_rolls_back_with_decision(self):
        item=self.pending_post();self.admin()
        with self.assertRaises(RuntimeError),self.db.begin_nested():
            decide(self.db,self.other,uuid.UUID(item['pending_revision_id']),'approved','Contexto válido',1)
            raise RuntimeError('fallo transaccional')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ModerationNotification).where(ModerationNotification.revision_id==uuid.UUID(item['pending_revision_id']),ModerationNotification.kind=='approved')),0)

    def test_real_authors_findings_and_report_counts(self):
        first=self.pending_post();self.admin()
        queue=self.client.get('/api/admin/moderation').json()
        row=next(r for r in queue['items'] if r['id']==first['pending_revision_id'])
        self.assertEqual(row['author'],self.author.display_name)
        self.assertTrue(row['findings'])
        self.viewer_user()
        self.client.post(f'/api/content-reports/publication/{self.post.id}',json={'reason':'spam'})
        self.owner()
        self.client.post(f'/api/content-reports/publication/{self.post.id}',json={'reason':'harassment'})
        self.admin()
        rows=self.client.get('/api/admin/moderation/reports').json()['items']
        self.assertTrue(all(r['report_count']==2 and r['author']==self.author.display_name for r in rows))

    def test_inbox_pagination_and_unread_total_not_page_size(self):
        self.pending_post();self.pending_post();self.pending_post()
        result=self.client.get('/api/me/notifications?limit=1').json()
        self.assertEqual(len(result['items']),1)
        self.assertTrue(result['has_more'])
        self.assertEqual(result['unread_count'],3)
