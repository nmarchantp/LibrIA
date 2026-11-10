import unittest
from io import BytesIO
from unittest.mock import patch

import httpx
from PIL import Image

from app.modules.demo.publications import complete_publication, event_payload, publication_files
from app.modules.demo.service import DemoBook
from app.modules.demo.worker import DemoAPI
from app.modules.social.schemas import PostCreate


class DemoPublicationsTest(unittest.TestCase):
    def setUp(self):
        self.book = DemoBook('11111111-1111-4111-8111-111111111111',
                             '22222222-2222-4222-8222-222222222222', 'Una historia compartida', 240)

    def test_all_event_categories_have_valid_complete_schedules(self):
        categories = set()
        for block in range(5):
            payload = event_payload(self.book, block * 32)
            event = PostCreate.model_validate(payload).event_details
            categories.add(event.category)
            self.assertLess(event.instants()[0], event.instants()[1])
            self.assertTrue(event.organizer)
            self.assertTrue(event.location)
        self.assertEqual(categories, {'fair', 'book_club', 'workshop', 'meetup', 'other'})

    @patch('app.modules.demo.publications.post_reference', return_value='verified-reference')
    def test_publications_link_books_and_respect_text_limits(self, reference):
        for kind in ('promotion', 'news', 'launch', 'event'):
            book = DemoBook(self.book.work_id, self.book.edition_id, 'Título largo ' * 25, 240)
            payload = event_payload(book, 0) if kind == 'event' else {
                'source': 'community', 'kind': 'community', 'publication_type': kind,
                'work_id': book.work_id, 'edition_id': book.edition_id}
            result = PostCreate.model_validate(complete_publication(payload, book, 0))
            self.assertEqual(result.book_ref, 'verified-reference')
            self.assertEqual(result.book_title, book.title[:200])
            self.assertLessEqual(len(result.body), 500)

    @patch('app.modules.demo.publications.cover_path')
    def test_gallery_uses_verified_image_and_handles_missing_cover(self, path):
        path.return_value.is_file.return_value = False
        self.assertIsNone(publication_files(self.book, 'event'))
        output = BytesIO()
        Image.effect_noise((200, 300), 80).convert('RGB').save(output, format='JPEG')
        content = output.getvalue()
        path.return_value.is_file.return_value = True
        path.return_value.read_bytes.return_value = content
        files = publication_files(self.book, 'promotion')
        self.assertEqual(files[0][0], 'images')
        self.assertEqual(files[0][1][1], content)
        path.return_value.read_bytes.return_value = b'not an image'
        self.assertIsNone(publication_files(self.book, 'promotion'))


class DemoMultipartTest(unittest.IsolatedAsyncioTestCase):
    async def test_event_details_and_images_survive_authenticated_upload(self):
        seen = []
        def respond(request):
            seen.append(request)
            return httpx.Response(200, json={'id': 'saved'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url='http://demo.test') as client:
            api = DemoAPI(client)
            api.tokens['autor'] = 'test-token'
            with patch('app.modules.demo.worker.ensure_enabled'), patch('app.modules.demo.worker.mark_demo_result'):
                await api.request('autor', 'POST', '/posts', {'body': 'Texto',
                    'event_details': {'location': 'Sala virtual'}}, sequence=42,
                    files=[('images', ('cover.jpg', b'image', 'image/jpeg'))])
        request = seen[0]
        self.assertIn('multipart/form-data', request.headers['content-type'])
        self.assertIn(b'"location": "Sala virtual"', request.content)
        self.assertIn(b'filename="cover.jpg"', request.content)
        self.assertEqual(request.headers['authorization'], 'Bearer test-token')
        self.assertIn('idempotency-key', request.headers)
