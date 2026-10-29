"""Create only labeled development fixtures, importing through the real resolver.

Synthetic provider evidence is explicit in the snapshot; no external request or
existing work is used. Credentials remain in the ignored tmp directory.
"""
from dataclasses import asdict
from datetime import datetime,timezone
import json
from pathlib import Path
import secrets
import uuid

from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission
from app.modules.users.identities import create_personal_profile
from app.modules.books.evidence import EditionEvidence,ExternalReference,normalize_isbns
from app.modules.books.resolution import import_book


def main():
    s=get_settings();url=make_url(s.database_url)
    if s.app_env!='development' or url.host not in ('127.0.0.1','localhost') or url.database!='libria' or not s.catalog_admin_merge_enabled:
        raise SystemExit('Only the activated local development project is allowed')
    root=Path(__file__).resolve().parents[3]
    marker=uuid.uuid4().hex[:12];password=secrets.token_urlsafe(24)
    email=f'catalog-phase7-{marker}@example.com';title=f'Prueba controlada fase 7 {marker}'
    engine=create_engine(s.database_url)
    with Session(engine) as db,db.begin():
        db.execute(text('SELECT pg_advisory_xact_lock(73155,1)'))
        user=User(display_name='Prueba catálogo fase 7 '+marker,role='lector');db.add(user);db.flush()
        db.add(AuthAccount(user_id=user.id,email=email,password_hash=hash_password(password)))
        db.add(AccountPermission(user_id=user.id,permission='admin'));create_personal_profile(db,user);db.flush()
        books=[]
        for index,language in enumerate(('es','en')):
            base='978'+str(uuid.uuid4().int%10**9).zfill(9)
            isbn=base+str(-sum(int(c)*(1 if i%2==0 else 3) for i,c in enumerate(base))%10)
            ten,thirteen=normalize_isbns([isbn]);external=f'phase7-test-{marker}-{index}'
            snapshot=dict(id=external,phase7_synthetic_fixture=True,volumeInfo=dict(title=title,authors=['Autor sintético fase 7'],language=language,
                publisher='Editorial de prueba '+str(index+1),pageCount=120+index*120,industryIdentifiers=[dict(type='ISBN_13',identifier=thirteen)]))
            evidence=EditionEvidence(ExternalReference('google-books','volume',external),title,('Autor sintético fase 7',),ten,thirteen,language,
                120+index*120,'Editorial de prueba '+str(index+1),json.dumps(snapshot),datetime.now(timezone.utc))
            imported=import_book(db,user.id,f'phase7-fixture-{marker}-{index}',evidence,'Importación autorizada de fixture sintético para recorrido fase 7')
            books.append(asdict(imported))
        fixture=dict(marker=marker,email=email,password=password,user_id=str(user.id),title=title,books=books)
    directory=root/'tmp';directory.mkdir(exist_ok=True)
    (directory/'catalog-phase7-fixture.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(marker=marker,created_test_works=[b['physical_work_id'] for b in books],credentials='tmp/catalog-phase7-fixture.json (ignored)'),indent=2))


if __name__=='__main__':main()
