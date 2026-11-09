import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy import select, func
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry, Reading
from app.modules.library.challenge_models import ReadingChallenge
from app.modules.library.challenge_router import current_year, finished_books
from tests import test_mural_feed as fixtures


class ReadingChallengeTest(unittest.TestCase):
    setUp = fixtures.MuralFeedTest.setUp
    tearDown = fixtures.MuralFeedTest.tearDown
    make_reading = fixtures.MuralFeedTest.make_reading
    make_event = fixtures.MuralFeedTest.make_event
    path = '/api/me/reading-challenge'

    def finished(self, year=None, work=None):
        work = work or Work(title='Challenge work')
        self.db.add(work); self.db.flush()
        entry = self.db.scalar(select(LibraryEntry).where(LibraryEntry.user_id==self.viewer.id, LibraryEntry.work_id==work.id))
        if not entry:
            entry=LibraryEntry(user_id=self.viewer.id, work_id=work.id); self.db.add(entry); self.db.flush()
        end=datetime(year or current_year(),6,1,12,tzinfo=timezone.utc)
        reading=Reading(library_entry_id=entry.id,work_id=work.id,status='finished',current_page=100,total_pages=100,
            started_at=end-timedelta(days=3),finished_at=end)
        self.db.add(reading);self.db.flush()
        return reading

    def test_empty_no_automatic_goal(self):
        data=self.client.get(self.path).json()
        self.assertIsNone(data['target']);self.assertEqual(data['year'],current_year())
        self.assertFalse(data['completed'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ReadingChallenge)),0)

    def test_create_edit_persist_and_one_row(self):
        for target in [12,20,5]:
            response=self.client.put(self.path,json={'target':target})
            self.assertEqual(response.status_code,200,response.text)
        self.db.expire_all()
        self.assertEqual(self.client.get(self.path).json()['target'],5)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ReadingChallenge).where(ReadingChallenge.user_id==self.viewer.id)),1)
        self.as_author();self.assertIsNone(self.client.get(self.path).json()['target'])
        self.client.put(self.path,json={'target':30})
        app.dependency_overrides[get_current_user]=lambda:self.viewer
        self.assertEqual(self.client.get(self.path).json()['target'],5)

    def as_author(self):app.dependency_overrides[get_current_user]=lambda:self.author

    def test_strict_limits_and_owner_payload(self):
        for target in [0,-1,1001,1.5,True,'12',None]:
            self.assertEqual(self.client.put(self.path,json={'target':target}).status_code,422)
        self.assertEqual(self.client.put(self.path,json={'target':12,'user_id':str(self.author.id)}).status_code,422)
        for target in [1,1000]:self.assertEqual(self.client.put(self.path,json={'target':target}).status_code,200)

    def test_year_states_duplicates_and_corrections(self):
        current=self.finished();self.finished(current_year()-1);self.finished(work=self.db.get(Work,current.work_id))
        data=self.client.put(self.path,json={'target':12}).json()
        self.assertEqual(data['finished_books'],1);self.assertEqual(data['percentage'],8);self.assertEqual(data['remaining'],11)
        latest=self.db.scalar(select(Reading).where(Reading.library_entry_id==current.library_entry_id).order_by(Reading.created_at.desc(),Reading.id.desc()))
        latest.status='reading';latest.finished_at=None;self.db.flush()
        self.assertEqual(self.client.get(self.path).json()['finished_books'],0,'A previous finished attempt cannot override the current state')
        latest.status='abandoned';latest.abandoned_at=datetime.now(timezone.utc);self.db.flush()
        self.assertEqual(self.client.get(self.path).json()['finished_books'],0)

    def test_exact_exceeded_and_increasing_goal(self):
        for _ in range(3):self.finished()
        data=self.client.put(self.path,json={'target':3}).json()
        self.assertTrue(data['completed']);self.assertFalse(data['exceeded']);self.assertEqual(data['percentage'],100)
        data=self.client.put(self.path,json={'target':2}).json()
        self.assertTrue(data['exceeded']);self.assertEqual(data['finished_books'],3);self.assertEqual(data['remaining'],0)
        data=self.client.put(self.path,json={'target':5}).json()
        self.assertFalse(data['completed']);self.assertEqual(data['finished_books'],3);self.assertEqual(data['percentage'],60)

    def test_archived_and_foreign_library_excluded(self):
        item=self.finished();entry=self.db.get(LibraryEntry,item.library_entry_id);entry.archived_at=datetime.now(timezone.utc);self.db.flush()
        self.assertEqual(self.client.get(self.path).json()['finished_books'],0)
        self.as_author();self.assertEqual(self.client.get(self.path).json()['finished_books'],0)

    def test_canonical_aliases_count_once(self):
        first,second=self.finished(),self.finished()
        with patch('app.modules.books.canonical.enabled',return_value=True),patch('app.modules.books.canonical.identity_snapshot',return_value=SimpleNamespace(root=lambda _:first.work_id)):
            self.assertEqual(finished_books(self.db,self.viewer.id,current_year()),1)
        self.assertNotEqual(first.work_id,second.work_id)

    def test_local_year_boundary_and_history_retained(self):
        year=current_year();reading=self.finished(year)
        reading.finished_at=datetime(year,1,1,1,tzinfo=timezone.utc);reading.started_at=reading.finished_at-timedelta(days=1);self.db.flush()
        self.assertEqual(self.client.get(self.path).json()['finished_books'],0,'January 1 UTC is still December in Santiago')
        self.assertEqual(self.client.get(f'{self.path}?year={year-1}').json()['finished_books'],1)
        self.db.add(ReadingChallenge(user_id=self.viewer.id,year=year-1,target=5));self.db.flush()
        self.client.put(self.path,json={'target':12})
        self.assertEqual(self.client.get(f'{self.path}?year={year-1}').json()['target'],5)

    def test_library_integrity_and_percentage_rounding(self):
        rows=[self.finished() for _ in range(8)]
        before=[(row.id,row.status,row.finished_at,row.work_id) for row in rows]
        data=self.client.put(self.path,json={'target':12}).json()
        self.assertEqual(data['percentage'],67)
        self.db.expire_all()
        self.assertEqual(before,[(row.id,row.status,row.finished_at,row.work_id) for row in rows])

    def test_authentication_required(self):
        del app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.get(self.path).status_code,401)
        self.assertEqual(self.client.put(self.path,json={'target':12}).status_code,401)


class ConcurrentChallengeTest(unittest.TestCase):
    def test_simultaneous_saves_keep_one_target(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from fastapi import Response
        from sqlalchemy import delete
        from app.core.config import get_settings
        from app.core.database import SessionLocal
        from app.modules.users.models import User
        from app.modules.library.challenge_router import save_challenge, ChallengeInput
        if get_settings().app_env not in {'development','test'}:
            self.skipTest('Isolated committed concurrency fixtures require development/test')
        with SessionLocal.begin() as db:
            user=User(display_name='Isolated annual challenge fixture');db.add(user);db.flush();identifier=user.id
        barrier=Barrier(4)
        def save(target):
            with SessionLocal() as db:
                user=db.get(User,identifier);barrier.wait(timeout=10)
                return save_challenge(ChallengeInput(target=target),db,user,Response())
        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                results=list(executor.map(save,[5,12,20,30]))
            self.assertTrue(all(item['target'] in [5,12,20,30] for item in results))
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(ReadingChallenge).where(ReadingChallenge.user_id==identifier)),1)
        finally:
            with SessionLocal.begin() as db:
                db.execute(delete(ReadingChallenge).where(ReadingChallenge.user_id==identifier))
                db.execute(delete(User).where(User.id==identifier))

