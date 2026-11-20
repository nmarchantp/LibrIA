"""Privacy must hold in API responses, independent of the visitor UI."""
import unittest
from sqlalchemy import select, func
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import ProfileFollow, FollowNotification
from tests import test_mural_feed as fixtures


class CommunityProfilesTest(unittest.TestCase):
    def test_showcase_opt_in_privacy_and_personal_data(self):
        path = f'/api/profiles/{self.profiles[self.author.id].id}/showcase'
        self.author.profile_visibility = 'public'
        self.author.public_sections = []
        self.reading.notebook = {'private': 'Private notebook text'}
        self.db.flush()
        for section in ('library', 'activity', 'analyses'):
            self.assertEqual(self.client.get(f'{path}/{section}').status_code, 403)
        self.as_user(self.author)
        chosen = ['library', 'activity', 'events', 'analyses']
        saved = self.client.patch('/api/profiles/me/literary-preferences', json={'public_sections': chosen})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['public_sections'], chosen)
        self.assertEqual(self.author.events_visibility, 'public')
        self.assertTrue(self.author.onboarding['shared'])
        self.as_user(self.viewer)
        library = self.client.get(f'{path}/library')
        self.assertEqual(library.status_code, 200, library.text)
        self.assertEqual(library.json()['items'][0]['title'], self.work.title)
        self.assertNotIn('notebook', library.text)
        self.assertNotIn('Private notebook text', library.text)
        activity = self.client.get(f'{path}/activity?limit=1')
        self.assertEqual(activity.status_code, 200, activity.text)
        self.assertEqual(activity.json()['items'][0]['body'], self.post.body)
        self.assertEqual(self.client.get(f'{path}/activity?offset=-1').status_code, 422)
        self.assertEqual(self.client.get(f'{path}/analyses').status_code, 200)
        from unittest.mock import patch
        from app.modules.analytics.models import AIAnalysis
        analysis = AIAnalysis(owner_id=self.author.id, target='showcase-test', version=1,
            data_hash='test', model='test', prompt_version='test', content={'profile': {
                'narrative_preferences': ['Narrative finding'], 'evidence_ids': ['secret-source'],
                'reader_essence': {'summary': 'Reading summary', 'source_notes': 'Secret raw notes'}}})
        self.db.add(analysis); self.db.flush()
        with patch('app.modules.analytics.reader_dna.read_current_dna', return_value={'analysis_id': analysis.id}), \
             patch('app.modules.analytics.recommendation_sync.recommendation_state', return_value={}):
            published = self.client.get(f'{path}/analyses')
        self.assertEqual(published.status_code, 200, published.text)
        self.assertIn('Narrative finding', published.text)
        self.assertIn('Reading summary', published.text)
        self.assertNotIn('secret-source', published.text)
        self.assertNotIn('Secret raw notes', published.text)
        self.author.profile_visibility = 'private'
        self.db.flush()
        self.assertEqual(self.client.get(f'{path}/library').status_code, 403)
        self.as_user(self.author)
        self.assertEqual(self.client.get(f'{path}/library?preview=true').status_code, 403)
        self.client.patch('/api/profiles/me/literary-preferences', json={'public_sections': []})
        self.assertEqual(self.author.events_visibility, 'private')
        self.assertFalse(self.author.onboarding['shared'])
        # The private events tab remains available to its owner.
        self.assertEqual(self.client.get(f'/api/profiles/{self.profiles[self.author.id].id}/events').status_code, 200)

    def test_owner_preview_uses_visitor_privacy(self):
        self.author.profile_visibility = 'private'
        self.author.public_sections = ['biography']
        self.author.biography = 'Private story'
        self.db.flush()
        self.as_user(self.author)
        path = f'/api/profiles/{self.profiles[self.author.id].id}'
        self.assertTrue(self.client.get(path).json()['can_view'])
        data = self.client.get(path + '?preview=true').json()
        self.assertFalse(data['can_view'])
        self.assertIsNone(data['biography'])
        self.assertEqual(data['visible_sections'], [])
        self.author.profile_visibility = 'public'
        self.db.flush()
        data = self.client.get(path + '?preview=true').json()
        self.assertTrue(data['can_view'])
        self.assertEqual(data['biography'], 'Private story')
        access = self.client.get(path + '/events/access?preview=true').json()
        self.assertFalse(access['is_owner'])
        self.author.onboarding = {**(self.author.onboarding or {}), 'shared': False}
        self.db.flush()
        self.assertIsNone(self.client.get(path + '/literary-dna?preview=true').json()['dna'])
        self.as_user(self.viewer)
        self.assertEqual(self.client.get(path + '?preview=true').status_code, 403)

    setUp = fixtures.MuralFeedTest.setUp
    tearDown = fixtures.MuralFeedTest.tearDown
    make_reading = fixtures.MuralFeedTest.make_reading
    make_event = fixtures.MuralFeedTest.make_event

    def as_user(self, user):
        app.dependency_overrides[get_current_user] = lambda: user

    def profile(self):
        return self.client.get(f'/api/profiles/{self.profiles[self.author.id].id}')

    def test_private_profile_requires_owner_to_follow_visitor(self):
        self.author.profile_visibility = 'private'
        self.author.biography = 'Secret biography'
        self.author.favorite_quotes = ['Secret quote']
        self.author.public_sections = ['biography', 'favorite_quotes']
        self.db.flush()
        response = self.profile()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertFalse(data['can_view'])  # viewer already follows owner
        self.assertTrue(data['following'])
        self.assertEqual(data['visible_sections'], [])
        self.assertIsNone(data['biography'])
        self.assertEqual(data['favorite_quotes'], [])
        self.assertNotIn('Secret', response.text)
        self.assertEqual(response.headers['cache-control'], 'private, no-store')
        self.db.add(ProfileFollow(profile_id=self.profiles[self.viewer.id].id, user_id=self.author.id))
        self.db.flush()
        data = self.profile().json()
        self.assertTrue(data['can_view'])
        self.assertTrue(data['follows_you'])
        self.assertEqual(data['biography'], 'Secret biography')
        self.db.query(ProfileFollow).filter_by(profile_id=self.profiles[self.viewer.id].id, user_id=self.author.id).delete()
        self.db.flush()
        self.assertFalse(self.profile().json()['can_view'])

    def test_public_profile_only_returns_selected_sections(self):
        self.author.biography = 'Hidden biography'
        self.author.literary_highlights = {'literary_crush': {'name': 'Private character'}, 'essential_books': [{'id': 'private-book', 'title': 'Private book'}]}
        self.author.favorite_quotes = ['Visible quote']
        self.author.public_sections = ['favorite_quotes']
        self.db.flush()
        data = self.profile().json()
        self.assertTrue(data['can_view'])
        self.assertEqual(data['visible_sections'], ['favorite_quotes'])
        self.assertEqual(data['favorite_quotes'], ['Visible quote'])
        self.assertIsNone(data['biography'])
        self.assertIsNone(data['literary_crush'])
        self.assertEqual(data['essential_books'], [])
        self.assertEqual(data['genres'], [])
        self.assertEqual(data['story_illustration'], 'none')
        self.assertNotIn('email', data)
        self.assertNotIn('user_id', data)

    def test_owner_settings_are_validated_and_patch_preserves_privacy(self):
        self.as_user(self.author)
        path = '/api/profiles/me/literary-preferences'
        response = self.client.patch(path, json={'profile_visibility': 'private', 'public_sections': []})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['public_sections'], [])
        self.client.patch(path, json={'biography': 'New biography'})
        self.assertEqual(self.client.get(path).json()['profile_visibility'], 'private')
        self.assertEqual(self.client.patch(path, json={'profile_visibility': 'invalid'}).status_code, 422)
        self.assertEqual(self.client.patch(path, json={'public_sections': ['email']}).status_code, 422)
        self.as_user(self.viewer)
        self.client.patch(path, json={'profile_visibility': 'public'})
        self.assertEqual(self.author.profile_visibility, 'private')

    def test_private_profile_blocks_public_event_agenda(self):
        self.author.profile_visibility = 'private'
        self.author.events_visibility = 'public'
        self.db.flush()
        path = f'/api/profiles/{self.profiles[self.author.id].id}/events'
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertFalse(self.client.get(path + '/access').json()['allowed'])
        self.as_user(self.author)
        self.assertEqual(self.client.get(path).status_code, 200)

    def test_follow_notifications_are_idempotent_and_recipient_only(self):
        path = f'/api/profiles/{self.profiles[self.other.id].id}/follow'
        self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual(self.client.post(path).status_code, 200)
        self.client.delete(path)
        self.client.post(path)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(FollowNotification)), 1)
        self.assertEqual(self.client.get('/api/me/follow-notifications').json()['items'], [])
        self.as_user(self.other)
        items = self.client.get('/api/me/follow-notifications').json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['profile_id'], str(self.profiles[self.viewer.id].id))
        read = f"/api/me/follow-notifications/{items[0]['id']}/read"
        self.assertEqual(self.client.put(read).status_code, 200)
        self.as_user(self.author)
        self.assertEqual(self.client.put(read).status_code, 404)
        self.assertEqual(self.client.post(f'/api/profiles/{self.profiles[self.author.id].id}/follow').status_code, 422)

    def test_connections_provide_profile_links_in_both_directions(self):
        result = self.client.get('/api/profiles/me/connections?kind=following')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['items'][0]['id'], str(self.profiles[self.author.id].id))
        self.assertEqual(self.client.get('/api/profiles/me/connections?kind=followers').json()['items'], [])
        self.as_user(self.author)
        self.assertEqual(self.client.get('/api/profiles/me/connections?kind=followers').json()['items'][0]['id'], str(self.profiles[self.viewer.id].id))

    def test_inactive_profiles_cannot_be_viewed_or_followed(self):
        from datetime import datetime, timezone
        self.author.suspended_at = datetime.now(timezone.utc)
        self.db.flush()
        self.assertEqual(self.profile().status_code, 404)
        self.assertEqual(self.client.post(f'/api/profiles/{self.profiles[self.author.id].id}/follow').status_code, 404)

    def test_summary_counts_finished_books_once_and_active_connections(self):
        from datetime import timedelta
        from app.modules.library.models import Reading
        self.reading.status = 'finished'
        self.reading.current_page = self.reading.total_pages
        self.reading.finished_at = self.now
        self.db.add(Reading(library_entry_id=self.reading.library_entry_id, work_id=self.work.id,
            status='finished', current_page=100, total_pages=100,
            started_at=self.now-timedelta(days=2), finished_at=self.now))
        self.db.flush()
        self.as_user(self.author)
        response = self.client.get('/api/profiles/me/social-summary')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'profile_id': str(self.profiles[self.author.id].id), 'finished_books': 1, 'followers': 1, 'following': 0, 'reviews': 1, 'events': 0})
        self.assertEqual(response.headers['cache-control'], 'private, no-store')
        self.as_user(self.viewer)
        data = self.client.get('/api/profiles/me/social-summary').json()
        self.assertEqual(data['finished_books'], 0)
        self.assertEqual(data['following'], 1)
        self.author.suspended_at = self.now
        self.db.flush()
        self.assertEqual(self.client.get('/api/profiles/me/social-summary').json()['following'], 0)

    def test_discovery_search_pagination_and_follow_removal(self):
        path = '/api/profiles/discover/people'
        # Unique fixture names keep this test independent from existing accounts.
        self.other.display_name = 'Discover-unique-person'
        self.db.flush()
        response = self.client.get(path + '?q=Discover-unique&limit=1')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['items'], [{'id': str(self.profiles[self.other.id].id), 'display_name': 'Discover-unique-person', 'avatar_url': None}])
        self.assertFalse(response.json()['has_more'])
        self.assertEqual(self.client.get(path + '?q=Mural%20viewer').json()['items'], [])
        self.assertEqual(self.client.get(path + '?q=Followed%20reader').json()['items'], [])
        self.assertEqual(self.client.get(path + '?q=Discover-unique&offset=1').json()['items'], [])
        self.assertEqual(self.client.get(path + '?q=%25').json()['items'], [])  # literal percent, not wildcard
        self.client.post(f'/api/profiles/{self.profiles[self.other.id].id}/follow')
        self.assertEqual(self.client.get(path + '?q=Discover-unique').json()['items'], [])
        self.client.delete(f'/api/profiles/{self.profiles[self.other.id].id}/follow')
        self.other.suspended_at = self.now
        self.db.flush()
        self.assertEqual(self.client.get(path + '?q=Discover-unique').json()['items'], [])
