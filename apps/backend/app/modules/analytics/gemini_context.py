"""Complete, traceable context preparation without silent text truncation."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def estimate_tokens(value: Any) -> int:
    """Conservative deterministic estimate used before every provider call."""
    return max(1, math.ceil(len(canonical_json(value).encode("utf-8")) / 4))


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    source_kind: str
    source_id: uuid.UUID
    work_id: uuid.UUID | None
    content: Any

    def wire(self, *, part: int | None = None, parts: int | None = None) -> dict[str, Any]:
        value = {
            "evidence_id": self.evidence_id,
            "source_kind": self.source_kind,
            "work_id": str(self.work_id) if self.work_id else None,
            "content": self.content,
        }
        if part is not None:
            value["segment"] = {"part": part, "parts": parts}
        return value


def profile_evidence_units(payload: Mapping[str, Any]) -> list[EvidenceUnit]:
    """Represent every eligible book field as explicit evidence units."""
    units: list[EvidenceUnit] = []
    for book in payload.get("books") or []:
        reading_id = uuid.UUID(str(book["reading_id"]))
        work_id = uuid.UUID(str(book["work_id"]))
        core = {
            key: book.get(key)
            for key in ("finished_at", "rating", "dimension_ratings", "finish_reflection", "metadata")
        }
        units.append(EvidenceUnit(f"reading:{reading_id}", "reading", reading_id, work_id, core))
        review_id = book.get("review_id")
        if review_id and book.get("review"):
            units.append(EvidenceUnit(
                f"review:{review_id}:{book.get('review_revision') or 1}", "review",
                uuid.UUID(str(review_id)), work_id, book["review"],
            ))
        notebook_id = (book.get("provenance") or {}).get("notebook_source_id") or reading_id
        if book.get("notebook"):
            units.append(EvidenceUnit(f"notebook:{reading_id}", "notebook", uuid.UUID(str(notebook_id)), work_id, book["notebook"]))
        for kind, field in (("note", "internal_notes"), ("theory", "theories")):
            for item in book.get(field) or []:
                source_id = uuid.UUID(str(item["source_id"]))
                units.append(EvidenceUnit(f"{kind}:{source_id}", kind, source_id, work_id, item))
    if payload.get('identity_version'):
        units = list({unit.evidence_id:unit for unit in units}.values())
    return units


def _split_unit(unit: EvidenceUnit, budget: int) -> list[dict[str, Any]]:
    wire = unit.wire()
    if estimate_tokens(wire) <= budget:
        return [wire]
    # Preserve the complete canonical representation. Segments are explicit,
    # ordered and traceable; nothing is silently discarded.
    serialized = canonical_json(unit.content)
    chars = max(64, budget * 3)
    while chars > 64 and estimate_tokens(unit.wire(part=1, parts=max(1, math.ceil(len(serialized) / chars))) | {"content": serialized[:chars]}) > budget:
        chars = int(chars * 0.8)
    parts = max(1, math.ceil(len(serialized) / chars))
    return [unit.wire(part=index + 1, parts=parts) | {"content": serialized[index * chars:(index + 1) * chars]}
            for index in range(parts)]


def chunk_evidence(units: Iterable[EvidenceUnit], token_budget: int) -> list[dict[str, Any]]:
    if token_budget < 100:
        raise ValueError("Context chunk budget is too small")
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for unit in units:
        for wire in _split_unit(unit, token_budget):
            candidate = {"evidence": [*current, wire]}
            if current and estimate_tokens(candidate) > token_budget:
                chunks.append({"index": len(chunks), "evidence": current})
                current = [wire]
            else:
                current.append(wire)
            if estimate_tokens({"evidence": current}) > token_budget:
                raise ValueError("One context segment exceeds the configured token budget")
    if current:
        chunks.append({"index": len(chunks), "evidence": current})
    total = len(chunks)
    return [{**chunk, "total": total, "hash": content_hash(chunk["evidence"])} for chunk in chunks]


def evidence_index(units: Iterable[EvidenceUnit]) -> dict[str, EvidenceUnit]:
    return {unit.evidence_id: unit for unit in units}
