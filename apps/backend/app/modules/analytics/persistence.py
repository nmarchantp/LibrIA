"""Persistence primitives for versioned profiles and asynchronous AI work.

The nightly ETL uses only the profile functions in this module.  Enqueue and
provider functions remain separate so profile construction cannot call an AI
provider or create recommendation jobs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.analytics.providers.base import TokenUsage


PROFILE_HASH_VERSION = "recommendation-profile-v1"
RELEVANT_BOOK_FIELDS = (
    "user_id",
    "reading_id",
    "work_id",
    "finished_at",
    "finish_event_id",
    "rating",
    "review_id",
    "review_revision",
    "review",
    "dimension_ratings",
    "notebook",
    "internal_notes",
    "theories",
    "finish_reflection",
    "provenance",
    "metadata",
)
RELEVANT_METADATA_FIELDS = (
    "id",
    "title",
    "description",
    "authors",
    "categories",
    "language",
    "pages",
    "edition_id",
    "edition_title",
    "original_language",
    "series_title",
    "volume_number",
    "first_publication_date",
    "publication_date",
    "publication_year",
    "format",
    "publisher_name",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def recommendation_profile_payload(books: Sequence[Mapping[str, Any]], *, identity=None) -> dict[str, Any]:
    """Select only finished, generally-rated >=4 inputs used by recommendations."""

    eligible: list[dict[str, Any]] = []
    for book in books:
        try:
            rating = Decimal(str(book.get("rating")))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if book.get("status") != "finished" or rating < Decimal("4"):
            continue
        if not book.get("reading_id") or not book.get("work_id"):
            raise ValueError("Eligible recommendation books require reading_id and work_id")
        selected = {field: book.get(field) for field in RELEVANT_BOOK_FIELDS}
        selected["rating"] = rating
        metadata = book.get("metadata")
        if isinstance(metadata, Mapping):
            selected["metadata"] = {
                field: metadata.get(field) for field in RELEVANT_METADATA_FIELDS
            }
        eligible.append(_json_value(selected))
    eligible.sort(key=lambda item: (str(item["reading_id"]), str(item["work_id"])))
    return {"hash_version": PROFILE_HASH_VERSION, "books": eligible, **({"identity_version": identity} if identity else {})}


def recommendation_profile_hash(books: Sequence[Mapping[str, Any]], *, identity=None) -> str:
    payload = recommendation_profile_payload(books, identity=identity)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def persist_reader_profile_version(
    db: Session,
    *,
    owner_id: uuid.UUID,
    etl_run_id: uuid.UUID,
    books: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Create one version per hash, tied to its first authorized ETL cutoff.

    Daily and administrator-requested manual runs may create profiles for
    every reader. The requester is audit information, not the profile owner.
    """

    payload = recommendation_profile_payload(books)
    from app.modules.books.canonical import enabled, identity_version
    identity = identity_version(db) if enabled() else None
    if identity:
        payload["identity_version"] = identity
    canonical_payload = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    data_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"reader-profile-version:{owner_id}"},
    )
    existing = db.execute(
        text(
            "SELECT * FROM ia.reader_profile_versions "
            "WHERE owner_id=:owner AND data_hash=:hash"
        ),
        {"owner": owner_id, "hash": data_hash},
    ).mappings().first()
    if existing:
        return existing
    conflicting_run = db.execute(
        text(
            "SELECT 1 FROM ia.reader_profile_versions "
            "WHERE owner_id=:owner AND etl_run_id=:run"
        ),
        {"owner": owner_id, "run": etl_run_id},
    ).first()
    if conflicting_run:
        raise ValueError("The ETL run already has a different recommendation profile hash")
    created = db.execute(
        text(
            """INSERT INTO ia.reader_profile_versions
               (owner_id, etl_run_id, data_hash, version, payload)
               SELECT :owner, r.id, :hash,
                      COALESCE((SELECT max(version) FROM ia.reader_profile_versions
                                WHERE owner_id=:owner), 0) + 1,
                      CAST(:payload AS jsonb)
               FROM analytics.ejecuciones_etl r
               WHERE r.id=:run AND (
                 (r.run_kind='daily' AND r.business_date IS NOT NULL)
                 OR r.run_kind='manual'
               )
               RETURNING *"""
        ),
        {
            "owner": owner_id,
            "run": etl_run_id,
            "hash": data_hash,
            "payload": canonical_payload,
        },
    ).mappings().first()
    if not created:
        raise ValueError("An authorized daily or administrator ETL run is required for recommendation profiles")
    if identity:
        db.execute(text("UPDATE ia.reader_profile_versions SET identity_version=:version WHERE id=:id"),
                   {"version": identity, "id": created["id"]})
    return created


def set_reader_profile_status(
    db: Session,
    *,
    profile_version_id: uuid.UUID,
    status: str,
    error_code: str | None = None,
) -> Mapping[str, Any]:
    if status not in {"pending", "ready", "failed"}:
        raise ValueError("Unsupported reader profile status")
    if status == "failed" and not error_code:
        raise ValueError("Failed reader profiles require an error code")
    row = db.execute(
        text(
            """UPDATE ia.reader_profile_versions SET
                 status=:status,
                 generated_at=CASE WHEN :status='ready' THEN now() END,
                 error_code=CASE WHEN :status='failed' THEN :error END,
                 updated_at=now()
               WHERE id=:id RETURNING *"""
        ),
        {"id": profile_version_id, "status": status, "error": error_code},
    ).mappings().first()
    if not row:
        raise ValueError("Reader profile version not found")
    return row


