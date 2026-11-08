import io
from PIL import Image
from sqlalchemy import select, func
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import PostBookCover, PostImage, ActivityView
from app.modules.books.models import Edition
from tests.test_mural_feed import MuralFeedTest


def png(color='red'):
    output=io.BytesIO()
    Image.new('RGB',(24,36),color).save(output,format='PNG')
    return output.getvalue()


class PublicationCoversTest(MuralFeedTest):
    def owner(self):
        app.dependency_overrides[get_current_user]=lambda:self.author

    def test_cover_lifecycle_is_publication_scoped(self):
        url=f'/api/posts/{self.post.id}/book-cover'
        self.assertEqual(self.client.put(url,files={'book_cover':('cover.png',png(),'image/png')}).status_code,403)
        self.owner()
        edition=Edition(work_id=self.work.id,title=self.work.title,language='es',cover_url='https://example.test/catalog-cover.png')
        self.db.add(edition);self.db.flush()
        self.post.work_id,self.post.edition_id=self.work.id,edition.id
        self.db.flush()
        gallery=PostImage(post_id=self.post.id,content_type='image/png',data=png('green'))
        self.db.add(gallery);self.db.flush()
        first=self.client.put(url,files={'book_cover':('cover.png',png(),'image/png')})
        self.assertEqual(first.status_code,200,first.text)
        first_url=first.json()['custom_book_cover_url']
        image=self.client.get('/api'+first_url)
        self.assertEqual(image.content,png())
        self.assertEqual(image.headers['content-type'],'image/png')
        self.assertEqual(image.headers['cache-control'],'private, no-store')
        summary=self.get('/social?audience=community')['items']
        item=next(item for item in summary if item['id']==str(self.post.id))
        self.assertEqual(item['custom_book_cover_url'],first_url)
        self.assertTrue(item['can_edit_book_cover'])
        replacement=self.client.put(url,files={'book_cover':('new.png',png('blue'),'image/png')})
        self.assertNotEqual(replacement.json()['custom_book_cover_url'],first_url)
        self.assertEqual(self.client.get(url).content,png('blue'))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(PostImage).where(PostImage.post_id==self.post.id)),1)
        self.assertEqual(self.db.get(PostImage,gallery.id).data,png('green'))
        self.assertEqual(self.db.get(Edition,edition.id).cover_url,'https://example.test/catalog-cover.png')
        self.assertEqual(next(i for i in self.client.get('/api/posts').json() if i['id']==str(self.post.id))['custom_book_cover_url'],replacement.json()['custom_book_cover_url'])
        for _ in range(2):self.assertEqual(self.client.delete(url).status_code,200)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertIsNone(next(i for i in self.get('/social?audience=community')['items'] if i['id']==str(self.post.id))['custom_book_cover_url'])
        self.assertEqual(next(i for i in self.get('/social?audience=community')['items'] if i['id']==str(self.post.id))['book_cover_url'],'https://example.test/catalog-cover.png')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ActivityView).where(ActivityView.post_id==self.post.id)),0)

    def test_invalid_uploads_and_visibility_changes(self):
        self.owner()
        url=f'/api/posts/{self.post.id}/book-cover'
        for data,status in [(b'not an image',415),(b'\x89PNG\r\n\x1a\ntruncated',415),(b'x'*(5*1024*1024+1),413)]:
            response=self.client.put(url,files={'book_cover':('bad.png',data,'image/png')})
            self.assertEqual(response.status_code,status,response.text)
        self.assertIsNone(self.db.get(PostBookCover,self.post.id))
        self.assertEqual(self.client.put(url,files={'book_cover':('cover.png',png(),'image/png')}).status_code,200)
        self.post.publication_type='event' # Readers cannot expose event posts under the current shared policy.
        self.db.flush()
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.delete(url).status_code,404)

    def test_create_with_cover_is_atomic_and_preserves_gallery(self):
        self.owner();self.author.role='admin';self.db.flush()
        data={'source':'event','publication_type':'event','kind':'community','title':'Launch', 'body':'Original text',
            'author_profile_id':str(self.profiles[self.author.id].id),'work_id':str(self.work.id),'book_title':self.work.title}
        response=self.client.post('/api/posts',data=data,files=[('images',('photo.png',png('green'),'image/png')),('book_cover',('cover.png',png(),'image/png'))])
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        self.assertEqual(len(item['images']),1)
        self.assertTrue(item['custom_book_cover_url'])
        self.assertEqual(self.client.get('/api'+item['custom_book_cover_url']).content,png())
        bad=self.client.post('/api/posts',data=data,files={'book_cover':('bad.png',b'broken','image/png')})
        self.assertEqual(bad.status_code,415,bad.text)
