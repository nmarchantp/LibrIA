"""Run mocked nightly integration tests in a newly created disposable database.

Run from apps/backend: .venv/Scripts/python.exe scripts/test_nightly_reading.py
Credentials stay in memory; the configured application database is never migrated.
"""
import os
import sys
import uuid
import socket
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import get_settings


def main():
    # A standalone temporary cluster needs neither CREATEDB on the application
    # role nor administrative credentials. No Windows service is installed.
    pg_bin = Path(os.getenv('PG_BIN', r'C:\Program Files\PostgreSQL\17\bin'))
    temporary = tempfile.TemporaryDirectory(prefix='libria-nightly-')
    data = Path(temporary.name) / 'data'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    def pg(command, *args):
        return subprocess.run([str(pg_bin / command), *map(str, args)], check=True,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, creationflags=flags, timeout=60)
    pg('initdb', '-D', data, '-U', 'postgres', '-A', 'trust', '--no-locale', '-E', 'UTF8')
    pg('pg_ctl', '-D', data, '-l', Path(temporary.name) / 'server.log',
       '-o', f'-p {port} -h 127.0.0.1', '-w', 'start')
    original = make_url(f'postgresql+psycopg://postgres@127.0.0.1:{port}/postgres')
    database_name = 'libria_nightly_test_' + uuid.uuid4().hex[:12]
    admin = create_engine(original.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{database_name}"'))
    os.environ['DATABASE_URL'] = original.set(database=database_name).render_as_string(hide_password=False)
    os.environ['LIBRIA_NIGHTLY_TEST'] = '1'
    os.environ['LIBRIA_STAGE5_TEST'] = '1'
    os.environ['LIBRIA_GEMINI_FIX_TEST'] = '1'
    # Legacy regression fixtures explicitly exercise the original HTTP contract.
    # Canonical feature behavior is enabled explicitly by its dedicated tests.
    for feature in ('CANONICAL', 'DISCOVERY', 'EDITIONLESS', 'ADMIN_MERGE', 'ADMIN_PREVIEW'):
        os.environ[f'CATALOG_{feature}_ENABLED'] = 'false'
    get_settings.cache_clear()
    from alembic import command
    from alembic.config import Config
    import unittest
    try:
        config = Config('alembic.ini')
        config.set_section_option('logger_alembic', 'level', 'WARN')
        command.upgrade(config, 'head')
        from app.core.database import engine
        total = 0
        for suite_name in sys.argv[1:] or ['tests.test_nightly_reading_analysis']:
            # Suites use different synthetic business dates. Keep their data
            # isolated as well as isolating the database from development.
            with engine.begin() as c:
                c.execute(text('TRUNCATE app.usuarios,app.obras,app.autores,analytics.ejecuciones_etl CASCADE'))
            suite = unittest.defaultTestLoader.loadTestsFromName(suite_name)
            print(f'Running {suite_name}', flush=True)
            result = unittest.TextTestRunner(verbosity=1, failfast=True).run(suite)
            total += result.testsRun
            if not result.wasSuccessful():
                return 1
        print(f'Isolated regression tests passed: {total}')
        return 0
    finally:
        from app.core.database import engine
        engine.dispose()
        try:
            with admin.connect() as c:
                c.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        finally:
            admin.dispose()
            pg('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')
            temporary.cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
