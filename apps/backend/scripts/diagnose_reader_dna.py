"""Explicit Gemini-only diagnostic generation; logs counts/rules, never source texts."""
import json
import re
import uuid
import sys
from dataclasses import replace
from sqlalchemy import text
from pydantic import ValidationError
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.analytics.gemini_worker import process_one
from app.modules.analytics.providers.gemini import GeminiProvider
from app.modules.analytics.recommendation_sync import _latest_state


class DiagnosticGemini(GeminiProvider):
    def generate_structured(self, request):
        original = request.validator
        def validate(value):
            try:
                return original(value)
            except (ValueError, ValidationError) as error:
                essence = value.get('reader_essence') or {}
                summary = essence.get('summary') or ''
                report = {'validation_error':type(error).__name__, 'summary_words':len(summary.split()),
                          'paragraphs':len(re.split(r'\n\s*\n',summary.strip())),
                          'traits':len(essence.get('traits') or [])}
                if isinstance(error, ValidationError):
                    report['rules'] = [item['type'] for item in error.errors(include_input=False,include_context=False)]
                    report['essence_shape_rule'] = any('120–180' in item['msg'] for item in error.errors(include_input=False,include_context=False))
                else:
                    # Every exposed message here is a fixed application rule.
                    reasons = ['Essence exceeds available personal evidence', 'DNA cites unknown or unregistered evidence',
                               'Essence must cite expressive personal evidence', 'A full essence needs expressive evidence across works',
                               'Evolution references a different version', 'Evolution contains unsupported citations',
                               'A preference change requires new personal evidence', 'Evolution flag must match supported changes',
                               'Supported changes require a narrative', 'Evolution must address the reader in second person',
                               'A valid global DNA must preserve all seven dimensions']
                    report['rule'] = str(error) if str(error) in reasons else 'other_validation_rule'
                print(json.dumps(report),flush=True)
                raise
        return super().generate_structured(replace(request,validator=validate))


def main():
    settings = get_settings()
    free = settings.gemini_free_test_mode and settings.app_env in {'development','test'}
    if not settings.gemini_worker_enabled or not (settings.gemini_paid_service_confirmed or free):
        raise SystemExit('Gemini activation is required')
    with SessionLocal() as db:
        if len(sys.argv) > 1:
            job_id = uuid.UUID(sys.argv[1])
            previous = db.execute(text("SELECT owner_id,target FROM ia.jobs WHERE id=:id AND job_kind='reader_profile' AND provider='gemini'"),{'id':job_id}).mappings().one()
            owner, target = previous['owner_id'], previous['target']
        else:
            previous = db.execute(text("SELECT owner_id FROM ia.jobs WHERE job_kind='reader_profile' ORDER BY created_at DESC LIMIT 1")).mappings().one()
            owner = previous['owner_id']
            state = _latest_state(db,owner)
            target = 'dna:' + str(state['profile_version_id']) + ':gemini-mvp:' + uuid.uuid4().hex
            job_id = uuid.uuid4()
            db.execute(text('''INSERT INTO ia.jobs(id,owner_id,target,job_kind,provider,model,prompt_version,profile_version_id)
              VALUES (:id,:owner,:target,'reader_profile','gemini',:model,:prompt,:profile)'''),
              {'id':job_id,'owner':owner,'target':target,'model':settings.gemini_model,
               'prompt':settings.reader_dna_prompt_version,'profile':state['profile_version_id']})
            db.commit()
    print(json.dumps({'job_id':str(job_id),'provider':'gemini'}),flush=True)
    provider = DiagnosticGemini(api_key=settings.gemini_api_key,model=settings.gemini_model,timeout_seconds=settings.ai_timeout_seconds)
    process_one(provider=provider,settings=settings,owner_id=owner,target=target)
    with SessionLocal() as db:
        result = db.execute(text('SELECT status,attempts,error_code FROM ia.jobs WHERE id=:id'),{'id':job_id}).mappings().one()
        print(json.dumps(dict(result)),flush=True)


if __name__ == '__main__':
    main()
