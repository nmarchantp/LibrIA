"""Only the authenticated owner can read or correct private AI results."""
import uuid
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.analytics.adaptive_ai import enqueue, latest, owned_entry, has_rating, expire_profiles, VERSION, PROFILE_VERSION

router = APIRouter(prefix='/me/ai', tags=['private-reader-ai'])
Owner = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


def overview(db, owner, target, response):
    response.headers['Cache-Control'] = 'no-store'
    expire_profiles(db,owner)
    db.commit()
    analysis = latest(db, owner, target)
    stored = latest(db,owner,target,valid=False) if target=='profile' and not analysis else None
    job = db.execute(text('SELECT id,target,status,attempts,error_code,updated_at,deadline_at FROM ia.jobs WHERE owner_id=:owner AND target=:target'),
                     {'owner': owner, 'target': target}).mappings().first()
    evidence = []
    needs_refresh = False
    if analysis and analysis['prompt_version'] != (PROFILE_VERSION if target=='profile' else VERSION):
        needs_refresh = not job or job['status']=='completed'
    if stored and stored['valid'] and not analysis:
        needs_refresh = not job or job['status']=='completed'
    if target=='profile' and analysis and not {'literary_identity','identity_evidence_ids'}.issubset(analysis['content']):
        analysis = None
        needs_refresh = not job or job['status']=='completed'
    if analysis:
        evidence = [dict(row) for row in db.execute(text('SELECT e.source_key,e.source_kind,e.source_id,e.work_id,w.title AS book_title FROM ia.evidence e LEFT JOIN app.obras w ON w.id=e.work_id WHERE e.analysis_id=:id'),
                                                   {'id': analysis['id']}).mappings().all()]
        analysis['source_cutoff_at']=db.execute(text('SELECT source_cutoff_at FROM analytics.projection_runs WHERE id=:id'),
                                              {'id':analysis['analytics_run_id']}).scalar()
    return {'analysis': analysis, 'job': dict(job) if job else None, 'evidence': evidence,
            'scope':'profile' if target=='profile' else 'book', 'needs_refresh':needs_refresh}


@router.get('/books/{book_id}')
def book_analysis(book_id: uuid.UUID, response: Response, user: Owner, db: Database):
    owned_entry(db, user.id, book_id)
    if not has_rating(db,user.id,book_id):
        response.headers['Cache-Control']='no-store'
        return {'scope':'book','status':'awaiting_rating','analysis':None,'job':None,'evidence':[]}
    return overview(db, user.id, 'book:'+str(book_id), response)


@router.post('/books/{book_id}/refresh', status_code=202)
def refresh_book(book_id: uuid.UUID, response: Response, user: Owner, db: Database):
    owned_entry(db, user.id, book_id)
    if not has_rating(db,user.id,book_id):
        raise HTTPException(422,'Valora este libro antes de solicitar su análisis individual')
    job = request_job(db,user.id,'book:'+str(book_id))
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'job_id': job['id'], 'status': job['status'],'job':dict(job)}


@router.get('/profile')
def profile(response: Response, user: Owner, db: Database):
    result = overview(db, user.id, 'profile', response)
    # Polling is a read of the last published ETL cut, never an ETL execution.
    snapshot=db.execute(text('''SELECT r.payload FROM analytics.reader_current c
        JOIN analytics.projection_runs r ON r.id=c.run_id WHERE c.owner_id=:owner'''),{'owner':user.id}).scalar()
    summary=None
    if snapshot:
        summary={'total':0,'pending':0,'reading':0,'finished':0,'abandoned':0,'rated':0}
        for book in snapshot['books']:
            if not book['archived']:
                summary['total']+=1
                summary[book['context']['state']]+=1
                summary['rated']+=int(book['context']['rated'])
    result['library_summary'] = summary
    return result


def request_job(db,owner,target):
    """A transport retry joins an active job instead of discarding its result."""
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':f'ai-request:{owner}:{target}'})
    if target=='profile':
        expire_profiles(db,owner)
    job=db.execute(text('SELECT * FROM ia.jobs WHERE owner_id=:owner AND target=:target FOR UPDATE'),
                   {'owner':owner,'target':target}).mappings().first()
    if job and job['status'] in ('pending','processing'):
        return dict(job)
    job=enqueue(db,owner,target)
    if target=='profile':
        db.execute(text("UPDATE ia.jobs SET deadline_at=now()+interval '55 seconds',not_before=now(),error_code=NULL WHERE id=:id"),{'id':job['id']})
        job=dict(db.execute(text('SELECT * FROM ia.jobs WHERE id=:id'),{'id':job['id']}).mappings().one())
    return job


