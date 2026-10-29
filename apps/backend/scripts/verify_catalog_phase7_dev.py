"""Read-only postflight for the specifically created development fixture."""
import json
from pathlib import Path
import uuid
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from app.core.config import get_settings


def main():
    root=Path(__file__).resolve().parents[3]
    fixture=json.loads((root/'tmp'/'catalog-phase7-fixture.json').read_text(encoding='utf-8'))
    s=get_settings();url=make_url(s.database_url)
    if s.app_env!='development' or url.host not in ('127.0.0.1','localhost') or url.database!='libria':
        raise SystemExit('Read-only postflight is restricted to local development')
    keys=('catalog_discovery_enabled','catalog_editionless_enabled','catalog_canonical_enabled','catalog_admin_preview_enabled','catalog_admin_merge_enabled')
    report=dict(flags={k:getattr(s,k) for k in keys},marker=fixture['marker'])
    ids=[uuid.UUID(b['physical_work_id']) for b in fixture['books']]
    owner=uuid.UUID(fixture['user_id'])
    with create_engine(s.database_url).connect() as c:
        c.execute(text('SET TRANSACTION READ ONLY'))
        report['head']=c.scalar(text('SELECT version_num FROM alembic_version'))
        report['catalog_works']=c.scalar(text('SELECT count(*) FROM app.obras'))
        report['test_works']=c.scalar(text('SELECT count(*) FROM app.obras WHERE id=ANY(:ids)'),dict(ids=ids))
        report['test_library_entries']=c.scalar(text('SELECT count(*) FROM app.entradas_biblioteca WHERE user_id=:owner'),dict(owner=owner))
        rows=c.execute(text('SELECT r.id,r.work_id,r.edition_id,r.current_page,r.total_pages FROM app.lecturas r JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id WHERE le.user_id=:owner ORDER BY r.work_id'),dict(owner=owner)).mappings().all()
        report['readings']=[{k:str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()} for row in rows]
        report['test_reviews']=c.scalar(text('SELECT count(*) FROM app.resenas WHERE created_by_user_id=:owner'),dict(owner=owner))
        report['test_ai_jobs']=c.scalar(text('SELECT count(*) FROM ia.jobs WHERE owner_id=:owner'),dict(owner=owner))
        report['test_ai_analyses']=c.scalar(text('SELECT count(*) FROM ia.analyses WHERE owner_id=:owner'),dict(owner=owner))
        report['active_test_redirects']=c.scalar(text('SELECT count(*) FROM app.redirecciones_obras WHERE source_work_id=ANY(:ids) AND retired_at IS NULL'),dict(ids=ids))
        report['unrelated_redirects']=c.scalar(text('SELECT count(*) FROM app.redirecciones_obras WHERE NOT(source_work_id=ANY(:ids) AND target_work_id=ANY(:ids))'),dict(ids=ids))
        report['test_operations']=[dict(id=str(r.id),kind=r.operation_type) for r in c.execute(text("SELECT id,operation_type FROM app.operaciones_catalogo WHERE actor_user_id=:owner AND operation_type IN ('merge','reversal') ORDER BY identity_version"),dict(owner=owner))]
        report['success']=all(report['flags'].values()) and report['head']=='0060_admin_merges' and report['test_works']==2 and report['test_reviews']==2 and report['test_ai_jobs']==0 and report['test_ai_analyses']==0 and report['active_test_redirects']==0 and report['unrelated_redirects']==0
    (root/'docs'/'catalog-canonical-phase7-development-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not report['success']:raise SystemExit(1)


if __name__=='__main__':main()
