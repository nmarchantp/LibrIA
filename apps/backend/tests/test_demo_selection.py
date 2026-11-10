import unittest
from unittest.mock import MagicMock, patch

from app.modules.demo.covers import download_cover, valid_image
from app.modules.demo.selection import CURATED_BOOKS, matches, prepare_selection, valid_selection


class DemoSelectionTest(unittest.TestCase):
    def test_all_twelve_requested_titles_match_their_authors(self):
        self.assertEqual(len(CURATED_BOOKS), 12)
        for spec in CURATED_BOOKS:
            self.assertTrue(matches(spec, spec['aliases'][0], [spec['author']]), spec['title'])
            self.assertFalse(matches(spec, spec['aliases'][0], ['Un autor distinto']))

    def test_excludes_summaries_journals_and_other_volumes(self):
        spec = next(item for item in CURATED_BOOKS if item['key'] == 'alas')
        self.assertFalse(matches(spec, 'Resumen de Alas de sangre', ['Rebecca Yarros']))
        self.assertFalse(matches(spec, 'Alas de sangre. Diario oficial', ['Rebecca Yarros']))
        self.assertFalse(matches(spec, 'Alas de hierro', ['Rebecca Yarros']))
        self.assertTrue(matches(spec, 'Alas de sangre (Empíreo 1)', ['Rebecca Yarros']))

    def test_cover_rejects_placeholders_html_and_untrusted_hosts(self):
        self.assertFalse(valid_image(b'<html>not an image</html>' * 150))
        self.assertFalse(valid_image(b'too small'))
        with patch('app.modules.demo.covers.httpx.Client') as client:
            self.assertIsNone(download_cover('http://127.0.0.1/private'))
            self.assertIsNone(download_cover('https://example.com/image.jpg'))
            client.assert_not_called()

    @patch('app.modules.demo.covers.Image.open')
    def test_cover_requires_a_real_portrait_sized_image(self, open_image):
        image = MagicMock(format='JPEG', width=128, height=196)
        open_image.return_value.__enter__.return_value = image
        self.assertTrue(valid_image(b'x' * 3000))
        image.width = 1
        self.assertFalse(valid_image(b'x' * 3000))

    @patch('app.modules.demo.selection.local_candidates', return_value=[])
    def test_old_random_selection_is_invalid(self, candidates):
        self.assertFalse(valid_selection(['11111111-1111-4111-8111-111111111111']))

    @patch('app.modules.demo.selection.select_with_cover', return_value=None)
    @patch('app.modules.demo.selection.import_selection', return_value=None)
    def test_no_unrelated_fallback_if_requested_books_are_unavailable(self, importer, local):
        with self.assertRaisesRegex(ValueError, 'ninguna edición'):
            prepare_selection(None, lambda: None)
        self.assertEqual(importer.call_count, 12)
