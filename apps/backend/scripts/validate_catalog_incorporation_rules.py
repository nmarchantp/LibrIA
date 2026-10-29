"""Run catalog rules against a private native PostgreSQL cluster on Windows.

Uses a fresh temporary directory and random loopback port, never the configured
application database. Stops its server in finally; retains logs for inspection.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import uuid

import psycopg
from psycopg import sql

from scripts.validate_catalog_phase1 import seed


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    binaries = Path(r"C:\Program Files\PostgreSQL\17\bin")
    root = Path(tempfile.mkdtemp(prefix="libria-catalog-rules-"))
    data = root / "data"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    def run(args, env=None):
        with (root / "commands.log").open("a", encoding="utf-8") as output:
            result = subprocess.run(args, env=env, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=120)
        if result.returncode:
            print((root / "commands.log").read_text(encoding="utf-8", errors="replace"))
            raise RuntimeError("Isolated catalog validation command failed")

    run([str(binaries / "initdb.exe"), "-D", str(data), "-U", "catalog_phase1",
         "--auth=trust", "--encoding=UTF8", "--no-locale"])
    started = False
    try:
        run([str(binaries / "pg_ctl.exe"), "-D", str(data), "-l", str(root / "postgres.log"),
             "-o", f"-p {port} -h 127.0.0.1 -F", "-w", "start"])
        started = True
        print("Temporary PostgreSQL ready; applying migrations.", flush=True)
        url = f"postgresql://catalog_phase1@127.0.0.1:{port}/catalog_phase1_disposable"
        marker = "catalog-phase1-" + uuid.uuid4().hex
        with psycopg.connect(f"postgresql://catalog_phase1@127.0.0.1:{port}/postgres", autocommit=True) as conn:
            conn.execute("CREATE DATABASE catalog_phase1_disposable")
            conn.execute(sql.SQL("COMMENT ON DATABASE catalog_phase1_disposable IS {}").format(sql.Literal(marker)))
        env = os.environ.copy()
        env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        env.update(DATABASE_URL=url.replace("postgresql://", "postgresql+psycopg://", 1), APP_ENV="test",
                   GEMINI_MODEL="gemini-3.5-flash-lite", AI_PRICING_MODEL="gemini-3.5-flash-lite",
                   CATALOG_PHASE1_TEST_URL=url, CATALOG_PHASE1_DISPOSABLE_MARKER=marker,
                   LIBRIA_STAGE3_MIGRATION_TEST="1", CATALOG_TEST_HEAD="0060_admin_merges")
        for flag in ("DISCOVERY", "CANONICAL", "EDITIONLESS", "ADMIN_PREVIEW", "ADMIN_MERGE"):
            env["CATALOG_" + flag + "_ENABLED"] = "false"
        run([sys.executable, "-m", "alembic", "upgrade", "0054_gemini_ledger_dna"], env)
        with psycopg.connect(url) as conn:
            ids = seed(conn)
        env["CATALOG_PHASE1_FIXTURE"] = json.dumps(ids)
        run([sys.executable, "-m", "alembic", "upgrade", "head"], env)
        print("Running catalog integration tests.", flush=True)
        result = subprocess.run([sys.executable, "-m", "unittest", "tests.test_catalog_incorporation_rules", "tests.test_catalog_maintenance", "tests.test_bibliographic_identity",
                                 "tests.test_catalog_phase2", "tests.test_catalog_phase3", "tests.test_catalog_phase4"],
                                env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(result.stdout)
        print(result.stderr)
        return result.returncode
    finally:
        if started:
            run([str(binaries / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"])
        print("Isolated PostgreSQL stopped. Logs: " + str(root))


if __name__ == "__main__":
    raise SystemExit(main())
