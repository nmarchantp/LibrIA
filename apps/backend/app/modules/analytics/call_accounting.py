"""Committed call ledger. Measured cost and unresolved liability never overlap.

The shared transaction lock serializes admission across every worker. A crashed
process leaves its reservation intact; only a verifiable response releases it.
Legacy attempt rows are included only when that attempt has no call ledger.
"""
import json
import uuid
from decimal import Decimal
from sqlalchemy import text
from app.modules.analytics.providers.base import TokenUsage


class BudgetExhausted(RuntimeError):
    pass


class LocalRateLimited(RuntimeError):
    pass


def usage_cost(settings, usage: TokenUsage) -> Decimal:
    return ((Decimal(usage.input_tokens) * Decimal(str(settings.ai_input_cost_per_million_usd))
             + Decimal(usage.output_tokens + usage.reasoning_tokens)
             * Decimal(str(settings.ai_output_cost_per_million_usd))) / Decimal(1_000_000)).quantize(Decimal('.00000001'))


LEGACY = """NOT EXISTS (SELECT 1 FROM ia.call_ledger c
    WHERE c.job_id=m.job_id AND c.attempt=m.attempt)"""
LIABILITY = """CASE WHEN state IN ('reserved','unknown','partial')
    THEN GREATEST(reserved_cost_usd,COALESCE(measured_cost_usd,0))
    ELSE COALESCE(measured_cost_usd,0) END"""
TOKENS = """CASE WHEN state IN ('reserved','unknown','partial') THEN
    GREATEST(reserved_tokens,COALESCE(total_tokens,0),
      COALESCE(input_tokens,0)+COALESCE(output_tokens,0)+COALESCE(reasoning_tokens,0))
    ELSE GREATEST(COALESCE(total_tokens,0),
      COALESCE(input_tokens,0)+COALESCE(output_tokens,0)+COALESCE(reasoning_tokens,0)) END"""


def monthly_snapshot(db, settings):
    legacy = Decimal(str(db.execute(text(f"""SELECT COALESCE(sum(estimated_cost_usd),0)
      FROM ia.usage_metrics m WHERE provider='gemini'
      AND created_at>=date_trunc('month',now()) AND {LEGACY}""")).scalar_one()))
    row = db.execute(text(f"""SELECT COALESCE(sum({LIABILITY}),0) committed,
      COALESCE(sum(measured_cost_usd) FILTER (WHERE state='measured'),0) measured,
      count(*) FILTER (WHERE state IN ('reserved','unknown','partial')) unresolved
      FROM ia.call_ledger WHERE provider='gemini' AND
        (created_at>=date_trunc('month',now()) OR state IN ('reserved','unknown','partial'))""")).mappings().one()
    committed = legacy + row['committed']
    return {'limit': Decimal(str(settings.ai_monthly_budget_usd)), 'spent': legacy + row['measured'],
            'legacy_unverified': legacy, 'measured': row['measured'],
            'pending_reconciliation': row['committed'] - row['measured'],
            'in_flight': row['unresolved'], 'committed': committed,
            'exhausted': committed >= Decimal(str(settings.ai_monthly_budget_usd))}


def job_totals(db, job_id):
    row = db.execute(text(f"""SELECT count(*) calls,COALESCE(sum({TOKENS}),0) tokens
        FROM ia.call_ledger WHERE job_id=:job"""), {'job': job_id}).mappings().one()
    old = db.execute(text(f"""SELECT COALESCE(sum(request_count),0) calls,
        COALESCE(sum(input_tokens+output_tokens+reasoning_tokens),0) tokens,
        COALESCE(sum(estimated_cost_usd),0) cost FROM ia.usage_metrics m
        WHERE job_id=:job AND {LEGACY}"""), {'job': job_id}).mappings().one()
    # Historical unknown costs have no original token reservation. Reserve a
    # conservative token equivalent at the cheapest configured rate upstream.
    return int(row['calls'] + old['calls']), int(row['tokens'] + old['tokens']), old['cost']


