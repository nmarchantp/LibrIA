"""Build deterministic recommendation profiles at successful nightly cutoffs.

This module deliberately has no provider, worker, endpoint or login imports.
User-authored text is persisted as untrusted evidence for a later stage; no AI
request and no ia.jobs row is created here.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text

from app.modules.analytics.persistence import (
    persist_reader_profile_version,
    recommendation_profile_hash,
    recommendation_profile_payload,
)


PROFILE_CONTEXT_TOKEN_BUDGET = 30_000


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def estimate_profile_context(payload: Mapping[str, Any]) -> dict[str, int | bool]:
    """Measure the complete JSON and conservatively estimate later token use."""

    context_bytes = len(_json_bytes(payload))
    estimated_tokens = (context_bytes + 3) // 4
    return {
        "context_bytes": context_bytes,
        "estimated_tokens": estimated_tokens,
        "requires_segmentation": estimated_tokens > PROFILE_CONTEXT_TOKEN_BUDGET,
    }


def _evidence_by_reader(
    connection, etl_run_id: uuid.UUID, cutoff
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    rows = connection.execute(
        text(
            """SELECT user_id,work_id,source_id,source_kind,source_at,provenance,payload
               FROM analytics.evidencia_lectora_personal
               WHERE etl_run_id=:run AND source_at < :cutoff
               ORDER BY user_id,work_id,source_kind,source_at,source_id"""
        ),
        {"run": etl_run_id, "cutoff": cutoff},
    ).mappings().all()
    result: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[row["user_id"]].append(dict(row))
    return result


def _finished_readings(connection, cutoff) -> list[dict[str, Any]]:
    """Return concrete finish events, keeping rereads as separate readings."""
    from app.core.config import get_settings
    # A later explicit selection must not appear in an earlier nightly cutoff.
    selected_later = "EXISTS (SELECT 1 FROM app.selecciones_edicion_lectura s WHERE s.reading_id=r.id AND s.created_at >= :cutoff)" if get_settings().catalog_editionless_enabled else "false"
    rows = connection.execute(
        text(
            f"""SELECT
                 le.user_id,
                 le.id AS library_entry_id,
                 r.id AS reading_id,
                 r.work_id,
                 ed.id AS edition_id,
                 r.finished_at,
                 r.updated_at AS reading_updated_at,
                 finish.id AS finish_event_id,
                 finish.created_at AS finish_event_at,
                 finish.reflection AS finish_reflection,
                 w.title,
                 w.description,
                 w.original_language,
                 w.series_title,
                 w.volume_number,
                 w.first_publication_date,
                 w.categories,
                 w.updated_at AS work_updated_at,
                 ed.title AS edition_title,
                 ed.language,
                 ed.page_count AS pages,
                 ed.description AS edition_description,
                 ed.publication_date,
                 ed.publication_year,
                 ed.format,
                 ed.publisher_name,
                 ed.updated_at AS edition_updated_at,
                 COALESCE((
                   SELECT jsonb_agg(
                     jsonb_build_object('id', a.id, 'name', a.name)
                     ORDER BY wa.position, a.id
                   )
                   FROM app.obras_autores wa
                   JOIN app.autores a ON a.id=wa.author_id
                   WHERE wa.work_id=w.id AND a.updated_at < :cutoff
                 ), '[]'::jsonb) AS authors
               FROM app.lecturas r
               JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
               JOIN app.obras w ON w.id=r.work_id
               LEFT JOIN app.ediciones ed ON ed.id=r.edition_id AND ed.work_id=r.work_id AND NOT ({selected_later})
               JOIN LATERAL (
                 SELECT ev.id,ev.created_at,ev.reflection
                 FROM app.eventos_lectura ev
                 WHERE ev.reading_id=r.id AND ev.actor_user_id=le.user_id
                   AND ev.kind='finish' AND ev.created_at < :cutoff
                   AND (ev.total_pages IS NULL OR ev.page=ev.total_pages)
                 ORDER BY ev.created_at DESC,ev.id DESC LIMIT 1
               ) finish ON true
               WHERE r.status='finished'
                 AND r.finished_at IS NOT NULL AND r.finished_at < :cutoff
                 AND finish.created_at=r.finished_at
                 AND (le.archived_at IS NULL OR le.archived_at >= :cutoff)
                 AND le.work_id=r.work_id
                 AND w.created_at < :cutoff AND (r.edition_id IS NULL OR ed.created_at < :cutoff OR {selected_later})
                 AND NOT EXISTS (
                   SELECT 1 FROM app.procedencia_demo d
                   WHERE (d.entity_type IN ('lecturas','reading') AND d.entity_id=r.id)
                      OR (d.entity_type='library' AND d.entity_id=le.id)
                      OR (d.entity_type IN ('obras','work') AND d.entity_id=w.id)
                      OR (d.entity_type='event' AND d.entity_id=finish.id)
                 )
               ORDER BY le.user_id,r.id"""
        ),
        {"cutoff": cutoff},
    ).mappings().all()
    result = [dict(row) for row in rows]
    from app.modules.books.canonical import enabled, identity_snapshot
    if enabled():
        snapshot = identity_snapshot(connection)
        roots = list({snapshot.root(r['work_id']) for r in result})
        metadata = {r['id']:dict(r) for r in connection.execute(text("""SELECT w.id,w.title,w.description,w.original_language,
            w.series_title,w.volume_number,w.first_publication_date,w.categories,w.updated_at AS work_updated_at,
            COALESCE((SELECT jsonb_agg(jsonb_build_object('id',a.id,'name',a.name) ORDER BY wa.position,a.id)
              FROM app.obras_autores wa JOIN app.autores a ON a.id=wa.author_id
              WHERE wa.work_id=w.id AND a.updated_at<:cutoff),'[]'::jsonb) AS authors
            FROM app.obras w WHERE w.id=ANY(:roots)"""), {'roots':roots,'cutoff':cutoff}).mappings()} if roots else {}
        result = [{**r, **{k:v for k,v in metadata[snapshot.root(r['work_id'])].items() if k!='id'},
            "physical_work_id": r["work_id"], "work_id": snapshot.root(r["work_id"]), "identity_version": snapshot.version} for r in result]
    return result


def _reader_books(
    owner_id: uuid.UUID,
    readings: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    cutoff,
) -> list[dict[str, Any]]:
    reviews: dict[uuid.UUID, Mapping[str, Any]] = {}
    notebooks: dict[uuid.UUID, Mapping[str, Any]] = {}
    notes: dict[uuid.UUID, list[Mapping[str, Any]]] = defaultdict(list)
    theories: dict[uuid.UUID, list[Mapping[str, Any]]] = defaultdict(list)

    for item in evidence:
        kind = item["source_kind"]
        if kind == "review":
            reviews[item["work_id"]] = item
        elif kind == "notebook":
            notebooks[item["source_id"]] = item
        elif kind == "note":
            notes[item["work_id"]].append(item)
        elif kind == "theory":
            theories[item["work_id"]].append(item)

    books: list[dict[str, Any]] = []
    for reading in readings:
        if reading["user_id"] != owner_id:
            continue
        review = reviews.get(reading["work_id"])
        if review is None:
            continue
        review_payload = dict(review["payload"] or {})
        try:
            rating = Decimal(str(review_payload.get("rating")))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if rating < Decimal("4"):
            continue

        notebook_source = notebooks.get(reading["reading_id"])
        notebook_payload = dict(notebook_source["payload"] or {}) if notebook_source else {}
        work_is_at_cutoff = reading["work_updated_at"] < cutoff
        edition_is_at_cutoff = reading["edition_updated_at"] is not None and reading["edition_updated_at"] < cutoff

        def authored(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "source_id": item["source_id"],
                    "body": (item["payload"] or {}).get("body"),
                    "recorded_at": item["source_at"],
                    "provenance": item["provenance"],
                }
                for item in items
            ]

        books.append(
            {
                "user_id": owner_id,
                "reading_id": reading["reading_id"],
                "work_id": reading["work_id"],
                "status": "finished",
                "finished_at": reading["finished_at"],
                "finish_event_id": reading["finish_event_id"],
                "rating": rating,
                "review_id": review["source_id"],
                "review_revision": review_payload.get("revision"),
                "review": {
                    "body": review_payload.get("body"),
                    "status": review_payload.get("status"),
                    "recorded_at": review["source_at"],
                },
                "dimension_ratings": review_payload.get("dimension_ratings") or {},
                "notebook": notebook_payload.get("notebook") or {},
                "internal_notes": authored(notes[reading["work_id"]]),
                "theories": authored(theories[reading["work_id"]]),
                "finish_reflection": reading["finish_reflection"],
                "metadata": {
                    "id": reading["work_id"],
                    "title": reading["title"] if work_is_at_cutoff else None,
                    "description": (
                        reading["edition_description"]
                        if edition_is_at_cutoff and reading["edition_description"]
                        else reading["description"] if work_is_at_cutoff else None
                    ),
                    "authors": reading["authors"],
                    "categories": reading["categories"] if work_is_at_cutoff else None,
                    "language": reading["language"] if edition_is_at_cutoff else None,
                    "pages": reading["pages"] if edition_is_at_cutoff else None,
                    "edition_id": reading["edition_id"],
                    "edition_title": reading["edition_title"] if edition_is_at_cutoff else None,
                    "original_language": reading["original_language"] if work_is_at_cutoff else None,
                    "series_title": reading["series_title"] if work_is_at_cutoff else None,
                    "volume_number": reading["volume_number"] if work_is_at_cutoff else None,
                    "first_publication_date": reading["first_publication_date"] if work_is_at_cutoff else None,
                    "publication_date": reading["publication_date"] if edition_is_at_cutoff else None,
                    "publication_year": reading["publication_year"] if edition_is_at_cutoff else None,
                    "format": reading["format"] if edition_is_at_cutoff else None,
                    "publisher_name": reading["publisher_name"] if edition_is_at_cutoff else None,
                },
                "provenance": {
                    **({"physical_work_id": reading["physical_work_id"], "identity_version": reading["identity_version"]} if "physical_work_id" in reading else {}),
                    "library_entry_id": reading["library_entry_id"],
                    "reading_id": reading["reading_id"],
                    "finish_event_id": reading["finish_event_id"],
                    "review_id": review["source_id"],
                    "review_recorded_at": review["source_at"],
                    "notebook_source_id": notebook_source["source_id"] if notebook_source else None,
                    "notebook_cutoff_complete": reading["reading_updated_at"] < cutoff,
                    "note_source_ids": [item["source_id"] for item in notes[reading["work_id"]]],
                    "theory_source_ids": [item["source_id"] for item in theories[reading["work_id"]]],
                    "metadata_cutoff_complete": work_is_at_cutoff and (reading["edition_id"] is None or edition_is_at_cutoff),
                    "author_link_history_available": False,
                    "user_text_trust": "untrusted",
                },
            }
        )
    return books


def _record_etl_state(
    connection,
    *,
    owner_id: uuid.UUID,
    etl_run_id: uuid.UUID,
    profile_version_id: uuid.UUID | None,
    outcome: str,
    eligible_books_count: int,
    context_bytes: int,
    estimated_tokens: int,
    requires_segmentation: bool,
) -> Mapping[str, Any]:
    params = {
        "owner": owner_id,
        "run": etl_run_id,
        "profile": profile_version_id,
        "outcome": outcome,
        "count": eligible_books_count,
        "bytes": context_bytes,
        "tokens": estimated_tokens,
        "segmentation": requires_segmentation,
    }
    created = connection.execute(
        text(
            """INSERT INTO ia.reader_profile_etl_states
                 (owner_id,etl_run_id,profile_version_id,outcome,eligible_books_count,
                  context_bytes,estimated_tokens,requires_segmentation)
               VALUES (:owner,:run,:profile,:outcome,:count,:bytes,:tokens,:segmentation)
               ON CONFLICT (owner_id,etl_run_id) DO NOTHING
               RETURNING *"""
        ),
        params,
    ).mappings().first()
    if created:
        return created
    return connection.execute(
        text(
            """SELECT * FROM ia.reader_profile_etl_states
               WHERE owner_id=:owner AND etl_run_id=:run"""
        ),
        params,
    ).mappings().one()


def build_nightly_reader_profiles(
    connection,
    etl_run_id: uuid.UUID,
    *,
    owner_id: uuid.UUID | None = None,
    allow_succeeded: bool = False,
) -> dict[str, Any]:
    """Build every reader for daily/manual publication, or repair one owner.

    ``requested_by`` audits who launched a manual run; it does not limit its
    readership. ``allow_succeeded`` supports idempotent per-owner preparation.
    """

    run = connection.execute(
        text(
            """SELECT id,status,run_kind,business_date,source_cutoff_at,requested_by
               FROM analytics.ejecuciones_etl WHERE id=:run FOR UPDATE"""
        ),
        {"run": etl_run_id},
    ).mappings().one()
    if run["run_kind"] == "daily":
        if run["business_date"] is None:
            return {"skipped": True, "reason": "daily_without_business_date"}
    elif run["run_kind"] == "manual":
        if run["requested_by"] is None:
            return {"skipped": True, "reason": "manual_without_requester"}
        is_admin = connection.execute(
            text(
                """SELECT 1 FROM app.permisos_cuenta
                   WHERE user_id=:owner AND permission='admin'"""
            ),
            {"owner": run["requested_by"]},
        ).first()
        if not is_admin:
            return {"skipped": True, "reason": "manual_requester_is_not_admin"}
    else:
        return {"skipped": True, "reason": "unsupported_run_kind"}
    if run["status"] != "running" and not (allow_succeeded and run["status"] == "succeeded"):
        raise ValueError("nightly_profile_requires_running_etl")

    cutoff = run["source_cutoff_at"]
    if owner_id is None:
        owners = connection.execute(
            text("SELECT id FROM app.usuarios WHERE created_at < :cutoff ORDER BY id"),
            {"cutoff": cutoff},
        ).scalars().all()
    else:
        owners = connection.execute(
            text("SELECT id FROM app.usuarios WHERE id=:owner AND created_at < :cutoff"),
            {"owner": owner_id, "cutoff": cutoff},
        ).scalars().all()
    evidence = _evidence_by_reader(connection, etl_run_id, cutoff)
    readings = _finished_readings(connection, cutoff)
    counts = {"empty": 0, "eligible_pending": 0, "unchanged": 0, "segmented": 0}

    for owner_id in owners:
        books = _reader_books(owner_id, readings, evidence.get(owner_id, ()), cutoff)
        if not books:
            state = _record_etl_state(
                connection,
                owner_id=owner_id,
                etl_run_id=etl_run_id,
                profile_version_id=None,
                outcome="empty",
                eligible_books_count=0,
                context_bytes=0,
                estimated_tokens=0,
                requires_segmentation=False,
            )
            connection.execute(
                text(
                    """UPDATE ia.recomendaciones_ia
                       SET is_current=false,invalidated_at=now(),
                           invalidated_by_etl_run_id=:run
                       WHERE owner_user_id=:owner AND is_current"""
                ),
                {"owner": owner_id, "run": etl_run_id},
            )
            counts[state["outcome"]] += 1
            continue

        from app.modules.books.canonical import enabled, identity_version
        identity = identity_version(connection) if enabled() else None
        payload = recommendation_profile_payload(books, identity=identity)
        size = estimate_profile_context(payload)
        data_hash = recommendation_profile_hash(books, identity=identity)
        existing = connection.execute(
            text(
                """SELECT id FROM ia.reader_profile_versions
                   WHERE owner_id=:owner AND data_hash=:hash"""
            ),
            {"owner": owner_id, "hash": data_hash},
        ).first()
        previous = connection.execute(
            text(
                """SELECT s.profile_version_id,s.outcome
                   FROM ia.reader_profile_etl_states s
                   JOIN analytics.ejecuciones_etl e ON e.id=s.etl_run_id
                   WHERE s.owner_id=:owner AND e.source_cutoff_at < :cutoff
                   ORDER BY e.source_cutoff_at DESC,e.id DESC LIMIT 1"""
            ),
            {"owner": owner_id, "cutoff": cutoff},
        ).mappings().first()
        profile = persist_reader_profile_version(
            connection,
            owner_id=owner_id,
            etl_run_id=etl_run_id,
            books=books,
        )
        state = _record_etl_state(
            connection,
            owner_id=owner_id,
            etl_run_id=etl_run_id,
            profile_version_id=profile["id"],
            outcome=(
                "unchanged"
                if existing
                and previous
                and previous["profile_version_id"] == profile["id"]
                and previous["outcome"] in {"eligible_pending", "unchanged"}
                else "eligible_pending"
            ),
            eligible_books_count=len({book['work_id'] for book in books}) if enabled() else len(payload["books"]),
            context_bytes=int(size["context_bytes"]),
            estimated_tokens=int(size["estimated_tokens"]),
            requires_segmentation=bool(size["requires_segmentation"]),
        )
        counts[state["outcome"]] += 1
        counts["segmented"] += int(state["requires_segmentation"])

    return {"skipped": False, "readers": len(owners), **counts}


def prepare_administrator_profile(connection, owner_id: uuid.UUID) -> dict[str, Any]:
    """Materialize one authenticated owner from the newest global ETL cutoff.

    Historical function name retained for callers; ownership is independent
    of the permission required to launch the ETL itself.
    """

    run_id = connection.execute(
        text(
            """SELECT id
               FROM analytics.ejecuciones_etl
               WHERE status='succeeded'
                 AND run_kind IN ('daily','manual')
               ORDER BY source_cutoff_at DESC, finished_at DESC NULLS LAST, id DESC
               LIMIT 1"""
        ),
        {"owner": owner_id},
    ).scalar()
    if run_id is None:
        return {"skipped": True, "reason": "no_succeeded_etl"}
    return build_nightly_reader_profiles(
        connection,
        run_id,
        owner_id=owner_id,
        allow_succeeded=True,
    )
