"""Backup and migrate only the explicitly configured local development database.

No seed, consolidation or application startup. Backup contains private data and
is written under the gitignored project backups directory, never to reports.
"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from app.core.config import get_settings

ROOT=Path(__file__).resolve().parents[3]


def domain_hashes(connection):
    tables=connection.execute(text("""SELECT table_schema,table_name FROM information_schema.tables
      WHERE table_schema IN ('app','analytics','ia','ai') AND table_type='BASE TABLE' ORDER BY 1,2""")).all()
    result={}
    for schema,table in tables:
        quoted='.'.join('"'+s.replace('"','""')+'"' for s in (schema,table))
        result[schema+'.'+table]=connection.execute(text(f"""SELECT count(*),md5(coalesce(string_agg(h,',' ORDER BY h),''))
          FROM (SELECT md5((to_jsonb(t)-'identity_version')::text) h FROM {quoted} t) s""")).one()._asdict()
    return result


def main():
    if sys.argv[1:]!=['--apply']:
        raise SystemExit('Explicit --apply required; targets only configured local libria development database')
    settings=get_settings();url=make_url(settings.database_url)
    if settings.app_env!='development' or url.host not in ('127.0.0.1','localhost') or url.database!='libria':
        raise SystemExit('Refusing a target outside the project local development database')
    config=Config('alembic.ini');graph=ScriptDirectory.from_config(config)
    if graph.get_heads()!=['0060_admin_merges'] or len(list(graph.walk_revisions()))!=60:
        raise SystemExit('Unexpected Alembic graph')
    executable=Path(r'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe')
    if not executable.is_file():
        raise SystemExit('pg_dump 17 required for the development backup')
    engine=create_engine(settings.database_url,connect_args={'connect_timeout':5})
    with engine.connect() as c:
        actual=c.execute(text('SELECT current_database(),inet_server_addr()::text,inet_server_port()')).one()
        if actual[0]!='libria' or not actual[1].startswith('127.'):
            raise SystemExit('Connected server does not match the permitted local target')
        old=c.scalar(text('SELECT version_num FROM alembic_version'))
        before=domain_hashes(c)
    backup=ROOT/'backups'/('catalog-phase7-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.dump')
    backup.parent.mkdir(exist_ok=True)
    env=os.environ.copy();env['PGPASSWORD']=url.password or ''
    subprocess.run([str(executable),'-h',url.host,'-p',str(url.port or 5432),'-U',url.username,'-Fc','-f',str(backup),url.database],env=env,check=True,capture_output=True)
    restore=executable.with_name('pg_restore.exe')
    subprocess.run([str(restore),'--list',str(backup)],check=True,capture_output=True)
    if backup.stat().st_size<100:
        raise SystemExit('Invalid backup')
    subprocess.run([sys.executable,'-m','alembic','upgrade','0060_admin_merges'],check=True)
    with engine.connect() as c:
        after=domain_hashes(c)
        unchanged=all(after.get(table)==values for table,values in before.items())
        head=c.scalar(text('SELECT version_num FROM alembic_version'))
    report=dict(database='local development libria',previous_revision=old,head=head,backup=str(backup),
        backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),backup_bytes=backup.stat().st_size,
        backup_format_validated=True,backup_restore_executed=False,historical_tables=len(before),historical_rows_preserved=unchanged)
    (ROOT/'docs'/'catalog-canonical-phase7-development-migration.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not unchanged:raise SystemExit('Historical data changed; inspect the backup before enabling features')


if __name__=='__main__':main()
