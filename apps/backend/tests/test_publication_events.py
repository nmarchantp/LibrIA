import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime,timezone
from sqlalchemy import select,func,delete
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.users.models import User
from app.modules.social.event_service import set_attendance
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post,PublicationEvent,EventAttendance,EventScheduleUpdate,PostImage
from tests.test_mural_feed import MuralFeedTest


class ConcurrentAttendanceTest(unittest.TestCase):
    def test_repeated_concurrent_confirmation_is_one_attendee(self):
        if get_settings().app_env not in {'development','test'}:
            self.skipTest('Isolated committed fixtures require development/test')
        with SessionLocal.begin() as db:
            owner,viewer=User(display_name='Isolated event owner'),User(display_name='Isolated event attendee')
            db.add_all([owner,viewer]);db.flush()
            post=Post(user_id=owner.id,author_role='admin',source='event',publication_type='event',kind='community',body='Isolated attendance concurrency fixture')
            db.add(post);db.flush()
            db.add(PublicationEvent(post_id=post.id,starts_at=datetime(2026,11,12,21,tzinfo=timezone.utc),timezone='America/Santiago',location='Test',organizer='Test',category='fair'))
            post_id,owner_id,viewer_id=post.id,owner.id,viewer.id
        barrier=Barrier(6)
        def run(_):
            with SessionLocal() as db:
                user=db.get(User,viewer_id)
                barrier.wait(timeout=10)
                return set_attendance(db,user,post_id,True)
        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                results=list(pool.map(run,range(6)))
            self.assertTrue(all(row['attending'] and row['attendee_count']==1 for row in results))
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(EventAttendance).where(EventAttendance.post_id==post_id)),1)
        finally:
            with SessionLocal.begin() as db:
                db.execute(delete(EventAttendance).where(EventAttendance.post_id==post_id))
                db.execute(delete(PublicationEvent).where(PublicationEvent.post_id==post_id))
                db.execute(delete(Post).where(Post.id==post_id))
                db.execute(delete(User).where(User.id.in_([owner_id,viewer_id])))


def details(day='2026-11-12',hour='18:00'):
    return {'start_date':day,'start_time':hour,'timezone':'America/Santiago','location':'Santiago de Chile','organizer':'Comunidad LibrIA','category':'fair'}


