"""Stage 3 nightly recommendation profile contracts.

Database cases are opt-in and must run only against a disposable loopback
PostgreSQL database.  They never use the developer's ``libria`` database.
"""

from __future__ import annotations

import inspect
import json
import os
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.modules.analytics.persistence import (
    recommendation_profile_hash,
    recommendation_profile_payload,
)
from app.modules.analytics.recommendation_profiles import (
    build_nightly_reader_profiles,
    estimate_profile_context,
)


def profile_book(**changes):
    value = {
        "user_id": uuid.uuid4(),
        "reading_id": uuid.uuid4(),
        "work_id": uuid.uuid4(),
        "status": "finished",
        "finished_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "finish_event_id": uuid.uuid4(),
        "rating": Decimal("4.00"),
        "review_id": uuid.uuid4(),
        "review_revision": 1,
        "review": {"body": "Reseña", "recorded_at": "2025-01-01T00:00:00+00:00"},
        "dimension_ratings": {"characters": 4},
        "notebook": {"summary": "Resumen propio"},
        "internal_notes": [{"source_id": str(uuid.uuid4()), "body": "Nota"}],
        "theories": [{"source_id": str(uuid.uuid4()), "body": "Teoría"}],
        "finish_reflection": {"reflection": "Reflexión"},
        "provenance": {"metadata_cutoff_complete": True},
        "metadata": {"title": "Obra", "authors": [{"name": "Autora"}]},
    }
    value.update(changes)
    return value


class RecommendationProfileContractTest(unittest.TestCase):
    def test_rating_4_is_included(self):
        self.assertEqual(len(recommendation_profile_payload([profile_book(rating=4)])["books"]), 1)

    def test_rating_475_is_included(self):
        self.assertEqual(len(recommendation_profile_payload([profile_book(rating=4.75)])["books"]), 1)

    def test_rating_375_is_excluded(self):
        self.assertEqual(recommendation_profile_payload([profile_book(rating=3.75)])["books"], [])

    def test_in_progress_with_high_rating_is_excluded(self):
        self.assertEqual(recommendation_profile_payload([profile_book(status="reading", rating=5)])["books"], [])

    def test_abandoned_with_high_rating_is_excluded(self):
        self.assertEqual(recommendation_profile_payload([profile_book(status="abandoned", rating=5)])["books"], [])

    def test_missing_rating_is_excluded(self):
        self.assertEqual(recommendation_profile_payload([profile_book(rating=None)])["books"], [])

    def test_review_change_changes_hash(self):
        value = profile_book()
        changed = {**value, "review": {**value["review"], "body": "Reseña editada"}}
        self.assertNotEqual(recommendation_profile_hash([value]), recommendation_profile_hash([changed]))

    def test_rating_change_changes_hash(self):
        value = profile_book()
        self.assertNotEqual(recommendation_profile_hash([value]), recommendation_profile_hash([{**value, "rating": 4.75}]))

    def test_theory_deletion_changes_hash(self):
        value = profile_book()
        self.assertNotEqual(recommendation_profile_hash([value]), recommendation_profile_hash([{**value, "theories": []}]))

    def test_context_measurement_keeps_complete_payload(self):
        payload = recommendation_profile_payload([profile_book(review={"body": "x" * 140_000})])
        size = estimate_profile_context(payload)
        self.assertGreater(size["context_bytes"], 140_000)
        self.assertTrue(size["requires_segmentation"])

    def test_builder_has_no_provider_or_enqueue_calls(self):
        source = inspect.getsource(__import__(
            "app.modules.analytics.recommendation_profiles", fromlist=["*"]
        ))
        self.assertNotIn("request_book(", source)
        self.assertNotIn("enqueue_recommendation_job(", source)
        self.assertNotIn("google.genai", source)
        self.assertNotIn("ollama", source.casefold())


