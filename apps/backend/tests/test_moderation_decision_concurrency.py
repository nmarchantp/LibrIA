"""Concurrent committed decisions in an isolated schema, never real content tables."""
import re
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import HTTPException
from sqlalchemy import text,select,func
from sqlalchemy.orm import Session
from app.main import app  # register all model dependencies
from app.core.config import get_settings
from app.core.database import engine
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission
from app.modules.social.models import Post
from app.modules.social.moderation_models import ModerationAudit,ContentReport
from app.modules.social.moderation_service import prepare_edit
from app.modules.social.moderation_decisions import decide,report_content


class ModerationDecisionConcurrencyTest(unittest.TestCase):
    def setUp(self):
        if get_settings().app_env not in {'development','test'}:self.skipTest('Requires local test database')
        self.schema='moderation_test_'+uuid.uuid4().hex
        self.addCleanup(self.cleanup_schema)
        tables=['usuarios','permisos_cuenta','publicaciones','resenas','comentarios_publicacion',
                'revisiones_moderacion','auditoria_moderacion','adjuntos_moderacion','solicitudes_moderacion',
                'reportes_contenido','imagenes_publicacion','portadas_publicacion','eventos_publicacion']
        # Resolve physical table names through metadata rather than guessing them.
        from app.modules.social.models import PostImage,PostBookCover,PublicationEvent
        tables=tables[:10]+['notificaciones_moderacion',PostImage.__tablename__,PostBookCover.__tablename__,PublicationEvent.__tablename__]
        with engine.begin() as db:
            db.execute(text(f'CREATE SCHEMA {self.schema}'))
            for table in tables:
                db.execute(text(f'CREATE TABLE {self.schema}.{table} (LIKE app.{table} INCLUDING ALL)'))
            for table,function,events in [
                ('auditoria_moderacion','protect_moderation_audit','UPDATE OR DELETE'),
                ('revisiones_moderacion','protect_moderation_proposal','UPDATE'),
                ('revisiones_moderacion','protect_moderation_resolution','UPDATE'),
                ('reportes_contenido','protect_moderation_resolution','UPDATE OR DELETE')]:
                db.execute(text(f'CREATE TRIGGER {function} BEFORE {events} ON {self.schema}.{table} FOR EACH ROW EXECUTE FUNCTION app.{function}()'))
        self.bind=engine.execution_options(schema_translate_map={'app':self.schema})
        with Session(self.bind) as db,db.begin():
            author=User(display_name='Isolated author',role='autor')
            admins=[User(display_name='Isolated admin') for _ in range(2)]
            db.add_all([author,*admins]);db.flush()
            for admin in admins:db.add(AccountPermission(user_id=admin.id,permission='admin'))
            post=Post(user_id=author.id,author_role='autor',source='community',publication_type='free',kind='community',body='Original')
            db.add(post);db.flush()
            self.author_id,self.admin_ids,self.post_id=author.id,[a.id for a in admins],post.id
            revision=prepare_edit(db,author,'publication',post.id,{'publication_type':'free','source':'community','body':'Te voy a matar'},request_key=uuid.uuid4(),expected_version=1)
            self.revision_id=revision.id

    def cleanup_schema(self):
        # This path can only remove the exact fresh test namespace, never app/public.
        if not re.fullmatch(r'moderation_test_[0-9a-f]{32}',self.schema):raise RuntimeError('Invalid test schema')
        with engine.begin() as db:db.execute(text(f'DROP SCHEMA IF EXISTS {self.schema} CASCADE'))

    def race(self,actions):
        barrier=Barrier(len(actions))
        def work(pair):
            user_id,action=pair
            with Session(self.bind) as db:
                admin=db.get(User,user_id)
                barrier.wait(timeout=10)
                try:
                    result=decide(db,admin,self.revision_id,action,'Revisión simultánea',1)
                    db.commit();return 200,result
                except HTTPException as error:
                    db.rollback();return error.status_code,None
        with ThreadPoolExecutor(max_workers=len(actions)) as pool:return list(pool.map(work,zip(self.admin_ids,actions)))

    def test_contradictory_decisions_have_only_one_winner(self):
        results=self.race(['approved','rejected'])
        self.assertEqual(sorted(code for code,_ in results),[200,409])
        with Session(self.bind) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ModerationAudit).where(ModerationAudit.action.in_(['approved','rejected']))),1)
            post=db.get(Post,self.post_id)
            self.assertEqual(post.body,'Te voy a matar' if next(r['status'] for code,r in results if code==200)=='approved' else 'Original')

    def test_same_decision_retries_are_idempotent(self):
        results=self.race(['approved','approved'])
        self.assertTrue(all(code==200 for code,_ in results),results)
        self.assertEqual(results[0][1],results[1][1])
        with Session(self.bind) as db:
            self.assertEqual(db.get(Post,self.post_id).moderation_version,2)
            self.assertEqual(db.scalar(select(func.count()).select_from(ModerationAudit).where(ModerationAudit.action=='approved')),1)

    def test_concurrent_reports_are_unique(self):
        barrier=Barrier(4)
        def work(_):
            with Session(self.bind) as db:
                user=db.get(User,self.author_id);barrier.wait(timeout=10)
                result=report_content(db,user,'publication',self.post_id,'spam','Revisar')
                db.commit();return result
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(work,range(4)))
        self.assertEqual(len({r['id'] for r in results}),1)
        with Session(self.bind) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ContentReport)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(ModerationAudit).where(ModerationAudit.action=='reported')),1)
