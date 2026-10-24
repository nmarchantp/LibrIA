import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine, get_db
from app.main import app
from app.modules.books.models import Work, Edition
from app.modules.library.models import LibraryEntry, Reading
from app.modules.users.preference_models import Trope, FavoriteTrope
from app.modules.users.reading_statistics import genre_distribution


class GenreDistributionTest(unittest.TestCase):
    def test_assignments_and_rounding(self):
        result = genre_distribution([["Fantasía", "Romance"], ["Fantasía"]])
        self.assertEqual(result["total_assignments"], 3)
        self.assertEqual([(g["name"], g["percentage"]) for g in result["genres"]], [("Fantasía", 66.7), ("Romance", 33.3)])

    def test_deduplicate_within_each_book(self):
        result = genre_distribution([["Fantasía", " fantasía ", "FANTASÍA", "Romance"], ["Fantasía"]])
        self.assertEqual(result["total_assignments"], 3)
        self.assertEqual(result["genres"][0]["assignments"], 2)

    def test_missing_and_invalid_metadata_do_not_create_a_genre(self):
        result = genre_distribution([None, [], {}, ["", " ", 42, None, {"category": "Ficción"}, "Sin categoría"], ["Romance"]])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["classified_books"], 1)
        self.assertEqual(result["unclassified_books"], 4)
        self.assertEqual(result["genres"][0]["percentage"], 100)
        self.assertEqual(genre_distribution([])["status"], "no_finished_books")
        self.assertEqual(genre_distribution([None, []])["status"], "insufficient_metadata")

    def test_top_five_denominator_includes_all_assignments(self):
        result = genre_distribution([["A", "B", "C", "D", "E", "F"]])
        self.assertEqual(result["total_assignments"], 6)
        self.assertEqual([g["name"] for g in result["genres"]], ["A", "B", "C", "D", "E"])
        self.assertTrue(all(g["percentage"] == 16.7 for g in result["genres"]))


class ReadingGenreIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if get_settings().app_env not in {"development", "test"}:
            raise unittest.SkipTest("Only development/test databases")

    def setUp(self):
        self.connection = engine.connect()
        self.tx = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.seq = 0
        self.owner = self.register()
        self.other = self.register()
        self.headers = {"Authorization": "Bearer " + self.owner["access_token"]}
        self.path = "/api/profiles/me/reading-genres"

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close(); self.tx.rollback(); self.connection.close()

    def register(self):
        r = self.client.post("/api/auth/register", json={"display_name": "Prueba de géneros", "email": f"{uuid.uuid4()}@example.com", "password": "test-password"})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def reading(self, categories, status="finished", entry=None, user=None, archived=False):
        at = datetime.now(timezone.utc) - timedelta(days=10) + timedelta(seconds=self.seq)
        self.seq += 1
        if entry is None:
            work = Work(title="Obra de prueba", categories=categories)
            self.db.add(work); self.db.flush()
            entry = LibraryEntry(user_id=uuid.UUID((user or self.owner)["user"]["id"]), work_id=work.id,
                                 archived_at=at if archived else None)
            self.db.add(entry); self.db.flush()
        edition = self.db.scalar(select(Edition).where(Edition.work_id == entry.work_id))
        if edition is None:
            edition = Edition(work_id=entry.work_id, title="Edición de prueba", language="es", page_count=100)
            self.db.add(edition); self.db.flush()
        row = Reading(library_entry_id=entry.id, work_id=entry.work_id, edition_id=edition.id, status=status,
            current_page=100 if status == "finished" else 0, total_pages=100, created_at=at,
            started_at=None if status == "pending" else at - timedelta(days=2),
            finished_at=at - timedelta(days=1) if status == "finished" else None,
            abandoned_at=at - timedelta(days=1) if status == "abandoned" else None)
        self.db.add(row); self.db.commit()
        return entry

    def stats(self):
        r = self.client.get(self.path, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_actual_states_and_private_ownership(self):
        self.reading(["Fantasía", "Romance"])
        self.reading(["Fantasía"])
        for state in ("pending", "reading", "abandoned"):
            self.reading(["No debe contarse"], status=state)
        self.reading(["Otro usuario"], user=self.other)
        self.reading(["Archivado"], archived=True)
        result = self.stats()
        self.assertEqual(result["finished_books"], 2)
        self.assertEqual(result["total_assignments"], 3)
        self.assertEqual([x["percentage"] for x in result["genres"]], [66.7, 33.3])
        self.assertEqual(self.client.get(self.path).status_code, 401)
        # Owner IDs in query strings cannot change the authenticated account.
        self.assertEqual(self.client.get(self.path, params={"user_id": self.other["user"]["id"]}, headers=self.headers).json(), result)

    def test_latest_attempt_and_duplicate_completion(self):
        entry = self.reading(["Fantasía"])
        self.reading(None, entry=entry)
        self.assertEqual(self.stats()["total_assignments"], 1)
        self.reading(None, status="reading", entry=entry)
        self.assertEqual(self.stats()["status"], "no_finished_books")

    def test_partial_coverage_and_community_projection(self):
        self.reading(None)
        self.assertEqual(self.stats()["status"], "insufficient_metadata")
        self.reading(["Misterio"])
        self.assertEqual(self.stats()["unclassified_books"], 1)
        own = self.client.get('/api/profiles/me/literary-preferences', headers=self.headers).json()
        public = self.client.get('/api/profiles/' + own['profile_id'], headers={"Authorization": "Bearer " + self.other["access_token"]})
        self.assertEqual(set(public.json()), {"id", "display_name", "avatar_url", "biography", "genres", "tropes", "intensities", "interests", "featured_category_id"})
        self.assertEqual(self.client.get('/api/profiles/' + own['profile_id'] + '/reading-genres', headers=self.headers).status_code, 404)

    def test_catalog_grouping_and_search_metadata(self):
        catalog = self.client.get('/api/profiles/preference-catalogs', headers=self.headers).json()
        topics = catalog['tropes']
        self.assertEqual(len(topics), 51)
        self.assertEqual(len({x['id'] for x in topics}), 51)
        self.assertEqual(len({x['name'].casefold() for x in topics}), 51)
        self.assertEqual(len({x['group'] for x in topics}), 5)
        self.assertIn('familia-encontrada', {x['id'] for x in topics})
        self.assertIn('grumpy-x-sunshine', {x['id'] for x in topics})

    def test_migration_reapplication_preserves_ids_and_selections(self):
        self.db.add(FavoriteTrope(user_id=uuid.UUID(self.owner['user']['id']), trope_id='dragones'))
        self.db.commit()
        self.db.close()
        spec = importlib.util.spec_from_file_location('catalog_migration', Path('migrations/versions/0044_trope_catalog_groups.py'))
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        before = self.connection.execute(select(Trope.id, Trope.name, Trope.active).order_by(Trope.id)).all()
        picks = self.connection.execute(select(FavoriteTrope.user_id, FavoriteTrope.trope_id)).all()
        with Operations.context(MigrationContext.configure(self.connection)):
            migration.downgrade()
            migration.upgrade()
        self.assertEqual(self.connection.execute(select(Trope.id, Trope.name, Trope.active).order_by(Trope.id)).all(), before)
        self.assertEqual(self.connection.execute(select(FavoriteTrope.user_id, FavoriteTrope.trope_id)).all(), picks)


if __name__ == '__main__':
    unittest.main()
