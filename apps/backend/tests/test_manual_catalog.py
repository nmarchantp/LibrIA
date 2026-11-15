import uuid
import json
import io
from PIL import Image
from unittest.mock import patch
from sqlalchemy import select, func
from app.modules.books.models import Work, Edition
from app.modules.books.catalog_models import CatalogOperation
from tests.test_mural_feed import MuralFeedTest
from app.main import app
from app.modules.auth.dependencies import get_current_user


def isbn():
    base = '978' + str(uuid.uuid4().int % 1000000000).zfill(9)
    return base + str(-sum(int(value) * (1 if index % 2 == 0 else 3) for index, value in enumerate(base)) % 10)


class ManualCatalogTest(MuralFeedTest):
    def test_uploaded_png_and_jpg_covers_are_persisted_and_public(self):
        self.prepare()
        for image_format, mime in [('PNG', 'image/png'), ('JPEG', 'image/jpeg')]:
            self.key = str(uuid.uuid4()); self.data['isbn'] = isbn()
            output = io.BytesIO()
            Image.new('RGB', (24, 36), 'purple').save(output, format=image_format)
            content = output.getvalue()
            files = {'data': (None, json.dumps(self.data)), 'cover': ('cover.jpg', content, mime)}
            response = self.client.post('/api/books/manual', files=files, headers={'Idempotency-Key': self.key})
            self.assertEqual(response.status_code, 201, response.text)
            replay = self.client.post('/api/books/manual', files=files, headers={'Idempotency-Key': self.key})
            self.assertEqual(replay.json(), response.json())
            edition = self.db.get(Edition, uuid.UUID(response.json()['edition_id']))
            cover = self.client.get(edition.cover_url)
            self.assertEqual(cover.status_code, 200)
            self.assertEqual(cover.headers['content-type'], mime)
            self.assertEqual(cover.content, content)
            detail = self.client.get('/api/books/' + response.json()['work_id'])
            self.assertIn('/cover', detail.json()['volumeInfo']['imageLinks']['thumbnail'])

    def test_invalid_cover_does_not_create_book(self):
        self.prepare()
        for content, status in [(b'invalid image', 415), (b'x' * (5 * 1024 * 1024 + 1), 413)]:
            response = self.client.post('/api/books/manual', files={
                'data': (None, json.dumps(self.data)), 'cover': ('cover.png', content, 'image/png')},
                headers={'Idempotency-Key': self.key})
            self.assertEqual(response.status_code, status, response.text)
            self.assertIsNone(self.db.scalar(select(Edition).where(Edition.isbn13 == self.data['isbn'])))
        output = io.BytesIO()
        Image.new('RGB', (24, 36)).save(output, format='GIF')
        response = self.client.post('/api/books/manual', files={'data': (None, json.dumps(self.data)),
            'cover': ('fake.png', output.getvalue(), 'image/png')}, headers={'Idempotency-Key': self.key})
        self.assertEqual(response.status_code, 415, response.text)

    def test_manual_url_cover_is_preserved(self):
        self.prepare()
        self.data['cover_url'] = 'https://example.com/cover.jpg'
        response = self.write()
        self.assertEqual(response.status_code, 201, response.text)
        edition = self.db.get(Edition, uuid.UUID(response.json()['edition_id']))
        self.assertEqual(edition.cover_url, self.data['cover_url'])

    def prepare(self, role='autor'):
        self.author.role = role
        self.db.commit()
        app.dependency_overrides[get_current_user] = lambda: self.db.get(type(self.author), self.author.id)
        self.key = str(uuid.uuid4())
        self.data = {'title': 'Registro manual ' + uuid.uuid4().hex, 'isbn': isbn(), 'authors': ['Autora manual'],
                     'language': 'es', 'page_count': 180, 'reason': 'Registro profesional con ISBN'}

    def write(self, data=None):
        return self.client.post('/api/books/manual', json=data or self.data, headers={'Idempotency-Key': self.key})

    def test_manual_registration_is_local_audited_and_replayable(self):
        self.prepare('admin')
        with patch('app.modules.books.router.google_request', side_effect=AssertionError('No external dependency')):
            response = self.write()
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(self.write().json(), response.json())
            work_id = uuid.UUID(response.json()['work_id'])
            edition = self.db.get(Edition, uuid.UUID(response.json()['edition_id']))
            self.assertEqual(edition.isbn13, self.data['isbn'])
            self.assertEqual(edition.created_by_user_id, self.author.id)
            local = self.client.get('/api/books', params={'q': self.data['title'], 'local_only': True})
            self.assertEqual(local.status_code, 200, local.text)
            self.assertIn(str(work_id), [item['libria']['workId'] for item in local.json()['items']])
            detail = self.client.get('/api/books/' + str(work_id))
            self.assertEqual(detail.status_code, 200, detail.text)
            publication = self.client.post('/api/posts', json={
                'source': 'community', 'kind': 'community', 'publication_type': 'launch',
                'title': 'Nuevo libro registrado', 'body': 'Lanzamiento de nuestra nueva obra',
                'book_ref': str(work_id), 'work_id': str(work_id), 'edition_id': str(edition.id),
                'book_title': self.data['title']})
            self.assertEqual(publication.status_code, 201, publication.text)
            self.assertEqual(publication.json()['work_id'], str(work_id))
            self.assertEqual(self.db.scalar(select(func.count()).select_from(CatalogOperation).where(CatalogOperation.request_key == self.key)), 1)
        self.key = str(uuid.uuid4())
        self.assertEqual(self.write().status_code, 409)

    def test_manual_role_restrictions_and_invalid_isbn(self):
        self.prepare('lector')
        self.assertEqual(self.write().status_code, 403)
        for role in ['influencer', 'libreria']:
            self.author.role = role; self.db.commit()
            self.assertEqual(self.write().status_code, 403)
        for role in ['autor', 'editorial', 'admin']:
            self.author.role = role; self.db.commit()
            self.key = str(uuid.uuid4()); self.data['title'] = 'Registro ' + uuid.uuid4().hex; self.data['isbn'] = isbn()
            self.assertEqual(self.write().status_code, 201)
        self.key = str(uuid.uuid4()); self.data['isbn'] = '9780000000000'
        self.assertEqual(self.write().status_code, 422)
        self.assertIsNone(self.db.scalar(select(Edition).where(Edition.isbn13 == '9780000000000')))

    def test_new_isbn_reuses_existing_work(self):
        self.prepare()
        first = self.write()
        self.assertEqual(first.status_code, 201, first.text)
        self.key = str(uuid.uuid4()); self.data['isbn'] = isbn()
        second = self.write()
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()['work_id'], first.json()['work_id'])
        self.assertNotEqual(second.json()['edition_id'], first.json()['edition_id'])
