"""Agenda privacy, date boundaries and original attendance, rolled back fixtures."""
from datetime import datetime, timedelta, timezone
import unittest
from sqlalchemy import select, func, event
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post, PublicationEvent, EventAttendance, ProfileFollow
from tests import test_mural_feed as fixtures


class ProfileEventsTest(unittest.TestCase):
    tearDown = fixtures.MuralFeedTest.tearDown
    make_reading = fixtures.MuralFeedTest.make_reading
    make_event = fixtures.MuralFeedTest.make_event
    def setUp(self):
        fixtures.MuralFeedTest.setUp(self)
        self.author.role = 'admin'
        self.now = datetime.now(timezone.utc)
        self.post.source = 'event'; self.post.publication_type = 'event'; self.post.author_role = 'admin'
        self.event = PublicationEvent(post_id=self.post.id, starts_at=self.now-timedelta(days=1),
            ends_at=self.now+timedelta(days=1), timezone='America/Santiago', location='Original place', organizer='Community', category='meetup')
        self.db.add(self.event); self.db.flush()
        self.path = f'/api/profiles/{self.profiles[self.author.id].id}/events'

    def as_user(self, user):
        app.dependency_overrides[get_current_user] = lambda: user

    def test_default_private_and_owner_only_privacy_update(self):
        self.assertEqual(self.author.events_visibility, 'private')
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.client.get(self.path+'/access').json(), {'allowed':False, 'is_owner':False})
        self.as_user(self.author)
        self.assertEqual(self.client.patch('/api/profiles/me/events/privacy', json={'visibility':'contacts'}).status_code, 200)
        self.db.expire(self.author)
        self.assertEqual(self.author.events_visibility, 'contacts')
        self.as_user(self.viewer)
        self.client.patch('/api/profiles/me/events/privacy', json={'visibility':'public'})
        self.assertEqual(self.author.events_visibility, 'contacts')
        self.assertEqual(self.client.patch('/api/profiles/me/events/privacy', json={'visibility':'invalid'}).status_code, 422)

    def test_contacts_direction_and_public_visibility(self):
        self.author.events_visibility='contacts'; self.db.flush()
        self.assertEqual(self.client.get(self.path).status_code, 200)  # viewer follows author
        self.as_user(self.other)
        self.db.add(ProfileFollow(user_id=self.author.id, profile_id=self.profiles[self.other.id].id)); self.db.flush()
        self.assertEqual(self.client.get(self.path).status_code, 403)  # reverse isn't sufficient
        self.author.events_visibility='public'; self.db.flush()
        self.assertEqual(len(self.client.get(self.path).json()['items']), 1)
        self.post.deleted_at=self.now; self.db.flush()
        self.assertEqual(self.client.get(self.path).json()['items'], [])
        self.post.deleted_at=None; self.post.author_role='lector'; self.db.flush()
        self.assertEqual(self.client.get(self.path).json()['items'], [])

    def test_attendance_cancel_and_reader_filters(self):
        response=self.client.put(f'/api/events/{self.post.id}/attendance')
        self.assertEqual(response.status_code,200,response.text)
        mine=self.client.get('/api/profiles/me/events').json()
        self.assertFalse(mine['can_organize']); self.assertEqual(mine['items'][0]['id'],str(self.post.id))
        self.assertTrue(mine['items'][0]['profile_attending'])
        self.assertEqual(self.client.get('/api/profiles/me/events?participation=organizing').json()['items'],[])
        self.client.delete(f'/api/events/{self.post.id}/attendance')
        self.assertEqual(self.client.get('/api/profiles/me/events?participation=attending').json()['items'],[])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EventAttendance).where(EventAttendance.post_id==self.post.id)),1)

    def test_creator_dedup_and_combined_filters(self):
        self.as_user(self.author)
        self.client.put(f'/api/events/{self.post.id}/attendance')
        for participation in ['all','attending','organizing']:
            data=self.client.get('/api/profiles/me/events?participation='+participation).json()
            self.assertEqual(len(data['items']),1)
            self.assertTrue(data['items'][0]['profile_attending']); self.assertTrue(data['items'][0]['profile_organizing'])
        self.event.ends_at=self.now-timedelta(seconds=1); self.db.flush()
        self.assertEqual(self.client.get('/api/profiles/me/events?period=upcoming').json()['items'],[])
        self.assertEqual(len(self.client.get('/api/profiles/me/events?period=past&participation=organizing').json()['items']),1)

    def test_multiday_and_endless_local_day_and_live_edits(self):
        self.as_user(self.author)
        self.assertEqual(len(self.client.get('/api/profiles/me/events').json()['items']),1)
        self.event.ends_at=None; self.event.starts_at=self.now-timedelta(days=3); self.db.flush()
        self.assertEqual(len(self.client.get('/api/profiles/me/events?period=past').json()['items']),1)
        self.event.starts_at=self.now; self.event.location='New place'; self.post.body='Edited description'; self.db.flush()
        result=self.client.get('/api/profiles/me/events').json()['items'][0]
        self.assertEqual(result['event_details']['location'],'New place'); self.assertEqual(result['body'],'Edited description')

    def test_permissions_before_pagination_and_bounded_queries(self):
        self.as_user(self.author)
        for i in range(8):
            post=Post(user_id=self.author.id,author_profile_id=self.profiles[self.author.id].id,author_role='admin',source='event',publication_type='event',kind='community',body='More')
            self.db.add(post);self.db.flush()
            self.db.add(PublicationEvent(post_id=post.id,starts_at=self.now+timedelta(days=i+2),timezone='UTC',location='Place',organizer='Org',category='fair'))
        self.db.flush()
        def measured(limit):
            calls=[]
            def count(*args):calls.append(1)
            event.listen(self.connection,'before_cursor_execute',count)
            try:
                response=self.client.get(f'/api/profiles/me/events?limit={limit}')
                self.assertEqual(response.status_code,200,response.text)
                return len(calls),response.json()
            finally:event.remove(self.connection,'before_cursor_execute',count)
        small,_=measured(1);large,data=measured(9)
        self.assertLessEqual(large,small+2);self.assertEqual(len(data['items']),9)
        self.assertFalse(data['has_more'])

