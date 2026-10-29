"""Schema tests: writes require the validator's own disposable DB and marker."""
from concurrent.futures import ThreadPoolExecutor
import ast
import json
import os
from pathlib import Path
import re
from threading import Barrier
import unittest
from urllib.parse import urlparse
import uuid

import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from app.core.config import Settings
from app.modules.books.catalog_models import CatalogOperation, WorkReference, CatalogIncorporation, WorkRedirect, CatalogOperationEffect
from app.modules.library.models import Reading
from app.modules.library.schemas import ReadingState


class Phase1Compatibility(unittest.TestCase):
    def test_flags_default_disabled(self):
        settings = Settings(_env_file=None)
        self.assertFalse(settings.catalog_canonical_enabled)
        self.assertFalse(settings.catalog_editionless_enabled)
        self.assertFalse(settings.catalog_admin_merge_enabled)

    def test_flags_cannot_activate_unimplemented_features(self):
        for field in ("catalog_canonical_enabled", "catalog_editionless_enabled", "catalog_admin_merge_enabled"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Settings(_env_file=None, **{field: True})

    def test_nullable_orm_and_response_without_fabricated_metadata(self):
        self.assertTrue(Reading.__table__.c.edition_id.nullable)
        value = ReadingState(reading_id=uuid.uuid4(), work_id=uuid.uuid4(), edition_id=None,
                             book_ref="internal-reference", book_title="Synthetic", status="pending",
                             current_page=0, total_pages=None, progress_percent=0)
        self.assertIsNone(value.edition_id)
        self.assertIsNone(value.total_pages)
        self.assertIsNone(value.catalog_volume)

    def test_new_models_do_not_replace_historical_tables(self):
        names = {model.__table__.name for model in (CatalogOperation, WorkReference, CatalogIncorporation, WorkRedirect, CatalogOperationEffect)}
        self.assertEqual(len(names), 5)
        self.assertNotIn("obras", names)
        self.assertNotIn("resenas", names)

    def test_new_upgrades_contain_no_historical_data_rewrite(self):
        directory = Path(__file__).resolve().parents[1] / "migrations" / "versions"
        for filename in ("0055_catalog_canonical_foundation.py", "0056_catalog_nullable_edition.py"):
            tree = ast.parse((directory / filename).read_text(encoding="utf-8"))
            upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
            for node in ast.walk(upgrade):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertIsNone(re.search(r"\b(?:UPDATE|DELETE\s+FROM|INSERT\s+INTO)\s+(?:app\.(?:obras|ediciones|lecturas|resenas|entradas_biblioteca)|analytics\.)", node.value, re.I))


class Phase1Postgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ.get("CATALOG_PHASE1_TEST_URL")
        if not cls.url:
            raise unittest.SkipTest("Use scripts.validate_catalog_phase1; no default database is allowed")
        marker = os.environ.get("CATALOG_PHASE1_DISPOSABLE_MARKER", "")
        parsed = urlparse(cls.url)
        if (parsed.hostname != "127.0.0.1" or parsed.path != "/catalog_phase1_disposable"
                or parsed.username != "catalog_phase1" or not marker.startswith("catalog-phase1-")):
            raise RuntimeError("Refusing a non-disposable PostgreSQL target")
        with psycopg.connect(cls.url) as conn:
            actual = conn.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
            if actual != marker:
                raise RuntimeError("Disposable DB ownership marker mismatch")
        cls.ids = json.loads(os.environ["CATALOG_PHASE1_FIXTURE"])

    def setUp(self):
        self.conn = psycopg.connect(self.url)
        self.conn.execute("SET LOCAL statement_timeout='10s'")

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def operation(self, kind="library_add", source=None, target=None, reverse=None, key=None, conn=None):
        conn = conn or self.conn
        op_id = uuid.uuid4()
        conn.execute("""INSERT INTO app.operaciones_catalogo
          (id,actor_user_id,operation_type,request_key,request_hash,source_work_id,target_work_id,reverses_operation_id,reason,evidence,context)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'Synthetic validation','{}','{}')""",
                     (op_id, self.ids["user"], kind, key or str(uuid.uuid4()), "a" * 64, source, target or self.ids["work"], reverse))
        return op_id

    def reference(self, op_id, status="provisional", external=None, evidence=None, verified=False, conn=None):
        conn = conn or self.conn
        ref_id = uuid.uuid4()
        conn.execute("""INSERT INTO app.referencias_obras
          (id,work_id,provider,reference_type,external_id,verification_status,evidence,verified_by,verified_at,operation_id)
          VALUES(%s,%s,'google-books','volume',%s,%s,%s,%s,CASE WHEN %s THEN now() END,%s)""",
                     (ref_id, self.ids["work"], external or str(uuid.uuid4()), status, Jsonb(evidence or {}), "synthetic-verifier" if verified else None, verified, op_id))
        return ref_id

    def redirect(self, source=None, target=None, conn=None):
        conn = conn or self.conn
        source, target = source or self.ids["other"], target or self.ids["work"]
        operation = self.operation("merge", source=source, target=target, conn=conn)
        redirect = uuid.uuid4()
        conn.execute("INSERT INTO app.redirecciones_obras(id,source_work_id,target_work_id,operation_id) VALUES(%s,%s,%s,%s)", (redirect, source, target, operation))
        return redirect, operation

    def test_a_head_and_historical_fixture_compatible(self):
        self.assertEqual(self.conn.execute("SELECT version_num FROM alembic_version").fetchone()[0], os.environ.get("CATALOG_TEST_HEAD", "0056_catalog_nullable_edition"))
        self.assertEqual(self.conn.execute("SELECT edition_id::text FROM app.lecturas WHERE id=%s", (self.ids["reading"],)).fetchone()[0], self.ids["edition"])
        self.assertEqual(str(self.conn.execute("SELECT rating FROM app.resenas WHERE id=%s", (self.ids["review"],)).fetchone()[0]), "4.25")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM app.obras WHERE title='Same synthetic title'").fetchone()[0], 2)

    def test_b_new_tables_empty_after_migration(self):
        for model in (CatalogOperation, WorkReference, CatalogIncorporation, WorkRedirect, CatalogOperationEffect):
            self.assertEqual(self.conn.execute("SELECT count(*) FROM app." + model.__tablename__).fetchone()[0], 0)

    def test_c_orm_matches_new_table_columns_and_indexes(self):
        engine = create_engine(self.url.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            inspector = inspect(engine)
            for model in (CatalogOperation, WorkReference, CatalogIncorporation, WorkRedirect, CatalogOperationEffect):
                table = model.__table__
                columns = {c["name"]: c for c in inspector.get_columns(table.name, schema="app")}
                self.assertEqual(set(columns), set(table.c.keys()))
                for column in table.c:
                    self.assertEqual(columns[column.name]["nullable"], column.nullable, (table.name, column.name))
                actual = {i["name"]: i for i in inspector.get_indexes(table.name, schema="app")}
                for index in table.indexes:
                    self.assertIn(index.name, actual)
                    self.assertEqual(actual[index.name]["column_names"], [c.name for c in index.columns])
                    self.assertEqual(actual[index.name]["unique"], index.unique)
        finally:
            engine.dispose()

    def test_null_edition_storage_does_not_create_edition_or_pages(self):
        count = self.conn.execute("SELECT count(*) FROM app.ediciones").fetchone()[0]
        row = self.conn.execute("""INSERT INTO app.lecturas(id,library_entry_id,work_id,edition_id)
          VALUES(%s,%s,%s,NULL) RETURNING edition_id,total_pages""", (uuid.uuid4(), self.ids["entry"], self.ids["work"])).fetchone()
        self.assertEqual(row, (None, None))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM app.ediciones").fetchone()[0], count)

    def test_null_edition_analytics_storage(self):
        self.conn.execute("""INSERT INTO analytics.hechos_lectura
          (etl_run_id,source_id,user_id,work_id,edition_id,event_kind,occurred_at,previous_page,page,total_pages,provenance)
          VALUES(%s,%s,%s,%s,NULL,'start',now(),0,0,100,'operational')""",
                          (self.ids["etl"], uuid.uuid4(), self.ids["user"], self.ids["work"]))

    def test_existing_reading_composite_fk_still_rejects_other_work_edition(self):
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), self.conn.transaction():
            self.conn.execute("INSERT INTO app.lecturas(id,library_entry_id,work_id,edition_id) VALUES(%s,%s,%s,%s)",
                              (uuid.uuid4(), self.ids["entry"], self.ids["work"], self.ids["other_edition"]))

    def test_reference_binding_unique_but_conflicting_evidence_can_be_retained(self):
        operation = self.operation()
        external = str(uuid.uuid4())
        self.reference(operation, external=external)
        with self.assertRaises(psycopg.errors.UniqueViolation), self.conn.transaction():
            self.reference(operation, external=external)
        self.reference(operation, external=external, status="contradictory")

    def test_confirmed_reference_requires_evidence_and_verifier(self):
        operation = self.operation()
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.reference(operation, status="confirmed")
        self.reference(operation, status="confirmed", evidence={"source": "synthetic"}, verified=True)

    def test_reference_operation_must_target_its_work(self):
        operation = self.operation(target=self.ids["other"])
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), self.conn.transaction():
            self.reference(operation)

    def test_request_key_is_unique_per_actor_and_operation(self):
        key = str(uuid.uuid4())
        self.operation(key=key)
        with self.assertRaises(psycopg.errors.UniqueViolation), self.conn.transaction():
            self.operation(key=key)

    def test_operation_history_cannot_be_changed_or_deleted(self):
        operation = self.operation()
        for statement in ("UPDATE app.operaciones_catalogo SET reason='changed' WHERE id=%s", "DELETE FROM app.operaciones_catalogo WHERE id=%s"):
            with self.subTest(statement=statement), self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
                self.conn.execute(statement, (operation,))

    def test_effect_history_cannot_be_changed_or_deleted(self):
        operation, effect = self.operation(), uuid.uuid4()
        self.conn.execute("INSERT INTO app.efectos_operacion_catalogo(id,operation_id,ordinal,entity_table,entity_id,after_state) VALUES(%s,%s,1,'app.obras',%s,'{}')", (effect, operation, self.ids["work"]))
        for statement in ("UPDATE app.efectos_operacion_catalogo SET after_state='{}' WHERE id=%s", "DELETE FROM app.efectos_operacion_catalogo WHERE id=%s"):
            with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
                self.conn.execute(statement, (effect,))

    def test_incorporation_preserves_nullable_explicit_selection(self):
        operation = self.operation()
        row_id = uuid.uuid4()
        self.conn.execute("""INSERT INTO app.incorporaciones_catalogo
          (id,operation_id,actor_user_id,origin,work_id,library_entry_id,requested_reference)
          VALUES(%s,%s,%s,'library',%s,%s,'{}')""", (row_id, operation, self.ids["user"], self.ids["work"], self.ids["entry"]))
        self.assertEqual(self.conn.execute("SELECT edition_id,edition_selected FROM app.incorporaciones_catalogo WHERE id=%s", (row_id,)).fetchone(), (None, False))
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute("DELETE FROM app.incorporaciones_catalogo WHERE id=%s", (row_id,))

    def test_incorporation_rejects_unselected_edition(self):
        operation = self.operation()
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute("""INSERT INTO app.incorporaciones_catalogo
              (id,operation_id,actor_user_id,origin,work_id,edition_id,library_entry_id,requested_reference)
              VALUES(%s,%s,%s,'library',%s,%s,%s,'{}')""", (uuid.uuid4(), operation, self.ids["user"], self.ids["work"], self.ids["edition"], self.ids["entry"]))

    def test_incorporation_rejects_wrong_operation_origin(self):
        operation = self.operation("admin_import")
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute("""INSERT INTO app.incorporaciones_catalogo
              (id,operation_id,actor_user_id,origin,work_id,library_entry_id,requested_reference)
              VALUES(%s,%s,%s,'library',%s,%s,'{}')""", (uuid.uuid4(), operation, self.ids["user"], self.ids["work"], self.ids["entry"]))

    def test_incorporation_preserves_explicit_edition(self):
        operation = self.operation()
        value = self.conn.execute("""INSERT INTO app.incorporaciones_catalogo
          (id,operation_id,actor_user_id,origin,work_id,edition_id,edition_selected,library_entry_id,requested_reference)
          VALUES(%s,%s,%s,'library',%s,%s,true,%s,'{}') RETURNING edition_id::text,edition_selected""",
          (uuid.uuid4(), operation, self.ids["user"], self.ids["work"], self.ids["edition"], self.ids["entry"])).fetchone()
        self.assertEqual(value, (self.ids["edition"], True))

    def test_incorporation_rejects_other_library_owner(self):
        other_user = uuid.uuid4()
        self.conn.execute("INSERT INTO app.usuarios(id,display_name,role) VALUES(%s,'Other synthetic','lector')", (other_user,))
        operation = uuid.uuid4()
        self.conn.execute("""INSERT INTO app.operaciones_catalogo
          (id,actor_user_id,operation_type,request_key,request_hash,target_work_id,reason,evidence,context)
          VALUES(%s,%s,'library_add',%s,%s,%s,'Synthetic','{}','{}')""", (operation, other_user, str(uuid.uuid4()), "a"*64, self.ids["work"]))
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute("""INSERT INTO app.incorporaciones_catalogo
              (id,operation_id,actor_user_id,origin,work_id,library_entry_id,requested_reference)
              VALUES(%s,%s,%s,'library',%s,%s,'{}')""", (uuid.uuid4(), operation, other_user, self.ids["work"], self.ids["entry"]))

    def test_redirect_cycle_and_second_active_destination_rejected(self):
        self.redirect()
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.redirect(source=self.ids["work"], target=self.ids["other"])
        with self.assertRaises(psycopg.errors.UniqueViolation), self.conn.transaction():
            self.redirect()

    def test_redirect_requires_matching_audited_pair(self):
        operation = self.operation()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), self.conn.transaction():
            self.conn.execute("INSERT INTO app.redirecciones_obras(id,source_work_id,target_work_id,operation_id) VALUES(%s,%s,%s,%s)",
                              (uuid.uuid4(), self.ids["other"], self.ids["work"], operation))

    def test_redirect_reversal_preserves_original_row(self):
        redirect, operation = self.redirect()
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute("DELETE FROM app.redirecciones_obras WHERE id=%s", (redirect,))
        reversal = self.operation("reversal", reverse=operation)
        self.conn.execute("UPDATE app.redirecciones_obras SET retired_at=now(),retirement_operation_id=%s WHERE id=%s", (reversal, redirect))
        self.redirect()  # A new active decision coexists with the old historical row.
        self.assertEqual(self.conn.execute("SELECT count(*) FROM app.redirecciones_obras").fetchone()[0], 2)

    def test_redirect_cannot_be_retargeted_or_retired_without_reversal(self):
        redirect, _ = self.redirect()
        for query in ("UPDATE app.redirecciones_obras SET target_work_id=source_work_id WHERE id=%s",
                      "UPDATE app.redirecciones_obras SET retired_at=now() WHERE id=%s"):
            with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
                self.conn.execute(query, (redirect,))

    def test_schema_transaction_failure_rolls_back_operation_and_reference(self):
        operation = None
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            operation = self.operation()
            self.reference(operation, status="confirmed")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM app.operaciones_catalogo WHERE id=%s", (operation,)).fetchone()[0], 0)

    def test_z_concurrent_identical_request_has_one_winner(self):
        barrier, key = Barrier(2), str(uuid.uuid4())

        def attempt(_):
            try:
                with psycopg.connect(self.url) as conn:
                    conn.execute("SET LOCAL statement_timeout='10s'")
                    barrier.wait(timeout=5)
                    self.operation(key=key, conn=conn)
                return "committed"
            except psycopg.errors.UniqueViolation:
                return "duplicate"
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), ["committed", "duplicate"])

    def test_z_concurrent_identical_reference_has_one_binding(self):
        barrier, external = Barrier(2), str(uuid.uuid4())

        def attempt(_):
            try:
                with psycopg.connect(self.url) as conn:
                    conn.execute("SET LOCAL statement_timeout='10s'")
                    operation = self.operation(conn=conn)
                    barrier.wait(timeout=5)
                    self.reference(operation, external=external, conn=conn)
                return "committed"
            except psycopg.errors.UniqueViolation:
                return "duplicate"
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), ["committed", "duplicate"])

    def test_z_concurrent_opposite_redirects_cannot_form_cycle(self):
        barrier = Barrier(2)

        def attempt(pair):
            try:
                with psycopg.connect(self.url) as conn:
                    conn.execute("SET LOCAL statement_timeout='10s'")
                    barrier.wait(timeout=5)
                    self.redirect(source=pair[0], target=pair[1], conn=conn)
                return "committed"
            except psycopg.errors.CheckViolation:
                return "cycle_rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            pairs = [(self.ids["work"], self.ids["other"]), (self.ids["other"], self.ids["work"])]
            self.assertEqual(sorted(pool.map(attempt, pairs)), ["committed", "cycle_rejected"])


if __name__ == "__main__":
    unittest.main()
