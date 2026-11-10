"""Real PostgreSQL requests; fixtures and media roll back after each test."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import unittest
from PIL import Image
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import ProfileFollow
from app.modules.social.story_models import Story
from app.modules.social.story_lifecycle import purge_expired_stories
from tests import test_mural_feed as fixtures


class UserStoriesTest(unittest.TestCase):
    setUp = fixtures.MuralFeedTest.setUp
    tearDown = fixtures.MuralFeedTest.tearDown
    make_reading = fixtures.MuralFeedTest.make_reading
    make_event = fixtures.MuralFeedTest.make_event

    def as_user(self, user):
        app.dependency_overrides[get_current_user] = lambda: user

    def groups(self, suffix=''):
        response = self.client.get('/api/stories' + suffix)
        self.assertEqual(response.status_code, 200, response.text)
        fixture_ids = {str(profile.id) for profile in self.profiles.values()}
        return [group for group in response.json()['items'] if group['profile_id'] in fixture_ids]

    def publish(self):
        output = BytesIO()
        Image.new('RGB', (80, 40), 'purple').save(output, 'PNG')
        response = self.client.post('/api/stories', content=output.getvalue(), headers={'Content-Type': 'image/png'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_reader_can_publish_vertical_image_for_exactly_24_hours(self):
        story = self.publish()
        created, expires = [datetime.fromisoformat(story[key].replace('Z', '+00:00')) for key in ('created_at', 'expires_at')]
        self.assertEqual(expires - created, timedelta(hours=24))
        groups = self.groups('?audience=contacts')
        self.assertEqual(groups[0]['profile_id'], str(self.profiles[self.viewer.id].id))
        self.assertTrue(groups[0]['is_owner'])
        image = self.client.get('/api' + story['image_url'])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers['cache-control'], 'private, no-store')
        self.assertEqual(Image.open(BytesIO(image.content)).size, (1080, 1920))

    def test_contacts_filter_and_profile_filter(self):
        self.as_user(self.author); followed = self.publish()
        self.as_user(self.other); stranger = self.publish()
        self.as_user(self.viewer)
        items = self.groups('?audience=contacts')
        self.assertEqual([story['id'] for group in items for story in group['stories']], [followed['id']])
        items = self.groups()
        self.assertEqual({story['id'] for group in items for story in group['stories']}, {followed['id'], stranger['id']})
        items = self.client.get('/api/stories', params={'profile_id': str(self.profiles[self.other.id].id)}).json()['items']
        self.assertEqual(items[0]['stories'][0]['id'], stranger['id'])

    def test_private_access_is_enforced_for_listing_and_media_and_revocation(self):
        self.author.profile_visibility = 'private'
        self.as_user(self.author); story = self.publish()
        self.as_user(self.viewer)
        self.assertEqual(self.groups(), [])
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 404)
        grant = ProfileFollow(profile_id=self.profiles[self.viewer.id].id, user_id=self.author.id)
        self.db.add(grant); self.db.flush()
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 200)
        self.db.delete(grant); self.db.flush()
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 404)

    def test_expired_story_is_inaccessible_and_purge_removes_binary(self):
        story = self.publish()
        import uuid
        row = self.db.get(Story, uuid.UUID(story['id']))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.flush()
        self.assertEqual(self.groups(), [])
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 404)
        purge_expired_stories(self.db)
        self.db.flush()
        self.assertIsNone(self.db.get(Story, row.id))

    def test_owner_only_deletion_and_inactive_author_hidden(self):
        self.as_user(self.author); story = self.publish()
        self.as_user(self.viewer)
        self.assertEqual(self.client.delete('/api/stories/' + story['id']).status_code, 404)
        self.author.suspended_at = datetime.now(timezone.utc); self.db.flush()
        self.assertEqual(self.groups(), [])
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 404)
        self.author.suspended_at = None; self.db.flush()
        self.as_user(self.author)
        self.assertEqual(self.client.delete('/api/stories/' + story['id']).status_code, 204)
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 404)

    def test_invalid_and_oversized_uploads_are_rejected(self):
        for content in (b'not an image', b'\x89PNG\r\n\x1a\ninvalid'):
            self.assertEqual(self.client.post('/api/stories', content=content).status_code, 422)
        self.assertEqual(self.client.post('/api/stories', content=b'x' * (5 * 1024 * 1024 + 1)).status_code, 413)
        self.viewer.suspended_at = datetime.now(timezone.utc); self.db.flush()
        self.assertEqual(self.client.post('/api/stories', content=b'no').status_code, 403)

    def test_active_limit_and_expired_upload_cleanup(self):
        profile_id = self.profiles[self.viewer.id].id
        now = datetime.now(timezone.utc)
        rows = [Story(profile_id=profile_id, content_type='image/jpeg', data=b'test',
                      created_at=now, expires_at=now + timedelta(hours=24)) for _ in range(20)]
        self.db.add_all(rows); self.db.flush()
        output = BytesIO(); Image.new('RGB', (10, 10)).save(output, 'PNG')
        self.assertEqual(self.client.post('/api/stories', content=output.getvalue()).status_code, 409)
        rows[0].expires_at = now - timedelta(seconds=1); self.db.flush()
        self.publish()
        self.assertEqual(len(self.groups()[0]['stories']), 20)

    def test_images_and_listing_require_authentication(self):
        story = self.publish()
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get('/api' + story['image_url']).status_code, 401)
        self.assertEqual(self.client.get('/api/stories').status_code, 401)

    def test_views_are_idempotent_and_specific_to_viewer_and_story(self):
        self.as_user(self.author)
        first, second = self.publish(), self.publish()
        self.as_user(self.viewer)
        self.assertFalse(any(story['seen'] for story in self.groups()[0]['stories']))
        path = '/api/stories/' + first['id'] + '/view'
        self.assertEqual(self.client.put(path).status_code, 204)
        self.assertEqual(self.client.put(path).status_code, 204)
        stories = {story['id']: story['seen'] for story in self.groups()[0]['stories']}
        self.assertTrue(stories[first['id']])
        self.assertFalse(stories[second['id']])
        self.as_user(self.other)
        self.assertFalse(any(story['seen'] for story in self.groups()[0]['stories']))

    def test_cannot_mark_private_or_expired_stories_viewed(self):
        self.author.profile_visibility = 'private'
        self.as_user(self.author); story = self.publish()
        self.as_user(self.viewer)
        path = '/api/stories/' + story['id'] + '/view'
        self.assertEqual(self.client.put(path).status_code, 404)
        self.as_user(self.author)
        import uuid
        self.db.get(Story, uuid.UUID(story['id'])).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.flush()
        self.assertEqual(self.client.put(path).status_code, 404)
