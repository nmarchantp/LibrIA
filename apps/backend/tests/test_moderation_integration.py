"""HTTP integration of moderation; all fixtures roll back."""
import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select,func
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post,PostComment,PostImage,PostBookCover,Review,ReviewRevision,EventAttendance,PublicationEvent
from app.modules.social.moderation_models import ModerationRevision,ModerationAttachment
from app.modules.books.community import public_rating
from app.modules.analytics.projections import extract_social
from tests import test_mural_feed as fixtures


def png():
    stream=io.BytesIO();Image.new('RGB',(2,2),'gold').save(stream,format='PNG');return stream.getvalue()


class ModerationIntegrationTest(unittest.TestCase):
    setUp=fixtures.MuralFeedTest.setUp
    tearDown=fixtures.MuralFeedTest.tearDown
    make_reading=fixtures.MuralFeedTest.make_reading
    make_event=fixtures.MuralFeedTest.make_event

    def owner(self):
        self.author.role='admin';self.db.flush()
        app.dependency_overrides[get_current_user]=lambda:self.author

    def viewer_user(self):app.dependency_overrides[get_current_user]=lambda:self.viewer

    def payload(self,body='Una invitación literaria',kind='news'):
        value={'source':'event' if kind=='event' else 'community','publication_type':kind,
               'kind':'community','title':'Encuentro','body':body,'work_id':str(self.work.id)}
        if kind=='event':value['event_details']={'start_date':'2026-11-14','start_time':'12:00',
            'end_date':'2026-11-15','end_time':'18:00','timezone':'America/Santiago','location':'Santiago','organizer':'Comunidad','category':'meetup'}
        return value

    def pending_post(self,kind='news'):
        self.owner()
        response=self.client.post('/api/posts',json=self.payload('Te voy a matar',kind))
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(response.json()['moderation_status'],'pending_review')
        return response.json()

    def test_normal_publications_and_all_suspicious_categories(self):
        self.owner()
        normal=self.client.post('/api/posts',json=self.payload()).json()
        self.assertEqual(normal['moderation_status'],'approved')
        self.assertEqual(self.client.get('/api/posts/'+normal['id']).status_code,200)
        for kind in ['free','news','promotion','launch','event']:
            item=self.pending_post(kind);identifier=item['id']
            self.viewer_user()
            self.assertEqual(self.client.get('/api/posts/'+identifier).status_code,404)
            self.assertNotIn(identifier,[row['id'] for row in self.client.get('/api/posts').json()])
            for category in ['social','events','launches','announcements','promotions']:
                data=self.client.get(f'/api/mural/{category}?audience=community').json()
                self.assertNotIn(identifier,[row['id'] for row in data['items']])
            for endpoint in ['like','comments','attendance']:
                path=f'/api/events/{identifier}/attendance' if endpoint=='attendance' else f'/api/activities/publication/{identifier}/{endpoint}'
                self.assertEqual(self.client.get(path).status_code,404 if endpoint!='like' else 405)

    def test_private_status_is_author_only_and_admin_requires_real_permission(self):
        item=self.pending_post();revision=item['pending_revision_id']
        self.assertEqual(self.client.get('/api/me/moderation/'+revision).status_code,200)
        self.assertTrue(self.client.get('/api/me/moderation').json()['items'])
        self.viewer_user()
        self.assertEqual(self.client.get('/api/me/moderation/'+revision).status_code,404)
        self.assertEqual(self.client.get('/api/me/moderation').json()['items'],[])
        self.assertEqual(self.client.get('/api/admin/moderation').status_code,403)

    def test_pending_event_never_enters_calendar_or_attendance(self):
        item=self.pending_post('event');identifier=item['id']
        for user in [self.author,self.viewer]:
            app.dependency_overrides[get_current_user]=lambda:user
            calendar=self.client.get('/api/events?from_date=2026-11-01&to_date=2026-11-30').json()
            self.assertNotIn(identifier,[row['id'] for row in calendar['items']])
            self.assertEqual(self.client.put(f'/api/events/{identifier}/attendance').status_code,404)
            self.assertEqual(self.client.get(f'/api/events/{identifier}/attendance').status_code,404)

    def test_pending_publication_images_and_cover_are_not_public(self):
        self.owner();data={key:str(value) for key,value in self.payload().items()}
        data['body']='Te voy a matar'
        response=self.client.post('/api/posts',data=data,files=[
            ('images',('photo.png',png(),'image/png')),('book_cover',('cover.png',png(),'image/png'))])
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        for path in [item['images'][0],item['custom_book_cover_url']]:
            self.assertEqual(self.client.get('/api'+path).status_code,404)
        self.viewer_user()
        self.assertEqual(self.client.get('/api'+item['images'][0]).status_code,404)

    def test_flagged_edit_preserves_event_images_cover_and_attendees(self):
        self.owner();created=self.client.post('/api/posts',json=self.payload(kind='event')).json()
        identifier=created['id'];post=self.db.get(Post,uuid.UUID(identifier))
        old_image=PostImage(post_id=post.id,content_type='image/png',data=png())
        old_cover=PostBookCover(post_id=post.id,content_type='image/png',data=png())
        self.db.add_all([old_image,old_cover,EventAttendance(post_id=post.id,user_id=self.viewer.id)]);self.db.flush()
        old_revision=old_cover.revision
        value=self.payload('Te voy a matar','event');value['event_details']['start_date']='2026-12-14';value['event_details']['end_date']='2026-12-15'
        value['existing_image_ids']='[]';value['cover_mode']='custom'
        import json
        data={key:json.dumps(item) if isinstance(item,dict) else str(item) for key,item in value.items()}
        response=self.client.put('/api/posts/'+identifier,data=data,files=[
            ('images',('new.png',png(),'image/png')),('book_cover',('cover.png',png(),'image/png'))])
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['moderation_status'],'pending_review')
        self.assertEqual(post.body,'Una invitación literaria')
        self.assertEqual(old_cover.revision,old_revision)
        self.assertIsNotNone(self.db.get(PostImage,old_image.id))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EventAttendance).where(EventAttendance.post_id==post.id)),1)
        pending=self.client.get('/api/me/moderation/'+response.json()['pending_revision_id']).json()
        self.assertEqual(len(pending['attachments']),2)
        private_asset=pending['attachments'][0]
        self.assertEqual(self.client.get('/api'+private_asset['url']).status_code,200)
        self.assertEqual(self.client.put(f'/api/posts/{identifier}/book-cover',files={'book_cover':('x.png',png(),'image/png')}).status_code,409)
        self.viewer_user()
        self.assertEqual(self.client.get('/api'+private_asset['url']).status_code,404)
        self.assertEqual(self.client.get(f'/api/posts/{identifier}/images/{private_asset["id"]}').status_code,404)
        visible=self.client.get('/api/posts/'+identifier).json()
        self.assertEqual(visible['body'],'Una invitación literaria')
        self.assertEqual(visible['event_details']['start_date'],'2026-11-14')
        self.assertTrue(any(row['id']==identifier for row in self.client.get('/api/events?from_date=2026-11-14&to_date=2026-11-15').json()['items']))

    def test_clean_rewrite_of_pending_post_publishes_same_id_and_withdraws_old_proposal(self):
        item=self.pending_post();identifier=item['id']
        result=self.client.put('/api/posts/'+identifier,json=self.payload('Contenido corregido'))
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['id'],identifier)
        self.assertEqual(result.json()['moderation_status'],'approved')
        self.assertEqual(self.client.get('/api/posts/'+identifier).json()['body'],'Contenido corregido')
        self.assertEqual(self.db.get(ModerationRevision,uuid.UUID(item['pending_revision_id'])).lifecycle,'superseded')

    def test_delete_pending_publication_withdraws_revision(self):
        item=self.pending_post()
        self.assertEqual(self.client.delete('/api/posts/'+item['id']).status_code,204)
        self.assertEqual(self.db.get(ModerationRevision,uuid.UUID(item['pending_revision_id'])).lifecycle,'withdrawn')
        self.assertEqual(self.client.get('/api/posts/'+item['id']).status_code,404)

    def test_review_creation_edit_average_and_revision_history(self):
        self.viewer_user()
        before=public_rating(self.db,{self.work.id})
        response=self.client.post('/api/reviews',json={'work_id':str(self.work.id),'body':'Te voy a matar','rating':1})
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        self.assertEqual(item['moderation_status'],'pending_review')
        self.assertIsNone(item['published_at'])
        self.assertEqual(public_rating(self.db,{self.work.id}),before)
        self.assertEqual(self.client.get('/api/reviews/'+item['id']).status_code,404)
        self.assertNotIn(item['id'],[r['id'] for r in self.client.get('/api/reviews/by-book/'+str(self.work.id)).json()['items']])
        self.assertEqual(len(self.client.get('/api/reviews/me').json()),1)
        clean=self.client.put('/api/reviews/'+item['id'],json={'body':'Una reseña normal','rating':5})
        self.assertEqual(clean.status_code,200,clean.text)
        self.assertIsNotNone(clean.json()['published_at'])
        baseline=public_rating(self.db,{self.work.id})
        revisions=self.db.scalar(select(func.count()).select_from(ReviewRevision).where(ReviewRevision.review_id==uuid.UUID(item['id'])))
        flagged=self.client.put('/api/reviews/'+item['id'],json={'body':'Eres un idiota','rating':1})
        self.assertEqual(flagged.status_code,200,flagged.text)
        self.assertEqual(flagged.json()['moderation_status'],'pending_review')
        self.assertEqual(self.client.get('/api/reviews/'+item['id']).json()['rating'],5)
        self.assertEqual(public_rating(self.db,{self.work.id}),baseline)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ReviewRevision).where(ReviewRevision.review_id==uuid.UUID(item['id']))),revisions)

    def test_private_review_draft_only_moderates_when_published(self):
        response=self.client.post('/api/reviews',json={'work_id':str(self.work.id),'body':'Te voy a matar','status':'draft'})
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        self.assertEqual(item['moderation_status'],'approved')
        self.assertIsNone(item['pending_revision_id'])
        result=self.client.put('/api/reviews/'+item['id'],json={'body':'Te voy a matar','status':'published'})
        self.assertEqual(result.json()['moderation_status'],'pending_review')
        self.assertEqual(self.db.get(Review,uuid.UUID(item['id'])).status,'draft')

    def test_comment_creation_and_counts_all_sources_and_legacy(self):
        for kind,item in [('publication',self.post),('review',self.review),('reading_event',self.events[0])]:
            path=f'/api/activities/{kind}/{item.id}'
            flagged=self.client.post(path+'/comments',json={'body':'Eres un idiota'})
            self.assertEqual(flagged.status_code,201,flagged.text)
            self.assertEqual(flagged.json()['comment']['moderation_status'],'pending_review')
            self.assertEqual(flagged.json()['interactions']['comment_count'],0)
            legacy=self.client.post(f'/api/posts/{item.id}/comments',json={'body':'Te voy a matar'})
            self.assertEqual(legacy.status_code,201,legacy.text)
            self.assertEqual(legacy.json()['moderation_status'],'pending_review')
            self.assertEqual(self.client.get(path+'/comments').json(),[])
            self.assertEqual(self.client.get(f'/api/posts/{item.id}/comments').json(),[])
            self.assertEqual(self.client.get(path).json()['comment_count'],0)

    def test_comment_pending_edits_keep_original_then_soft_delete(self):
        path=f'/api/activities/publication/{self.post.id}'
        item=self.client.post(path+'/comments',json={'body':'Comentario original'}).json()['comment']
        target=path+'/comments/'+item['id']
        result=self.client.put(target,json={'body':'Te voy a matar'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['comment']['moderation_status'],'pending_review')
        self.assertEqual(self.client.get(path+'/comments').json()[0]['body'],'Comentario original')
        self.assertEqual(self.client.get(path).json()['comment_count'],1)
        self.assertEqual(self.client.delete(target).status_code,200)
        stored=self.db.get(PostComment,uuid.UUID(item['id']))
        self.assertIsNotNone(stored.deleted_at)
        self.assertEqual(stored.body,'Comentario original')
        self.assertEqual(self.client.get(path+'/comments').json(),[])
        self.assertEqual(self.client.get(path).json()['comment_count'],0)
        revision=self.db.get(ModerationRevision,uuid.UUID(result.json()['comment']['pending_revision_id']))
        self.assertEqual(revision.lifecycle,'withdrawn')

    def test_comment_pending_creation_can_be_corrected_without_duplication(self):
        path=f'/api/activities/review/{self.review.id}'
        item=self.client.post(path+'/comments',json={'body':'Eres un idiota'}).json()['comment']
        response=self.client.put(path+'/comments/'+item['id'],json={'body':'Texto corregido'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['comment']['id'],item['id'])
        self.assertEqual(self.client.get(path).json()['comment_count'],1)

    def test_idempotency_and_conflicting_versions(self):
        self.owner()
        headers={'Idempotency-Key':str(uuid.uuid4())}
        one=self.client.post('/api/posts',json=self.payload('Te voy a matar'),headers=headers)
        two=self.client.post('/api/posts',json=self.payload('Te voy a matar'),headers=headers)
        self.assertEqual(one.json()['id'],two.json()['id'])
        self.assertEqual(self.client.post('/api/posts',json=self.payload('Texto distinto'),headers=headers).status_code,409)
        clean=self.client.post('/api/posts',json=self.payload()).json()
        identifier=clean['id'];version=clean['moderation_version']
        accepted=self.client.put('/api/posts/'+identifier,json=self.payload('Primera edición'),headers={'If-Match':str(version)})
        self.assertEqual(accepted.status_code,200,accepted.text)
        self.assertEqual(self.client.put('/api/posts/'+identifier,json=self.payload('Segunda edición'),headers={'If-Match':str(version)}).status_code,409)
        self.assertEqual(self.client.get('/api/posts/'+identifier).json()['body'],'Primera edición')

    def test_idempotency_for_reviews_and_both_comment_routes(self):
        headers={'Idempotency-Key':str(uuid.uuid4())}
        payload={'work_id':str(self.work.id),'body':'Te voy a matar'}
        first=self.client.post('/api/reviews',json=payload,headers=headers)
        second=self.client.post('/api/reviews',json=payload,headers=headers)
        self.assertEqual(first.status_code,201,first.text)
        self.assertEqual(first.json()['id'],second.json()['id'])
        for route in [f'/api/activities/publication/{self.post.id}/comments',f'/api/posts/{self.post.id}/comments']:
            headers={'Idempotency-Key':str(uuid.uuid4())}
            first=self.client.post(route,json={'body':'Eres un idiota'},headers=headers).json()
            second=self.client.post(route,json={'body':'Eres un idiota'},headers=headers).json()
            if 'comment' in first:first,second=first['comment'],second['comment']
            self.assertEqual(first['id'],second['id'])

    def test_client_cannot_choose_approved_status_and_analysis_failure_is_closed(self):
        self.owner()
        value=self.payload('Te voy a matar');value['moderation_status']='approved'
        self.assertEqual(self.client.post('/api/posts',json=value).status_code,422)
        with patch('app.modules.social.moderation_integration.analyze_content',side_effect=OSError('invalid config')):
            result=self.client.post('/api/posts',json=self.payload())
            self.assertEqual(result.status_code,503,result.text)

    def test_analytics_social_excludes_pending_and_deleted_comments(self):
        path=f'/api/activities/review/{self.review.id}'
        clean=self.client.post(path+'/comments',json={'body':'Comentario visible'}).json()['comment']
        pending=self.client.post(path+'/comments',json={'body':'Te voy a matar'}).json()['comment']
        values=extract_social(self.db,self.viewer.id)
        ids={str(value['source_id']) for value in values if value['kind']=='comment'}
        self.assertIn(clean['id'],ids)
        self.assertNotIn(pending['id'],ids)
        self.client.delete(path+'/comments/'+clean['id'])
        ids={str(value['source_id']) for value in extract_social(self.db,self.viewer.id) if value['kind']=='comment'}
        self.assertNotIn(clean['id'],ids)

    def test_history_and_library_remain_untouched_by_pending_edit(self):
        original_reading=(self.reading.status,self.reading.current_page,self.reading.total_pages)
        self.owner();payload=self.payload('Te voy a matar',kind='note')
        payload['book_ref']=self.post.book_ref;payload['book_title']=self.post.book_title
        result=self.client.put('/api/posts/'+str(self.post.id),json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(original_reading,(self.reading.status,self.reading.current_page,self.reading.total_pages))
        self.assertEqual(self.client.get('/api/posts/'+str(self.post.id)).json()['body'],'Public note')

    def test_analytics_parent_visibility_and_public_filter_before_limit(self):
        path=f'/api/activities/reading_event/{self.events[0].id}'
        self.client.post(path+'/comments',json={'body':'Comentario visible'})
        self.reading.status='abandoned';self.reading.abandoned_at=datetime.now(timezone.utc);self.db.flush()
        comments=[row for row in extract_social(self.db,self.viewer.id) if row['kind']=='comment']
        self.assertEqual(comments,[])
        self.owner()
        valid=self.client.post('/api/posts',json=self.payload()).json()
        for _ in range(4):self.pending_post()
        visible=self.client.get('/api/mural/announcements?audience=community&limit=1').json()
        self.assertEqual([row['id'] for row in visible['items']],[valid['id']])
