import unittest
from unittest.mock import AsyncMock, patch
import random
import uuid

from app.modules.demo.service import DemoBook, DemoPaused
from app.modules.demo.worker import (DemoAPI, event_payload, generate_action, independent_reading,
                                    review_action, shuffled_schedule, reading_actor, choose_reading)
from app.modules.social.schemas import PostCreate


BOOK = DemoBook('11111111-1111-4111-8111-111111111111',
                '22222222-2222-4222-8222-222222222222', 'Un libro real del catálogo', 240)


class GeneratePostsTest(unittest.IsolatedAsyncioTestCase):
    def test_event_has_valid_calendar_details(self):
        value = PostCreate.model_validate(event_payload(BOOK, 7))
        start, end = value.event_details.instants()
        self.assertLess(start, end)
        self.assertEqual(value.publication_type, 'event')

    async def test_uses_reading_events_instead_of_activity_posts(self):
        api = AsyncMock()
        api.request.side_effect = [[{'work_id': BOOK.work_id, 'status': 'reading',
                                    'reading_id': 'reading', 'current_page': 0}], {}]
        await independent_reading(api, [BOOK], 'camila', 1, random.Random(1))
        self.assertEqual(api.request.call_args.args[2], '/readings/events')
        self.assertEqual(api.request.call_args.args[3]['event'], 'progress')
        self.assertGreater(api.request.call_args.args[3]['current_page'], 0)
        self.assertLess(api.request.call_args.args[3]['current_page'], BOOK.pages)

    async def test_an_active_reading_keeps_its_book_and_increases_pages(self):
        api = AsyncMock()
        api.request.side_effect = [[{'work_id': BOOK.work_id, 'status': 'reading',
                                    'reading_id': 'attempt', 'current_page': 30, 'total_pages': 240}], {}]
        await independent_reading(api, [BOOK], 'camila', 2, random.Random(2))
        payload = api.request.call_args.args[3]
        self.assertEqual(payload['reading_id'], 'attempt')
        self.assertEqual(payload['book_ref'], BOOK.work_id)
        self.assertGreater(payload['current_page'], 30)

    async def test_reader_reviews_are_preserved(self):
        api = AsyncMock()
        api.request.return_value = [{'id': 'existing-review'}]
        await review_action(api, 'camila', BOOK, 3)
        api.request.assert_awaited_once()

    @patch('app.modules.demo.worker.ensure_enabled', side_effect=DemoPaused)
    async def test_disabled_mode_prevents_all_requests(self, enabled):
        client = AsyncMock()
        with self.assertRaises(DemoPaused):
            await DemoAPI(client).request('camila', 'POST', '/posts', {})
        client.request.assert_not_awaited()
        client.post.assert_not_awaited()

    def test_balanced_randomness_repeats_safely_and_rotates_every_reader(self):
        first = [shuffled_schedule(i) for i in range(32)]
        self.assertEqual(first, [shuffled_schedule(i) for i in range(32)])
        self.assertNotEqual([a for a, _ in first], [shuffled_schedule(i)[0] for i in range(32, 64)])
        self.assertEqual(sum(a == 'reading' for a, _ in first), 20)
        for kind in ('event', 'promotion', 'news', 'launch', 'note', 'theory', 'free'):
            self.assertEqual(sum(a == kind for a, _ in first), 1)
        people = [reading_actor(i) for i in range(35)]
        self.assertTrue(all(a != b for a, b in zip(people, people[1:])))
        for offset in range(0, 35, 7):
            self.assertEqual(len(set(people[offset:offset + 7])), 7)

    def test_profiles_start_different_books_and_keep_their_own_attempt(self):
        books = [DemoBook(str(uuid.uuid4()), str(uuid.uuid4()), f'Book {i}', 240) for i in range(12)]
        people = [reading_actor(i) for i in range(7)]
        choices = [choose_reading(books, [], actor)[0].work_id for actor in people]
        self.assertEqual(len(set(choices)), 7)
        active = {'work_id': books[9].work_id, 'status': 'reading', 'current_page': 85}
        selected, state = choose_reading(books, [active], 'valentina')
        self.assertEqual(selected, books[9])
        self.assertEqual(state['current_page'], 85)
