"""Full demo cycle against the real APIs inside a rolled-back transaction."""
import importlib
import unittest
import uuid
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.database import engine, get_db
from app.main import app
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.demo.models import DemoMode
from app.modules.demo.service import DemoBook, DemoPaused, PERSONAS, identifier, prepare_actors, prepare_catalog
from app.modules.demo.worker import DemoAPI, generate_action, due_state, producer_lease, shuffled_schedule
from app.modules.library.models import Reading, ReadingEvent
from app.modules.social.models import Post, PostComment, PublicationEvent, Review
from app.modules.users.identity_models import AccountPermission
from app.modules.users.models import User


class DemoModeIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.addCleanup(self.connection.close)
        self.transaction = self.connection.begin()
        self.addCleanup(self.transaction.rollback)
        self.factory = sessionmaker(bind=self.connection, join_transaction_mode='create_savepoint', expire_on_commit=False)
        if not self.connection.scalar(text("SELECT to_regclass('app.modo_demo')")):
            migration = importlib.import_module('migrations.versions.0087_demo_mode')
            with patch.object(migration, 'op', Operations(MigrationContext.configure(self.connection))):
                migration.upgrade()
        self.patches = [patch('app.modules.demo.service.SessionLocal', self.factory),
                        patch('app.modules.demo.worker.SessionLocal', self.factory),
                        patch('app.modules.demo.worker.NAMESPACE', uuid.uuid4())]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        def get_test_db():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = get_test_db
        self.addCleanup(app.dependency_overrides.clear)
        with self.factory() as db:
            mode = db.get(DemoMode, 1)
            mode.enabled = True
            mode.catalog_edition_ids = []
            mode.sequence = 0
            db.commit()
        prepare_actors()
        with self.factory() as db:
            work = Work(title='Libro de prueba demo ' + uuid.uuid4().hex)
            db.add(work)
            db.flush()
            edition = Edition(work_id=work.id, title=work.title, language='es', page_count=240)
            db.add(edition)
            db.flush()
            for provider in ('google-books', 'libria-feed'):
                db.add(CatalogSource(edition_id=edition.id, provider=provider,
                    external_id='demo-test-' + uuid.uuid4().hex, fetched_at=edition.created_at,
                    payload={'kind': 'books#volume', 'volumeInfo': {'title': work.title, 'language': 'es'}}))
            self.book = DemoBook(str(work.id), str(edition.id), work.title, 240)
            db.commit()

    async def test_cycle_populates_every_category_and_can_be_stopped(self):
        books = [self.book]
        with self.factory() as db:
            for index in range(2):
                work = Work(title=f'Another independent reading {index} ' + uuid.uuid4().hex)
                db.add(work)
                db.flush()
                edition = Edition(work_id=work.id, title=work.title, language='es', page_count=180 + index * 80)
                db.add(edition)
                db.flush()
                db.add(CatalogSource(edition_id=edition.id, provider='libria-feed', external_id='interleaved-' + uuid.uuid4().hex,
                                     fetched_at=edition.created_at))
                books.append(DemoBook(str(work.id), str(edition.id), edition.title, edition.page_count))
            db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://demo.test') as client:
            api = DemoAPI(client)
            for sequence in range(96):
                with self.subTest(sequence=sequence):
                    await generate_action(api, books, sequence)
            mural = await api.request('valentina', 'GET', '/mural?limit=3')
            for category in ('started', 'progress', 'finished', 'reviews', 'social'):
                self.assertTrue(mural['categories'][category]['items'], category)
            for category in ('events', 'launches', 'announcements', 'promotions'):
                page = await api.request('valentina', 'GET', '/mural/' + category)
                self.assertTrue(page['items'], category)
                for item in page['items']:
                    if str(item['work_id']) in {book.work_id for book in books}:
                        self.assertTrue(item['book_title'], category)
                        self.assertTrue(item['book_ref'], category)
            with self.factory() as db:
                work_ids = [uuid.UUID(book.work_id) for book in books]
                events = list(db.scalars(select(ReadingEvent).join(Reading, Reading.id == ReadingEvent.reading_id)
                    .where(Reading.work_id.in_(work_ids)).order_by(ReadingEvent.created_at, ReadingEvent.id)))
                self.assertEqual(len({event.actor_user_id for event in events}), 7)
                self.assertEqual({event.kind for event in events}, {'start', 'progress', 'finish'})
                attempts = {}
                for event in events:
                    attempts.setdefault(event.reading_id, []).append(event)
                for attempt in attempts.values():
                    self.assertEqual(attempt[0].kind, 'start')
                    self.assertEqual([e.page for e in attempt], sorted(e.page for e in attempt))
                post_books = set(db.scalars(select(Post.work_id).where(Post.work_id.in_(work_ids))))
                self.assertGreaterEqual(len(post_books), 2)
                self.assertGreater(db.scalar(select(func.count()).select_from(PostComment).where(
                    PostComment.user_id.in_([identifier('user:' + p[0]) for p in PERSONAS]))), 0)
                self.assertTrue(db.scalar(select(PublicationEvent.post_id).join(Post).where(Post.work_id.in_(work_ids))))
                self.assertTrue(db.scalar(text("SELECT count(*) FROM app.procedencia_demo WHERE dataset_version='showcase-v1'")))
                db.get(DemoMode, 1).enabled = False
                db.commit()
            with self.assertRaises(DemoPaused):
                await generate_action(api, [self.book], 96)

    async def test_event_upload_retry_and_legacy_related_book(self):
        from io import BytesIO
        from PIL import Image
        output = BytesIO()
        Image.effect_noise((200, 300), 80).convert('RGB').save(output, format='JPEG')
        files = [('images', ('cover.jpg', output.getvalue(), 'image/jpeg'))]
        sequence = next(step for step in range(32) if shuffled_schedule(step)[0] == 'event')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://demo.test') as client:
            api = DemoAPI(client)
            with patch('app.modules.demo.worker.publication_files', return_value=files):
                first = await generate_action(api, [self.book], sequence)
                second = await generate_action(api, [self.book], sequence)
            self.assertEqual(first['id'], second['id'])
            self.assertEqual(len(first['images']), 1)
            self.assertEqual(first['event_details']['category'], 'book_club')
            with self.factory() as db:
                post = db.get(Post, uuid.UUID(first['id']))
                post.book_title = None
                post.book_ref = None
                db.commit()
            page = await api.request('valentina', 'GET', '/mural/events')
            item = next(item for item in page['items'] if item['id'] == first['id'])
            self.assertEqual(item['book_title'], self.book.title)
            self.assertTrue(item['book_ref'])

    async def test_control_requires_admin_and_applies_without_restart(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://demo.test') as client:
            result = await client.get('/api/admin/demo')
            self.assertEqual(result.status_code, 401)
            api = DemoAPI(client)
            await api.request('camila', 'GET', '/readings/me')
            headers = {'Authorization': 'Bearer ' + api.tokens['camila']}
            result = await client.patch('/api/admin/demo', headers=headers, json={'enabled': False})
            self.assertEqual(result.status_code, 403)
            with self.factory() as db:
                db.add(AccountPermission(user_id=identifier('user:camila'), permission='admin'))
                db.commit()
            result = await client.patch('/api/admin/demo', headers=headers,
                                        json={'enabled': False, 'interval_seconds': 45})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertFalse(result.json()['enabled'])
            result = await client.patch('/api/admin/demo', headers=headers,
                                        json={'enabled': True, 'interval_seconds': 1})
            self.assertEqual(result.status_code, 422)

    async def test_restart_reuses_selected_editions_without_provider(self):
        with self.factory() as db:
            db.get(DemoMode, 1).catalog_edition_ids = [self.book.edition_id]
            db.commit()
        with patch('app.modules.demo.selection.valid_selection', return_value=True), \
             patch('app.modules.books.google_books.google_request') as provider:
            selected = prepare_catalog(None)
        self.assertEqual(selected, [self.book])
        provider.assert_not_called()

    async def test_disabled_mode_has_no_due_work_and_lease_is_exclusive(self):
        with self.factory() as db:
            db.get(DemoMode, 1).enabled = False
            db.commit()
        self.assertIsNone(due_state())
        # Do not contend with an administrator's live demonstration producer.
        with patch('app.modules.demo.worker.LOCK_ID', 1_000_000_000 + uuid.uuid4().int % 1_000_000_000):
            with producer_lease() as first:
                self.assertTrue(first)
                with producer_lease() as second:
                    self.assertFalse(second)
            with producer_lease() as next_producer:
                self.assertTrue(next_producer)

    async def test_catalog_uses_only_the_curated_selection(self):
        admin_id = identifier('user:camila')
        with patch('app.modules.demo.selection.valid_selection', return_value=False), \
             patch('app.modules.demo.selection.prepare_selection', return_value=([self.book.edition_id], [])) as selector:
            books = prepare_catalog(admin_id)
        self.assertEqual(books, [self.book])
        self.assertEqual(selector.call_args.args[0], admin_id)
        with self.factory() as db:
            self.assertEqual(db.get(DemoMode, 1).catalog_edition_ids, [self.book.edition_id])

    async def test_new_selection_hides_old_demo_posts_but_keeps_real_users(self):
        from app.modules.social.feed_service import query_items
        from datetime import datetime, timezone
        with self.factory() as db:
            mode = db.get(DemoMode, 1)
            mode.catalog_edition_ids = [self.book.edition_id]
            reader = User(display_name='Real reader fixture')
            db.add(reader)
            db.flush()
            old_demo = Post(user_id=identifier('user:camila'), author_role='lector', source='community',
                kind='community', publication_type='note', body='Old demo selection')
            real = Post(user_id=reader.id, author_role='lector', source='community',
                kind='community', publication_type='note', body='Real activity is retained')
            current = Post(user_id=identifier('user:camila'), author_role='lector', source='community',
                kind='community', publication_type='note', body='New demo selection', edition_id=uuid.UUID(self.book.edition_id),
                work_id=uuid.UUID(self.book.work_id))
            db.add_all([old_demo, real, current])
            db.flush()
            with patch('app.modules.demo.presentation.cover_path') as path:
                path.return_value.is_file.return_value = True
                records = query_items(db, reader, 'community', 'social', datetime.now(timezone.utc), 100)
            ids = {record.id for record in records}
            self.assertIn(current.id, ids)
            self.assertIn(real.id, ids)
            self.assertNotIn(old_demo.id, ids)
            self.assertIsNotNone(db.get(Post, old_demo.id))
