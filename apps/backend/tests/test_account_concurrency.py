"""Two real PostgreSQL connections in a disposable schema; no development rows touched."""
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import engine
from app.modules.auth.repository import AuthRepository
from app.core.security import hash_password
from app.modules.users.account_service import (request_deletion, issue_challenge, cancel_deletion, lock_user, now)
from app.modules.users.account_lifecycle import process_expired_accounts
from app.modules.users.models import User


class AccountConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self.schema = 'test_account_' + uuid.uuid4().hex
        with engine.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            for table in ('usuarios', 'cuentas_autenticacion', 'sesiones_autenticacion', 'perfiles',
                          'capacidades_perfil', 'miembros_perfil', 'auditoria_cuentas', 'desafios_cuenta', 'fotos_cuenta'):
                c.execute(text(f'CREATE TABLE "{self.schema}".{table} (LIKE app.{table} INCLUDING ALL)'))
        self.test_engine = engine.execution_options(schema_translate_map={'app': self.schema})
        with Session(self.test_engine, expire_on_commit=False) as db:
            user = AuthRepository(db).create_account(uuid.uuid4().hex + '@example.com', hash_password('password123'), 'Prueba concurrente', 'lector')
            self.user_id = user.id
            request_deletion(db, user, 'password123')
            self.token = issue_challenge(db, user, 'recover_deletion')
            db.commit()

    def tearDown(self):
        # Identifier generated solely by this test; never interpolate user input.
        if not self.schema.startswith('test_account_') or len(self.schema) != 45:
            raise AssertionError('Unexpected disposable schema')
        with engine.begin() as c:
            c.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    def test_recovery_lock_prevents_worker_from_processing(self):
        locked = threading.Event()
        release = threading.Event()
        def recover():
            with Session(self.test_engine) as db:
                lock_user(db, self.user_id)
                locked.set()
                if not release.wait(5):
                    raise AssertionError('Worker did not finish')
                cancel_deletion(db, self.token)
                db.commit()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(recover)
            self.assertTrue(locked.wait(5))
            try:
                with Session(self.test_engine) as db:
                    # Advance the worker past the deadline while recovery still
                    # holds the row acquired inside the permitted window.
                    with patch('app.modules.users.account_lifecycle.now', return_value=now()+timedelta(days=31)):
                        self.assertEqual(process_expired_accounts(db), 0)
                    db.commit()
            finally:
                release.set()
            future.result(timeout=5)
        with Session(self.test_engine) as db:
            self.assertEqual(db.get(User, self.user_id).account_status, 'active')

    def test_finalization_wins_at_deadline_and_recovery_cannot_resurrect(self):
        with Session(self.test_engine) as db:
            user = db.get(User, self.user_id)
            user.deletion_requested_at = now() - timedelta(days=31)
            user.deletion_scheduled_at = user.deletion_requested_at + timedelta(days=30)
            db.commit()
        processed = threading.Event()
        release = threading.Event()
        def finalize():
            with Session(self.test_engine) as db:
                count = process_expired_accounts(db)
                processed.set()
                if not release.wait(5):
                    raise AssertionError('Recovery did not start')
                db.commit()
                return count
        def recover():
            with Session(self.test_engine) as db:
                try:
                    cancel_deletion(db, self.token)
                    db.commit()
                    return 'recovered'
                except HTTPException:
                    db.rollback()
                    return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            worker = pool.submit(finalize)
            self.assertTrue(processed.wait(5))
            recovery = pool.submit(recover)
            release.set()
            self.assertEqual(worker.result(timeout=5), 1)
            self.assertEqual(recovery.result(timeout=5), 'rejected')
        with Session(self.test_engine) as db:
            self.assertEqual(db.get(User, self.user_id).account_status, 'anonymized')
            self.assertEqual(process_expired_accounts(db), 0)
