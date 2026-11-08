import uuid
from sqlalchemy import select,func
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post,PostImage,PostComment,PostLike,ActivityView,ReviewLike,ReviewRevision,Review
from app.modules.books.models import Work
from tests.test_mural_feed import MuralFeedTest


class ContentManagementTest(MuralFeedTest):
    def owner(self):app.dependency_overrides[get_current_user]=lambda:self.author
    def viewer_user(self):app.dependency_overrides[get_current_user]=lambda:self.viewer
    def payload(self,kind='news'):
        return {'publication_type':kind,'source':'event' if kind=='event' else 'community','title':'Edited publication',
            'body':'Edited text','book_ref':str(self.work.id),'work_id':str(self.work.id),'book_title':self.work.title,
            'author_profile_id':str(self.profiles[self.author.id].id)}

    def test_publication_edits_preserve_identity_and_interactions(self):
        path=f'/api/posts/{self.post.id}'
        typed=f'/api/activities/publication/{self.post.id}'
        self.client.put(typed+'/like')
        comment=self.client.post(typed+'/comments',json={'body':'Original comment'}).json()['comment']
        image=PostImage(post_id=self.post.id,content_type='image/png',data=b'original bytes')
        self.db.add(image);self.db.flush()
        created=self.post.created_at
        count=self.db.scalar(select(func.count()).select_from(Post))
        self.assertEqual(self.client.put(path,json=self.payload()).status_code,403)
        self.owner();self.author.role='admin';self.db.flush()
        for kind in ['event','news','promotion','launch','free']:
            response=self.client.put(path,json=self.payload(kind))
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['id'],str(self.post.id))
            self.assertEqual(response.json()['like_count'],1)
            self.assertEqual(response.json()['comment_count'],1)
            self.assertEqual(response.json()['view_count'],1)
            self.assertEqual(self.post.created_at,created)
            self.assertIsNotNone(self.post.updated_at)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Post)),count)
        self.assertEqual(self.db.get(PostComment,uuid.UUID(comment['id'])).body,'Original comment')
        self.assertEqual(self.db.get(PostImage,image.id).data,b'original bytes')

    def test_soft_delete_preserves_children_and_revokes_stale_access(self):
        typed=f'/api/activities/publication/{self.post.id}'
        self.client.put(typed+'/like');self.client.post(typed+'/comments',json={'body':'Retained'})
        path=f'/api/posts/{self.post.id}'
        self.assertEqual(self.client.delete(path).status_code,403)
        self.owner()
        self.assertEqual(self.client.delete(path).status_code,204)
        self.assertIsNotNone(self.db.get(Post,self.post.id).deleted_at)
        for model in (PostLike,PostComment,ActivityView):
            self.assertEqual(self.db.scalar(select(func.count()).select_from(model).where(model.post_id==self.post.id)),1)
        self.assertNotIn(str(self.post.id),[item['id'] for item in self.get('/social?audience=community')['items']])
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.put(typed+'/like').status_code,404)
        self.assertEqual(self.client.post(typed+'/comments',json={'body':'No'}).status_code,404)

    def test_comment_edit_delete_ownership_and_counts_all_sources(self):
        for kind,item in [('publication',self.post),('review',self.review),('reading_event',self.events[0])]:
            self.viewer_user()
            path=f'/api/activities/{kind}/{item.id}'
            created=self.client.post(path+'/comments',json={'body':'Original'}).json()['comment']
            target=path+'/comments/'+created['id']
            self.owner()
            self.assertEqual(self.client.put(target,json={'body':'Hijack'}).status_code,404)
            self.assertEqual(self.client.delete(target).status_code,404)
            self.viewer_user()
            result=self.client.put(target,json={'body':'Corrected'})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['comment']['id'],created['id'])
            self.assertEqual(result.json()['comment']['created_at'],created['created_at'])
            self.assertIsNotNone(result.json()['comment']['edited_at'])
            self.assertEqual(result.json()['interactions']['comment_count'],1)
            self.assertEqual(result.json()['interactions']['view_count'],1)
            wrong=f'/api/activities/publication/{uuid.uuid4()}/comments/{created["id"]}'
            self.assertEqual(self.client.delete(wrong).status_code,404)
            deleted=self.client.delete(target)
            self.assertEqual(deleted.status_code,200,deleted.text)
            self.assertEqual(deleted.json()['interactions']['comment_count'],0)
            self.assertEqual(deleted.json()['interactions']['view_count'],1)

    def test_review_revision_and_hide_retain_relations(self):
        path=f'/api/activities/review/{self.review.id}'
        self.client.put(path+'/like');self.client.post(path+'/comments',json={'body':'Keep review comment'})
        self.owner()
        response=self.client.put(f'/api/reviews/{self.review.id}',json={'body':'Revised review','rating':4.5,'dimension_ratings':{'romance':3.25},'status':'published'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['id'],str(self.review.id))
        self.assertEqual(response.json()['revision_number'],2)
        self.assertEqual(self.client.delete(f'/api/reviews/{self.review.id}').status_code,204)
        self.assertEqual(self.db.get(Review,self.review.id).status,'hidden')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ReviewLike).where(ReviewLike.review_id==self.review.id)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(PostComment).where(PostComment.review_id==self.review.id)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ActivityView).where(ActivityView.review_id==self.review.id)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ReviewRevision).where(ReviewRevision.review_id==self.review.id)),2)
        self.assertEqual(self.client.get(f'/api/reviews/{self.review.id}').status_code,404)

    def test_hide_draft_does_not_invent_publication_date(self):
        self.owner()
        work=Work(title='Unpublished review draft');self.db.add(work);self.db.flush()
        response=self.client.post('/api/reviews',json={'work_id':str(work.id),'body':'Private draft','status':'draft'})
        self.assertEqual(response.status_code,201,response.text)
        identifier=uuid.UUID(response.json()['id'])
        self.assertEqual(self.client.delete(f'/api/reviews/{identifier}').status_code,204)
        draft=self.db.get(Review,identifier)
        self.assertEqual(draft.status,'hidden')
        self.assertIsNone(draft.published_at)

    def test_edit_upload_preserves_existing_gallery_and_is_atomic(self):
        from tests.test_publication_covers import png
        from app.modules.social.models import PostBookCover
        self.owner();self.author.role='admin';self.db.flush()
        photo=PostImage(post_id=self.post.id,content_type='image/png',data=png('green'))
        self.db.add(photo);self.db.flush()
        data=self.payload('event');data['existing_image_ids']='["'+str(photo.id)+'"]';data['cover_mode']='custom'
        url=f'/api/posts/{self.post.id}'
        response=self.client.put(url,data=data,files={'book_cover':('cover.png',png(),'image/png')})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.db.get(PostImage,photo.id).data,png('green'))
        self.assertEqual(self.db.get(PostBookCover,self.post.id).data,png())
        original=self.post.title
        data['title']='Should not save'
        invalid=self.client.put(url,data=data,files={'book_cover':('invalid.png',b'broken','image/png')})
        self.assertEqual(invalid.status_code,415,invalid.text)
        self.assertEqual(self.post.title,original)
