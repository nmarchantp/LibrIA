"""Read-only mural projections; all fixture writes roll back."""
import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent
from app.modules.social.models import Post, PostComment, ProfileFollow, Review
from app.modules.users.identities import create_personal_profile
from app.modules.users.models import User


class MuralFeedTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.viewer, self.author, self.other = [User(display_name=name) for name in ('Mural viewer', 'Followed reader', 'Other reader')]
        self.db.add_all([self.viewer, self.author, self.other])
        self.db.flush()
        self.profiles = {u.id: create_personal_profile(self.db, u) for u in (self.viewer, self.author, self.other)}
        self.db.flush()
        self.db.add(ProfileFollow(user_id=self.viewer.id, profile_id=self.profiles[self.author.id].id))
        self.work = Work(title="Mural test book")
        self.db.add(self.work)
        self.db.flush()
        self.now = datetime.now(timezone.utc) - timedelta(hours=1)
        self.reading = self.make_reading(self.author)
        self.events = [self.make_event(self.reading, self.author, 'progress', page, i) for i, page in enumerate([16, 25, 43])]
        self.start = self.make_event(self.reading, self.author, 'start', 0, -1)
        self.finish = self.make_event(self.reading, self.author, 'finish', 100, 4)
        self.private = self.make_event(self.reading, self.author, 'progress', 50, 5, public=False)
        self.other_reading = self.make_reading(self.other)
        self.other_event = self.make_event(self.other_reading, self.other, 'progress', 60, 6)
        self.review = Review(author_profile_id=self.profiles[self.author.id].id, created_by_user_id=self.author.id,
            work_id=self.work.id, body='Public review', rating=4, status='published', published_at=self.now,
            created_at=self.now, updated_at=self.now)
        self.post = Post(user_id=self.author.id, author_profile_id=self.profiles[self.author.id].id,
            author_role='lector', source='community', kind='community', publication_type='note', body='Public note',
            book_ref=str(self.work.id), book_title=self.work.title)
        self.db.add_all([self.review, self.post])
        self.db.flush()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.viewer
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def make_reading(self, user, total=100):
        entry = self.db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == user.id, LibraryEntry.work_id == self.work.id))
        if not entry:
            entry = LibraryEntry(user_id=user.id, work_id=self.work.id)
            self.db.add(entry)
            self.db.flush()
        reading = Reading(library_entry_id=entry.id, work_id=self.work.id, status='reading', current_page=43,
                          total_pages=total, started_at=self.now - timedelta(days=1))
        self.db.add(reading)
        self.db.flush()
        return reading

    def make_event(self, reading, actor, kind, page, minute, public=True):
        item = ReadingEvent(reading_id=reading.id, actor_user_id=actor.id, kind=kind,
            previous_page=0, page=page, total_pages=reading.total_pages, is_public=public,
            created_at=self.now + timedelta(minutes=minute))
        self.db.add(item)
        self.db.flush()
        return item

    def get(self, path):
        response = self.client.get('/api/mural' + path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_summary_latest_per_reading_and_classification(self):
        data = self.get('?audience=contacts')['categories']
        self.assertEqual([i['id'] for i in data['progress']['items']], [str(self.events[-1].id)])
        self.assertEqual(data['progress']['items'][0]['progress_percent'], 43)
        self.assertEqual(data['started']['items'][0]['id'], str(self.start.id))
        self.assertEqual(data['finished']['items'][0]['id'], str(self.finish.id))
        self.assertEqual(data['reviews']['items'][0]['id'], str(self.review.id))
        self.assertEqual(data['social']['items'][0]['id'], str(self.post.id))
        self.assertNotIn('additions', data)
        reread = self.make_reading(self.author)
        extra = self.make_event(reread, self.author, 'progress', 12, 7)
        ids = [i['id'] for i in self.get('?audience=contacts')['categories']['progress']['items']]
        self.assertEqual(set(ids), {str(extra.id), str(self.events[-1].id)})

    def test_publication_categories_filter_before_pagination(self):
        groups = {}
        for category, publication_type in [('events', 'event'), ('launches', 'launch'), ('announcements', 'news'), ('promotions', 'promotion')]:
            groups[category] = []
            for index in range(3):
                post = Post(user_id=self.author.id, author_profile_id=self.profiles[self.author.id].id,
                    author_role='admin', source='event' if publication_type == 'event' else 'community',
                    kind='community', publication_type=publication_type, title=f'{category} {index}',
                    body='Full publication text', created_at=self.now + timedelta(minutes=index))
                self.db.add(post)
                groups[category].append(post)
        stranger = Post(user_id=self.other.id, author_profile_id=self.profiles[self.other.id].id,
            author_role='admin', source='event', kind='community', publication_type='event',
            title='Other event', body='Another public event', created_at=self.now + timedelta(minutes=10))
        self.db.add(stranger)
        self.db.flush()
        for category, posts in groups.items():
            page = self.get(f'/{category}?audience=contacts&limit=2')
            self.assertEqual([item['id'] for item in page['items']], [str(posts[2].id), str(posts[1].id)])
            cursor = page['next_cursor']
            last = self.get(f'/{category}?audience=contacts&limit=2&cursor={cursor}')
            self.assertEqual([item['id'] for item in last['items']], [str(posts[0].id)])
            self.assertIsNone(last['next_cursor'])
            wrong_category = 'launches' if category == 'events' else 'events'
            self.assertEqual(self.client.get(f'/api/mural/{wrong_category}?audience=contacts&cursor={cursor}').status_code, 422)
        self.assertIn(str(stranger.id), [item['id'] for item in self.get('/events?audience=community')['items']])
        self.assertNotIn(str(stranger.id), [item['id'] for item in self.get('/events?audience=contacts')['items']])
        legacy = Post(user_id=self.author.id, author_profile_id=self.profiles[self.author.id].id,
            author_role='admin', source='event', kind='community', title='Legacy event', body='Original historical event')
        self.db.add(legacy)
        self.db.flush()
        self.assertIn(str(legacy.id), [item['id'] for item in self.get('/events?audience=contacts')['items']])

    def test_full_history_pagination_and_cursor_scope(self):
        first = self.get('/progress?audience=contacts&limit=2')
        self.assertEqual([i['id'] for i in first['items']], [str(self.events[2].id), str(self.events[1].id)])
        cursor = first['next_cursor']
        self.make_event(self.reading, self.author, 'progress', 70, 9)
        second = self.get('/progress?audience=contacts&limit=2&cursor=' + cursor)
        self.assertEqual([i['id'] for i in second['items']], [str(self.events[0].id)])
        self.assertIsNone(second['next_cursor'])
        for path in ['/progress?audience=community&cursor=', '/started?audience=contacts&cursor=']:
            self.assertEqual(self.client.get('/api/mural' + path + cursor).status_code, 422)
        self.assertEqual(self.client.get('/api/mural/progress?cursor=invalid').status_code, 422)

    def test_social_excludes_dedicated_categories_before_limits_and_pagination(self):
        self.post.created_at=self.now-timedelta(minutes=20)
        allowed=[]
        for index,kind in enumerate(('note','theory','free',None,'institutional')):
            row=Post(user_id=self.author.id,author_profile_id=self.profiles[self.author.id].id,
                author_role='admin',source='community',kind='community',publication_type=kind,
                body=f'General literary conversation {index}',created_at=self.now+timedelta(minutes=index))
            self.db.add(row);allowed.append(row)
        excluded={}
        for index,(category,kind) in enumerate((('events','event'),('launches','launch'),('announcements','news'),('promotions','promotion'))):
            row=Post(user_id=self.author.id,author_profile_id=self.profiles[self.author.id].id,
                author_role='admin',source='event' if kind=='event' else 'community',kind='community',
                publication_type=kind,title='Stella Tack en Chile' if kind=='event' else category,
                body='Dedicated category publication',created_at=self.now+timedelta(minutes=30+index))
            self.db.add(row);excluded[category]=row
        legacy=Post(user_id=self.author.id,author_profile_id=self.profiles[self.author.id].id,
            author_role='admin',source='event',kind='community',publication_type=None,body='Legacy event',created_at=self.now+timedelta(minutes=40))
        stranger=Post(user_id=self.other.id,author_profile_id=self.profiles[self.other.id].id,
            author_role='admin',source='community',kind='community',publication_type='free',body='Public conversation from an unfollowed profile')
        deleted=Post(user_id=self.author.id,author_profile_id=self.profiles[self.author.id].id,
            author_role='admin',source='community',kind='community',publication_type='note',body='Deleted note',deleted_at=self.now)
        hidden=Post(user_id=self.author.id,author_profile_id=self.profiles[self.author.id].id,
            author_role='lector',source='community',kind='community',publication_type='free',body='Not authorized by visibility policy')
        self.db.add_all([legacy,stranger,deleted,hidden]);self.db.flush()
        before=self.db.execute(select(Post.id,Post.body,Post.publication_type,Post.source).order_by(Post.id)).all()
        preview=self.get('?audience=contacts&limit=2')['categories']['social']
        expected=[str(row.id) for row in reversed(allowed)]+[str(self.post.id)]
        self.assertEqual([item['id'] for item in preview['items']],expected[:2])
        self.assertTrue(preview['has_more'])
        seen=[];cursor=None
        while True:
            page=self.get('/social?audience=contacts&limit=2'+(f'&cursor={cursor}' if cursor else ''))
            seen.extend(item['id'] for item in page['items'])
            cursor=page['next_cursor']
            if not cursor:break
        self.assertEqual(seen,expected)
        community=self.get('/social?audience=community&limit=50')['items']
        community_ids={item['id'] for item in community}
        self.assertIn(str(stranger.id),community_ids)
        forbidden={str(row.id) for row in [*excluded.values(),legacy,deleted,hidden]}
        self.assertFalse(forbidden&community_ids)
        for audience in ('contacts','community'):
            summary_ids={item['id'] for item in self.get(f'?audience={audience}&limit=12')['categories']['social']['items']}
            self.assertFalse(forbidden&summary_ids)
        for category,row in excluded.items():
            self.assertIn(str(row.id),{item['id'] for item in self.get(f'/{category}?audience=contacts')['items']})
        self.assertIn(str(legacy.id),{item['id'] for item in self.get('/events?audience=contacts')['items']})
        self.assertEqual(self.db.execute(select(Post.id,Post.body,Post.publication_type,Post.source).order_by(Post.id)).all(),before)

    def test_audiences_nonreciprocal_and_privacy(self):
        contacts = self.get('/progress?audience=contacts')['items']
        self.assertTrue(all(i['user_id'] == str(self.author.id) for i in contacts))
        community = self.get('/progress?audience=community')['items']
        self.assertIn(str(self.other_event.id), [i['id'] for i in community])
        self.assertNotIn(str(self.private.id), [i['id'] for i in community])
        self.review.status = 'hidden'
        self.db.flush()
        self.assertEqual(self.get('/reviews?audience=contacts')['items'], [])
        app.dependency_overrides[get_current_user] = lambda: self.author
        self.assertTrue(all(not group['items'] for group in self.get('?audience=contacts')['categories'].values()))

    def test_pages_without_percentage_and_abandonment_barrier(self):
        reading = self.make_reading(self.author, total=None)
        page_event = self.make_event(reading, self.author, 'progress', 82, 7)
        item = next(i for i in self.get('/progress?audience=contacts')['items'] if i['id'] == str(page_event.id))
        self.assertIsNone(item['progress_percent'])
        self.assertEqual(item['page'], 82)
        reading.status, reading.abandoned_at = 'abandoned', self.now + timedelta(minutes=9)
        self.db.flush()
        self.assertNotIn(str(page_event.id), [i['id'] for i in self.get('/progress?audience=contacts')['items']])

    def test_read_only_comments_and_bounded_queries(self):
        comment = PostComment(reading_event_id=self.events[0].id, user_id=self.viewer.id,
                              author_profile_id=self.profiles[self.viewer.id].id, body='Existing comment')
        self.db.add(comment)
        self.db.flush()
        before = [self.db.scalar(select(func.count()).select_from(model)) for model in (Post, ReadingEvent, Review, PostComment)]
        calls = []
        def counted(*args): calls.append(1)
        event.listen(self.connection, 'before_cursor_execute', counted)
        try:
            self.get('?audience=contacts&limit=1')
            small = len(calls)
            calls.clear()
            self.get('?audience=contacts&limit=12')
            self.assertEqual(len(calls), small)
        finally:
            event.remove(self.connection, 'before_cursor_execute', counted)
        after = [self.db.scalar(select(func.count()).select_from(model)) for model in (Post, ReadingEvent, Review, PostComment)]
        self.assertEqual(before, after)
        comments = self.client.get(f'/api/posts/{self.events[0].id}/comments')
        self.assertEqual(comments.status_code, 200)
        self.assertIn(str(comment.id), [i['id'] for i in comments.json()])

    def test_empty_and_authentication(self):
        app.dependency_overrides[get_current_user] = lambda: self.other
        data = self.get('?audience=contacts')['categories']
        self.assertTrue(all(not value['items'] for value in data.values()))
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get('/api/mural').status_code, 401)
        self.assertEqual(self.client.get('/api/mural/progress').status_code, 401)

    def test_deep_history_is_complete_without_duplicate_ids(self):
        extra = [self.make_event(self.reading, self.author, 'progress', 44 + i, 10 + i) for i in range(25)]
        expected = {str(item.id) for item in self.events + extra}
        received, cursor = [], None
        for _ in range(10):
            data = self.get('/progress?audience=contacts&limit=5' + ('&cursor=' + cursor if cursor else ''))
            received.extend(item['id'] for item in data['items'])
            cursor = data['next_cursor']
            if cursor is None:
                break
        self.assertIsNone(cursor)
        self.assertEqual(len(received), len(set(received)))
        self.assertEqual(set(received), expected)
        preview = self.get('?audience=contacts')['categories']['progress']['items']
        self.assertEqual([item['id'] for item in preview], [str(extra[-1].id)])

    def test_canonical_current_review_visibility_before_pagination(self):
        duplicate = Work(title='Historical equivalent work')
        self.db.add(duplicate)
        self.db.flush()
        hidden = Review(author_profile_id=self.profiles[self.author.id].id, created_by_user_id=self.author.id,
            work_id=duplicate.id, body='New private version', status='hidden', published_at=self.now,
            created_at=self.now, updated_at=self.now + timedelta(minutes=1))
        self.db.add(hidden)
        self.db.flush()
        snapshot = SimpleNamespace(mapping={self.work.id: SimpleNamespace(canonical_work_id=self.work.id),
            duplicate.id: SimpleNamespace(canonical_work_id=self.work.id)})
        with patch('app.modules.books.canonical.enabled', return_value=True), \
             patch('app.modules.books.canonical.identity_snapshot', return_value=snapshot), \
             patch('app.modules.books.consistency.review_preferences', return_value={}):
            self.assertEqual(self.get('/reviews?audience=contacts&limit=1')['items'], [])
        preference = {(self.profiles[self.author.id].id, self.work.id): self.review.id}
        with patch('app.modules.books.canonical.enabled', return_value=True), \
             patch('app.modules.books.canonical.identity_snapshot', return_value=snapshot), \
             patch('app.modules.books.consistency.review_preferences', return_value=preference):
            self.assertEqual(self.get('/reviews?audience=contacts')['items'][0]['id'], str(self.review.id))