@router.post('/profile/refresh', status_code=202)
def refresh_profile(response: Response, user: Owner, db: Database):
    job = request_job(db,user.id,'profile')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'job_id': job['id'], 'status': job['status'],'job':dict(job)}


@router.get('/profile/history')
def history(response: Response, user: Owner, db: Database, limit: int = Query(20, ge=1, le=100), before: int | None = Query(None, ge=1)):
    response.headers['Cache-Control'] = 'no-store'
    rows = db.execute(text("""SELECT id,version,content,valid,model,created_at FROM ia.analyses
        WHERE owner_id=:owner AND target='profile' AND (CAST(:before AS integer) IS NULL OR version<:before)
        ORDER BY version DESC LIMIT :limit"""), {'owner': user.id, 'before': before, 'limit': limit}).mappings().all()
    return {'items': [dict(row) for row in rows]}


@router.get('/jobs/{job_id}')
def job_status(job_id: uuid.UUID, response: Response, user: Owner, db: Database):
    response.headers['Cache-Control'] = 'no-store'
    expire_profiles(db,user.id)
    db.commit()
    job = db.execute(text('SELECT id,target,status,attempts,error_code,updated_at,deadline_at FROM ia.jobs WHERE id=:id AND owner_id=:owner'),
                     {'id': job_id, 'owner': user.id}).mappings().first()
    if not job:
        raise HTTPException(404, 'Tarea propia no encontrada')
    return dict(job)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    analysis_id: uuid.UUID
    action: Literal['confirm','correct','reject']
    information: str = Field(default='', max_length=3000)

    @model_validator(mode='after')
    def require_correction(self):
        if self.action == 'correct' and not self.information:
            raise ValueError('Explica tu corrección')
        return self


@router.post('/feedback', status_code=202)
def feedback(payload: FeedbackRequest, response: Response, user: Owner, db: Database):
    analysis = db.execute(text('SELECT * FROM ia.analyses WHERE id=:id AND owner_id=:owner FOR UPDATE'),
                          {'id': payload.analysis_id, 'owner': user.id}).mappings().first()
    if not analysis or not analysis['valid']:
        raise HTTPException(404, 'Interpretación propia vigente no encontrada')
    # A superseded version is visible in history but cannot correct current output.
    current = latest(db, user.id, analysis['target'])
    if not current or current['id'] != analysis['id']:
        raise HTTPException(409, 'La interpretación cambió. Actualiza antes de corregirla.')
    fid = uuid.uuid4()
    db.execute(text("""INSERT INTO ia.feedback(id,owner_id,analysis_id,action,original_interpretation,information)
        VALUES (:id,:owner,:analysis,:action,CAST(:original AS jsonb),:information)"""),
        {'id': fid, 'owner': user.id, 'analysis': analysis['id'], 'action': payload.action,
         'original': json.dumps(analysis['content']), 'information': payload.information})
    if payload.action != 'confirm':
        db.execute(text('UPDATE ia.analyses SET valid=false WHERE id=:id'), {'id': analysis['id']})
        if analysis['target'] != 'profile':
            db.execute(text("UPDATE ia.analyses SET valid=false WHERE owner_id=:owner AND target='profile'"), {'owner': user.id})
    job = enqueue(db, user.id, analysis['target'])
    if analysis['target'] != 'profile':
        enqueue(db, user.id, 'profile')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'id': fid, 'status': 'pending', 'job_id': job['id']}


@router.get('/feedback')
def feedback_history(response: Response, user: Owner, db: Database):
    response.headers['Cache-Control'] = 'no-store'
    rows = db.execute(text("""SELECT id,analysis_id,action,information,status,created_at,processed_at
        FROM ia.feedback WHERE owner_id=:owner ORDER BY created_at DESC LIMIT 100"""), {'owner': user.id}).mappings().all()
    return {'items': [dict(row) for row in rows]}
