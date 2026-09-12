"""Pruebas de integridad contra PostgreSQL; cada caso revierte sus datos."""

import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User
from app.modules.books.models import Work, Edition
from app.modules.library.models import LibraryEntry, Reading


class DataModelTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Prueba transaccional")
        self.user.auth_account = AuthAccount(email=f"{uuid.uuid4()}@example.test", password_hash="test-only")
        self.work = Work(title="Obra de prueba")
        self.db.add_all([self.user, self.work])
        self.db.flush()
        self.edition = Edition(work_id=self.work.id, title="Edición de prueba", language="es", page_count=300)
        self.entry = LibraryEntry(user_id=self.user.id, work_id=self.work.id)
        self.db.add_all([self.edition, self.entry])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def reading(self, **changes):
        values = dict(library_entry_id=self.entry.id, work_id=self.work.id, edition_id=self.edition.id,
                      status="reading", current_page=75, total_pages=300, started_at=datetime.now(timezone.utc))
        values.update(changes)
        return Reading(**values)

    def reject(self, record):
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(record)
                self.db.flush()

    def test_auth_relationship_after_rename(self):
        self.db.expire_all()
        account = self.db.scalar(select(AuthAccount).where(AuthAccount.user_id == self.user.id))
        self.assertEqual(account.user.display_name, "Prueba transaccional")

    def test_rereadings_and_percentage(self):
        first, second = self.reading(), self.reading(current_page=1)
        self.db.add_all([first, second])
        self.db.flush()
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.progress_percentage, Decimal("25.00"))
        self.assertEqual(second.progress_percentage, Decimal("0.33"))
        self.assertIsNone(self.reading(total_pages=None).progress_percentage)

    def test_page_and_state_constraints(self):
        for changes in [dict(current_page=301), dict(current_page=-1), dict(total_pages=0),
                        dict(total_pages=None), dict(status="invalid"), dict(status="finished"),
                        dict(status="pending")]:
            with self.subTest(changes=changes):
                self.reject(self.reading(**changes))

    def test_abandonment_requires_reason(self):
        now = datetime.now(timezone.utc)
        for reason in [None, "", "   "]:
            self.reject(self.reading(status="abandoned", started_at=now, abandoned_at=now, abandonment_reason=reason))
        self.db.add(self.reading(status="abandoned", started_at=now, abandoned_at=now, abandonment_reason="No me interesó"))
        self.db.flush()

    def test_edition_must_match_library_work(self):
        other = Work(title="Otra obra")
        self.db.add(other)
        self.db.flush()
        edition = Edition(work_id=other.id, title="Otra edición", language="en", page_count=280)
        self.db.add(edition)
        self.db.flush()
        self.reject(self.reading(edition_id=edition.id))

    def test_library_unique_and_positive_page_count(self):
        self.reject(LibraryEntry(user_id=self.user.id, work_id=self.work.id))
        self.reject(Edition(work_id=self.work.id, title="Inválida", language="es", page_count=0))


if __name__ == "__main__":
    unittest.main()
