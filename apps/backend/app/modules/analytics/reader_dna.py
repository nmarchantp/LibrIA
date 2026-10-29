"""DNA identity depends on interpreted evidence, model and its own prompt."""
from sqlalchemy import text
from app.modules.analytics.gemini_context import content_hash, profile_evidence_units


def dna_fingerprint(payload):
    units = [unit.wire() for unit in profile_evidence_units(payload)]
    return content_hash({'identity_version':payload['identity_version'],'units':units} if payload.get('identity_version') else units)


def find_dna(db, owner, payload, model, prompt):
    return db.execute(text('''SELECT d.* FROM ia.reader_dna d JOIN ia.analyses a ON a.id=d.analysis_id
      WHERE d.owner_id=:owner AND a.valid
      AND d.source_hash=:hash AND d.model=:model AND d.prompt_version=:prompt'''),
      {'owner':owner,'hash':dna_fingerprint(payload),'model':model,'prompt':prompt}).mappings().first()


def enqueue_dna(db, owner, profile_id, model, prompt):
    db.execute(text('''INSERT INTO ia.jobs
      (owner_id,target,job_kind,provider,model,prompt_version,profile_version_id)
      VALUES (:owner,:target,'reader_profile','gemini',:model,:prompt,:profile)
      ON CONFLICT (owner_id,target) DO NOTHING'''),
      {'owner':owner,'target':f'dna:{profile_id}:{content_hash([model,prompt])}',
       'model':model,'prompt':prompt,'profile':profile_id})


def read_current_dna(db, owner, settings):
    # Read-only. Never enqueues recommendations or invokes Gemini.
    from app.modules.analytics.recommendation_sync import _latest_state
    state = _latest_state(db, owner)
    if not state or not state['profile_version_id']:
        return None
    payload = db.execute(text('SELECT payload FROM ia.reader_profile_versions WHERE id=:id'),
                         {'id':state['profile_version_id']}).scalar()
    return find_dna(db, owner, payload or {}, settings.gemini_model, settings.reader_dna_prompt_version)
