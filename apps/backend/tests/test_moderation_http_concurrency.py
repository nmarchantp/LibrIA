"""Committed clean-content fixtures exercise HTTP races and are removed by exact owner ID."""
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import delete,select,func
from app.main import app
from app.core.config import get_settings
from app.core.database import SessionLocal,get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from app.modules.users.identities import create_personal_profile
from app.modules.social.models import Post
from app.modules.social.moderation_models import ModerationRequest


class ModerationHTTPConcurrencyTest(unittest.TestCase):
    def setUp(self):
        if get_settings().app_env not in {'development','test'}:self.skipTest('Isolated fixtures require development/test')
        with SessionLocal.begin() as db:
            user=User(display_name='Isolated moderation HTTP fixture',role='autor')
            db.add(user);db.flush();self.identifier=user.id
            create_personal_profile(db,user);db.flush()
            post=Post(user_id=user.id,source='community',publication_type='free',author_role='autor',kind='community',body='Original')
            db.add(post);db.flush();self.post_id=post.id
        def current(db=Depends(get_db)):return db.get(User,self.identifier)
        app.dependency_overrides[get_current_user]=current

    def tearDown(self):
        app.dependency_overrides.clear()
        if not hasattr(self,'identifier'):return
        with SessionLocal.begin() as db:
            db.execute(delete(ModerationRequest).where(ModerationRequest.user_id==self.identifier))
            db.execute(delete(Post).where(Post.user_id==self.identifier))
            db.execute(delete(Profile).where(Profile.owner_user_id==self.identifier))
            db.execute(delete(User).where(User.id==self.identifier))

    def test_simultaneous_create_retries_have_one_post(self):
        key=str(uuid.uuid4());barrier=Barrier(4)
        body={'source':'community','publication_type':'free','kind':'community','body':'Una publicación normal'}
        def create(_):
            with TestClient(app) as client:
                barrier.wait(timeout=10)
                response=client.post('/api/posts',json=body,headers={'Idempotency-Key':key})
                return response.status_code,response.json()
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(4)))
        self.assertTrue(all(code==201 for code,_ in results),results)
        self.assertEqual(len({row['id'] for _,row in results}),1)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Post).where(Post.user_id==self.identifier)),2)

    def test_competing_edits_with_same_base_version_do_not_overwrite(self):
        barrier=Barrier(2)
        def edit(body):
            with TestClient(app) as client:
                barrier.wait(timeout=10)
                response=client.put(f'/api/posts/{self.post_id}',json={'source':'community','publication_type':'free','body':body},
                    headers={'If-Match':'1','Idempotency-Key':str(uuid.uuid4())})
                return response.status_code,response.json()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,['First edit','Second edit']))
        self.assertEqual(sorted(code for code,_ in results),[200,409],results)
        winner=next(row['body'] for code,row in results if code==200)
        with SessionLocal() as db:
            post=db.get(Post,self.post_id)
            self.assertEqual(post.body,winner)
            self.assertEqual(post.moderation_version,2)
