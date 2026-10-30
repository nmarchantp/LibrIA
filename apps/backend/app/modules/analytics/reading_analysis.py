"""Individual reading policy. Daily or administrator ETL authorizes inference."""
import uuid
from dataclasses import replace
from sqlalchemy import text
from app.core.config import get_settings
from app.modules.analytics.gemini_context import canonical_json, content_hash

CONTRACT = 'nightly-reading-v1'


class IneligibleReading(ValueError):
    pass


def normalize(value):
    if isinstance(value, str):
        return ' '.join(value.split())
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def context(db, owner, event):
    # Reuse the complete existing extractor, including canonical review selection.
    from app.modules.analytics.gemini_worker import _individual_context
    payload, units = _individual_context(db, {'owner_id': owner, 'reading_event_id': event})
    state = next(u.content['status'] for u in units if u.source_kind == 'reading')
    active = db.execute(text('''SELECT le.archived_at IS NULL FROM app.eventos_lectura ev
      JOIN app.lecturas r ON r.id=ev.reading_id JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
      WHERE ev.id=:event AND le.user_id=:owner'''), {'event': event, 'owner': owner}).scalar()
    if not active or state not in {'finished', 'abandoned'}:
        raise IneligibleReading('not_eligible')
    # "hidden" removes a previously published review from the community wall;
    # it is still the owner's persisted private review, not a deletion.
    reviews = [u for u in units if u.source_kind == 'review' and normalize(u.content.get('body') or '')]
    if len(reviews) != 1:
        raise IneligibleReading('requires_review')
    normalized = []
    for unit in units:
        if unit.source_kind == 'review':
            if unit not in reviews:
                continue
            # Revision counters are provenance, not a change in meaning. This
            # also permits reuse after reverting an edit to its original text.
            unit = replace(unit, evidence_id=f'review:{unit.source_id}',
                           content={key:value for key,value in unit.content.items() if key != 'status'})
        normalized.append(replace(unit, content=normalize(unit.content)))
    normalized.sort(key=lambda u: u.evidence_id)
    payload['evidence'] = [u.wire() for u in normalized]
    payload['contract_version'] = CONTRACT
    return payload, normalized


def fingerprint(payload):
    # Identity version is a catalog-wide counter; unrelated merges must not
    # regenerate this event. Resolved work identity remains in the payload.
    return content_hash({k: v for k, v in payload.items() if k != 'identity_version'})


def reusable(db, owner, event, digest, settings):
    return db.execute(text('''SELECT a.* FROM ia.analyses a
      WHERE a.owner_id=:owner AND a.reading_event_id=:event AND a.valid
      AND a.provider='gemini' AND a.model=:model AND a.prompt_version=:prompt
      AND a.data_hash=:hash ORDER BY a.created_at DESC LIMIT 1'''),
      {'owner': owner, 'event': event, 'hash': digest, 'model': settings.gemini_model,
       'prompt': settings.reading_analysis_prompt_version}).mappings().first()


def prepare_nightly(db, cutoff, run_id, settings=None):
    settings = settings or get_settings()
    result = {'prepared': 0, 'reused': 0, 'ineligible': 0}
    requests = db.execute(text('''SELECT * FROM ia.reading_analysis_requests
      WHERE changed_at < :cutoff ORDER BY reading_event_id FOR UPDATE'''), {'cutoff': cutoff}).mappings().all()
    for request in requests:
        owner, event = request['owner_id'], request['reading_event_id']
        try:
            payload, _ = context(db, owner, event)
        except IneligibleReading as error:
            db.execute(text('UPDATE ia.reading_analysis_requests SET error_code=:code WHERE reading_event_id=:event'),
                       {'code': str(error), 'event': event})
            result['ineligible'] += 1
            continue
        digest = fingerprint(payload)
        if reusable(db, owner, event, digest, settings):
            db.execute(text('UPDATE ia.reading_analysis_requests SET error_code=NULL WHERE reading_event_id=:event'), {'event':event})
            result['reused'] += 1
            continue
        job_id = uuid.uuid4()
        target = f'reading-event:{event}:gemini:{settings.gemini_model}:{settings.reading_analysis_prompt_version}:{digest}'
        job = db.execute(text('''INSERT INTO ia.jobs
          (id,owner_id,target,job_kind,provider,model,prompt_version,reading_event_id,evidence_hash,not_before)
          VALUES(:id,:owner,:target,'reading_event_analysis','gemini',:model,:prompt,:event,:hash,now())
          ON CONFLICT DO NOTHING RETURNING id'''),
          {'id': job_id, 'owner': owner, 'target': target, 'event': event, 'hash': digest,
           'model': settings.gemini_model, 'prompt': settings.reading_analysis_prompt_version}).scalar()
        if job:
            db.execute(text('''INSERT INTO ia.reading_analysis_snapshots(job_id,payload,etl_run_id)
              VALUES(:job,CAST(:payload AS jsonb),:run)'''),
              {'job': job, 'payload': canonical_json(payload), 'run': run_id})
            result['prepared'] += 1
        elif request['error_code'] == 'retry_requested':
            retried = db.execute(text('''UPDATE ia.jobs SET status='pending',not_before=now(),locked_at=NULL,
              error_code=NULL,updated_at=now() WHERE reading_event_id=:event AND evidence_hash=:hash
              AND model=:model AND prompt_version=:prompt AND provider='gemini' AND job_kind='reading_event_analysis'
              AND status='failed' AND attempts<:maximum RETURNING id'''),
              {'event':event,'hash':digest,'model':settings.gemini_model,
               'prompt':settings.reading_analysis_prompt_version,'maximum':settings.ai_job_max_attempts}).scalar()
            result['prepared'] += int(retried is not None)
        db.execute(text('''UPDATE ia.reading_analysis_requests SET prepared_at=clock_timestamp(),error_code=NULL
          WHERE reading_event_id=:event'''), {'event': event})
    return result


