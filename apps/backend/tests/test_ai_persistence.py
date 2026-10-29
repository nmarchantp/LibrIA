"""Stage 2 persistence contracts; integration cases require a disposable PostgreSQL."""

import json
import os
import threading
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.analytics.persistence import (
    enqueue_reading_event_analysis,
    enqueue_recommendation_job,
    persist_reader_profile_version,
    recommendation_profile_hash,
    record_ai_usage,
    set_reader_profile_status,
)
from app.modules.analytics.providers.base import TokenUsage


def book(reading_id=None, work_id=None, **changes):
    value = {
        "reading_id": reading_id or uuid.uuid4(),
        "work_id": work_id or uuid.uuid4(),
        "status": "finished",
        "rating": Decimal("4.5"),
        "review": {"body": "Una reseña relevante."},
        "dimension_ratings": {"characters": 4},
        "internal_notes": [{"body": "Una nota privada."}],
        "theories": [{"body": "Una teoría de lectura."}],
        "metadata": {"title": "Una obra", "authors": ["Una autora"]},
    }
    value.update(changes)
    return value


class RecommendationHashTest(unittest.TestCase):
    def test_hash_uses_only_eligible_recommendation_inputs(self):
        eligible = book()
        baseline = recommendation_profile_hash([eligible])
        self.assertEqual(
            baseline,
            recommendation_profile_hash([
                {
                    **eligible,
                    "unrelated_etl_metric": 999,
                    "metadata": {**eligible["metadata"], "unrelated_catalog_field": "ignored"},
                },
                book(status="abandoned", rating=5),
                book(status="finished", rating=3.75),
            ]),
        )
        self.assertNotEqual(
            baseline,
            recommendation_profile_hash([{**eligible, "internal_notes": [{"body": "Cambió"}]}]),
        )

    def test_hash_is_stable_but_distinguishes_rereading_instances(self):
        reading_id = uuid.uuid4()
        work_id = uuid.uuid4()
        value = book(reading_id=reading_id, work_id=work_id)
        reordered = dict(reversed(list(value.items())))
        self.assertEqual(recommendation_profile_hash([value]), recommendation_profile_hash([reordered]))
        self.assertNotEqual(
            recommendation_profile_hash([value]),
            recommendation_profile_hash([book(reading_id=uuid.uuid4(), work_id=work_id)]),
        )