def reserve_call(db, job, attempt, phase, estimated_input, output, settings):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('gemini-monthly-budget'))"))
    current = db.execute(text('SELECT status,attempts,model FROM ia.jobs WHERE id=:job FOR UPDATE'),
                         {'job': job}).mappings().one()
    if current['status'] != 'processing' or current['attempts'] != attempt:
        db.rollback()
        raise BudgetExhausted('lease_lost')
    cooldown = db.execute(text('''SELECT extract(epoch FROM until_at-now()) FROM ia.provider_cooldowns
        WHERE provider='gemini' AND model=:model AND until_at>now()'''), {'model':current['model']}).scalar()
    if cooldown:
        from app.modules.analytics.providers.base import AIProviderQuotaError
        db.rollback()
        raise AIProviderQuotaError('Provider cooldown active', retry_after=float(cooldown))
    recent = db.execute(text("""SELECT count(*) FROM ia.call_ledger
        WHERE provider='gemini' AND created_at>now()-interval '60 seconds'""")).scalar_one()
    if recent >= settings.ai_requests_per_minute:
        db.rollback()
        raise LocalRateLimited('local_rpm_limit')
    calls, tokens, legacy_cost = job_totals(db, job)
    legacy_unknown = db.execute(text(f"""SELECT EXISTS(SELECT 1 FROM ia.usage_metrics m
        WHERE job_id=:job AND {LEGACY} AND final_status<>'succeeded')"""), {'job': job}).scalar_one()
    if legacy_unknown:
        tokens = max(tokens, int(Decimal(str(legacy_cost)) * 1_000_000 /
                                Decimal(str(min(settings.ai_input_cost_per_million_usd, settings.ai_output_cost_per_million_usd)))))
    reservation = estimated_input + output
    cost = usage_cost(settings, TokenUsage(input_tokens=estimated_input, output_tokens=output))
    if calls >= settings.ai_max_calls_per_job or tokens + reservation > settings.ai_job_token_budget:
        db.rollback()
        raise BudgetExhausted('job_budget_exhausted')
    snapshot = monthly_snapshot(db, settings)
    if snapshot['committed'] + cost > snapshot['limit']:
        db.rollback()
        raise BudgetExhausted('monthly_budget_exhausted')
    call_id = uuid.uuid4()
    db.execute(text("""INSERT INTO ia.call_ledger
      (id,job_id,attempt,ordinal,provider,model,phase,state,reserved_tokens,reserved_cost_usd)
      SELECT :id,id,:attempt,:ordinal,provider,model,:phase,'reserved',:tokens,:cost
      FROM ia.jobs WHERE id=:job"""), {'id': call_id, 'job': job, 'attempt': attempt,
       'ordinal': calls + 1, 'phase': phase, 'tokens': reservation, 'cost': cost})
    db.commit()
    return call_id


def settle_call(db, call_id, settings, *, usage=None, error=None, request_id=None, finish_reason=None):
    # Called after every response and before publication/lease validation.
    db.rollback()
    fields = usage.present_fields if usage and usage.present_fields is not None else (
        frozenset(('prompt_token_count','candidates_token_count','thoughts_token_count',
                   'total_token_count','cached_content_token_count')) if usage else frozenset())
    state = 'measured' if usage and usage.verified else 'partial' if usage else 'unknown'
    if error and error.status_code in {400,401,403,404,429} and usage is None:
        state = 'released'  # explicit rejection, not an ambiguous timeout
    names = {'input_tokens':'prompt_token_count','output_tokens':'candidates_token_count',
             'reasoning_tokens':'thoughts_token_count','total_tokens':'total_token_count',
             'cached_input_tokens':'cached_content_token_count'}
    counters = {key: getattr(usage, key) if usage and name in fields else None for key,name in names.items()}
    # Missing optional thought count is known zero only for a consistent complete total.
    if usage and usage.verified and counters['reasoning_tokens'] is None:
        counters['reasoning_tokens'] = 0
    db.execute(text("""UPDATE ia.call_ledger SET state=:state,input_tokens=:input_tokens,
      output_tokens=:output_tokens,reasoning_tokens=:reasoning_tokens,total_tokens=:total_tokens,
      cached_input_tokens=:cached_input_tokens,metadata_fields=CAST(:fields AS jsonb),
      measured_cost_usd=:cost,request_id=:request,finish_reason=:finish,error_code=:error,
      settled_at=now() WHERE id=:id AND state IN ('reserved','unknown','partial')"""),
      {**counters,'id':call_id,'state':state,'fields':json.dumps(sorted(fields)),
       'cost':usage_cost(settings,usage) if usage else None,'request':request_id,
       'finish':finish_reason,'error':error.code if error else None})
    db.commit()


def reconcile_call(db, call_id, settings, *, usage, request_id, verification_reference):
    """Explicit internal reconciliation from verified provider records, never age.

    No HTTP/admin endpoint automatically assumes an ambiguous request was free.
    The reference is an opaque audit ticket, not private provider response text.
    """
    if not usage.verified or not request_id or not verification_reference:
        raise ValueError('Verified usage, provider request id and audit reference required')
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('gemini-monthly-budget'))"))
    row = db.execute(text('SELECT * FROM ia.call_ledger WHERE id=:id FOR UPDATE'), {'id':call_id}).mappings().one()
    if row['state'] not in {'unknown','partial'}:
        raise ValueError('Only unresolved calls can be reconciled')
    if row['request_id'] and row['request_id'] != request_id:
        raise ValueError('Provider request id does not match')
    db.execute(text('''UPDATE ia.call_ledger SET state='measured',input_tokens=:input,
      output_tokens=:output,reasoning_tokens=:reasoning,total_tokens=:total,
      cached_input_tokens=:cached,measured_cost_usd=:cost,request_id=:request,
      metadata_fields=CAST(:fields AS jsonb),
      reconciliation_reference=:reference,settled_at=now() WHERE id=:id'''),
      {'id':call_id,'input':usage.input_tokens,'output':usage.output_tokens,
       'reasoning':usage.reasoning_tokens,'total':usage.total_tokens,'cached':usage.cached_input_tokens,
       'cost':usage_cost(settings,usage),'request':request_id,'reference':verification_reference,
       'fields':json.dumps(sorted(usage.present_fields or ('prompt_token_count','candidates_token_count',
                       'thoughts_token_count','total_token_count','cached_content_token_count')))})
    db.commit()
