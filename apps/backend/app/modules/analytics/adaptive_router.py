"""Only the authenticated owner can read or correct private AI results."""
import uuid
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.identity_models import AccountPermission
from app.modules.users.models import User
from app.modules.analytics.adaptive_ai import latest, owned_entry, VERSION, PROFILE_VERSION
from app.modules.analytics.recommendation_profiles import prepare_administrator_profile
from app.modules.analytics.recommendation_sync import recommendation_state
from app.modules.analytics.persistence import enqueue_reading_event_analysis

router = APIRouter(prefix='/me/ai', tags=['private-reader-ai'])
Owner = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


def overview(db, owner, target, response):
    response.headers['Cache-Control'] = 'no-store'
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
    from app.modules.books.canonical import enabled, canonical_members, identity_version
    work_ids = list(canonical_members(db, book_id)) if enabled() else [book_id]
    response.headers['Cache-Control']='no-store'
    analysis = db.execute(text('''SELECT a.* FROM ia.analyses a
        JOIN ia.jobs j ON j.id=a.job_id
        JOIN app.eventos_lectura ev ON ev.id=a.reading_event_id
        JOIN app.lecturas r ON r.id=ev.reading_id
        WHERE a.owner_id=:owner AND r.work_id=ANY(:works) AND a.provider='gemini'
          AND j.job_kind='reading_event_analysis' AND a.valid
        ORDER BY a.created_at DESC LIMIT 1'''), {'owner': user.id, 'works': work_ids}).mappings().first()
    if enabled() and analysis and analysis.get('identity_version') != identity_version(db):
        analysis = None
    job = db.execute(text('''SELECT j.id,j.target,j.status,j.attempts,j.error_code,j.updated_at,j.not_before,j.locked_at,
        j.prompt_version,j.model
        FROM ia.jobs j JOIN app.eventos_lectura ev ON ev.id=j.reading_event_id
        JOIN app.lecturas r ON r.id=ev.reading_id
        WHERE j.owner_id=:owner AND r.work_id=ANY(:works) AND j.job_kind='reading_event_analysis'
          AND j.provider='gemini' ORDER BY ev.created_at DESC,j.created_at DESC LIMIT 1'''),
        {'owner': user.id, 'works': work_ids}).mappings().first()
    evidence=[]
    if analysis:
        evidence=[dict(row) for row in db.execute(text('''SELECT e.source_key,e.source_kind,e.source_id,e.work_id,
            w.title AS book_title FROM ia.evidence e LEFT JOIN app.obras w ON w.id=e.work_id
            WHERE e.analysis_id=:analysis ORDER BY e.source_key'''), {'analysis':analysis['id']}).mappings().all()]
    if job and job['status'] in {'pending', 'processing'}:
        status = job['status']
    elif analysis:
        status = 'ready'
    elif job and (job['status'] == 'completed' or str(job['error_code'] or '').startswith(('obsolete', 'reading_event_unavailable'))):
        status = 'obsolete'
    elif job and job['error_code'] == 'monthly_budget_exhausted':
        status = 'budget_exhausted'
    else:
        status = job['status'] if job else 'awaiting_terminal_event'
    return {'scope':'book','status':status,'analysis':dict(analysis) if analysis else None,
            'job':dict(job) if job else None,'evidence':evidence}