def book_state(db, owner, works, settings=None):
    settings = settings or get_settings()
    event = db.execute(text('''SELECT ev.id FROM app.eventos_lectura ev
      JOIN app.lecturas r ON r.id=ev.reading_id JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
      WHERE le.user_id=:owner AND r.work_id=ANY(:works) AND ev.actor_user_id=:owner
      AND ev.kind IN ('finish','abandon') ORDER BY ev.created_at DESC,ev.id DESC LIMIT 1'''),
      {'owner': owner, 'works': works}).scalar()
    from app.modules.analytics.generation_runtime import generation_runtime
    base = {'scope': 'book', 'analysis': None, 'job': None, 'evidence': [], 'needs_refresh': False,
            **generation_runtime(settings)}
    if event is None:
        return {**base, 'status': 'not_eligible'}
    try:
        payload, _ = context(db, owner, event)
    except IneligibleReading as error:
        return {**base, 'status': str(error)}
    digest = fingerprint(payload)
    current = reusable(db, owner, event, digest, settings)
    previous = current or db.execute(text('''SELECT * FROM ia.analyses WHERE owner_id=:owner
      AND reading_event_id=:event AND provider='gemini' AND valid AND content ? 'experience_summary'
      ORDER BY created_at DESC LIMIT 1'''), {'owner': owner, 'event': event}).mappings().first()
    job = db.execute(text('''SELECT id,status,attempts,error_code,not_before FROM ia.jobs
      WHERE owner_id=:owner AND reading_event_id=:event AND evidence_hash=:hash
      AND model=:model AND prompt_version=:prompt AND job_kind='reading_event_analysis'
      ORDER BY created_at DESC LIMIT 1'''), {'owner': owner, 'event': event, 'hash': digest,
      'model': settings.gemini_model, 'prompt': settings.reading_analysis_prompt_version}).mappings().first()
    retry_scheduled = False
    if current:
        status = 'completed'
    elif job and job['status'] == 'processing':
        status = 'update_processing' if previous else 'processing'
    elif job and job['status'] == 'failed':
        retry = db.execute(text('SELECT error_code FROM ia.reading_analysis_requests WHERE reading_event_id=:event'),
                           {'event':event}).scalar()
        retry_scheduled = retry == 'retry_requested'
        status = ('update_pending' if previous else 'waiting_nightly_processing') if retry == 'retry_requested' else 'failed'
    elif previous:
        status = 'update_pending'
    elif job and job['status'] == 'pending':
        status = 'queued'
    else:
        status = 'waiting_nightly_processing'
    evidence = []
    if previous:
        evidence = [dict(row) for row in db.execute(text('''SELECT e.source_key,e.source_kind,e.source_id,e.work_id
          FROM ia.evidence e WHERE e.analysis_id=:id ORDER BY e.source_key'''), {'id':previous['id']}).mappings()]
    return {**base, 'status': status, 'analysis': dict(previous) if previous else None,
            'evidence': evidence,
            'job': dict(job) if job else None, 'needs_refresh': not bool(current),
            'retry_scheduled': retry_scheduled,
            'retry_exhausted': bool(job and job['attempts'] >= settings.ai_job_max_attempts),
            'reading_event_id': event}