@unittest.skipUnless(
    os.getenv("LIBRIA_STAGE3_MIGRATION_TEST") == "1",
    "requires a disposable PostgreSQL with LIBRIA_STAGE3_MIGRATION_TEST=1",
)
class NightlyRecommendationProfileDatabaseTest(unittest.TestCase):
    run_counter = 0

    @classmethod
    def setUpClass(cls):
        cls.database_url = os.environ["DATABASE_URL"]
        url = make_url(cls.database_url)
        if url.host not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Stage 3 tests require loopback PostgreSQL")
        if url.database == "libria":
            raise RuntimeError("Stage 3 tests refuse to use the local libria database")
        cls.engine = create_engine(cls.database_url)
        config = Config("alembic.ini")
        command.upgrade(config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def create_owner(self, label="Lectora de etapa 3"):
        owner_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO app.usuarios(id,display_name) VALUES (:id,:name)"),
                {"id": owner_id, "name": label},
            )
        return owner_id

    def create_run(self, *, status="running"):
        type(self).run_counter += 1
        run_id = uuid.uuid4()
        business_date = date(2040, 1, 1) + timedelta(days=type(self).run_counter)
        cutoff = datetime.combine(business_date + timedelta(days=1), datetime.min.time(), timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO analytics.ejecuciones_etl
                       (id,status,started_at,finished_at,source_cutoff_at,transform_version,
                        business_date,period_start,run_kind,phase)
                       VALUES (:id,:status,:start,:finished,:cutoff,'stage3-test',
                               :day,:period,'daily',:phase)"""
                ),
                {
                    "id": run_id,
                    "status": status,
                    "start": cutoff,
                    "finished": cutoff if status != "running" else None,
                    "cutoff": cutoff,
                    "day": business_date,
                    "period": cutoff - timedelta(days=1),
                    "phase": "completed" if status == "succeeded" else status,
                },
            )
        return run_id, cutoff

    def seed_reading(self, owner_id, cutoff, *, status="finished", work_id=None, rating=4, reflection=None):
        work_id = work_id or uuid.uuid4()
        author_id, edition_id, entry_id, reading_id, event_id = (uuid.uuid4() for _ in range(5))
        started = cutoff - timedelta(days=4)
        closed = cutoff - timedelta(days=2)
        with self.engine.begin() as connection:
            if not connection.execute(text("SELECT 1 FROM app.obras WHERE id=:id"), {"id": work_id}).first():
                connection.execute(
                    text("INSERT INTO app.obras(id,title,description,categories) VALUES (:id,'Obra','Descripción','[\"novela\"]'::jsonb)"),
                    {"id": work_id},
                )
                connection.execute(text("INSERT INTO app.autores(id,name) VALUES (:id,'Autora')"), {"id": author_id})
                connection.execute(
                    text("INSERT INTO app.obras_autores(work_id,author_id,position) VALUES (:work,:author,1)"),
                    {"work": work_id, "author": author_id},
                )
            connection.execute(
                text(
                    """INSERT INTO app.ediciones(id,work_id,title,language,page_count,description)
                       VALUES (:id,:work,'Edición','es',100,'Descripción de edición')"""
                ),
                {"id": edition_id, "work": work_id},
            )
            existing_entry = connection.execute(
                text("SELECT id FROM app.entradas_biblioteca WHERE user_id=:owner AND work_id=:work"),
                {"owner": owner_id, "work": work_id},
            ).scalar_one_or_none()
            if existing_entry is None:
                connection.execute(
                    text("INSERT INTO app.entradas_biblioteca(id,user_id,work_id) VALUES (:id,:owner,:work)"),
                    {"id": entry_id, "owner": owner_id, "work": work_id},
                )
            else:
                entry_id = existing_entry
            values = {
                "id": reading_id,
                "entry": entry_id,
                "work": work_id,
                "edition": edition_id,
                "status": status,
                "page": 100 if status == "finished" else 40,
                "started": started,
                "finished": closed if status == "finished" else None,
                "abandoned": closed if status == "abandoned" else None,
            }
            connection.execute(
                text(
                    """INSERT INTO app.lecturas
                       (id,library_entry_id,work_id,edition_id,status,current_page,total_pages,
                        started_at,finished_at,abandoned_at)
                       VALUES (:id,:entry,:work,:edition,:status,:page,100,:started,:finished,:abandoned)"""
                ),
                values,
            )
            if status == "finished":
                connection.execute(
                    text(
                        """INSERT INTO app.eventos_lectura
                           (id,reading_id,actor_user_id,kind,previous_page,page,total_pages,
                            is_public,reflection,created_at)
                           VALUES (:id,:reading,:owner,'finish',40,100,100,false,
                                   CAST(:reflection AS jsonb),:closed)"""
                    ),
                    {
                        "id": event_id,
                        "reading": reading_id,
                        "owner": owner_id,
                        "reflection": json.dumps(reflection) if reflection is not None else None,
                        "closed": closed,
                    },
                )
        return {"work": work_id, "reading": reading_id, "event": event_id, "rating": rating}

    def seed_evidence(
        self, run_id, owner_id, item, cutoff, *, notebook=None, note=None,
        theory=None, at=None, review_id=None
    ):
        at = at or cutoff - timedelta(days=1)
        review_id = review_id or uuid.uuid4()
        rows = [
            {
                "run": run_id,
                "owner": owner_id,
                "work": item["work"],
                "source": review_id,
                "kind": "review",
                "at": at,
                "payload": json.dumps({
                    "body": "Reseña privada",
                    "rating": item["rating"],
                    "dimension_ratings": {"characters": 4.5},
                    "status": "published",
                    "revision": 1,
                }),
            }
        ]
        for kind, value, source in (
            ("notebook", notebook, item["reading"]),
            ("note", note, uuid.uuid4()),
            ("theory", theory, uuid.uuid4()),
        ):
            if value is not None:
                payload = {"notebook": value} if kind == "notebook" else {"body": value}
                rows.append({
                    "run": run_id, "owner": owner_id, "work": item["work"],
                    "source": source, "kind": kind, "at": at,
                    "payload": json.dumps(payload),
                })
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO analytics.evidencia_lectora_personal
                       (etl_run_id,user_id,work_id,source_id,source_kind,source_at,provenance,payload)
                       VALUES (:run,:owner,:work,:source,:kind,:at,'unclassified',CAST(:payload AS jsonb))"""
                ),
                rows,
            )
        return review_id

    def build(self, run_id):
        with self.engine.begin() as connection:
            return build_nightly_reader_profiles(connection, run_id)

    def profile_payload(self, owner_id):
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT payload FROM ia.reader_profile_versions WHERE owner_id=:owner ORDER BY version DESC LIMIT 1"),
                {"owner": owner_id},
            ).scalar_one()

    def test_evidence_is_associated_with_exact_reading_and_work(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        item = self.seed_reading(owner, cutoff, reflection={"reflection": "Final"})
        self.seed_evidence(run, owner, item, cutoff, notebook={"summary": "Cuaderno"}, note="Nota", theory="Teoría")
        self.build(run)
        book = self.profile_payload(owner)["books"][0]
        self.assertEqual(book["reading_id"], str(item["reading"]))
        self.assertEqual(book["finish_event_id"], str(item["event"]))
        self.assertEqual(book["notebook"], {"summary": "Cuaderno"})
        self.assertEqual(book["internal_notes"][0]["body"], "Nota")
        self.assertEqual(book["theories"][0]["body"], "Teoría")
        self.assertEqual(book["finish_reflection"], {"reflection": "Final"})

    def test_readers_are_privately_isolated(self):
        first, second = self.create_owner("Primera"), self.create_owner("Segunda")
        run, cutoff = self.create_run()
        first_item = self.seed_reading(first, cutoff)
        second_item = self.seed_reading(second, cutoff)
        self.seed_evidence(run, first, first_item, cutoff, note="Sólo primera")
        self.seed_evidence(run, second, second_item, cutoff, note="Sólo segunda")
        self.build(run)
        first_payload, second_payload = self.profile_payload(first), self.profile_payload(second)
        self.assertIn("Sólo primera", json.dumps(first_payload, ensure_ascii=False))
        self.assertNotIn("Sólo segunda", json.dumps(first_payload, ensure_ascii=False))
        self.assertIn("Sólo segunda", json.dumps(second_payload, ensure_ascii=False))

    def test_rereads_remain_distinct_reading_instances(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        first = self.seed_reading(owner, cutoff)
        second = self.seed_reading(owner, cutoff, work_id=first["work"])
        self.seed_evidence(run, owner, first, cutoff)
        self.build(run)
        books = self.profile_payload(owner)["books"]
        self.assertEqual({book["reading_id"] for book in books}, {str(first["reading"]), str(second["reading"])})

    def test_repeating_same_etl_is_idempotent(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        item = self.seed_reading(owner, cutoff)
        self.seed_evidence(run, owner, item, cutoff)
        first, second = self.build(run), self.build(run)
        with self.engine.connect() as connection:
            profiles = connection.execute(text("SELECT count(*) FROM ia.reader_profile_versions WHERE owner_id=:owner"), {"owner": owner}).scalar_one()
            states = connection.execute(text("SELECT count(*) FROM ia.reader_profile_etl_states WHERE owner_id=:owner AND etl_run_id=:run"), {"owner": owner, "run": run}).scalar_one()
        self.assertEqual((profiles, states), (1, 1))
        self.assertEqual((first["eligible_pending"], second["eligible_pending"]), (1, 1))

    def test_failed_etl_transaction_leaves_no_profile(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        item = self.seed_reading(owner, cutoff)
        self.seed_evidence(run, owner, item, cutoff)
        connection = self.engine.connect()
        transaction = connection.begin()
        try:
            build_nightly_reader_profiles(connection, run)
            transaction.rollback()
        finally:
            connection.close()
        with self.engine.connect() as connection:
            count = connection.execute(text("SELECT count(*) FROM ia.reader_profile_versions WHERE owner_id=:owner"), {"owner": owner}).scalar_one()
        self.assertEqual(count, 0)

    def test_hundred_books_create_one_profile_and_no_ai_jobs(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        first = self.seed_reading(owner, cutoff)
        for _ in range(99):
            self.seed_reading(owner, cutoff, work_id=first["work"])
        self.seed_evidence(run, owner, first, cutoff)
        with self.engine.connect() as connection:
            jobs_before = connection.execute(
                text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner"),
                {"owner": owner},
            ).scalar_one()
        self.build(run)
        with self.engine.connect() as connection:
            profile = connection.execute(text("SELECT payload FROM ia.reader_profile_versions WHERE owner_id=:owner"), {"owner": owner}).scalar_one()
            jobs_after = connection.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner"), {"owner": owner}).scalar_one()
        self.assertEqual(len(profile["books"]), 100)
        self.assertEqual(jobs_after, jobs_before)

    def test_empty_profile_state_invalidates_old_recommendations_without_job(self):
        owner = self.create_owner()
        run, _ = self.create_run()
        recommendation_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO ia.recomendaciones_ia
                       (id,owner_user_id,data_hash,model,version,content)
                       VALUES (:id,:owner,'old','qwen3:1.7b','legacy','[]'::jsonb)"""
                ),
                {"id": recommendation_id, "owner": owner},
            )
        self.build(run)
        with self.engine.connect() as connection:
            state = connection.execute(text("SELECT outcome,profile_version_id FROM ia.reader_profile_etl_states WHERE owner_id=:owner AND etl_run_id=:run"), {"owner": owner, "run": run}).one()
            current = connection.execute(text("SELECT is_current,invalidated_by_etl_run_id FROM ia.recomendaciones_ia WHERE id=:id"), {"id": recommendation_id}).one()
            jobs = connection.execute(text("SELECT count(*) FROM ia.jobs WHERE owner_id=:owner"), {"owner": owner}).scalar_one()
        self.assertEqual(tuple(state), ("empty", None))
        self.assertEqual(tuple(current), (False, run))
        self.assertEqual(jobs, 0)

    def test_pending_day_recovery_reuses_unchanged_profile(self):
        owner = self.create_owner()
        first_run, first_cutoff = self.create_run()
        item = self.seed_reading(owner, first_cutoff)
        evidence_at = first_cutoff - timedelta(days=1)
        review_id = self.seed_evidence(first_run, owner, item, first_cutoff, at=evidence_at)
        self.build(first_run)
        second_run, second_cutoff = self.create_run()
        self.seed_evidence(
            second_run, owner, item, second_cutoff,
            at=evidence_at, review_id=review_id,
        )
        self.build(second_run)
        with self.engine.connect() as connection:
            profiles = connection.execute(text("SELECT count(*) FROM ia.reader_profile_versions WHERE owner_id=:owner"), {"owner": owner}).scalar_one()
            outcome = connection.execute(text("SELECT outcome FROM ia.reader_profile_etl_states WHERE owner_id=:owner AND etl_run_id=:run"), {"owner": owner, "run": second_run}).scalar_one()
        self.assertEqual((profiles, outcome), (1, "unchanged"))

    def test_post_cutoff_evidence_is_excluded(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        item = self.seed_reading(owner, cutoff)
        self.seed_evidence(run, owner, item, cutoff, note="Información futura", at=cutoff + timedelta(hours=1))
        self.build(run)
        with self.engine.connect() as connection:
            outcome = connection.execute(text("SELECT outcome FROM ia.reader_profile_etl_states WHERE owner_id=:owner AND etl_run_id=:run"), {"owner": owner, "run": run}).scalar_one()
        self.assertEqual(outcome, "empty")

    def test_schema_links_profile_to_nightly_etl_not_projection(self):
        owner = self.create_owner()
        run, cutoff = self.create_run()
        item = self.seed_reading(owner, cutoff)
        self.seed_evidence(run, owner, item, cutoff)
        self.build(run)
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT etl_run_id,projection_run_id,payload->>'hash_version' FROM ia.reader_profile_versions WHERE owner_id=:owner"), {"owner": owner}).one()
        self.assertEqual(tuple(row), (run, None, "recommendation-profile-v1"))


if __name__ == "__main__":
    unittest.main()