@router.post('/books/{book_id}/refresh', status_code=202)
def refresh_book(book_id: uuid.UUID, response: Response, user: Owner, db: Database, force: bool = False):
    owned_entry(db, user.id, book_id)
    from app.modules.books.canonical import enabled, canonical_members
    work_ids = list(canonical_members(db, book_id)) if enabled() else [book_id]
    response.headers['Cache-Control'] = 'no-store'
    if force and db.get(AccountPermission, (user.id, 'admin')) is None:
        raise HTTPException(403, 'Se requiere una cuenta administradora')
    event_id = db.execute(text('''SELECT ev.id FROM app.eventos_lectura ev
        JOIN app.lecturas r ON r.id=ev.reading_id
        JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
        WHERE le.user_id=:owner AND r.work_id=ANY(:works)
          AND ev.actor_user_id=:owner AND ev.kind IN ('finish','abandon')
        ORDER BY ev.created_at DESC,ev.id DESC LIMIT 1'''),
        {'owner': user.id, 'works': work_ids}).scalar()
    if event_id is None:
        raise HTTPException(409, 'Termina o abandona una lectura de este libro antes de analizarla')
    settings = get_settings()
    if force:
        existing = db.execute(text('''SELECT status,attempts FROM ia.jobs WHERE reading_event_id=:event
          AND provider=:provider AND model=:model AND prompt_version=:prompt'''),
          {'event':event_id,'provider':settings.ai_provider,'model':settings.gemini_model,
           'prompt':settings.reading_analysis_prompt_version}).mappings().first()
        if existing and (existing['status']=='processing' or existing['attempts']>=settings.ai_job_max_attempts):
            raise HTTPException(409,'El trabajo está en curso o alcanzó su límite acumulado de intentos')
    job = enqueue_reading_event_analysis(
        db,
        reading_event_id=event_id,
        provider=settings.ai_provider,
        model=settings.gemini_model,
        prompt_version=settings.reading_analysis_prompt_version,
        delay_minutes=0,
    )
    if force and job['status'] == 'completed' and job['attempts'] < settings.ai_job_max_attempts:
        job = db.execute(text("""UPDATE ia.jobs SET status='pending',revision=revision+1,
          not_before=now(),error_code=NULL,updated_at=now() WHERE id=:id RETURNING *"""),
          {'id':job['id']}).mappings().one()
    elif job['status'] == 'failed' and job['attempts'] < settings.ai_job_max_attempts:
        job = db.execute(text('''UPDATE ia.jobs SET status='pending',error_code=NULL,
            not_before=now(),locked_at=NULL,updated_at=now() WHERE id=:id RETURNING *'''),
            {'id': job['id']}).mappings().one()
    elif job['status'] == 'completed':
        # A completed job can have an invalidated or pre-canonical result. The
        # worker checks the current evidence hash before reusing any analysis.
        current = book_analysis(book_id, response, user, db)
        if not current['analysis']:
            if job['attempts'] >= settings.ai_job_max_attempts:
                raise HTTPException(409, 'El análisis necesita actualizarse, pero alcanzó su límite de intentos')
            job = db.execute(text("""UPDATE ia.jobs SET status='pending',not_before=now(),
                error_code=NULL,locked_at=NULL,updated_at=now()
                WHERE id=:id AND status='completed' RETURNING *"""),
                {'id':job['id']}).mappings().one()
    elif job['status'] == 'pending':
        job = db.execute(text("UPDATE ia.jobs SET not_before=now(),updated_at=now() WHERE id=:id RETURNING *"),
                         {'id': job['id']}).mappings().one()
    db.commit()
    return {'job_id': job['id'], 'status': job['status'], 'job': dict(job)}


@router.get('/profile')
def profile(response: Response, user: Owner, db: Database):
    state = recommendation_state(db, user.id, enqueue=False)
    from app.modules.analytics.reader_dna import read_current_dna
    dna = read_current_dna(db, user.id, get_settings())
    analysis = db.execute(text('''SELECT a.* FROM ia.analyses a JOIN ia.jobs j ON j.id=a.job_id
        WHERE a.owner_id=:owner AND a.provider='gemini' AND a.valid
          AND j.job_kind IN ('recommendation','reader_profile') AND a.content ? 'profile'
        ORDER BY a.created_at DESC LIMIT 1'''),
        {'owner':user.id}).mappings().first()
    analysis = dict(analysis) if analysis else None
    from app.modules.books.canonical import enabled, identity_version
    if enabled() and analysis and analysis.get('identity_version') != identity_version(db):
        analysis = None
    if dna:
        analysis = dict(db.execute(text('SELECT * FROM ia.analyses WHERE id=:id'),
                                  {'id':dna['analysis_id']}).mappings().one())
    else:
        dna_job = db.execute(text('''SELECT id,status,error_code FROM ia.jobs WHERE owner_id=:owner
          AND job_kind='reader_profile' AND model=:model AND prompt_version=:prompt
          ORDER BY created_at DESC LIMIT 1'''), {'owner':user.id,'model':get_settings().gemini_model,
          'prompt':get_settings().reader_dna_prompt_version}).mappings().first()
        if dna_job and dna_job['status'] in {'pending','processing','failed'}:
            state = {**state,'status':dna_job['status'],'generation_status':dna_job['status'],'job_id':str(dna_job['id']),
                     'error_code':dna_job['error_code']}
    if analysis:
        analysis['content']=(analysis.get('content') or {}).get('profile')
    evidence=[]
    if analysis:
        evidence=[dict(row) for row in db.execute(text('''SELECT e.source_key,e.source_kind,e.source_id,e.work_id,
            w.title AS book_title FROM ia.evidence e LEFT JOIN app.obras w ON w.id=e.work_id
            WHERE e.analysis_id=:analysis ORDER BY e.source_key'''),{'analysis':analysis['id']}).mappings().all()]
    result = {'scope':'profile','status':'ready' if dna else state['status'],
              'analysis': analysis,
              'recommendations': (state.get('recommendations') or {}).get('recommendations'),
              'job': {'id':state.get('job_id'),'status':state.get('generation_status',state['status']),
                      'error_code':state.get('error_code')} if state.get('job_id') and not dna else None,
              'evidence': evidence, 'needs_refresh': False}
    response.headers['Cache-Control']='no-store'
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


