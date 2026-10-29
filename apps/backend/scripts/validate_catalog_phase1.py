"""Own disposable Docker PostgreSQL only; never accepts a database URL.

Run from apps/backend with the local virtualenv. All catalog writes are synthetic.
The owned container has tmpfs storage, no host mount, a random loopback port,
and is stopped in finally. No existing database/container is touched.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

import psycopg
from psycopg import sql
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "0054_gemini_ledger_dna"
HEAD = "0056_catalog_nullable_edition"
NEW_TABLES = ("operaciones_catalogo", "referencias_obras", "incorporaciones_catalogo",
              "redirecciones_obras", "efectos_operacion_catalogo")
REGRESSIONS = ("tests.test_catalog_mirror", "tests.test_open_library", "tests.test_book_community",
               "tests.test_reviews", "tests.test_bibliographic_identity")


def snapshot(conn, tables=None):
    if tables is None:
        tables = conn.execute("""SELECT table_schema,table_name FROM information_schema.tables
          WHERE table_type='BASE TABLE' AND table_schema IN ('app','analytics','ia','ai')
          ORDER BY table_schema,table_name""").fetchall()
    data = {}
    for schema, table in tables:
        rows = conn.execute(sql.SQL("SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY to_jsonb(t)::text")
                            .format(sql.Identifier(schema), sql.Identifier(table))).fetchall()
        data[schema + "." + table] = [r[0] for r in rows]
    return data


def seed(conn):
    ids = {key: str(uuid.uuid4()) for key in ("user", "profile", "work", "other", "author", "edition", "other_edition", "entry", "reading", "event", "review", "etl")}
    conn.execute("INSERT INTO app.usuarios(id,display_name,role) VALUES(%s,'Phase1 Synthetic','lector')", (ids["user"],))
    conn.execute("INSERT INTO app.perfiles(id,kind,owner_user_id,display_name) VALUES(%s,'personal',%s,'Phase1 Synthetic')", (ids["profile"], ids["user"]))
    for work in ("work", "other"):
        conn.execute("INSERT INTO app.obras(id,title) VALUES(%s,'Same synthetic title')", (ids[work],))
    conn.execute("INSERT INTO app.autores(id,name) VALUES(%s,'Synthetic Author')", (ids["author"],))
    for work in ("work", "other"):
        conn.execute("INSERT INTO app.obras_autores(work_id,author_id,position) VALUES(%s,%s,1)", (ids[work], ids["author"]))
    for edition, work in (("edition", "work"), ("other_edition", "other")):
        conn.execute("INSERT INTO app.ediciones(id,work_id,title,language,page_count) VALUES(%s,%s,'Same synthetic title','es',100)", (ids[edition], ids[work]))
        for provider in ("google-books", "libria-feed"):
            conn.execute("INSERT INTO app.fuentes_catalogo(id,edition_id,provider,external_id,fetched_at,payload) VALUES(%s,%s,%s,%s,now(),%s::jsonb)",
                         (uuid.uuid4(), ids[edition], provider, 'phase1-' + edition,
                          json.dumps({"volumeInfo": {"title": "Same synthetic title", "authors": ["Synthetic Author"]}})))
    conn.execute("INSERT INTO app.entradas_biblioteca(id,user_id,work_id) VALUES(%s,%s,%s)", (ids["entry"], ids["user"], ids["work"]))
    conn.execute("INSERT INTO app.lecturas(id,library_entry_id,work_id,edition_id,status,total_pages,started_at) VALUES(%s,%s,%s,%s,'reading',100,now())",
                 (ids["reading"], ids["entry"], ids["work"], ids["edition"]))
    conn.execute("INSERT INTO app.eventos_lectura(id,reading_id,actor_user_id,kind,previous_page,page,total_pages,is_public) VALUES(%s,%s,%s,'start',0,0,100,true)", (ids["event"], ids["reading"], ids["user"]))
    conn.execute("INSERT INTO app.resenas(id,author_profile_id,created_by_user_id,work_id,edition_id,body,rating,status,published_at) VALUES(%s,%s,%s,%s,%s,'Synthetic review',4.25,'published',now())",
                 (ids["review"], ids["profile"], ids["user"], ids["work"], ids["edition"]))
    conn.execute("INSERT INTO app.revisiones_resena(review_id,revision_number,recorded_by_user_id,body,rating,is_spoiler,status,edition_id) VALUES(%s,1,%s,'Synthetic review',4.25,false,'published',%s)",
                 (ids["review"], ids["user"], ids["edition"]))
    conn.execute("INSERT INTO analytics.ejecuciones_etl(id,status,started_at,finished_at,source_cutoff_at,transform_version) VALUES(%s,'succeeded',now(),now(),now(),'phase1-fixture')", (ids["etl"],))
    conn.execute("INSERT INTO analytics.catalogo_obras(etl_run_id,work_id,title) VALUES(%s,%s,'Synthetic')", (ids["etl"], ids["work"]))
    conn.execute("INSERT INTO analytics.hechos_lectura(etl_run_id,source_id,user_id,work_id,edition_id,event_kind,occurred_at,previous_page,page,total_pages,provenance) VALUES(%s,%s,%s,%s,%s,'start',now(),0,0,100,'operational')",
                 (ids["etl"], ids["event"], ids["user"], ids["work"], ids["edition"]))
    return ids


def main(*, extra_test_modules=(), phase="phase1", target_head=HEAD):
    os.chdir(ROOT)
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = list(script.walk_revisions(head=target_head))
    if script.get_heads() != ["0060_admin_merges"] or len(revisions) != int(target_head[:4]) or script.get_bases() != ["0001_auth_users"]:
        raise RuntimeError("Review Alembic graph before running this phase-specific validator")
    historical = list(script.walk_revisions(base="base", head=BASELINE))
    marker = "catalog-phase1-" + uuid.uuid4().hex
    container = "libria-" + marker
    database = "catalog_phase1_disposable"
    password = secrets.token_hex(24)
    result = dict(scope="owned_disposable_postgres_only", validation_phase=phase, baseline=BASELINE, head=target_head,
                  revision_count=len(revisions), historical_migrations=[dict(revision=r.revision,
                    file=Path(r.path).name, sha256=hashlib.sha256(Path(r.path).read_bytes()).hexdigest()) for r in reversed(historical)],
                  new_migrations=[dict(revision=r.revision, file=Path(r.path).name,
                    sha256=hashlib.sha256(Path(r.path).read_bytes()).hexdigest())
                    for r in reversed(revisions) if r.revision not in {h.revision for h in historical}],
                  checks={}, success=False, container_removed=False)
    started = False

    def run(args, env=None):
        completed = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
        output = (completed.stdout + completed.stderr).replace(password, "[redacted]")
        if completed.returncode:
            raise RuntimeError(output[-18000:])
        return output.strip()

    try:
        run(["docker", "run", "--detach", "--rm", "--pull=never", "--name", container,
             "--label", "libria.catalog.phase1=" + marker,
             "--tmpfs", "/var/lib/postgresql/data:rw,size=268435456",
             "--publish", "127.0.0.1::5432", "--env", "POSTGRES_DB=" + database,
             "--env", "POSTGRES_USER=catalog_phase1", "--env", "POSTGRES_PASSWORD=" + password,
             "postgres:17-alpine"])
        started = True
        info = json.loads(run(["docker", "inspect", container]))[0]
        if any(m["Type"] != "tmpfs" for m in info["Mounts"]):
            raise RuntimeError("Disposable container unexpectedly has persistent mounts")
        result["isolation"] = dict(image_id=info["Image"], storage="tmpfs", persistent_mounts=False,
                                   database=database, loopback_only=True, workers_started=False)
        binding = info["NetworkSettings"]["Ports"]["5432/tcp"][0]
        if binding["HostIp"] != "127.0.0.1":
            raise RuntimeError("Disposable port must be loopback-only")
        url = f"postgresql://catalog_phase1:{password}@127.0.0.1:{binding['HostPort']}/{database}"
        env = os.environ.copy()
        env.update(DATABASE_URL=url.replace("postgresql://", "postgresql+psycopg://", 1), APP_ENV="test",
                   GEMINI_MODEL="gemini-3.5-flash-lite", AI_PRICING_MODEL="gemini-3.5-flash-lite",
                   CATALOG_DISCOVERY_ENABLED="false", CATALOG_ADMIN_PREVIEW_ENABLED="false",
                   CATALOG_CANONICAL_ENABLED="false", CATALOG_EDITIONLESS_ENABLED="false", CATALOG_ADMIN_MERGE_ENABLED="false",
                   ANALYTICS_SCHEDULER_ENABLED="false", PROJECTION_SCHEDULER_ENABLED="false", GEMINI_WORKER_ENABLED="false",
                   CATALOG_PHASE1_TEST_URL=url, CATALOG_PHASE1_DISPOSABLE_MARKER=marker)
        env.update(CATALOG_TEST_HEAD=target_head, CATALOG_TEST_PHASE=phase, CATALOG_DISCOVERY_ENABLED="false")
        if phase in {"phase4", "phase5", "phase6", "phase7"}:
            env["LIBRIA_STAGE3_MIGRATION_TEST"] = "1"
        deadline = time.monotonic() + 45
        while True:
            try:
                with psycopg.connect(url, connect_timeout=2, autocommit=True) as conn:
                    conn.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(database), sql.Literal(marker)))
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise RuntimeError("Disposable PostgreSQL did not become ready") from None
                time.sleep(0.5)
        run([sys.executable, "-B", "-m", "alembic", "upgrade", BASELINE], env)
        with psycopg.connect(url) as conn:
            ids = seed(conn)
        with psycopg.connect(url) as conn:
            before = snapshot(conn)
            constraints = conn.execute("""SELECT n.nspname,c.relname,p.conname,pg_get_constraintdef(p.oid)
              FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname IN ('app','analytics','ia','ai') ORDER BY 1,2,3""").fetchall()
        result["checks"]["fresh_baseline_upgrade"] = True
        result["checks"]["existing_tables_snapshotted"] = len(before)
        result["checks"]["existing_rows_snapshotted"] = sum(map(len, before.values()))
        result["baseline_regression_output"] = run([sys.executable, "-B", "-m", "unittest", *REGRESSIONS], env)
        # Exercise the exact new DDL inside a transaction and inject a failure.
        # No version stamping: the real Alembic upgrade follows after rollback checks.
        engine = create_engine(env["DATABASE_URL"])
        try:
            try:
                with engine.begin() as connection:
                    with Operations.context(MigrationContext.configure(connection)):
                        for migration in reversed(revisions):
                            if migration.revision not in {h.revision for h in historical}:
                                migration.module.upgrade()
                        connection.exec_driver_sql("SELECT 1/0")
            except DBAPIError as exc:
                if getattr(exc.orig, "sqlstate", None) != "22012":
                    raise
            else:
                raise AssertionError("Injected DDL failure unexpectedly succeeded")
        finally:
            engine.dispose()
        with psycopg.connect(url) as conn:
            if conn.execute("SELECT to_regclass('app.operaciones_catalogo')").fetchone()[0] is not None:
                raise AssertionError("DDL rollback left phase-1 tables behind")
            if conn.execute("SELECT is_nullable FROM information_schema.columns WHERE table_schema='app' AND table_name='lecturas' AND column_name='edition_id'").fetchone()[0] != "NO":
                raise AssertionError("DDL rollback did not restore NOT NULL")
            if snapshot(conn, [tuple(name.split(".")) for name in before]) != before:
                raise AssertionError("Regression tests or DDL rollback changed historical rows")
        result["checks"]["injected_ddl_failure_fully_rolled_back"] = True
        run([sys.executable, "-B", "-m", "alembic", "upgrade", target_head], env)
        with psycopg.connect(url) as conn:
            after = snapshot(conn, [tuple(name.split(".")) for name in before])
            def historical_values(data):
                result = {}
                for name, rows in data.items():
                    values = [json.loads(row) for row in rows]
                    if name in {"analytics.projection_runs", "analytics.ejecuciones_etl", "ia.reader_profile_versions", "ia.analyses"}:
                        for value in values:
                            value.pop("identity_version", None)
                    result[name] = sorted(json.dumps(value, sort_keys=True) for value in values)
                return result
            if historical_values(before) != historical_values(after):
                raise AssertionError("Historical rows changed during phase-1 migration")
            if int(target_head[:4]) >= 58:
                for table in ("analytics.projection_runs", "analytics.ejecuciones_etl", "ia.reader_profile_versions", "ia.analyses"):
                    if conn.execute(sql.SQL("SELECT count(*) FROM {} WHERE identity_version IS NOT NULL").format(sql.Identifier(*table.split('.')))).fetchone()[0]:
                        raise AssertionError("Migration populated identity provenance on historical rows")
                result['checks']['new_identity_columns_null_on_historical_rows'] = True
            after_constraints = conn.execute("""SELECT n.nspname,c.relname,p.conname,pg_get_constraintdef(p.oid)
              FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname IN ('app','analytics','ia','ai') ORDER BY 1,2,3""").fetchall()
            relaxed = {("app", "lecturas", "ck_lecturas_started"), ("app", "lecturas", "ck_lecturas_finished")} if int(target_head[:4]) >= 57 else set()
            if not {row for row in constraints if row[:3] not in relaxed}.issubset(set(after_constraints)):
                raise AssertionError("A historical constraint changed")
            for table in NEW_TABLES:
                if conn.execute(sql.SQL("SELECT count(*) FROM app.{}").format(sql.Identifier(table))).fetchone()[0]:
                    raise AssertionError("Migration unexpectedly populated " + table)
        result["checks"].update(historical_rows_unchanged=True, historical_constraints_preserved_except_declared_relaxations=True,
                                relaxed_constraints=sorted(name[2] for name in relaxed), new_tables_empty=True)
        env["CATALOG_PHASE1_FIXTURE"] = json.dumps(ids)
        result["test_output"] = run([sys.executable, "-B", "-m", "unittest", "tests.test_catalog_phase0", "tests.test_catalog_phase1", *REGRESSIONS, *extra_test_modules, "-v"], env)
        with psycopg.connect(url) as conn:
            before_repeat = snapshot(conn)
        run([sys.executable, "-B", "-m", "alembic", "upgrade", target_head], env)
        with psycopg.connect(url) as conn:
            if before_repeat != snapshot(conn):
                raise AssertionError("Repeat upgrade changed data")
            result["postgres_version"] = conn.execute("SELECT version()").fetchone()[0]
        result["checks"]["repeat_upgrade_noop"] = True
        result["checks"]["historical_snapshot_sha256"] = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc).replace(password, "[redacted]")
    finally:
        if started:
            try:
                info = json.loads(run(["docker", "inspect", container]))[0]
                if info["Config"]["Labels"].get("libria.catalog.phase1") != marker:
                    raise RuntimeError("Refusing cleanup of a container not owned by this run")
                run(["docker", "stop", "--time", "5", container])
                if run(["docker", "ps", "--all", "--filter", "label=libria.catalog.phase1=" + marker,
                        "--format", "{{.ID}}"]):
                    raise RuntimeError("Owned disposable container still exists after stop")
                result["container_removed"] = True  # --rm, all PGDATA was tmpfs.
            except Exception as exc:
                result["cleanup_error"] = str(exc)
                result["success"] = False
        report = ROOT.parents[1] / "docs" / f"catalog-canonical-{phase}-results.json"
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {key: value for key, value in result.items()
               if key not in {"historical_migrations", "test_output", "baseline_regression_output"}}
    summary["test_summaries"] = {key: re.findall(r"Ran (\d+) tests in ([0-9.]+)s", result.get(key, ""))
                                 for key in ("baseline_regression_output", "test_output")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
