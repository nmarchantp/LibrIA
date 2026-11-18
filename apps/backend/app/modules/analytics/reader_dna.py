"""DNA identity depends on interpreted evidence, model and its own prompt."""
from sqlalchemy import text
from app.modules.analytics.gemini_context import content_hash, profile_evidence_units

DIMENSIONS = ('narrative_preferences', 'character_preferences', 'themes_and_conflicts',
              'emotional_patterns', 'rating_patterns', 'genres_and_styles',
              'interests_from_notes_and_theories')


def personal_signatures(units):
    """Metadata edits cannot masquerade as new personal literary evidence."""
    result = {}
    for unit in units:
        value = unit.content
        if unit.source_kind == 'reading':
            value = {key: value.get(key) for key in ('rating', 'dimension_ratings', 'finish_reflection')}
        result[unit.evidence_id] = content_hash(value)
    return result


def assess_evidence(units):
    """An upper bound, not a semantic assertion about what the texts express."""
    import re
    expressive = []
    words = 0
    for unit in units:
        value = unit.content.get('finish_reflection') if unit.source_kind == 'reading' else unit.content
        # Count actual values, never JSON keys, metadata or numeric ratings.
        def strings(item):
            if isinstance(item, str):
                yield item
            elif isinstance(item, dict):
                for key, child in item.items():
                    if key not in {'source_id', 'source_at', 'work_id', 'created_at', 'updated_at'}:
                        yield from strings(child)
            elif isinstance(item, list):
                for child in item:
                    yield from strings(child)
        count = sum(len(re.findall(r'\b\w+\b', item)) for item in strings(value))
        if count >= 12:
            expressive.append(unit)
            words += count
    works = {str(unit.work_id) for unit in expressive if unit.work_id}
    sufficient = len(works) >= 2 and len(expressive) >= 2 and words >= 180
    level = 'sufficient' if sufficient else 'partial' if expressive else 'insufficient'
    return {'evidence_level': level, 'expressive_sources': len(expressive),
            'expressive_works': len(works), 'authored_words': words,
            'expressive_evidence_ids': [unit.evidence_id for unit in expressive]}


def previous_dna(db, owner):
    return db.execute(text('''SELECT d.*, p.payload AS source_payload FROM ia.reader_dna d
      JOIN ia.analyses a ON a.id=d.analysis_id
      JOIN ia.reader_profile_versions p ON p.id=d.source_profile_id
      WHERE d.owner_id=:owner AND a.valid ORDER BY d.created_at DESC,d.id DESC LIMIT 1'''),
      {'owner': owner}).mappings().first()


def evolution_context(previous, units):
    current = personal_signatures(units)
    if not previous:
        return {'reference_version_id': None, 'previous': None, 'changed_personal_evidence_ids': []}
    old = personal_signatures(profile_evidence_units(previous['source_payload']))
    old_content = previous['content']
    # Compare dimensions, not the old prose. No need to resend the old personal
    # interpretation or any source text to the provider.
    reference = {key: old_content.get(key, []) for key in DIMENSIONS}
    reference['evidence_ids'] = old_content.get('evidence_ids', [])
    reference['reader_essence'] = {'evidence_level': (old_content.get('reader_essence') or {}).get('evidence_level', 'insufficient')}
    return {'reference_version_id': str(previous['id']), 'previous': reference,
            'changed_personal_evidence_ids': sorted(key for key, value in current.items() if old.get(key) != value)}


def validate_dna(value, units, context):
    from app.modules.analytics.gemini_contracts import ReaderDnaInterpretation
    if not set(DIMENSIONS).issubset(value):
        raise ValueError('A valid global DNA must preserve all seven dimensions')
    result = ReaderDnaInterpretation.model_validate(value).model_dump()
    allowed = {unit.evidence_id for unit in units}
    quality = assess_evidence(units)
    levels = ['insufficient', 'partial', 'sufficient']
    essence = result['reader_essence']
    if levels.index(essence['evidence_level']) > levels.index(quality['evidence_level']):
        raise ValueError('Essence exceeds available personal evidence')
    if not set(result['evidence_ids']).issubset(allowed) or not set(essence['evidence_ids']).issubset(set(result['evidence_ids'])):
        raise ValueError('DNA cites unknown or unregistered evidence')
    expressive = set(quality['expressive_evidence_ids'])
    if essence['evidence_level'] != 'insufficient' and not expressive.intersection(essence['evidence_ids']):
        raise ValueError('Essence must cite expressive personal evidence')
    if essence['evidence_level'] == 'sufficient':
        works = {str(unit.work_id) for unit in units if unit.evidence_id in expressive.intersection(essence['evidence_ids']) and unit.work_id}
        if len(works) < 2:
            raise ValueError('A full essence needs expressive evidence across works')
    evolution = result['evolution']
    previous = context.get('previous') or {}
    if evolution['reference_version_id'] != context['reference_version_id']:
        raise ValueError('Evolution references a different version')
    comparable = essence['evidence_level'] == 'sufficient' and (previous.get('reader_essence') or {}).get('evidence_level') == 'sufficient'
    changed = set(context['changed_personal_evidence_ids'])
    if not comparable:
        evolution.update(has_meaningful_changes=False, summary=None, stable_patterns=[], emerging_interests=[], changing_preferences=[])
    else:
        reference_ids = set(previous.get('evidence_ids') or [])
        for category in ('stable_patterns', 'emerging_interests', 'changing_preferences'):
            for claim in evolution[category]:
                if not set(claim['evidence_ids']).issubset(set(result['evidence_ids'])) or not set(claim['reference_evidence_ids']).issubset(reference_ids):
                    raise ValueError('Evolution contains unsupported citations')
                if category != 'stable_patterns' and not changed.intersection(claim['evidence_ids']):
                    raise ValueError('A preference change requires new personal evidence')
        meaningful = bool(evolution['emerging_interests'] or evolution['changing_preferences'])
        if evolution['has_meaningful_changes'] != meaningful:
            raise ValueError('Evolution flag must match supported changes')
        if meaningful and not evolution['summary']:
            raise ValueError('Supported changes require a narrative')
        if not meaningful and not evolution['summary']:
            evolution['summary'] = 'En tus versiones comparables no se detectan cambios de preferencias suficientemente respaldados.'
        if evolution['summary']:
            import re
            if not re.search(r'\b(tú|tu|tus|te|ti|sigues|mantienes|valoras|disfrutas)\b', evolution['summary'], re.I):
                raise ValueError('Evolution must address the reader in second person')
    result['schema_version'] = 2
    return result


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


def read_current_dna(db, owner, settings, *, allow_stale=True):
    # Read-only. Never enqueues recommendations or invokes Gemini.
    from app.modules.analytics.recommendation_sync import _latest_state
    state = _latest_state(db, owner)
    current = None
    if state and state['profile_version_id']:
        payload = db.execute(text('SELECT payload FROM ia.reader_profile_versions WHERE id=:id'),
                             {'id':state['profile_version_id']}).scalar()
        current = find_dna(db, owner, payload or {}, settings.gemini_model, settings.reader_dna_prompt_version)
    if current:
        return {**dict(current), 'is_current': True}
    if allow_stale:
        # Preserve the latest valid result during updates, schema changes and failures.
        previous = db.execute(text('''SELECT d.* FROM ia.reader_dna d JOIN ia.analyses a ON a.id=d.analysis_id
          WHERE d.owner_id=:owner AND a.valid ORDER BY d.created_at DESC,d.id DESC LIMIT 1'''),
          {'owner':owner}).mappings().first()
        if previous:
            return {**dict(previous), 'is_current': False}
    return None