def _require_provider_values(provider: str, model: str, prompt_version: str) -> tuple[str, str, str]:
    values = tuple(value.strip() for value in (provider, model, prompt_version))
    if any(not value for value in values):
        raise ValueError("Provider, model and prompt version are required")
    return values


def enqueue_recommendation_job(
    db: Session,
    *,
    profile_version_id: uuid.UUID,
    provider: str,
    model: str,
    prompt_version: str,
) -> Mapping[str, Any]:
    """Deduplicate one recommendation request per logical profile/provider tuple."""

    provider, model, prompt_version = _require_provider_values(provider, model, prompt_version)
    suffix = hashlib.sha256(f"{provider}\0{model}\0{prompt_version}".encode()).hexdigest()[:20]
    target = f"recommendation:{profile_version_id}:{suffix}"
    params = {
        "profile": profile_version_id,
        "provider": provider,
        "model": model,
        "prompt": prompt_version,
        "target": target,
    }
    created = db.execute(
        text(
            """INSERT INTO ia.jobs
                 (owner_id, target, job_kind, provider, model, prompt_version, profile_version_id)
               SELECT owner_id, :target, 'recommendation', :provider, :model, :prompt, id
               FROM ia.reader_profile_versions WHERE id=:profile
               ON CONFLICT DO NOTHING RETURNING *"""
        ),
        params,
    ).mappings().first()
    if created:
        return created
    existing = db.execute(
        text(
            """SELECT * FROM ia.jobs WHERE job_kind='recommendation'
               AND profile_version_id=:profile AND provider=:provider
               AND model=:model AND prompt_version=:prompt"""
        ),
        params,
    ).mappings().first()
    if not existing:
        raise ValueError("Reader profile version not found")
    return existing


def enqueue_reading_event_analysis(
    db: Session,
    *,
    reading_event_id: uuid.UUID,
    provider: str,
    model: str,
    prompt_version: str,
    delay_minutes: int = 30,
) -> Mapping[str, Any]:
    """Queue exactly one logical analysis for a concrete finish/abandon event."""

    provider, model, prompt_version = _require_provider_values(provider, model, prompt_version)
    if delay_minutes < 0:
        raise ValueError("Reading analysis delay cannot be negative")
    params = {
        "event": reading_event_id,
        "provider": provider,
        "model": model,
        "prompt": prompt_version,
        "delay": delay_minutes,
    }
    created = db.execute(
        text(
            """INSERT INTO ia.jobs
                 (owner_id, target, job_kind, provider, model, prompt_version, reading_event_id, not_before)
               SELECT le.user_id, 'reading-event:' || ev.id::text || ':' || :provider || ':' || :model || ':' || :prompt,
                      'reading_event_analysis', :provider, :model, :prompt, ev.id,
                      ev.created_at + (:delay * interval '1 minute')
               FROM app.eventos_lectura ev
               JOIN app.lecturas r ON r.id=ev.reading_id
               JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
               WHERE ev.id=:event AND ev.kind IN ('finish','abandon')
               ON CONFLICT DO NOTHING RETURNING *"""
        ),
        params,
    ).mappings().first()
    if created:
        db.execute(text('UPDATE ia.jobs SET consolidation_seconds=:seconds WHERE id=:id'),
                   {'seconds':delay_minutes * 60,'id':created['id']})
        return created
    existing = db.execute(
        text(
            "SELECT * FROM ia.jobs WHERE job_kind='reading_event_analysis' "
            "AND reading_event_id=:event AND provider=:provider "
            "AND model=:model AND prompt_version=:prompt"
        ),
        params,
    ).mappings().first()
    if not existing:
        raise ValueError("A finished or abandoned reading event is required")
    return existing


def record_ai_usage(
    db: Session,
    *,
    job_id: uuid.UUID,
    attempt: int,
    provider: str,
    model: str,
    usage: TokenUsage,
    duration_ms: int,
    final_status: str,
    estimated_cost_usd: Decimal | None = None,
    request_count: int = 0,
    context_fragments: int = 0,
) -> Mapping[str, Any]:
    """Persist technical usage only; no credentials, prompts or private content."""

    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise ValueError("Provider and model are required")
    params = {
        "job": job_id,
        "attempt": attempt,
        "provider": provider,
        "model": model,
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "reasoning": usage.reasoning_tokens,
        "cached": usage.cached_input_tokens,
        "duration": duration_ms,
        "status": final_status,
        "cost": estimated_cost_usd,
        "requests": request_count,
        "fragments": context_fragments,
    }
    created = db.execute(
        text(
            """INSERT INTO ia.usage_metrics
                 (job_id, attempt, provider, model, input_tokens, output_tokens,
                  reasoning_tokens, cached_input_tokens, duration_ms, final_status,
                  estimated_cost_usd, request_count, context_fragments)
               VALUES (:job, :attempt, :provider, :model, :input, :output,
                       :reasoning, :cached, :duration, :status, :cost, :requests, :fragments)
               ON CONFLICT (job_id, attempt) DO NOTHING RETURNING *"""
        ),
        params,
    ).mappings().first()
    if created:
        return created
    existing = db.execute(
        text("SELECT * FROM ia.usage_metrics WHERE job_id=:job AND attempt=:attempt"),
        params,
    ).mappings().first()
    if not existing:
        raise ValueError("AI job not found or usage values are invalid")
    return existing
