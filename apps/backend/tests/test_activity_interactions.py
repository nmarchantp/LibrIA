"""Social footer contracts, authorization and database-level idempotency."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.social.models import ActivityView, Post, PostLike, PostComment, ReadingEventLike
from app.modules.social.interaction_service import add_comment, like
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from tests.test_mural_feed import MuralFeedTest
import unittest


class ActivityInteractionsTest(MuralFeedTest):
    def test_comment_limits_by_activity_source(self):
        for event in self.events[:3]:
            url = self.url('reading_event', event.id)
            before = self.client.get(url).json()
            rejected = self.client.post(url + '/comments', json={'body': ' '.join(['palabra'] * 201)})
            self.assertEqual(rejected.status_code, 422, rejected.text)
            self.assertEqual(self.client.get(url).json()['comment_count'], before['comment_count'])
            self.assertEqual(self.client.get(url).json()['view_count'], before['view_count'])
            body = '\n\t'.join(['palabra'] * 200)
            accepted = self.client.post(url + '/comments', json={'body': body})
            self.assertEqual(accepted.status_code, 201, accepted.text)
            self.assertEqual(accepted.json()['comment']['body'], body)
        for kind, item in [('publication', self.post), ('review', self.review)]:
            url = self.url(kind, item.id)
            self.assertEqual(self.client.post(url + '/comments', json={'body': 'a' * 1001}).status_code, 422)
            self.assertEqual(self.client.post(url + '/comments', json={'body': 'a' * 1000}).status_code, 201)

    def url(self, kind, identifier, suffix=''):
        return f'/api/activities/{kind}/{identifier}{suffix}'

    def test_likes_all_sources_and_unlike_keeps_views(self):
        for kind, item in [('publication', self.post), ('review', self.review), ('reading_event', self.events[0])]:
            url = self.url(kind, item.id)
            self.assertEqual(self.client.get(url).json()['view_count'], 0)
            for _ in range(2):
                response = self.client.put(url + '/like')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['like_count'], 1)
                self.assertTrue(response.json()['liked_by_me'])
                self.assertEqual(response.json()['view_count'], 1)
            result = self.client.delete(url + '/like').json()
            self.assertEqual(result['like_count'], 0)
            self.assertFalse(result['liked_by_me'])
            self.assertEqual(result['view_count'], 1)

    def test_view_unique_across_intents_comments_likes_and_legacy_routes(self):
        item = self.events[0]
        url = self.url('reading_event', item.id)
        for action in ['open', 'open_comments', 'open']:
            response = self.client.put(url + '/view', json={'action': action})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['view_count'], 1)
        result = self.client.post(url + '/comments', json={'body': 'Typed comment'}).json()
        self.assertEqual(result['interactions']['view_count'], 1)
        self.assertEqual(result['interactions']['comment_count'], 1)
        legacy = f'/api/posts/{item.id}'
        self.assertEqual(self.client.put(legacy + '/like').json()['like_count'], 1)
        self.assertEqual(self.client.post(legacy + '/comments', json={'body': 'Legacy comment'}).status_code, 201)
        data = self.client.get(url).json()
        self.assertEqual((data['like_count'], data['comment_count'], data['view_count']), (1, 2, 1))
        self.assertEqual(len(self.client.get(legacy + '/comments').json()), 2)

    def test_author_excluded_and_counters_independent(self):
        from app.main import app
        from app.modules.auth.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: self.author
        for kind, item in [('publication', self.post), ('review', self.review), ('reading_event', self.events[0])]:
            url = self.url(kind, item.id)
            self.assertEqual(self.client.put(url + '/view', json={'action': 'open'}).json()['view_count'], 0)
            self.assertEqual(self.client.put(url + '/like').json()['view_count'], 0)
            result = self.client.post(url + '/comments', json={'body': 'Own comment'}).json()['interactions']
            self.assertEqual((result['like_count'], result['comment_count'], result['view_count']), (1, 1, 0))
            self.assertFalse(result['capabilities']['can_register_view'])

    def test_gets_do_not_record_views_and_counts_are_not_page_length(self):
        self.db.add_all(PostComment(reading_event_id=self.events[0].id, user_id=self.viewer.id,
            body=f'Existing {index}') for index in range(120))
        self.db.flush()
        url = self.url('reading_event', self.events[0].id)
        for _ in range(2):
            self.get('?audience=community')
            self.get('/progress?audience=contacts')
            self.client.get(url + '/comments')
        data = self.client.get(url).json()
        self.assertEqual(data['view_count'], 0)
        self.assertEqual(data['comment_count'], 120)
        self.assertEqual(len(self.client.get(url + '/comments').json()), 100)
        item = next(item for item in self.get('/progress?audience=contacts')['items'] if item['id'] == str(self.events[0].id))
        self.assertEqual(item['comment_count'], 120)
        self.assertEqual(item['view_count'], 0)

    def test_stale_private_and_invalid_requests_do_not_count(self):
        for kind, item in [('reading_event', self.private)]:
            url = self.url(kind, item.id)
            self.assertEqual(self.client.put(url + '/view', json={'action': 'open'}).status_code, 404)
            self.assertEqual(self.client.put(url + '/like').status_code, 404)
            self.assertEqual(self.client.post(url + '/comments', json={'body': 'No'}).status_code, 404)
        url = self.url('review', self.review.id)
        self.client.get(url)  # A card that was initially public.
        self.review.status = 'hidden'
        self.db.flush()
        for endpoint, payload in [('/like', None), ('/view', {'action': 'open'})]:
            self.assertEqual(self.client.put(url + endpoint, json=payload).status_code, 404)
        self.assertEqual(self.client.post(url + '/comments', json={'body': 'No'}).status_code, 404)
        self.assertEqual(self.client.get(f'/api/posts/{self.review.id}/comments').status_code, 404)
        public = self.url('publication', self.post.id)
        self.assertEqual(self.client.put(public + '/view', json={'action': 'scroll'}).status_code, 422)
        self.assertEqual(self.client.put(public + '/view', json={'action': 'open', 'user_id': str(self.other.id)}).status_code, 422)
        self.assertEqual(self.client.post(public + '/comments', json={'body': ''}).status_code, 422)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ActivityView)), 0)

    def test_cross_source_uuid_collision_is_unambiguous(self):
        duplicate = Post(id=self.events[0].id, user_id=self.author.id, author_role='admin', source='community', kind='community', body='Separate source')
        self.db.add(duplicate)
        self.db.flush()
        for kind in ['publication', 'reading_event']:
            self.assertEqual(self.client.put(self.url(kind, duplicate.id, '/like')).status_code, 200)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ActivityView)), 2)
        self.assertEqual(self.client.get(f'/api/posts/{duplicate.id}/comments').status_code, 409)
        self.assertEqual(self.client.get(self.url('publication', duplicate.id)).json()['like_count'], 1)
        self.assertEqual(self.client.get(self.url('reading_event', duplicate.id)).json()['like_count'], 1)

    def test_constraints_and_identity_not_exposed(self):
        url = self.url('reading_event', self.events[0].id)
        result = self.client.put(url + '/view', json={'action': 'open'}).json()
        self.assertNotIn('user_id', result)
        self.assertNotIn('viewers', result)
        for values in [dict(user_id=self.viewer.id), dict(user_id=self.viewer.id, post_id=self.post.id, reading_event_id=self.events[0].id),
                       dict(user_id=self.viewer.id, reading_event_id=self.events[0].id)]:
            with self.assertRaises(IntegrityError), self.db.begin_nested():
                self.db.add(ActivityView(**values))
                self.db.flush()
        self.client.put(url + '/like')
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.add(ReadingEventLike(user_id=self.viewer.id, reading_event_id=self.events[0].id))
            self.db.flush()

    def test_typed_routes_require_session(self):
        from app.main import app
        from app.modules.auth.dependencies import get_current_user
        app.dependency_overrides.pop(get_current_user)
        url = self.url('reading_event', self.events[0].id)
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url + '/comments').status_code, 401)
        self.assertEqual(self.client.put(url + '/view', json={'action': 'open'}).status_code, 401)
        self.assertEqual(self.client.put(url + '/like').status_code, 401)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ActivityView)), 0)

    def test_legacy_likes_do_not_backfill_views(self):
        self.db.add(PostLike(post_id=self.post.id, user_id=self.viewer.id))
        self.db.flush()
        counts = self.client.get(self.url('publication', self.post.id)).json()
        self.assertEqual((counts['like_count'], counts['view_count']), (1, 0))

    def test_abandoned_reading_stale_interaction_rejected(self):
        url = self.url('reading_event', self.events[0].id)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.reading.status, self.reading.abandoned_at = 'abandoned', self.now
        self.db.flush()
        self.assertEqual(self.client.put(url + '/like').status_code, 404)
        self.assertEqual(self.client.put(url + '/view', json={'action': 'open'}).status_code, 404)
        self.assertEqual(self.client.get(url + '/comments').status_code, 404)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ActivityView)), 0)


class ConcurrentInteractionsTest(unittest.TestCase):
    def test_simultaneous_requests_one_like_one_view(self):
        if get_settings().app_env not in {'development', 'test'}:
            self.skipTest('Committed concurrency fixtures are limited to development/test')
        # Separate connections need committed parents. These are new UUID fixtures,
        # not historical rows; only their exact IDs are cleaned up below.
        with SessionLocal.begin() as db:
            owner, viewer = User(display_name='Isolated interaction owner'), User(display_name='Isolated interaction viewer')
            db.add_all([owner, viewer]); db.flush()
            profile = Profile(kind='personal', owner_user_id=viewer.id, display_name='Isolated viewer profile')
            db.add(profile); db.flush()
            post = Post(user_id=owner.id, author_role='admin', source='community', kind='community', body='Isolated concurrency fixture')
            db.add(post); db.flush()
            post_id, owner_id, viewer_id, profile_id = post.id, owner.id, viewer.id, profile.id
        barrier = Barrier(6)
        def run(index):
            with SessionLocal.begin() as db:
                barrier.wait(timeout=10)
                if index % 2:
                    return add_comment(db, 'publication', post_id, viewer_id, profile_id, f'Concurrent {index}')[1]
                return like(db, 'publication', post_id, viewer_id, True)
        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(run, range(6)))
            self.assertTrue(all(result['view_count'] == 1 for result in results))
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(ActivityView).where(ActivityView.post_id == post_id)), 1)
                self.assertEqual(db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)), 1)
                self.assertEqual(db.scalar(select(func.count()).select_from(PostComment).where(PostComment.post_id == post_id)), 3)
        finally:
            with SessionLocal.begin() as db:
                for model in [ActivityView, PostLike, PostComment]:
                    db.execute(delete(model).where(model.post_id == post_id))
                db.execute(delete(Post).where(Post.id == post_id))
                db.execute(delete(Profile).where(Profile.id == profile_id))
                db.execute(delete(User).where(User.id.in_([owner_id, viewer_id])))
