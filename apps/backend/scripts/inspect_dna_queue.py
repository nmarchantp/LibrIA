"""Read-only local queue diagnostics; never prints credentials or personal texts."""
import json
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import SessionLocal

settings = get_settings()
print(json.dumps({'worker_enabled': settings.gemini_worker_enabled,
                  'model': settings.gemini_model, 'dna_prompt': settings.reader_dna_prompt_version}))
with SessionLocal() as db:
    for name, sql in {
        'queue': "SELECT job_kind,status,prompt_version,error_code,count(*) AS count FROM ia.jobs GROUP BY 1,2,3,4 ORDER BY 1,2",
        'recent_dna_jobs': "SELECT id,job_kind,status,attempts,prompt_version,error_code,created_at,updated_at,not_before,locked_at FROM ia.jobs WHERE job_kind IN ('reader_profile','recommendation') ORDER BY created_at DESC LIMIT 12",
        'dna_versions': "SELECT prompt_version,count(*) AS count,max(created_at) AS latest FROM ia.reader_dna GROUP BY 1",
        'provider_cooldowns': "SELECT provider,model,until_at,reason FROM ia.provider_cooldowns",
    }.items():
        print(name, json.dumps([dict(row) for row in db.execute(text(sql)).mappings()], default=str))
