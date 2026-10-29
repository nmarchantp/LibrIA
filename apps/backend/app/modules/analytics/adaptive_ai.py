"""Provider-neutral helpers retained for persisted reader analysis data.

The executable local-model implementation is frozen under ``legacy/ollama``.
New inference is owned exclusively by ``gemini_worker``.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

VERSION = "reading-event-v1"
PROFILE_VERSION = "recommendations-v1"
PROFILE_CATEGORIES = ("historical_affinities", "recent_affinities", "exploratory_interests",
                      "satisfaction_factors", "abandonment_factors", "confirmed_preferences")


class LegacyAIFlowDisabled(RuntimeError):
    """Raised if obsolete synchronous inference is invoked by old code."""


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class BookAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sentiment: Literal["positivo", "negativo", "mixto", "indeterminado"]
    analysis_state: Literal["provisional", "consolidado", "insuficiente"]
    abandonment_context: Literal["externo", "obra", "mixto", "indeterminado"]
    emotions: list[Claim] = Field(max_length=8)
    valued_aspects: list[Claim] = Field(max_length=8)
    questioned_aspects: list[Claim] = Field(max_length=8)
    preferences: list[Claim] = Field(max_length=8)
    interpretation: str = Field(min_length=1, max_length=1800)
    limitations: list[str] = Field(min_length=1, max_length=5)


class ReaderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interpretation: str = Field(min_length=1, max_length=2200)
    literary_identity: str = Field(min_length=1, max_length=900)
    identity_evidence_ids: list[str] = Field(max_length=24)
    historical_affinities: list[Claim] = Field(max_length=8)
    recent_affinities: list[Claim] = Field(max_length=8)
    exploratory_interests: list[Claim] = Field(max_length=8)
    satisfaction_factors: list[Claim] = Field(max_length=8)
    abandonment_factors: list[Claim] = Field(max_length=8)
    confirmed_preferences: list[Claim] = Field(max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=5)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in value if not unicodedata.combining(c))))


def validate_profile_quality(content):
    placeholders = {"resumen", "summary", "texto", "text", "string", "descripcion", "interpretacion",
                    "identidad", "afinidad", "preferencia", "ejemplo", "example", "placeholder",
                    "pendiente", "sin datos", "no disponible", "n a", "null", "none"}
    for field in ("literary_identity", "interpretation"):
        value = content.get(field, "")
        if not isinstance(value, str) or not _normalized(value) or _normalized(value) in placeholders:
            raise ValueError("placeholder_profile")
    seen = set()
    for category in PROFILE_CATEGORIES:
        for claim in content.get(category, []):
            value = _normalized(claim.get("text", ""))
            if value in placeholders or len(value.split()) < 4:
                raise ValueError("placeholder_profile_claim")
            if value in seen:
                raise ValueError("repeated_profile_claim")
            seen.add(value)
    return content


def validate_book_quality(content):
    fillers = {"resumen", "summary", "texto", "text", "string", "placeholder", "ejemplo", "example"}
    texts = [content.get("interpretation", "")] + [claim.get("text", "")
        for key in ("emotions", "valued_aspects", "questioned_aspects", "preferences")
        for claim in content.get(key, [])]
    if any(not value.strip() or value.strip().casefold().strip(" .:") in fillers for value in texts):
        raise ValueError("placeholder_book_analysis")
    return content


def hash_data(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def owned_entry(db, owner, work):
    from app.modules.books.canonical import enabled
    if enabled():
        from app.modules.analytics.canonical_views import owned_entry as canonical_entry
        return canonical_entry(db, owner, work)
    row = db.execute(text("""SELECT le.id,le.work_id,w.title,w.categories FROM app.entradas_biblioteca le
        JOIN app.obras w ON w.id=le.work_id WHERE le.user_id=:owner AND le.work_id=:work AND le.archived_at IS NULL
        AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE
          (d.entity_type='obras' AND d.entity_id=w.id) OR (d.entity_type='library' AND d.entity_id=le.id))"""),
        {"owner": owner, "work": work}).mappings().first()
    if not row:
        raise HTTPException(404, "Libro propio no encontrado")
    return row


def has_rating(db, owner, work):
    from app.modules.books.canonical import enabled
    if enabled():
        from app.modules.books.consistency import current_reviews
        return any(r.rating is not None and r.status != "hidden" for r in current_reviews(db, {work}, reader_id=owner))
    return bool(db.execute(text("""SELECT 1 FROM app.resenas r JOIN app.perfiles p ON p.id=r.author_profile_id
        WHERE p.kind='personal' AND p.owner_user_id=:owner AND r.created_by_user_id=:owner
        AND r.work_id=:work AND r.rating IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='review' AND d.entity_id=r.id)
        LIMIT 1"""), {"owner": owner, "work": work}).first())


def feedback_sources(db, owner, target):
    rows = db.execute(text("""SELECT DISTINCT ON (f.analysis_id) f.id,f.action,f.information,
        f.original_interpretation,f.created_at FROM ia.feedback f JOIN ia.analyses a ON a.id=f.analysis_id
        WHERE f.owner_id=:owner AND a.target=:target
        ORDER BY f.analysis_id,f.created_at DESC,f.id DESC"""),
        {"owner": owner, "target": target}).mappings().all()
    return [{"key": "feedback:" + str(row["id"]), "kind": "feedback", "id": str(row["id"]),
             "at": row["created_at"].isoformat(), "data": {"action": row["action"],
             "information": row["information"], "original_interpretation": row["original_interpretation"]}}
            for row in sorted(rows, key=lambda value: (value["created_at"], str(value["id"])))]


def latest(db, owner, target, valid=True):
    row = db.execute(text("""SELECT id,target,version,data_hash,content,model,prompt_version,provider,
        valid,created_at,analytics_run_id,job_id,reading_event_id FROM ia.analyses
        WHERE owner_id=:owner AND target=:target ORDER BY version DESC LIMIT 1"""),
        {"owner": owner, "target": target}).mappings().first()
    if not row or (valid and not row["valid"]):
        return None
    from app.modules.books.canonical import enabled, identity_version
    if enabled() and valid:
        version = db.execute(text("SELECT identity_version FROM ia.analyses WHERE id=:id"), {"id": row["id"]}).scalar()
        if version != identity_version(db):
            return None
    return dict(row)


def book_context(db, owner, work):
    from app.modules.books.canonical import enabled, resolve_canonical_work
    if enabled():
        work = resolve_canonical_work(db, work).canonical_work_id
    from app.modules.analytics.projections import reader_snapshot
    book = next((item for item in reader_snapshot(db, owner)["books"]
                 if item["work_id"] == str(work) and not item["archived"]), None)
    if not book:
        raise HTTPException(404, "Libro propio no encontrado")
    return book["context"]


def context_hash(context):
    return hash_data(context)


def profile_context(db, owner):
    from app.modules.analytics.projections import reader_snapshot
    snapshot = reader_snapshot(db, owner)
    return {"sources": snapshot.get("profile_feedback", []), "pending_books": [],
            "library_summary": {"total": len([book for book in snapshot["books"] if not book["archived"]])}}


def enqueue(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("La cola adaptativa heredada esta desactivada")


def expire_profiles(*_args, **_kwargs):
    return None


def infer(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("La inferencia sincrona heredada esta desactivada")


def process_one(*_args, **_kwargs):
    raise LegacyAIFlowDisabled("El worker heredado esta desactivado")
