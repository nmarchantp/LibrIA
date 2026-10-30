"""Durable Gemini worker for recommendation and terminal-reading jobs.

The worker never consumes ``adaptive_analysis`` rows. A timeout or broken
connection is ambiguous (Gemini may have completed remotely), so retries are
bounded and may duplicate remote computation; PostgreSQL uniqueness constraints
still prevent duplicate publication.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.modules.analytics.gemini_context import (
    EvidenceUnit, canonical_json, chunk_evidence, content_hash, estimate_tokens,
    evidence_index, profile_evidence_units,
)
from app.modules.analytics.gemini_contracts import (
    ProfileChunkSummary, ProfileInterpretation, RecommendationGeneration,
    RecommendationTransportGeneration, recommendation_transport_json_schema,
    ReadingAnalysis, reading_transport_json_schema, normalize_reading_transport,
)
from app.modules.analytics.gemini_prompts import (
    CHUNK_SYSTEM, RECOMMENDATION_SYSTEM, REDUCE_SYSTEM, READING_SYSTEM,
)
from app.modules.analytics.persistence import record_ai_usage, set_reader_profile_status
from app.modules.analytics.providers.base import (
    AIProvider, AIProviderError, AIProviderInvalidResponseError,
    PromptKind, StructuredGenerationRequest, TokenUsage,
)
from app.modules.analytics.providers.factory import build_ai_provider
from app.modules.analytics.call_accounting import (
    BudgetExhausted, LocalRateLimited, monthly_snapshot, reserve_call, settle_call, usage_cost,
)

LOGGER = logging.getLogger(__name__)
SUPPORTED_KINDS = ("recommendation", "reading_event_analysis", "reader_profile")


@dataclass
class AttemptBudget:
    max_calls: int
    max_tokens: int
    calls: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    request_ids: list[str] = field(default_factory=list)
    fragments: int = 0
    # A request can be billed even when no response or usage metadata reaches
    # LibrIA. Keep its conservative reservation until a response is accounted.
    unsettled_tokens: int = 0
    job_id: uuid.UUID | None = None
    attempt: int | None = None

    def reserve(self, estimated_input: int, output: int) -> None:
        if self.calls + 1 > self.max_calls:
            raise AIProviderInvalidResponseError("AI job call budget exceeded")
        known = self.usage.accounted_tokens
        if known + estimated_input + output > self.max_tokens:
            raise AIProviderInvalidResponseError("AI job token budget exceeded")
        self.calls += 1
        self.unsettled_tokens = estimated_input + output

    def add(self, result) -> None:
        old = self.usage
        new = result.usage
        self.usage = TokenUsage(
            input_tokens=old.input_tokens + new.input_tokens,
            output_tokens=old.output_tokens + new.output_tokens,
            total_tokens=old.total_tokens + new.total_tokens,
            cached_input_tokens=old.cached_input_tokens + new.cached_input_tokens,
            reasoning_tokens=old.reasoning_tokens + new.reasoning_tokens,
        )
        if result.provider_request_id:
            self.request_ids.append(result.provider_request_id)
        self.unsettled_tokens = 0


def _attempt_reservation(settings: Settings) -> Decimal:
    """Compatibility display bound only; admission now reserves individual calls."""
    rate = max(Decimal(str(settings.ai_input_cost_per_million_usd)),
               Decimal(str(settings.ai_output_cost_per_million_usd)))
    return (Decimal(settings.ai_job_token_budget) * rate / Decimal(1_000_000)).quantize(Decimal('0.00000001'))


def monthly_budget_snapshot(db: Session, settings: Settings) -> dict[str, Decimal | int | bool]:
    return monthly_snapshot(db, settings)


def claim_next_job(db: Session, settings: Settings) -> dict[str, Any] | None:
    """Claim one due Gemini row or reclaim a lease left by a dead worker."""
    cooldown = db.execute(text('''SELECT EXISTS(SELECT 1 FROM ia.provider_cooldowns
      WHERE provider='gemini' AND model=:model AND until_at>now())'''),
      {'model':settings.gemini_model}).scalar_one()
    if cooldown:
        db.rollback()
        return None
    db.execute(text("""UPDATE ia.call_ledger c SET state='unknown',error_code='worker_lost',settled_at=now()
      FROM ia.jobs j WHERE j.id=c.job_id AND j.attempts=c.attempt AND c.state='reserved'
        AND j.status='processing' AND j.locked_at<now()-:lease*interval '1 second'"""),
      {'lease':settings.ai_job_lease_seconds})
    # A process may die after claiming its final allowed attempt. Such a row is
    # terminalized after the lease instead of remaining processing forever.
    db.execute(text("""UPDATE ia.jobs SET status='failed',error_code='lease_attempts_exhausted',
      locked_at=NULL,updated_at=now() WHERE provider='gemini'
      AND job_kind IN ('recommendation','reading_event_analysis','reader_profile')
      AND status='processing' AND attempts>=:max_attempts
      AND locked_at < now() - (:lease * interval '1 second')"""),
      {"max_attempts": settings.ai_job_max_attempts, "lease": settings.ai_job_lease_seconds})
    db.execute(text("""UPDATE ia.reader_profile_versions p SET status='failed',generated_at=NULL,
      error_code='lease_attempts_exhausted',updated_at=now()
      WHERE p.status<>'ready' AND EXISTS (SELECT 1 FROM ia.jobs j
        WHERE j.profile_version_id=p.id AND j.provider='gemini' AND j.status='failed'
          AND j.error_code='lease_attempts_exhausted')"""))
    # Admission and per-call reservations share this lock across workers.
    # Unresolved calls remain liabilities rather than definitive expenditure.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('gemini-monthly-budget'))"))
    budget = monthly_budget_snapshot(db, settings)
    if budget["exhausted"]:
        db.execute(text("""UPDATE ia.jobs SET status='pending',error_code='monthly_budget_exhausted',locked_at=NULL,
          not_before=date_trunc('month',now())+interval '1 month',updated_at=now()
          WHERE id=(SELECT id FROM ia.jobs WHERE provider='gemini'
            AND job_kind IN ('recommendation','reading_event_analysis','reader_profile')
            AND ((status='pending' AND not_before<=now()) OR
                 (status='processing' AND locked_at < now()-(:lease * interval '1 second')))
            ORDER BY not_before,created_at,id FOR UPDATE SKIP LOCKED LIMIT 1)"""),
          {"lease": settings.ai_job_lease_seconds})
        db.commit()
        return None
    row = db.execute(text("""
        WITH candidate AS (
          SELECT id FROM ia.jobs
          WHERE provider='gemini'
            AND job_kind IN ('recommendation','reading_event_analysis','reader_profile')
            AND attempts < :max_attempts
            AND (
              (status='pending' AND not_before<=now()) OR
              (status='processing' AND locked_at < now() - (:lease * interval '1 second'))
            )
          ORDER BY not_before,created_at,id
          FOR UPDATE SKIP LOCKED LIMIT 1
        )
        UPDATE ia.jobs j SET status='processing',locked_at=now(),attempts=j.attempts+1,
          error_code=NULL,updated_at=now()
        FROM candidate c WHERE j.id=c.id RETURNING j.*
    """), {"max_attempts": settings.ai_job_max_attempts,
            "lease": settings.ai_job_lease_seconds}).mappings().first()
    db.commit()
    return dict(row) if row else None


def _safe_error_code(error: Exception) -> str:
    if isinstance(error, AIProviderError):
        return error.code
    if isinstance(error, ValidationError):
        return "business_validation"
    return "worker_internal"


def _estimated_cost(settings: Settings, usage: TokenUsage) -> Decimal:
    return usage_cost(settings, usage)


def _conservative_attempt_cost(settings: Settings, budget: AttemptBudget) -> Decimal:
    """Known usage plus a worst-rate reserve for the last ambiguous request."""
    known = _estimated_cost(settings, budget.usage)
    rate = max(Decimal(str(settings.ai_input_cost_per_million_usd)),
               Decimal(str(settings.ai_output_cost_per_million_usd)))
    unknown = Decimal(budget.unsettled_tokens) * rate / Decimal(1_000_000)
    return (known + unknown).quantize(Decimal("0.00000001"))


def _touch_lease(db: Session, budget: AttemptBudget) -> None:
    if budget.job_id is None or budget.attempt is None:
        return
    updated = db.execute(text("""UPDATE ia.jobs SET locked_at=now(),updated_at=now()
      WHERE id=:id AND status='processing' AND attempts=:attempt"""),
      {"id": budget.job_id, "attempt": budget.attempt}).rowcount
    db.commit()
    if updated != 1:
        raise LeaseLost("lease_lost")


def _acquire_global_slot(db: Session, settings: Settings, budget: AttemptBudget) -> tuple[int, float]:
    """Cross-process concurrency and RPM limiter using session advisory locks."""
    namespace = 1_947_322_051
    checked_at = time.monotonic()
    while True:
        for slot in range(settings.ai_max_concurrent_requests):
            if db.execute(text("SELECT pg_try_advisory_lock(:namespace,:slot)"),
                          {"namespace": namespace, "slot": slot}).scalar_one():
                db.commit()
                try:
                    _touch_lease(db, budget)
                except Exception:
                    db.execute(text("SELECT pg_advisory_unlock(:namespace,:slot)"),
                               {"namespace": namespace, "slot": slot})
                    db.commit()
                    raise
                return slot, time.monotonic()
        db.rollback()
        if time.monotonic() - checked_at >= 5:
            _touch_lease(db, budget); checked_at = time.monotonic()
        time.sleep(0.05)


def _release_global_slot(db: Session, settings: Settings, slot: int, started: float) -> None:
    # Holding each slot until its share of the minute elapsed makes the aggregate
    # start rate no greater than AI_REQUESTS_PER_MINUTE across worker processes.
    spacing = 60 * settings.ai_max_concurrent_requests / settings.ai_requests_per_minute
    remaining = spacing - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)
    try:
        db.execute(text("SELECT pg_advisory_unlock(:namespace,:slot)"),
                   {"namespace": 1_947_322_051, "slot": slot})
        db.commit()
    except Exception:
        db.rollback()
        raise


def _invoke(db: Session, provider: AIProvider, request: StructuredGenerationRequest,
            budget: AttemptBudget, settings: Settings):
    if budget.job_id:
        # Account lifecycle changes revoke access to queued work as well as HTTP
        # sessions. Check before every provider call, including chunked jobs.
        allowed = db.execute(text("""SELECT EXISTS(SELECT 1 FROM ia.jobs j
          JOIN app.usuarios u ON u.id=j.owner_id WHERE j.id=:id
          AND u.account_status='active' AND u.suspended_at IS NULL)"""), {"id": budget.job_id}).scalar_one()
        if not allowed:
            raise PermanentJobError('account_restricted')
    # UTF-8 bytes provide a deliberately conservative input reservation without
    # another network RPC. Include schema and system text, not just evidence.
    envelope = {"system": request.system_instruction, "user": request.user_content,
                "schema": dict(request.response_schema)}
    if budget.job_id:
        # A queued historical contract must never silently use today's model.
        model = db.execute(text('SELECT model FROM ia.jobs WHERE id=:id'), {'id':budget.job_id}).scalar_one()
        if model != settings.gemini_model:
            raise PermanentJobError('model_contract_changed')
        request = replace(request, model=model)
    estimate = len(canonical_json(envelope).encode('utf-8')) + 256
    if estimate > settings.ai_context_token_budget:
        raise PermanentJobError('complete_context_budget_exceeded')
    slot, started = _acquire_global_slot(db, settings, budget)
    call_id = None
    try:
        while True:
            try:
                call_id = reserve_call(db, budget.job_id, budget.attempt, request.accounting_phase or request.prompt_kind.value,
                                       estimate, request.max_output_tokens or settings.ai_output_token_budget, settings)
                break
            except LocalRateLimited:
                _touch_lease(db, budget)
                time.sleep(.5)
        budget.calls += 1
        budget.unsettled_tokens = estimate + (request.max_output_tokens or settings.ai_output_token_budget)
        try:
            result = provider.generate_structured(request)
        except AIProviderError as error:
            settle_call(db, call_id, settings, usage=error.usage, error=error,
                        request_id=error.request_id, finish_reason=error.finish_reason)
            if error.usage:
                budget.add(type('UsageResult', (), {'usage':error.usage, 'provider_request_id':error.request_id})())
            elif error.status_code in {400,401,403,404,429}:
                budget.unsettled_tokens = 0
            raise
        except Exception:
            settle_call(db, call_id, settings)
            raise
        settle_call(db, call_id, settings, usage=result.usage,
                    request_id=result.provider_request_id, finish_reason=result.finish_reason)
    finally:
        _release_global_slot(db, settings, slot, started)
    if result.provider != "gemini":
        raise AIProviderInvalidResponseError("Unexpected provider for Gemini job")
    budget.add(result)
    return result.content


def _request(model, system: str, payload: Any, settings: Settings, kind: PromptKind):
    return StructuredGenerationRequest.for_pydantic(
        prompt_kind=kind,
        system_instruction=system,
        user_content=canonical_json(payload),
        response_model=model,
        timeout_seconds=settings.ai_timeout_seconds,
        max_output_tokens=settings.ai_output_token_budget,
    )


def _summary_request(system: str, payload: Any, settings: Settings, allowed: set[str], *, event=False):
    def validate(value):
        parsed = ProfileChunkSummary.model_validate(value).model_dump()
        if not set(parsed["evidence_ids"]).issubset(allowed):
            raise ValueError("Profile summary cites unsupported evidence")
        return parsed

    return StructuredGenerationRequest(
        prompt_kind=PromptKind.BOOK_ANALYSIS if event else PromptKind.READER_PROFILE,
        accounting_phase=('event_' if event else 'dna_') + ('reduce' if system == REDUCE_SYSTEM else 'chunk'),
        system_instruction=system,
        user_content=canonical_json(payload),
        response_schema=ProfileChunkSummary.model_json_schema(), validator=validate,
        timeout_seconds=settings.ai_timeout_seconds,
        max_output_tokens=settings.ai_output_token_budget,
    )


def _chunk_cache(db: Session, owner: uuid.UUID, chunk_hash: str, model: str,
                 prompt: str) -> dict[str, Any] | None:
    target = f"profile-fragment:{chunk_hash}:{content_hash({'model': model, 'prompt': prompt})[:16]}"
    return db.execute(text("""SELECT content FROM ia.analyses
        WHERE owner_id=:owner AND target=:target AND data_hash=:hash
          AND provider='gemini' AND model=:model AND prompt_version=:prompt AND valid
        ORDER BY created_at DESC LIMIT 1"""),
        {"owner": owner, "target": target, "hash": chunk_hash,
         "model": model, "prompt": prompt}).scalar()


def _save_chunk(db: Session, owner: uuid.UUID, chunk_hash: str, content: dict[str, Any],
                model: str, prompt: str) -> None:
    target = f"profile-fragment:{chunk_hash}:{content_hash({'model': model, 'prompt': prompt})[:16]}"
    db.execute(text("""INSERT INTO ia.analyses
        (id,owner_id,target,version,data_hash,content,model,prompt_version,provider)
        VALUES (:id,:owner,:target,1,:hash,CAST(:content AS jsonb),:model,:prompt,'gemini')
        ON CONFLICT (owner_id,target,version) DO NOTHING"""),
        {"id": uuid.uuid4(), "owner": owner, "target": target,
         "hash": chunk_hash, "content": canonical_json(content), "model": model, "prompt": prompt})
    db.commit()


def _summarize_profile(db: Session, provider: AIProvider, job: dict[str, Any], payload: dict[str, Any],
                       settings: Settings, budget: AttemptBudget) -> tuple[dict[str, Any], list[dict[str, Any]], list[EvidenceUnit]]:
    units = profile_evidence_units(payload)
    chunks = chunk_evidence(units, min(settings.ai_chunk_token_budget, max(100, (settings.ai_context_token_budget - 3500) // 5)))
    budget.fragments += len(chunks)
    summaries: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for chunk in chunks:
        cached = _chunk_cache(db, job["owner_id"], chunk["hash"], job["model"], f"{job['prompt_version']}:chunk-v1")
        allowed = {item["evidence_id"] for item in chunk["evidence"]}
        if cached is None:
            value = _invoke(db, provider, _summary_request(CHUNK_SYSTEM, chunk, settings, allowed), budget, settings)
            _save_chunk(db, job["owner_id"], chunk["hash"], value, job["model"], f"{job['prompt_version']}:chunk-v1")
            reused = False
        else:
            value = ProfileChunkSummary.model_validate(cached).model_dump()
            if not set(value["evidence_ids"]).issubset(allowed):
                raise ValueError("Cached profile summary cites unsupported evidence")
            reused = True
        summaries.append(value)
        traces.append({"hash": chunk["hash"], "index": chunk["index"], "total": chunk["total"],
                       "evidence_ids": sorted({item["evidence_id"] for item in chunk["evidence"]}),
                       "reused": reused})

    # Hierarchical reduction keeps the final prompt bounded. Each reduction is
    # also content-addressed and reusable.
    summary_target = max(100, (settings.ai_context_token_budget - 3500) // 8)
    while estimate_tokens({"summaries": summaries}) > summary_target:
        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        for summary in summaries:
            if current and estimate_tokens({"summaries": [*current, summary]}) > min(settings.ai_chunk_token_budget, max(100, (settings.ai_context_token_budget - 3500) // 5)):
                groups.append(current); current = []
            current.append(summary)
        if current:
            groups.append(current)
        if len(groups) >= len(summaries):
            raise AIProviderInvalidResponseError("Profile summaries cannot fit the context budget")
        reduced: list[dict[str, Any]] = []
        for group in groups:
            budget.fragments += 1
            value_hash = content_hash(group)
            allowed = {evidence for summary in group for evidence in summary["evidence_ids"]}
            cached = _chunk_cache(db, job["owner_id"], value_hash, job["model"], f"{job['prompt_version']}:reduce-v1")
            if cached is None:
                value = _invoke(db, provider, _summary_request(REDUCE_SYSTEM, {"summaries": group},
                                                           settings, allowed), budget, settings)
                _save_chunk(db, job["owner_id"], value_hash, value, job["model"], f"{job['prompt_version']}:reduce-v1")
            else:
                value = ProfileChunkSummary.model_validate(cached).model_dump()
                if not set(value["evidence_ids"]).issubset(allowed):
                    raise ValueError("Cached reduction cites unsupported evidence")
            reduced.append(value)
        summaries = reduced
    return {"summaries": summaries}, traces, units


def _catalog_candidates(db: Session, owner: uuid.UUID, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(text("""
      SELECT w.id AS work_id,w.identity_key,w.title,left(COALESCE(w.description,''),2000) AS description,
        w.categories,w.original_language,
        COALESCE((SELECT jsonb_agg(a.name ORDER BY wa.position,a.id)
          FROM app.obras_autores wa JOIN app.autores a ON a.id=wa.author_id
          WHERE wa.work_id=w.id),'[]'::jsonb) AS authors,
        e.id AS edition_id,e.title AS edition_title,e.language,e.page_count,e.cover_url,e.isbn13,e.isbn10,
        COALESCE((SELECT jsonb_agg(jsonb_build_object('provider',s.provider,'external_id',s.external_id,
                          'validation_status',s.validation_status) ORDER BY s.provider,s.external_id)
          FROM app.fuentes_catalogo s WHERE s.edition_id=e.id),'[]'::jsonb) AS sources
      FROM app.obras w
      JOIN LATERAL (SELECT ed.* FROM app.ediciones ed WHERE ed.work_id=w.id
                    ORDER BY (ed.cover_url IS NOT NULL) DESC,ed.created_at,ed.id LIMIT 1) e ON true
      WHERE length(trim(w.title))>0
        AND EXISTS (SELECT 1 FROM app.obras_autores wa WHERE wa.work_id=w.id)
        AND NOT EXISTS (SELECT 1 FROM app.entradas_biblioteca le
                        WHERE le.user_id=:owner AND le.work_id=w.id)
        AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d
                        WHERE d.entity_type IN ('obras','work') AND d.entity_id=w.id)
      ORDER BY w.id LIMIT :limit
    """), {"owner": owner, "limit": limit}).mappings().all()
    result = [{key: (str(value) if isinstance(value, uuid.UUID) else value) for key, value in dict(row).items()}
              for row in rows if row["authors"]]
    from app.modules.books.canonical import enabled, identity_snapshot
    if enabled():
        snapshot = identity_snapshot(db)
        owned = {snapshot.root(key) for key in db.execute(text('SELECT work_id FROM app.entradas_biblioteca WHERE user_id=:owner'), {'owner':owner}).scalars()}
        unique = {}
        for row in result:
            root = snapshot.root(row['work_id'])
            if root not in owned:
                unique.setdefault(root, {**row, 'work_id':str(root), 'physical_work_id':row['work_id'], 'identity_key':None,
                    'canonical_work_id':str(root)})
        return list(unique.values())
    return result


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _merge_profile_summaries(summaries: list[dict[str, Any]]) -> ProfileInterpretation:
    fields = (
        "narrative_preferences", "character_preferences", "themes_and_conflicts",
        "genres_and_styles", "emotional_patterns", "interests_from_notes_and_theories",
        "rating_patterns", "evidence_ids",
    )
    merged = {
        field: list(dict.fromkeys(
            value for summary in summaries for value in summary.get(field, [])
        ))[:200 if field == "evidence_ids" else 12]
        for field in fields
    }
    return ProfileInterpretation.model_validate(merged)


def _validate_recommendations(raw: Any, candidates: list[dict[str, Any]], allowed_evidence: set[str],
                              profile: ProfileInterpretation | None = None) -> dict[str, Any]:
    if profile is not None:
        # Gemini occasionally repeats evidence or echoes catalog display fields
        # even under a strict response schema. Keep only transport fields and
        # let LibrIA validate every identifier against its own trusted data.
        raw_items = raw.get("recommendations", []) if isinstance(raw, dict) else []
        normalized = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence_ids", [])
            normalized.append({
                "work_id": item.get("work_id"),
                "justification": item.get("justification"),
                "evidence_ids": list(dict.fromkeys(evidence)) if isinstance(evidence, list) else [],
            })
        transport = RecommendationTransportGeneration.model_validate(
            {"recommendations": normalized}
        ).model_dump()
        parsed = {"profile": profile.model_dump(), "recommendations": transport["recommendations"]}
    else:
        parsed = RecommendationGeneration.model_validate(raw).model_dump()
    lookup = {str(item["work_id"]): item for item in candidates}
    seen_works: set[str] = set()
    seen_identities: set[str] = set()
    valid: list[dict[str, Any]] = []
    for selection in parsed["recommendations"]:
        candidate = lookup.get(selection["work_id"])
        if candidate is None or selection["work_id"] in seen_works:
            continue
        identity = candidate.get("identity_key") or selection["work_id"]
        if identity in seen_identities:
            continue
        authors = [str(value) for value in candidate["authors"]]
        if profile is None:
            if _norm(selection["title"]) != _norm(candidate["title"]):
                raise ValueError("Recommendation title does not match the catalog")
            if not any(_norm(selection["author"]) == _norm(author) for author in authors):
                raise ValueError("Recommendation author does not match the catalog")
        evidence_ids = [value for value in selection["evidence_ids"] if value in allowed_evidence]
        if not evidence_ids:
            continue
        seen_works.add(selection["work_id"]); seen_identities.add(identity)
        valid.append({
            "work_id": selection["work_id"], "title": candidate["title"], "authors": authors,
            "edition_id": candidate["edition_id"], "cover_url": candidate["cover_url"],
            "sources": candidate["sources"], "justification": selection["justification"],
            "evidence_ids": evidence_ids,
        })
    if not valid:
        raise ValueError("No grounded recommendation matches the verified batch")
    parsed["recommendations"] = valid
    return parsed


def _candidate_batches(profile_input: dict[str, Any], candidates: list[dict[str, Any]],
                       token_budget: int) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for candidate in candidates:
        proposed = [*current, candidate]
        if current and estimate_tokens({**profile_input, "verified_candidates": proposed}) > token_budget:
            batches.append(current); current = [candidate]
        else:
            current = proposed
        if estimate_tokens({**profile_input, "verified_candidates": current}) > token_budget:
            raise PermanentJobError("catalog_candidate_exceeds_context_budget")
    if current:
        batches.append(current)
    return batches


def _latest_profile_is(db: Session, owner: uuid.UUID, profile: uuid.UUID) -> bool:
    from app.modules.books.canonical import enabled
    if enabled():
        from app.modules.analytics.recommendation_sync import _latest_state
        state = _latest_state(db, owner)
        return bool(state and state['profile_version_id'] == profile)
    value = db.execute(text("""SELECT s.profile_version_id
      FROM ia.reader_profile_etl_states s JOIN analytics.ejecuciones_etl e ON e.id=s.etl_run_id
      WHERE s.owner_id=:owner AND e.status='succeeded'
        AND e.run_kind IN ('daily','manual')
      ORDER BY e.source_cutoff_at DESC,e.finished_at DESC NULLS LAST,s.created_at DESC LIMIT 1"""),
      {"owner": owner}).scalar()
    return value == profile


def _persist_evidence(db: Session, analysis_id: uuid.UUID, ids: set[str],
                      lookup: dict[str, EvidenceUnit]) -> None:
    for key in sorted(ids):
        source = lookup.get(key)
        if source is None:
            raise ValueError("Unknown evidence id")
        db.execute(text("""INSERT INTO ia.evidence
          (analysis_id,source_key,source_kind,source_id,work_id,source_hash)
          VALUES (:analysis,:key,:kind,:source,:work,:hash) ON CONFLICT DO NOTHING"""),
          {"analysis": analysis_id, "key": key, "kind": source.source_kind,
           "source": source.source_id, "work": source.work_id, "hash": content_hash(source.content)})


def _rank_candidates(candidates, profile):
    import re
    terms = set(re.findall(r'\w{4,}', canonical_json(profile).casefold()))
    ranked = sorted(candidates, key=lambda c: (
        -len(terms.intersection(re.findall(r'\w{4,}', canonical_json(
            {k:c.get(k) for k in ('title','description','categories')}).casefold()))), str(c['work_id'])))
    # A round-robin across primary authors keeps lower-ranked voices available.
    groups = {}
    for candidate in ranked:
        groups.setdefault(tuple(candidate.get('authors', [])[:1]), []).append(candidate)
    result = []
    while groups:
        for key in list(groups):
            result.append(groups[key].pop(0))
            if not groups[key]:
                del groups[key]
    return result


def _ensure_dna(db, provider, job, profile, settings, budget):
    from app.modules.analytics.reader_dna import dna_fingerprint, find_dna
    fingerprint = dna_fingerprint(profile['payload'])
    key = f"dna:{job['owner_id']}:{fingerprint}:{job['model']}:{settings.reader_dna_prompt_version}"
    # Session lock survives commits made by the ledger and cache. Keep leases
    # alive while another worker builds the exact same DNA.
    while not db.execute(text('SELECT pg_try_advisory_lock(hashtextextended(:key,0))'), {'key':key}).scalar_one():
        db.rollback()
        _touch_lease(db, budget)
        time.sleep(.1)
    db.commit()
    try:
        cached = find_dna(db, job['owner_id'], profile['payload'], job['model'], settings.reader_dna_prompt_version)
        if cached:
            return dict(cached)
        dna_job = {**job, 'prompt_version': settings.reader_dna_prompt_version}
        summary, traces, units = _summarize_profile(db, provider, dna_job, profile['payload'], settings, budget)
        content = _merge_profile_summaries(summary['summaries']).model_dump()
        analysis_id = uuid.uuid4()
        target = f"profile:{profile['id']}:dna:{settings.reader_dna_prompt_version}"
        db.execute(text('''INSERT INTO ia.analyses
          (id,owner_id,target,version,data_hash,content,model,prompt_version,provider,job_id)
          VALUES (:id,:owner,:target,COALESCE((SELECT max(version)+1 FROM ia.analyses
            WHERE owner_id=:owner AND target=:target),1),:hash,CAST(:content AS jsonb),:model,:prompt,'gemini',:job)'''),
          {'id':analysis_id,'owner':job['owner_id'],'target':target,'hash':fingerprint,
           'content':canonical_json({'profile':content,'trace':{'chunks':traces,'provider_request_ids':budget.request_ids}}),'model':job['model'],
           'prompt':settings.reader_dna_prompt_version,'job':job['id']})
        if profile['payload'].get('identity_version'):
            db.execute(text('UPDATE ia.analyses SET identity_version=:version WHERE id=:id'), {'version':profile['payload']['identity_version'],'id':analysis_id})
        _persist_evidence(db, analysis_id, set(content['evidence_ids']), evidence_index(units))
        result = db.execute(text('''INSERT INTO ia.reader_dna
          (analysis_id,owner_id,source_profile_id,source_hash,model,prompt_version,content,trace)
          VALUES (:analysis,:owner,:profile,:hash,:model,:prompt,CAST(:content AS jsonb),CAST(:trace AS jsonb))
          ON CONFLICT (owner_id,source_hash,model,prompt_version) DO UPDATE SET
            analysis_id=EXCLUDED.analysis_id,content=EXCLUDED.content,trace=EXCLUDED.trace,created_at=now()
          RETURNING *'''),
          {'analysis':analysis_id,'owner':job['owner_id'],'profile':profile['id'],'hash':fingerprint,'model':job['model'],
           'prompt':settings.reader_dna_prompt_version,'content':canonical_json(content),
           'trace':canonical_json({'chunks':traces,'provider_request_ids':budget.request_ids})}).mappings().one()
        db.commit()
        return dict(result)
    finally:
        db.rollback()
        db.execute(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'), {'key':key})
        db.commit()


def _process_dna(db, provider, job, settings, budget):
    profile = db.execute(text('SELECT * FROM ia.reader_profile_versions WHERE id=:id AND owner_id=:owner'),
                         {'id':job['profile_version_id'],'owner':job['owner_id']}).mappings().one()
    if not _latest_profile_is(db, job['owner_id'], profile['id']):
        raise ObsoleteJob('obsolete_profile')
    _ensure_dna(db, provider, job, profile, settings, budget)


def _process_recommendation(db: Session, provider: AIProvider, job: dict[str, Any],
                            settings: Settings, budget: AttemptBudget) -> None:
    profile = db.execute(text("""SELECT * FROM ia.reader_profile_versions
      WHERE id=:id AND owner_id=:owner"""),
      {"id": job["profile_version_id"], "owner": job["owner_id"]}).mappings().first()
    if not profile or not profile["payload"] or not _latest_profile_is(db, job["owner_id"], profile["id"]):
        raise ObsoleteJob("obsolete_profile")
    candidates = _catalog_candidates(db, job["owner_id"], settings.ai_recommendation_candidate_limit)
    if not candidates:
        raise PermanentJobError("no_verified_candidates")
    dna = _ensure_dna(db, provider, job, profile, settings, budget)
    units = profile_evidence_units(profile['payload'])
    profile_input = {'summaries': [dna['content']]}
    traces = dna['trace'].get('chunks', [])
    allowed = set(evidence_index(units))
    # Rank locally and interleave authors before sending only semantic fields.
    candidates = _rank_candidates(candidates, dna['content'])
    wire_candidates = [{key:c.get(key) for key in ('work_id','title','authors','description','categories','original_language')}
                       for c in candidates]
    batches = _candidate_batches(profile_input, wire_candidates, max(100, (settings.ai_context_token_budget - 2500) // 5))

    final_profile = _merge_profile_summaries(profile_input["summaries"])

    def generate_from(pool: list[dict[str, Any]]) -> dict[str, Any]:
        pool_ids = {c['work_id'] for c in pool}
        trusted_pool = [c for c in candidates if c['work_id'] in pool_ids]
        def validate(value):
            return _validate_recommendations(value, trusted_pool, allowed, profile=final_profile)
        batch_hash = content_hash({'profile':profile_input,'candidates':pool,'system':RECOMMENDATION_SYSTEM})
        cache_prompt = f"{job['prompt_version']}:selection-v1"
        cached = _chunk_cache(db, job['owner_id'], batch_hash, job['model'], cache_prompt)
        if cached:
            return validate(cached)
        request = StructuredGenerationRequest(
            prompt_kind=PromptKind.RECOMMENDATIONS,
            system_instruction=RECOMMENDATION_SYSTEM,
            user_content=canonical_json({**profile_input, "verified_candidates": pool}),
            response_schema=recommendation_transport_json_schema(), validator=validate,
            timeout_seconds=settings.ai_timeout_seconds, max_output_tokens=settings.ai_output_token_budget,
        )
        value = _invoke(db, provider, request, budget, settings)
        _save_chunk(db, job['owner_id'], batch_hash, value, job['model'], cache_prompt)
        return value

    if len(batches) == 1:
        result = generate_from(batches[0])
    else:
        selected: list[dict[str, Any]] = []
        selected_works: set[str] = set()
        selected_identities: set[str] = set()
        candidate_lookup = {str(item["work_id"]): item for item in candidates}
        for batch in batches:
            try:
                partial = generate_from(batch)
            except AIProviderInvalidResponseError:
                # One malformed catalog batch must not discard other grounded,
                # independently validated selections.
                continue
            for recommendation in partial["recommendations"]:
                work_id = recommendation["work_id"]
                candidate = candidate_lookup[work_id]
                identity = candidate.get("identity_key") or work_id
                if work_id in selected_works or identity in selected_identities:
                    continue
                selected.append(recommendation)
                selected_works.add(work_id)
                selected_identities.add(identity)
                if len(selected) == 8:
                    break
            if len(selected) == 8:
                break
        if not selected:
            raise AIProviderInvalidResponseError("No catalog batch produced grounded recommendations")
        result = {"profile": final_profile.model_dump(), "recommendations": selected}
    if not _latest_profile_is(db, job["owner_id"], profile["id"]):
        raise ObsoleteJob("obsolete_profile")
    current = db.execute(text("SELECT status,attempts FROM ia.jobs WHERE id=:id FOR UPDATE"),
                         {"id": job["id"]}).mappings().one()
    if current["status"] != "processing" or current["attempts"] != job["attempts"]:
        raise LeaseLost("lease_lost")
    analysis_id = uuid.uuid4()
    all_ids = set(result["profile"]["evidence_ids"])
    for item in result["recommendations"]:
        all_ids.update(item["evidence_ids"])
    if not all_ids.issubset(allowed):
        raise ValueError("Profile interpretation cites unsupported evidence")
    stored = {**result, "trace": {"profile_hash": profile["data_hash"], "chunks": traces,
                                    "provider_request_ids": budget.request_ids}}
    db.execute(text("""INSERT INTO ia.analyses
      (id,owner_id,target,version,data_hash,content,model,prompt_version,provider,job_id)
      VALUES (:id,:owner,:target,:version,:hash,CAST(:content AS jsonb),:model,:prompt,'gemini',:job)"""),
      {"id": analysis_id, "owner": job["owner_id"],
       "target": f"profile:{profile['id']}:{job['prompt_version']}",
       "version": profile["version"], "hash": profile["data_hash"], "content": canonical_json(stored),
       "model": job["model"], "prompt": job["prompt_version"], "job": job["id"]})
    if profile['payload'].get('identity_version'):
        db.execute(text('UPDATE ia.analyses SET identity_version=:version WHERE id=:id'), {'version':profile['payload']['identity_version'],'id':analysis_id})
    _persist_evidence(db, analysis_id, all_ids, evidence_index(units))
    etl_run = profile["etl_run_id"]
    db.execute(text("""UPDATE ia.recomendaciones_ia SET is_current=false,invalidated_at=now(),
      invalidated_by_etl_run_id=:run WHERE owner_user_id=:owner AND is_current"""),
      {"owner": job["owner_id"], "run": etl_run})
    db.execute(text("""INSERT INTO ia.recomendaciones_ia
      (id,owner_user_id,data_hash,model,version,content,provider,profile_version_id,job_id)
      VALUES (:id,:owner,:hash,:model,:prompt,CAST(:content AS jsonb),'gemini',:profile,:job)"""),
      {"id": uuid.uuid4(), "owner": job["owner_id"], "hash": content_hash({"profile": profile["data_hash"], "candidates": [c["work_id"] for c in candidates]}),
       "model": job["model"], "prompt": job["prompt_version"], "content": canonical_json(stored),
       "profile": profile["id"], "job": job["id"]})
    set_reader_profile_status(db, profile_version_id=profile["id"], status="ready")


def _individual_context(db: Session, job: dict[str, Any]) -> tuple[dict[str, Any], list[EvidenceUnit]]:
    row = db.execute(text("""SELECT ev.id AS event_id,ev.kind,ev.reason,ev.reflection,ev.created_at AS event_at,
      ev.page,ev.total_pages,r.current_page,r.total_pages AS reading_total_pages,r.id AS reading_id,r.status,r.notebook,r.abandonment_reason,
      r.started_at,r.finished_at,r.abandoned_at,r.work_id,r.edition_id,w.title,w.description,w.categories,
      ed.title AS edition_title,ed.language,ed.page_count,
      COALESCE((SELECT jsonb_agg(a.name ORDER BY wa.position,a.id) FROM app.obras_autores wa
        JOIN app.autores a ON a.id=wa.author_id WHERE wa.work_id=w.id),'[]'::jsonb) AS authors
      FROM app.eventos_lectura ev JOIN app.lecturas r ON r.id=ev.reading_id
      JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id AND le.user_id=:owner
      JOIN app.obras w ON w.id=r.work_id LEFT JOIN app.ediciones ed ON ed.id=r.edition_id
      WHERE ev.id=:event AND ev.actor_user_id=:owner AND ev.kind IN ('finish','abandon')"""),
      {"event": job["reading_event_id"], "owner": job["owner_id"]}).mappings().first()
    if not row:
        raise ObsoleteJob("reading_event_unavailable")
    work, reading, event = row["work_id"], row["reading_id"], row["event_id"]
    units = [
        EvidenceUnit(f"event:{event}", "reading_event", event, work,
                     {key: row[key] for key in ("kind", "reason", "reflection", "event_at", "page", "total_pages")}),
        EvidenceUnit(f"reading:{reading}", "reading", reading, work,
                     {key: row[key] for key in ("status", "current_page", "reading_total_pages", "abandonment_reason", "started_at", "finished_at", "abandoned_at")}),
        EvidenceUnit(f"metadata:{work}", "metadata", work, work,
                     {key: row[key] for key in ("title", "description", "categories", "authors", "edition_title", "language", "page_count")}),
    ]
    if row["notebook"]:
        units.append(EvidenceUnit(f"notebook:{reading}", "notebook", reading, work, row["notebook"]))
    review = db.execute(text("""SELECT rv.id,rv.body,rv.rating,rv.dimension_ratings,rv.status,rv.revision_number
      FROM app.resenas rv JOIN app.perfiles p ON p.id=rv.author_profile_id
      WHERE p.kind='personal' AND p.owner_user_id=:owner AND rv.created_by_user_id=:owner
        AND rv.work_id=:work ORDER BY rv.updated_at DESC,rv.id DESC LIMIT 1"""),
      {"owner": job["owner_id"], "work": work}).mappings().first()
    if review:
        units.append(EvidenceUnit(f"review:{review['id']}:{review['revision_number']}", "review", review["id"], work,
                                  {key: review[key] for key in ("body", "rating", "dimension_ratings", "status")}))
    from app.modules.books.canonical import enabled, canonical_members
    work_ids = list(canonical_members(db, work)) if enabled() else [work]
    posts = db.execute(text("""SELECT po.id,po.publication_type,po.body,po.created_at
      FROM app.publicaciones po JOIN app.perfiles p ON p.id=po.author_profile_id
      WHERE p.kind='personal' AND p.owner_user_id=:owner AND po.user_id=:owner
        AND po.work_id=ANY(:works) AND po.publication_type IN ('note','theory') AND NOT po.legacy_content
      ORDER BY po.created_at,po.id"""), {"owner": job["owner_id"], "works": work_ids}).mappings().all()
    for post in posts:
        units.append(EvidenceUnit(f"{post['publication_type']}:{post['id']}", post["publication_type"],
                                  post["id"], work, {"body": post["body"], "created_at": post["created_at"]}))
    from app.modules.books.canonical import enabled, identity_snapshot
    identity = None
    if enabled():
        from dataclasses import replace
        from app.modules.books.consistency import current_reviews
        snapshot = identity_snapshot(db)
        root = snapshot.root(work)
        units = [replace(unit, work_id=root) for unit in units if unit.source_kind != 'review']
        personal_profiles = set(db.execute(text("SELECT id FROM app.perfiles WHERE kind='personal' AND owner_user_id=:owner"),
                                            {'owner':job['owner_id']}).scalars())
        reviews = [r for r in current_reviews(db, {work}, reader_id=job['owner_id'])
                   if r.author_profile_id in personal_profiles]
        for current in reviews:
            units.append(EvidenceUnit(f'review:{current.id}:{current.revision_number}', 'review', current.id, root,
                {'body':current.body, 'rating':current.rating, 'dimension_ratings':current.dimension_ratings, 'status':current.status}))
        work, identity = root, snapshot.version
    payload = {"event_kind": row["kind"], "reading_id": str(reading), "work_id": str(work),
               **({'identity_version':identity} if identity else {}),
               "evidence": [unit.wire() for unit in units]}
    return payload, units


def _event_summary(db, provider, job, system, payload, settings, allowed, budget):
    digest = content_hash({'event':str(job['reading_event_id']),'system':system,'payload':payload})
    prompt = f"{job['prompt_version']}:event-summary-v1"
    cached = _chunk_cache(db, job['owner_id'], digest, job['model'], prompt)
    if cached is not None:
        return _summary_request(system, payload, settings, allowed, event=True).validate(cached)
    result = _invoke(db, provider, _summary_request(system,payload,settings,allowed,event=True),budget,settings)
    db.execute(text('SELECT reading_event_id FROM ia.reading_analysis_requests WHERE reading_event_id=:event FOR UPDATE'),
               {'event':job['reading_event_id']})
    if not db.execute(text('SELECT payload FROM ia.reading_analysis_snapshots WHERE job_id=:job'), {'job':job['id']}).scalar():
        raise ObsoleteJob('withdrawn_evidence')
    _save_chunk(db,job['owner_id'],digest,result,job['model'],prompt)
    return result


def _process_individual(db: Session, provider: AIProvider, job: dict[str, Any],
                        settings: Settings, budget: AttemptBudget) -> None:
    from app.modules.analytics.reading_analysis import context, fingerprint, reusable, IneligibleReading
    snapshot = db.execute(text('SELECT payload FROM ia.reading_analysis_snapshots WHERE job_id=:job'),
                          {'job':job['id']}).scalar()
    if not snapshot:
        raise ObsoleteJob('nightly_preparation_required')
    try:
        current, _ = context(db, job['owner_id'], job['reading_event_id'])
    except IneligibleReading as error:
        raise ObsoleteJob(str(error)) from error
    if fingerprint(current) != job['evidence_hash']:
        raise ObsoleteJob('obsolete_nightly_evidence')
    if reusable(db, job['owner_id'], job['reading_event_id'], job['evidence_hash'], settings):
        return
    payload = snapshot
    units = [EvidenceUnit(item['evidence_id'], item['source_kind'],
              uuid.UUID(item['evidence_id'].split(':')[1]),
              uuid.UUID(item['work_id']) if item.get('work_id') else None, item['content'])
             for item in snapshot['evidence']]
    source_hash = fingerprint(snapshot)
    if len(canonical_json(payload).encode('utf-8')) > settings.ai_context_token_budget - 3500:
        # The same complete fragmentation strategy is exposed to the model in a
        # single structured envelope. Refuse if even that envelope cannot fit;
        # never silently truncate private text.
        fragments = chunk_evidence(units, min(settings.ai_chunk_token_budget, max(100, (settings.ai_context_token_budget - 3500) // 5)))
        budget.fragments += len(fragments)
        summaries = []
        for fragment in fragments:
            allowed_fragment = {item["evidence_id"] for item in fragment["evidence"]}
            summaries.append(_event_summary(db, provider, job,
                                             CHUNK_SYSTEM.replace('reader profile', 'concrete reading experience'), fragment,
                                             settings, allowed_fragment, budget))
        while estimate_tokens({"fragment_summaries": summaries}) > max(100, (settings.ai_context_token_budget - 3500) // 8):
            groups, current = [], []
            for summary in summaries:
                if current and estimate_tokens({"summaries": [*current, summary]}) > min(settings.ai_chunk_token_budget, max(100, (settings.ai_context_token_budget - 3500) // 5)):
                    groups.append(current); current = []
                current.append(summary)
            if current:
                groups.append(current)
            if len(groups) >= len(summaries):
                raise AIProviderInvalidResponseError("Individual summaries cannot fit the context budget")
            reduced = []
            for group in groups:
                budget.fragments += 1
                allowed_group = {evidence for summary in group for evidence in summary["evidence_ids"]}
                reduced.append(_event_summary(db, provider, job, REDUCE_SYSTEM, {'summaries':group},
                                               settings, allowed_group, budget))
            summaries = reduced
        payload = {"event_kind": payload["event_kind"], "reading_id": payload["reading_id"],
                   "work_id": payload["work_id"], "fragment_summaries": summaries,
                   "all_evidence_ids": sorted(evidence_index(units))}
    allowed = set(evidence_index(units))

    def validate(value):
        parsed = ReadingAnalysis.model_validate(normalize_reading_transport(value)).model_dump()
        if parsed["event_kind"] != payload["event_kind"] or not set(parsed["evidence_ids"]).issubset(allowed):
            raise ValueError("Individual analysis has unsupported event or evidence")
        expected = {('experience_summary', 0)} | {(field, index)
            for field in ('valued_elements','friction_points','themes_and_interests','emotional_response','rating_observations')
            for index in range(len(parsed[field]))}
        citations = parsed['observation_evidence']
        if {(item['field'],item['index']) for item in citations} != expected or len(citations) != len(expected):
            raise ValueError('Individual observations require exact evidence references')
        cited = set(parsed['evidence_ids'])
        if any(not set(item['evidence_ids']).issubset(cited) for item in citations):
            raise ValueError('Individual observation cites unsupported evidence')
        return parsed

    request = StructuredGenerationRequest(
        prompt_kind=PromptKind.BOOK_ANALYSIS, system_instruction=READING_SYSTEM,
        user_content=canonical_json(payload), response_schema=reading_transport_json_schema(
            evidence_ids=sorted(allowed), event_kind=payload['event_kind']),
        validator=validate, timeout_seconds=settings.ai_timeout_seconds,
        max_output_tokens=settings.ai_output_token_budget,
    )
    result = _invoke(db, provider, request, budget, settings)
    # Serialize publication with source-change request triggers. A changed source
    # leaves this immutable snapshot historical; book_state only calls it current
    # when its hash matches. A withdrawn review forbids retaining new output.
    db.execute(text('SELECT reading_event_id FROM ia.reading_analysis_requests WHERE reading_event_id=:event FOR UPDATE'),
               {'event':job['reading_event_id']})
    try:
        context(db, job['owner_id'], job['reading_event_id'])
    except IneligibleReading as error:
        raise ObsoleteJob(str(error)) from error
    if not db.execute(text('SELECT payload FROM ia.reading_analysis_snapshots WHERE job_id=:job'),
                      {'job':job['id']}).scalar():
        raise ObsoleteJob('withdrawn_evidence')
    locked = db.execute(text("SELECT status,attempts FROM ia.jobs WHERE id=:id FOR UPDATE"),
                        {"id": job["id"]}).mappings().one()
    if locked["status"] != "processing" or locked["attempts"] != job["attempts"]:
        raise LeaseLost("lease_lost")
    analysis_id = uuid.uuid4()
    stored = {**result, "trace": {"context_hash": content_hash(payload),
                                    "provider_request_ids": budget.request_ids}}
    db.execute(text("""INSERT INTO ia.analyses
      (id,owner_id,target,version,data_hash,content,model,prompt_version,provider,job_id,reading_event_id)
      VALUES (:id,:owner,:target,COALESCE((SELECT max(version)+1 FROM ia.analyses
        WHERE owner_id=:owner AND target=:target),1),:hash,CAST(:content AS jsonb),:model,:prompt,'gemini',:job,:event)"""),
      {"id": analysis_id, "owner": job["owner_id"], "target": f"reading-event:{job['reading_event_id']}",
       "hash": source_hash, "content": canonical_json(stored), "model": job["model"],
       "prompt": job["prompt_version"], "job": job["id"], "event": job["reading_event_id"]})
    if payload.get('identity_version'):
        db.execute(text('UPDATE ia.analyses SET identity_version=:version WHERE id=:id'), {'version':payload['identity_version'],'id':analysis_id})
    _persist_evidence(db, analysis_id, set(result["evidence_ids"]), evidence_index(units))


class PermanentJobError(RuntimeError):
    pass


class ObsoleteJob(PermanentJobError):
    pass


class LeaseLost(RuntimeError):
    pass


class TransientJobError(RuntimeError):
    pass


def _finish_attempt(db: Session, job: dict[str, Any], budget: AttemptBudget, started: float,
                    settings: Settings, *, status: str, error_code: str | None = None) -> None:
    record_ai_usage(db, job_id=job["id"], attempt=job["attempts"], provider="gemini",
                    model=job["model"], usage=budget.usage,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                    final_status="succeeded" if status == "completed" else "failed",
                    estimated_cost_usd=_conservative_attempt_cost(settings, budget),
                    request_count=budget.calls, context_fragments=budget.fragments)
    db.execute(text("""UPDATE ia.jobs SET status=:status,error_code=:error,locked_at=NULL,updated_at=now()
      WHERE id=:id AND status='processing' AND attempts=:attempt"""),
      {"status": status, "error": error_code, "id": job["id"], "attempt": job["attempts"]})
    if status == "failed" and job["profile_version_id"] and error_code != "obsolete_profile":
        set_reader_profile_status(db, profile_version_id=job["profile_version_id"],
                                  status="failed", error_code=error_code or "generation_failed")
    db.commit()


def _retry_attempt(db: Session, job: dict[str, Any], budget: AttemptBudget, started: float,
                   settings: Settings, error_code: str, *, retry_after=None, quota_exhausted=False) -> None:
    record_ai_usage(db, job_id=job["id"], attempt=job["attempts"], provider="gemini",
                    model=job["model"], usage=budget.usage,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)), final_status="failed",
                    estimated_cost_usd=_conservative_attempt_cost(settings, budget),
                    request_count=budget.calls, context_fragments=budget.fragments)
    if job["attempts"] >= settings.ai_job_max_attempts:
        status, delay = "failed", 0
    else:
        status = "pending"
        delay = settings.ai_retry_base_seconds * (2 ** (job["attempts"] - 1)) * random.uniform(0.75, 1.25)
        delay = max(delay, retry_after or 0)
        if error_code == 'source_changed_during_generation':
            delay = max(delay, settings.reading_analysis_delay_minutes * 60)
        if error_code == 'provider_quota':
            delay = max(delay, 86400 if quota_exhausted else 900 if retry_after is None else 60)
    if error_code == 'provider_quota':
        cooldown_delay = max(retry_after or 0, 86400 if quota_exhausted else 900 if retry_after is None else 60)
        db.execute(text('''INSERT INTO ia.provider_cooldowns(provider,model,until_at,reason)
          VALUES ('gemini',:model,now()+:delay*interval '1 second',:reason)
          ON CONFLICT (provider,model) DO UPDATE SET until_at=GREATEST(
            ia.provider_cooldowns.until_at,EXCLUDED.until_at),reason=EXCLUDED.reason'''),
          {'model':job['model'],'delay':cooldown_delay,
           'reason':'quota_exhausted' if quota_exhausted else 'rate_limited'})
    db.execute(text("""UPDATE ia.jobs SET status=:status,error_code=:error,locked_at=NULL,
      not_before=now()+(:delay * interval '1 second'),updated_at=now()
      WHERE id=:id AND status='processing' AND attempts=:attempt"""),
      {"status": status, "error": error_code, "delay": delay,
       "id": job["id"], "attempt": job["attempts"]})
    if status == "failed" and job["profile_version_id"]:
        set_reader_profile_status(db, profile_version_id=job["profile_version_id"],
                                  status="failed", error_code=error_code)
    db.commit()


def process_one(*, provider: AIProvider | None = None, settings: Settings | None = None,
                session_factory=SessionLocal) -> bool:
    """Process at most one row. Dependency injection guarantees mock-only tests."""
    resolved = settings or get_settings()
    free_test_allowed = (
        resolved.gemini_free_test_mode
        and resolved.app_env in {"development", "test"}
    )
    if provider is None and (not resolved.gemini_worker_enabled or (
        not resolved.gemini_paid_service_confirmed and not free_test_allowed
    )):
        raise RuntimeError("Gemini worker activation requires explicit paid-service approval or an allowed development free-test mode")
    with session_factory() as holder, holder.get_bind().connect() as pinned, Session(bind=pinned) as db:
        job = claim_next_job(db, resolved)
        if not job:
            return False
        started = time.monotonic()
        budget = AttemptBudget(resolved.ai_max_calls_per_job, resolved.ai_job_token_budget,
                               job_id=job["id"], attempt=job["attempts"])
        try:
            selected = provider or build_ai_provider(resolved)
            expected_prompt = {'recommendation':resolved.recommendation_prompt_version,
                               'reader_profile':resolved.reader_dna_prompt_version,
                               'reading_event_analysis':resolved.reading_analysis_prompt_version}.get(job['job_kind'])
            if job['prompt_version'] != expected_prompt:
                raise ObsoleteJob('obsolete_prompt_contract')
            if job["job_kind"] == "recommendation":
                _process_recommendation(db, selected, job, resolved, budget)
            elif job["job_kind"] == "reading_event_analysis":
                _process_individual(db, selected, job, resolved, budget)
            elif job['job_kind'] == 'reader_profile':
                _process_dna(db, selected, job, resolved, budget)
            else:
                raise PermanentJobError("unsupported_job_kind")
            _finish_attempt(db, job, budget, started, resolved, status="completed")
        except LeaseLost:
            db.rollback()
        except BudgetExhausted as error:
            db.rollback()
            code = str(error)
            if code == 'monthly_budget_exhausted':
                _retry_attempt(db, job, budget, started, resolved, code)
                db.execute(text("""UPDATE ia.jobs SET not_before=date_trunc('month',now())+interval '1 month'
                  WHERE id=:id AND status='pending'"""), {'id':job['id']})
                db.commit()
            elif code != 'lease_lost':
                _finish_attempt(db, job, budget, started, resolved, status='failed', error_code=code)
        except (ObsoleteJob, PermanentJobError) as error:
            db.rollback()
            _finish_attempt(db, job, budget, started, resolved, status="failed", error_code=str(error))
        except AIProviderError as error:
            db.rollback()
            if error.retryable:
                _retry_attempt(db, job, budget, started, resolved, error.code,
                               retry_after=error.retry_after, quota_exhausted=error.quota_exhausted)
            else:
                _finish_attempt(db, job, budget, started, resolved, status="failed", error_code=error.code)
        except TransientJobError as error:
            db.rollback(); _retry_attempt(db, job, budget, started, resolved, str(error))
        except (ValidationError, ValueError) as error:
            db.rollback(); _finish_attempt(db, job, budget, started, resolved, status="failed",
                                           error_code=_safe_error_code(error))
        except Exception as error:
            db.rollback()
            # SQLAlchemy exception tracebacks can contain bound private JSON.
            LOGGER.error("Gemini job failed: %s", type(error).__name__)
            _retry_attempt(db, job, budget, started, resolved, "worker_internal")
        return True


async def worker_loop() -> None:
    settings = get_settings()
    while True:
        results = await asyncio.gather(*(
            asyncio.to_thread(process_one, settings=settings)
            for _ in range(settings.ai_max_concurrent_requests)
        ))
        await asyncio.sleep(0.1 if any(results) else settings.ai_worker_poll_seconds)