@router.post('/profile/refresh', status_code=202)
def refresh_profile(response: Response, user: Owner, db: Database):
    response.headers['Cache-Control'] = 'no-store'
    preparation = prepare_administrator_profile(db, user.id)
    # The deterministic profile is persisted before provider work is queued.
    db.commit()
    from app.modules.analytics.reader_dna import enqueue_dna, read_current_dna
    from app.modules.analytics.recommendation_sync import _latest_state
    settings = get_settings()
    current = _latest_state(db, user.id)
    dna = read_current_dna(db, user.id, settings)
    job = None
    if current and current['profile_version_id'] and not dna:
        enqueue_dna(db, user.id, current['profile_version_id'], settings.gemini_model, settings.reader_dna_prompt_version)
        job = db.execute(text('''SELECT * FROM ia.jobs WHERE owner_id=:owner
          AND job_kind='reader_profile' AND profile_version_id=:profile AND model=:model
          AND prompt_version=:prompt ORDER BY created_at DESC LIMIT 1'''),
          {'owner':user.id,'profile':current['profile_version_id'],'model':settings.gemini_model,
           'prompt':settings.reader_dna_prompt_version}).mappings().one()
        if job['status'] in {'failed','completed'} and job['attempts'] < settings.ai_job_max_attempts:
            db.execute(text("UPDATE ia.jobs SET status='pending',not_before=now(),error_code=NULL WHERE id=:id"), {'id':job['id']})
        db.commit()
    status = 'ready' if dna else job['status'] if job else 'insufficient_data'
    if job and job['status'] in {'failed','completed'} and job['attempts'] < settings.ai_job_max_attempts:
        status = 'pending'
    return {**recommendation_state(db, user.id, enqueue=False),
            'status':status,
            'job_id':str(job['id']) if job else None,'profile_preparation':preparation}


@router.get('/profile/history')
def history(response: Response, user: Owner, db: Database, limit: int = Query(20, ge=1, le=100), before: int | None = Query(None, ge=1)):
    response.headers['Cache-Control'] = 'no-store'
    rows = db.execute(text("""SELECT id,version,content,valid,model,provider,created_at FROM ia.analyses
        WHERE owner_id=:owner AND (target='profile' OR target LIKE 'profile:%')
          AND (CAST(:before AS integer) IS NULL OR version<:before)
        ORDER BY version DESC LIMIT :limit"""), {'owner': user.id, 'before': before, 'limit': limit}).mappings().all()
    return {'items': [dict(row) for row in rows]}


@router.get('/jobs/{job_id}')
def job_status(job_id: uuid.UUID, response: Response, user: Owner, db: Database):
    response.headers['Cache-Control'] = 'no-store'
    job = db.execute(text('''SELECT id,target,job_kind,provider,status,attempts,error_code,updated_at,
        not_before,locked_at,deadline_at FROM ia.jobs WHERE id=:id AND owner_id=:owner'''),
                     {'id': job_id, 'owner': user.id}).mappings().first()
    if not job:
        raise HTTPException(404, 'Tarea propia no encontrada')
    result=dict(job)
    if result['status']=='failed' and str(result['error_code'] or '').startswith(('obsolete','reading_event_unavailable')):
        result['status']='obsolete'
    return result


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
    # Feedback history is preserved, but never creates a second per-event job
    # and never bridges historical results into a disabled provider path.
    db.execute(text("UPDATE ia.feedback SET status='processed',processed_at=now() WHERE id=:id"), {'id':fid})
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'id': fid, 'status': 'processed', 'job_id': None}


@router.get('/feedback')
def feedback_history(response: Response, user: Owner, db: Database):
    response.headers['Cache-Control'] = 'no-store'
    rows = db.execute(text("""SELECT id,analysis_id,action,information,status,created_at,processed_at
        FROM ia.feedback WHERE owner_id=:owner ORDER BY created_at DESC LIMIT 100"""), {'owner': user.id}).mappings().all()
    return {'items': [dict(row) for row in rows]}