@unittest.skipUnless(
    os.getenv("LIBRIA_STAGE2_MIGRATION_TEST") == "1",
    "requires a disposable PostgreSQL with LIBRIA_STAGE2_MIGRATION_TEST=1",
)
class AIPersistenceMigrationTest(unittest.TestCase):
    run_counter = 0

    @classmethod
    def setUpClass(cls):
        cls.database_url = os.environ["DATABASE_URL"]
        url = make_url(cls.database_url)
        if url.host not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Stage 2 migration tests require loopback PostgreSQL")
        cls.engine = create_engine(cls.database_url)
        config = Config("alembic.ini")
        command.upgrade(config, "0048_quarter_ratings")

        cls.owner_id = uuid.uuid4()
        cls.run_id = uuid.uuid4()
        cls.legacy_job_id = uuid.uuid4()
        cls.legacy_analysis_id = uuid.uuid4()
        cls.legacy_recommendation_id = uuid.uuid4()
        cls.legacy_interpretation_id = uuid.uuid4()
        cls.legacy_content = {"historical": "se conserva"}
        with cls.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO app.usuarios(id,display_name) VALUES (:id,'Lector histórico')"),
                {"id": cls.owner_id},
            )
            connection.execute(
                text(
                    """INSERT INTO analytics.projection_runs
                       (id,owner_id,transform_version,source_hash,payload)
                       VALUES (:id,:owner,'legacy-etl','legacy-source','{}'::jsonb)"""
                ),
                {"id": cls.run_id, "owner": cls.owner_id},
            )
            connection.execute(
                text("INSERT INTO ia.jobs(id,owner_id,target) VALUES (:id,:owner,'profile')"),
                {"id": cls.legacy_job_id, "owner": cls.owner_id},
            )
            connection.execute(
                text(
                    """INSERT INTO ia.analyses
                       (id,owner_id,target,version,data_hash,content,model,prompt_version,analytics_run_id)
                       VALUES (:id,:owner,'profile',1,'legacy-hash',CAST(:content AS jsonb),
                               'qwen3:1.7b','legacy-profile-v1',:run)"""
                ),
                {
                    "id": cls.legacy_analysis_id,
                    "owner": cls.owner_id,
                    "run": cls.run_id,
                    "content": json.dumps(cls.legacy_content),
                },
            )
            connection.execute(
                text(
                    """INSERT INTO ia.evidence
                       (analysis_id,source_key,source_kind,source_id,source_hash)
                       VALUES (:analysis,'review:legacy','review',:source,'evidence-hash')"""
                ),
                {"analysis": cls.legacy_analysis_id, "source": uuid.uuid4()},
            )
            connection.execute(
                text(
                    """INSERT INTO ia.recomendaciones_ia
                       (id,owner_user_id,data_hash,model,version,content,analytics_run_id)
                       VALUES (:id,:owner,'legacy-rec-hash','qwen3:1.7b','legacy-rec-v1',
                               CAST(:content AS jsonb),:run)"""
                ),
                {
                    "id": cls.legacy_recommendation_id,
                    "owner": cls.owner_id,
                    "run": cls.run_id,
                    "content": json.dumps([{"id": "legacy-book"}]),
                },
            )
            connection.execute(
                text(
                    """INSERT INTO ia.interpretaciones_ia
                       (id,scope,subject_key,owner_user_id,data_hash,provider,model,prompt_version,content)
                       VALUES (:id,'personal',:subject,:owner,'legacy-insight-hash','ollama',
                               'qwen3:1.7b','legacy-insight-v1','{}'::jsonb)"""
                ),
                {
                    "id": cls.legacy_interpretation_id,
                    "subject": str(cls.owner_id),
                    "owner": cls.owner_id,
                },
            )
        command.upgrade(config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def create_owner_run(self):
        owner_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO app.usuarios(id,display_name) VALUES (:id,'Lector de prueba')"),
                {"id": owner_id},
            )
        return owner_id, self.create_daily_run(owner_id)

    def create_daily_run(self, owner_id):
        type(self).run_counter += 1
        run_id = uuid.uuid4()
        business_date = date(2000, 1, 1) + timedelta(days=type(self).run_counter)
        cutoff = datetime.combine(
            business_date + timedelta(days=1), datetime.min.time(), timezone.utc
        )
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO analytics.projection_runs
                       (id,owner_id,transform_version,source_hash,payload)
                       VALUES (:id,:owner,'test-etl',:hash,'{}'::jsonb)"""
                ),
                {"id": run_id, "owner": owner_id, "hash": uuid.uuid4().hex},
            )
            connection.execute(
                text(
                    """INSERT INTO analytics.ejecuciones_etl
                       (id,status,started_at,finished_at,source_cutoff_at,
                        transform_version,business_date,period_start,run_kind,phase)
                       VALUES (:id,'succeeded',:cutoff,:cutoff,:cutoff,
                               'test-nightly',:day,:start,'daily','completed')"""
                ),
                {
                    "id": run_id,
                    "cutoff": cutoff,
                    "day": business_date,
                    "start": cutoff - timedelta(days=1),
                },
            )
        return run_id

    def profile(self, owner_id, run_id, books=None):
        with Session(self.engine) as db:
            value = persist_reader_profile_version(
                db,
                owner_id=owner_id,
                etl_run_id=run_id,
                books=books or [book()],
            )
            result = dict(value)
            db.commit()
        return result

    def test_upgrade_preserves_and_labels_historical_ollama_rows(self):
        with self.engine.connect() as connection:
            analysis = connection.execute(
                text("SELECT provider,content FROM ia.analyses WHERE id=:id"),
                {"id": self.legacy_analysis_id},
            ).mappings().one()
            recommendation = connection.execute(
                text("SELECT provider,content FROM ia.recomendaciones_ia WHERE id=:id"),
                {"id": self.legacy_recommendation_id},
            ).mappings().one()
            view_provider = connection.execute(
                text("SELECT provider FROM analytics.recomendaciones_ia WHERE id=:id"),
                {"id": self.legacy_recommendation_id},
            ).scalar_one()
            evidence_count = connection.execute(
                text("SELECT count(*) FROM ia.evidence WHERE analysis_id=:id"),
                {"id": self.legacy_analysis_id},
            ).scalar_one()
        self.assertEqual((analysis["provider"], recommendation["provider"], view_provider), ("ollama",) * 3)
        self.assertEqual(analysis["content"], self.legacy_content)
        self.assertEqual(recommendation["content"], [{"id": "legacy-book"}])
        self.assertEqual(evidence_count, 1)

    def test_existing_queue_remains_compatible(self):
        with self.engine.connect() as connection:
            row = connection.execute(
                text("SELECT job_kind,provider,status,revision,attempts FROM ia.jobs WHERE id=:id"),
                {"id": self.legacy_job_id},
            ).one()
        self.assertEqual(tuple(row), ("adaptive_analysis", "ollama", "pending", 1, 0))

    def test_profile_versions_deduplicate_hash_and_separate_users(self):
        owner, first_run = self.create_owner_run()
        shared_book = book()
        first = self.profile(owner, first_run, [shared_book])
        second_run = self.create_daily_run(owner)
        same = self.profile(owner, second_run, [shared_book])
        self.assertEqual(first["id"], same["id"])

        third_run = self.create_daily_run(owner)
        changed = self.profile(owner, third_run, [{**shared_book, "review": {"body": "Cambió"}}])
        self.assertEqual((first["version"], changed["version"]), (1, 2))

        other_owner, other_run = self.create_owner_run()
        other = self.profile(other_owner, other_run, [shared_book])
        self.assertNotEqual(first["id"], other["id"])
        self.assertEqual(other["version"], 1)

    def test_profile_etl_foreign_key_is_enforced(self):
        owner, _ = self.create_owner_run()
        with self.assertRaises(IntegrityError):
            with Session(self.engine) as db:
                db.execute(
                    text(
                        """INSERT INTO ia.reader_profile_versions
                           (owner_id,etl_run_id,data_hash,version)
                           VALUES (:owner,:run,:hash,1)"""
                    ),
                    {"owner": owner, "run": uuid.uuid4(), "hash": "a" * 64},
                )
                db.commit()

    def test_recommendation_jobs_are_deduplicated(self):
        owner, run = self.create_owner_run()
        profile = self.profile(owner, run)
        with Session(self.engine) as db:
            first = dict(enqueue_recommendation_job(
                db,
                profile_version_id=profile["id"],
                provider="gemini",
                model="gemini-3.5-flash-lite",
                prompt_version="recommendations-v1",
            ))
            second = dict(enqueue_recommendation_job(
                db,
                profile_version_id=profile["id"],
                provider="gemini",
                model="gemini-3.5-flash-lite",
                prompt_version="recommendations-v1",
            ))
            db.commit()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["job_kind"], "recommendation")

    def test_simultaneous_recommendation_enqueues_create_one_job(self):
        owner, run = self.create_owner_run()
        profile = self.profile(owner, run)
        barrier = threading.Barrier(2)
        ids = []
        errors = []

        def enqueue():
            try:
                with Session(self.engine) as db:
                    barrier.wait(timeout=5)
                    row = enqueue_recommendation_job(
                        db,
                        profile_version_id=profile["id"],
                        provider="gemini",
                        model="gemini-3.5-flash-lite",
                        prompt_version="recommendations-concurrent-v1",
                    )
                    value = row["id"]
                    db.commit()
                    ids.append(value)
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        threads = [threading.Thread(target=enqueue) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 1)
        with self.engine.connect() as connection:
            count = connection.execute(
                text(
                    """SELECT count(*) FROM ia.jobs WHERE job_kind='recommendation'
                       AND profile_version_id=:profile AND prompt_version='recommendations-concurrent-v1'"""
                ),
                {"profile": profile["id"]},
            ).scalar_one()
        self.assertEqual(count, 1)

    def create_closure_event(self, owner_id, kind):
        work_id, edition_id, entry_id, reading_id, event_id = (uuid.uuid4() for _ in range(5))
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO app.obras(id,title) VALUES (:id,'Obra para cierre')"),
                {"id": work_id},
            )
            connection.execute(
                text(
                    "INSERT INTO app.ediciones(id,work_id,title,language,page_count) "
                    "VALUES (:id,:work,'Edición','es',100)"
                ),
                {"id": edition_id, "work": work_id},
            )
            connection.execute(
                text(
                    "INSERT INTO app.entradas_biblioteca(id,user_id,work_id) "
                    "VALUES (:id,:owner,:work)"
                ),
                {"id": entry_id, "owner": owner_id, "work": work_id},
            )
            connection.execute(
                text(
                    """INSERT INTO app.lecturas
                       (id,library_entry_id,work_id,edition_id,status,current_page,total_pages,
                        started_at,finished_at,abandoned_at)
                       VALUES (:id,:entry,:work,:edition,:status,:page,100,:started,:finished,:abandoned)"""
                ),
                {
                    "id": reading_id,
                    "entry": entry_id,
                    "work": work_id,
                    "edition": edition_id,
                    "status": "finished" if kind == "finish" else "abandoned",
                    "page": 100 if kind == "finish" else 40,
                    "started": now,
                    "finished": now if kind == "finish" else None,
                    "abandoned": now if kind == "abandon" else None,
                },
            )
            connection.execute(
                text(
                    """INSERT INTO app.eventos_lectura
                       (id,reading_id,actor_user_id,kind,previous_page,page,total_pages,is_public)
                       VALUES (:id,:reading,:owner,:kind,0,:page,100,false)"""
                ),
                {
                    "id": event_id,
                    "reading": reading_id,
                    "owner": owner_id,
                    "kind": kind,
                    "page": 100 if kind == "finish" else 40,
                },
            )
        return reading_id, event_id

    def test_closure_event_identity_supports_rereads_and_one_request_each(self):
        owner, _ = self.create_owner_run()
        first_reading, finish_event = self.create_closure_event(owner, "finish")
        second_reading, abandon_event = self.create_closure_event(owner, "abandon")
        with Session(self.engine) as db:
            first = dict(enqueue_reading_event_analysis(
                db,
                reading_event_id=finish_event,
                provider="gemini",
                model="gemini-3.5-flash-lite",
                prompt_version="book-analysis-v1",
            ))
            duplicate = dict(enqueue_reading_event_analysis(
                db,
                reading_event_id=finish_event,
                provider="gemini",
                model="gemini-3.5-flash-lite",
                prompt_version="book-analysis-v1",
            ))
            second = dict(enqueue_reading_event_analysis(
                db,
                reading_event_id=abandon_event,
                provider="gemini",
                model="gemini-3.5-flash-lite",
                prompt_version="book-analysis-v1",
            ))
            db.commit()
        self.assertEqual(first["id"], duplicate["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first_reading, second_reading)

    def test_usage_metrics_store_tokens_without_private_content(self):
        owner, run = self.create_owner_run()
        profile = self.profile(owner, run)
        with Session(self.engine) as db:
            job = enqueue_recommendation_job(
                db,
                profile_version_id=profile["id"],
                provider="gemini",
                model="gemini-3.5-flash-lite",
                prompt_version="recommendations-usage-v1",
            )
            metric = dict(record_ai_usage(
                db,
                job_id=job["id"],
                attempt=1,
                provider="gemini",
                model="gemini-3.5-flash-lite",
                usage=TokenUsage(
                    input_tokens=120,
                    output_tokens=35,
                    reasoning_tokens=8,
                    cached_input_tokens=20,
                    total_tokens=163,
                ),
                duration_ms=845,
                final_status="succeeded",
                estimated_cost_usd=Decimal("0.00012345"),
            ))
            duplicate = dict(record_ai_usage(
                db,
                job_id=job["id"],
                attempt=1,
                provider="gemini",
                model="gemini-3.5-flash-lite",
                usage=TokenUsage(input_tokens=999),
                duration_ms=999,
                final_status="failed",
            ))
            db.commit()
        self.assertEqual(metric["id"], duplicate["id"])
        self.assertEqual((metric["input_tokens"], metric["reasoning_tokens"], metric["cached_input_tokens"]), (120, 8, 20))
        with self.engine.connect() as connection:
            columns = {row["column_name"] for row in connection.execute(text(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema='ia' AND table_name='usage_metrics'"""
            )).mappings()}
        self.assertFalse({"api_key", "prompt", "content"} & columns)

    def test_profile_status_has_generation_timestamp(self):
        owner, run = self.create_owner_run()
        profile = self.profile(owner, run)
        with Session(self.engine) as db:
            ready = dict(set_reader_profile_status(
                db, profile_version_id=profile["id"], status="ready"
            ))
            db.commit()
        self.assertEqual(ready["status"], "ready")
        self.assertIsNotNone(ready["generated_at"])
        self.assertIsNone(ready["error_code"])


if __name__ == "__main__":
    unittest.main()