class PublicationEventsTest(MuralFeedTest):
    def test_calendar_ranges_use_event_local_dates_and_include_multiday_events(self):
        self.owner()
        schedules=[{**details('2026-10-31','23:30'),'end_date':'2026-11-02','end_time':'09:00'},details('2026-11-30','23:30'),details('2026-12-01','00:30')]
        identifiers=[]
        for schedule in schedules:
            payload=self.payload(schedule);payload.pop('book_ref')
            response=self.client.post('/api/posts',json=payload)
            self.assertEqual(response.status_code,201,response.text)
            identifiers.append(response.json()['id'])
        self.viewer_user()
        query='/api/events?from_date=2026-11-01&to_date=2026-11-30'
        data=self.client.get(query).json()
        ids={item['id'] for item in data['items']}
        self.assertTrue(set(identifiers[:2]).issubset(ids));self.assertNotIn(identifiers[2],ids)
        self.assertIn(identifiers[0],{item['id'] for item in self.client.get('/api/events?from_date=2026-11-01&to_date=2026-11-01').json()['items']})
        self.assertEqual(self.client.get(query+'&limit=1').json()['items'][0]['id'],data['items'][0]['id'])
        self.assertEqual(self.client.get(query+'&limit=1&offset=1').json()['items'][0]['id'],data['items'][1]['id'])
        self.assertTrue(self.client.get(query+'&limit=1').json()['has_more'])
        self.assertEqual(self.client.get('/api/events?from_date=2026-11-30&to_date=2026-11-01').status_code,422)
        self.assertEqual(self.client.get('/api/events?from_date=2020-01-01&to_date=2026-11-01').status_code,422)
        self.assertEqual(self.client.get('/api/events?from_date=invalid').status_code,422)
        self.owner();self.client.delete(f'/api/posts/{identifiers[1]}');self.viewer_user()
        self.assertNotIn(identifiers[1],{item['id'] for item in self.client.get(query).json()['items']})
        self.db.get(Post,uuid.UUID(identifiers[0])).author_role='lector';self.db.flush()
        self.assertNotIn(identifiers[0],{item['id'] for item in self.client.get(query).json()['items']})

    def owner(self):
        self.author.role='admin';self.db.flush()
        app.dependency_overrides[get_current_user]=lambda:self.author
    def viewer_user(self):app.dependency_overrides[get_current_user]=lambda:self.viewer
    def payload(self,event=None):
        return {'source':'event','publication_type':'event','kind':'community','title':'Stella a Chile','body':'Encuentro literario de prueba',
            'author_profile_id':str(self.profiles[self.author.id].id),'work_id':str(self.work.id),'book_ref':str(self.work.id),
            'book_title':self.work.title,'event_details':event or details()}

    def test_existing_stella_fixture_edit_keeps_same_event_and_attendees(self):
        self.post.title='Stella a Chile';self.post.publication_type='event';self.post.source='event';self.post.author_role='admin';self.post.work_id=self.work.id
        self.db.add_all(PostImage(post_id=self.post.id,content_type='image/png',data=b'original test photo') for _ in range(6));self.db.flush()
        original_id,created=self.post.id,self.post.created_at
        self.owner()
        first=self.client.put(f'/api/posts/{original_id}',json=self.payload())
        self.assertEqual(first.status_code,200,first.text)
        self.assertTrue(first.json()['can_manage'])
        self.assertEqual(first.json()['event_details']['id'],str(original_id))
        self.viewer_user()
        for _ in range(3):self.assertEqual(self.client.put(f'/api/events/{original_id}/attendance').json()['attendee_count'],1)
        social=f'/api/activities/publication/{original_id}'
        self.client.put(social+'/like');self.client.post(social+'/comments',json={'body':'Nos vemos allí'})
        self.owner()
        changed=details('2026-11-13','19:30');changed['location']='Nuevo lugar';changed['category']='book_club'
        response=self.client.put(f'/api/posts/{original_id}',json={**self.payload(changed),'title':'Stella a Chile — actualizado'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['id'],str(original_id));self.assertEqual(self.post.created_at,created)
        self.assertEqual(len(response.json()['images']),6)
        self.assertEqual((response.json()['like_count'],response.json()['comment_count'],response.json()['view_count']),(1,1,1))
        event=response.json()['event_details']
        self.assertEqual((event['start_date'],event['start_time'],event['schedule_revision']),('2026-11-13','19:30',2))
        self.assertIsNotNone(event['schedule_update'])
        self.viewer_user()
        calendar=next(row for row in self.client.get('/api/events').json()['items'] if row['id']==str(original_id))
        mural=next(row for row in self.get('/events?audience=community')['items'] if row['id']==str(original_id))
        self.assertEqual(calendar['event_details'],{**mural['event_details'],'observed_at':calendar['event_details']['observed_at']})
        self.assertTrue(calendar['event_details']['attending']);self.assertEqual(calendar['event_details']['attendee_count'],1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(PublicationEvent).where(PublicationEvent.post_id==original_id)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EventScheduleUpdate).where(EventScheduleUpdate.post_id==original_id)),1)

    def test_create_calendar_cancel_and_delete_preserve_history(self):
        self.owner()
        payload=self.payload();payload.pop('book_ref')
        result=self.client.post('/api/posts',json=payload)
        self.assertEqual(result.status_code,201,result.text)
        identifier=result.json()['id'];self.assertEqual(result.json()['event_details']['start_date'],'2026-11-12')
        self.viewer_user()
        self.client.put(f'/api/events/{identifier}/attendance')
        for _ in range(2):self.assertFalse(self.client.delete(f'/api/events/{identifier}/attendance').json()['attending'])
        self.assertIsNotNone(self.db.get(EventAttendance,(uuid.UUID(identifier),self.viewer.id)))
        self.client.put(f'/api/events/{identifier}/attendance')
        self.assertEqual(self.client.put(f'/api/posts/{identifier}',json=self.payload()).status_code,403)
        self.owner()
        self.assertEqual(self.client.delete(f'/api/posts/{identifier}').status_code,204)
        self.assertNotIn(identifier,[row['id'] for row in self.client.get('/api/events').json()['items']])
        self.assertIsNotNone(self.db.get(PublicationEvent,uuid.UUID(identifier)))
        self.assertTrue(self.db.get(EventAttendance,(uuid.UUID(identifier),self.viewer.id)).attending)
        self.assertEqual(self.client.put(f'/api/events/{identifier}/attendance').status_code,404)

    def test_timezone_validation_and_no_historical_inference(self):
        self.owner()
        payload=self.payload();payload.pop('book_ref')
        invalid=[details('2026-09-06','00:30'),details('2026-04-04','23:30'),{**details(),'timezone':'Not/AZone'},
            {**details(),'end_date':'2026-11-11','end_time':'18:00'},{**details(),'end_date':'2026-11-13'}]
        for schedule in invalid:
            response=self.client.post('/api/posts',json={**payload,'event_details':schedule})
            self.assertEqual(response.status_code,422,response.text)
        result=self.client.post('/api/posts',json=payload).json()
        self.assertEqual(result['event_details']['start_time'],'18:00')
        self.assertEqual(datetime.fromisoformat(result['event_details']['starts_at']).astimezone(timezone.utc).strftime('%H:%M'),'21:00')
        legacy={**payload,'event_details':None,'body':'Dice 12 de noviembre en texto, pero no es una fecha estructurada'}
        old=self.client.post('/api/posts',json=legacy)
        self.assertEqual(old.status_code,201,old.text);identifier=old.json()['id']
        self.assertIsNone(old.json()['event_details'])
        self.assertNotIn(identifier,[row['id'] for row in self.client.get('/api/events').json()['items']])
        self.assertEqual(self.client.put(f'/api/events/{identifier}/attendance').status_code,404)
