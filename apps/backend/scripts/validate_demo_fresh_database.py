"""Exercise the full demonstration on an owned, initially empty PostgreSQL cluster.

No application URL argument is accepted. The real .env/database are never
changed. Provider metadata and images are fetched afresh, with a private cache.
The private server is stopped in finally, and logs retained for inspection.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import uuid


BACKEND = Path(__file__).resolve().parents[1]
REPORT = BACKEND.parents[1] / 'artifacts' / 'demo-fresh-database' / 'last-result.json'


async def exercise_owned():
    import httpx
    from sqlalchemy import func, select, text
    from app.core.config import get_settings
    from app.core.database import SessionLocal, engine
    from app.main import app
    from app.modules.demo import covers
    from app.modules.demo.models import DemoMode
    from app.modules.demo.service import DemoPaused, prepare_actors, prepare_catalog
    from app.modules.demo.selection import selection_labels
    from app.modules.demo.worker import DemoAPI, generate_action, record_result, producer_lease
    from app.modules.books.models import Work
    from app.modules.library.models import Reading, ReadingEvent
    from app.modules.social.models import Post, Review
    from app.modules.users.models import User

    marker = os.environ.get('LIBRIA_FRESH_DEMO_MARKER', '')
    if not marker.startswith('demo-fresh-') or engine.url.host != '127.0.0.1' or engine.url.port == 5432:
        raise RuntimeError('Refusing to validate an unowned PostgreSQL server')
    with engine.connect() as connection:
        actual = connection.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))
        if actual != marker or not engine.url.database.startswith('demo_fresh_'):
            raise RuntimeError('Owned database marker does not match')
    covers.COVER_DIR = Path(os.environ['LIBRIA_FRESH_DEMO_CACHE'])
    if covers.COVER_DIR.exists():
        raise RuntimeError('The fresh validation must start without cached covers')
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Work)) == 0
        assert db.scalar(select(func.count()).select_from(User)) == 1
        mode = db.get(DemoMode, 1)
        assert mode.enabled is False and mode.catalog_edition_ids == []
        head = db.scalar(text('SELECT version_num FROM alembic_version'))

    print('Empty catalog confirmed; testing administrator login and switch.', flush=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fresh-demo.test') as client:
        login = await client.post('/api/auth/login', json={'email': 'demo.admin@example.com',
                                                        'password': get_settings().libria_demo_admin_password or get_settings().libria_demo_password})
        assert login.status_code == 200, login.text
        headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
        enabled = await client.patch('/api/admin/demo', json={'enabled': True, 'interval_seconds': 10}, headers=headers)
        assert enabled.status_code == 200, enabled.text
        admin_id = uuid.UUID(str(login.json()['user']['id']))
        prepare_actors()
        print('Importing the twelve approved books from providers into the empty catalog.', flush=True)
        books = await asyncio.to_thread(prepare_catalog, admin_id)
        labels, missing = selection_labels([book.edition_id for book in books])
        assert len(books) == 12 and not missing, {'prepared': labels, 'missing': missing}
        for book in books:
            result = await client.get(covers.cached_cover_url(book.edition_id))
            assert result.status_code == 200 and covers.valid_image(result.content)
        print('All twelve imported editions and their fresh cover downloads verified.', flush=True)

        with producer_lease() as first:
            assert first
            with producer_lease() as second:
                assert not second
        api = DemoAPI(client)
        for sequence in range(96):
            await generate_action(api, books, sequence)
            record_result(sequence)
            if sequence % 16 == 15:
                print(f'Fresh demonstration: {sequence + 1}/96 interleaved actions completed.', flush=True)
        for category in ('started', 'progress', 'finished', 'reviews', 'social',
                         'events', 'launches', 'announcements', 'promotions'):
            page = await api.request('camila', 'GET', '/mural/' + category)
            assert page['items'], category
        with SessionLocal() as db:
            events = list(db.scalars(select(ReadingEvent).order_by(ReadingEvent.created_at)))
            assert len({event.actor_user_id for event in events}) == 7
            assert {'start', 'progress', 'finish'}.issubset({event.kind for event in events})
            attempts = {}
            for event in events:
                attempts.setdefault(event.reading_id, []).append(event)
            for attempt in attempts.values():
                assert attempt[0].kind == 'start'
                assert [event.page for event in attempt] == sorted(event.page for event in attempt)
            distinct_books = db.scalar(select(func.count(func.distinct(Reading.work_id))).select_from(Reading))
            assert distinct_books >= 5
            users = db.scalar(select(func.count()).select_from(User))
            assert users == 9  # administrator + eight fictional personas
            post_count = db.scalar(select(func.count()).select_from(Post))
            review_count = db.scalar(select(func.count()).select_from(Review))
            assert review_count > 0

        print('Testing persisted progress with a new API client and disabling the producer.', flush=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fresh-demo.test') as restarted:
            with SessionLocal() as db:
                resume = db.get(DemoMode, 1).sequence
            assert resume == 96
            await generate_action(DemoAPI(restarted), books, resume)
            record_result(resume)
        disabled = await client.patch('/api/admin/demo', json={'enabled': False, 'interval_seconds': 10}, headers=headers)
        assert disabled.status_code == 200 and not disabled.json()['enabled']
        try:
            await generate_action(api, books, 97)
        except DemoPaused:
            pass
        else:
            raise AssertionError('Disabled demonstration accepted another action')
        with SessionLocal() as db:
            assert db.get(DemoMode, 1).sequence == 97
    engine.dispose()
    return {'status': 'passed', 'scope': 'owned_empty_postgresql_only', 'migration_head': head,
            'imported_books': len(books), 'prepared_titles': labels, 'covers_verified': 12,
            'personas': users - 1, 'interleaved_steps': 97, 'reading_events': len(events),
            'distinct_reading_books': distinct_books, 'posts_before_resume': post_count,
            'reviews_before_resume': review_count, 'switch_on_off': True, 'resume_verified': True,
            'application_database_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exercise-owned', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.exercise_owned:
        result = asyncio.run(exercise_owned())
        Path(os.environ['LIBRIA_FRESH_DEMO_RESULT']).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    binaries = Path(os.environ.get('PG_BIN', r'C:\Program Files\PostgreSQL\17\bin'))
    root = Path(tempfile.mkdtemp(prefix='libria-fresh-demo-'))
    data = root / 'data'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    def command(arguments, env=None, timeout=120):
        with (root / 'commands.log').open('a', encoding='utf-8') as log:
            result = subprocess.run(arguments, cwd=BACKEND, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout, creationflags=flags)
        if result.returncode:
            print((root / 'commands.log').read_text(encoding='utf-8', errors='replace'))
            raise RuntimeError('Fresh demonstration validation command failed; logs: ' + str(root))
    started = False
    try:
        command([str(binaries / 'initdb.exe'), '-D', str(data), '-U', 'demo_validator', '-A', 'trust', '-E', 'UTF8', '--no-locale'])
        command([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-l', str(root / 'postgres.log'),
                 '-o', f'-p {port} -h 127.0.0.1 -F', '-w', 'start'])
        started = True
        import psycopg
        from psycopg import sql
        name = 'demo_fresh_' + uuid.uuid4().hex
        marker = 'demo-fresh-' + uuid.uuid4().hex
        with psycopg.connect(f'postgresql://demo_validator@127.0.0.1:{port}/postgres', autocommit=True) as connection:
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            connection.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(name), sql.Literal(marker)))
        env = os.environ.copy()
        env.update(DATABASE_URL=f'postgresql+psycopg://demo_validator@127.0.0.1:{port}/{name}',
            APP_ENV='test', LIBRIA_DEMO_PASSWORD=uuid.uuid4().hex, JWT_SECRET=uuid.uuid4().hex * 2,
            PYTHONUTF8='1', PYTHONIOENCODING='utf-8', LIBRIA_FRESH_DEMO_MARKER=marker,
            LIBRIA_FRESH_DEMO_CACHE=str(root / 'covers'), LIBRIA_FRESH_DEMO_RESULT=str(root / 'result.json'),
            GEMINI_WORKER_ENABLED='false', ANALYTICS_SCHEDULER_ENABLED='false', PROJECTION_SCHEDULER_ENABLED='false')
        for feature in ('CANONICAL', 'DISCOVERY', 'EDITIONLESS', 'ADMIN_MERGE', 'ADMIN_PREVIEW'):
            env[f'CATALOG_{feature}_ENABLED'] = 'true'
        print('Private PostgreSQL started. Applying all migrations and the installation seed from zero.', flush=True)
        command([sys.executable, '-m', 'scripts.migrate_and_seed'], env)
        command([sys.executable, '-m', 'scripts.seed_default_admin', '--account-only'], env)
        print('Checking fresh startup, real provider imports, covers, mural, and administrator controls.', flush=True)
        command([sys.executable, '-m', 'scripts.validate_demo_fresh_database', '--exercise-owned'], env, timeout=900)
        result = json.loads((root / 'result.json').read_text(encoding='utf-8'))
        result['logs'] = str(root)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        if started:
            command([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-m', 'fast', '-w', 'stop'])
        print('Private PostgreSQL stopped. Logs: ' + str(root), flush=True)


if __name__ == '__main__':
    main()
