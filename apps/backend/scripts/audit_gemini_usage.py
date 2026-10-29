"""Read-only audit of persisted Gemini metadata. Never invokes the provider."""
import json
from sqlalchemy import text
from app.core.database import SessionLocal


def main():
    queries = {
        'by_operation_and_status': '''SELECT j.job_kind,j.prompt_version,j.status,j.error_code,
          count(DISTINCT j.id) jobs,count(*) attempts,sum(m.request_count) calls,
          sum(m.input_tokens) input_tokens,sum(m.output_tokens) candidate_tokens,
          sum(m.reasoning_tokens) reasoning_tokens,sum(m.estimated_cost_usd) recorded_cost,
          sum((m.input_tokens*0.30+(m.output_tokens+m.reasoning_tokens)*2.50)/1000000) metadata_cost,
          min(m.request_count) min_calls,max(m.request_count) max_calls,
          max(m.input_tokens) max_input_attempt,max(m.output_tokens) max_output_attempt,
          sum(m.context_fragments) fragments
          FROM ia.usage_metrics m JOIN ia.jobs j ON j.id=m.job_id
          WHERE m.provider='gemini' AND m.model='gemini-3.5-flash-lite'
          GROUP BY j.job_kind,j.prompt_version,j.status,j.error_code''',
        'jobs': '''SELECT job_kind,attempts,status,count(*) jobs FROM ia.jobs
          WHERE provider='gemini' GROUP BY job_kind,attempts,status''',
        'published_traces': '''SELECT j.job_kind,count(*) analyses,
          count(*) FILTER (WHERE jsonb_array_length(
            COALESCE(a.content->'trace'->'provider_request_ids','[]'::jsonb))>0) with_request_ids
          FROM ia.analyses a JOIN ia.jobs j ON j.id=a.job_id
          WHERE a.provider='gemini' GROUP BY j.job_kind''',
        'per_job': '''SELECT j.job_kind,j.prompt_version,j.status,j.error_code,
          count(*) attempts,sum(m.request_count) calls,sum(m.input_tokens) input_tokens,
          sum(m.output_tokens) candidate_tokens,sum(m.reasoning_tokens) reasoning_tokens,
          sum((m.input_tokens*0.30+(m.output_tokens+m.reasoning_tokens)*2.50)/1000000) metadata_cost,
          sum(m.estimated_cost_usd) recorded_cost
          FROM ia.usage_metrics m JOIN ia.jobs j ON j.id=m.job_id
          WHERE m.provider='gemini' AND m.model='gemini-3.5-flash-lite'
          GROUP BY j.id,j.job_kind,j.prompt_version,j.status,j.error_code
          ORDER BY j.job_kind,metadata_cost''',
    }
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        result = {key: [dict(row) for row in db.execute(text(query)).mappings()]
                  for key, query in queries.items()}
        ledger_exists = db.execute(text("SELECT to_regclass('ia.call_ledger') IS NOT NULL")).scalar_one()
        result['accounting'] = {'ledger_available':ledger_exists,
          'cost_basis':'local paid-rate equivalent; not a confirmed Google charge',
          'legacy':'Attempt aggregates may mix unknown reservations and observations; never treat missing metadata as verified zero.'}
        if ledger_exists:
            result['per_call_phase'] = [dict(row) for row in db.execute(text('''
              SELECT phase,state,count(*) calls,sum(input_tokens) input_tokens,
                sum(output_tokens) visible_output_tokens,sum(reasoning_tokens) reasoning_tokens,
                sum(total_tokens) total_tokens,sum(measured_cost_usd) observed_cost,
                sum(reserved_cost_usd) FILTER (WHERE state IN ('reserved','partial','unknown')) unresolved_reservation
              FROM ia.call_ledger WHERE provider='gemini' GROUP BY phase,state ORDER BY phase,state''')).mappings()]
            from app.modules.analytics.call_accounting import monthly_snapshot
            from app.core.config import get_settings
            result['monthly_budget'] = monthly_snapshot(db, get_settings())
        db.rollback()
    print(json.dumps(result, default=str, indent=2))


if __name__ == '__main__':
    main()
