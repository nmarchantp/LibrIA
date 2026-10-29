"""Private reader-authored evidence. Never consumed by group analysis."""
import json
from sqlalchemy import text

MAX_ITEMS = 32
MAX_TEXT = 18000


def extract_personal(connection, cutoff):
    from app.modules.books.canonical import enabled
    statuses = "'draft','published','hidden'" if enabled() else "'draft','published'"
    # Notebooks have no revision history: never pretend today's edit existed at
    # an earlier cutoff. Reviews do have revisions and can be reconstructed.
    rows = connection.execute(text(f"""
        SELECT le.user_id, r.work_id, r.id AS source_id, 'notebook' AS source_kind,
            r.updated_at AS source_at,
            jsonb_build_object('title', w.title, 'notebook', r.notebook) AS payload
        FROM app.lecturas r JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
        JOIN app.obras w ON w.id=r.work_id
        WHERE r.updated_at < :cutoff AND EXISTS (SELECT 1 FROM jsonb_each_text(r.notebook) n WHERE n.key IN ('characters','places','summary') AND length(trim(n.value)) > 0)
          AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE
            (d.entity_type='lecturas' AND d.entity_id=r.id) OR
            (d.entity_type='library' AND d.entity_id=le.id) OR
            (d.entity_type='obras' AND d.entity_id=r.work_id))
        UNION ALL
        SELECT p.owner_user_id, r.work_id, r.id, 'review', v.recorded_at,
            jsonb_build_object('title', w.title, 'body', v.body, 'rating', v.rating,
                'dimension_ratings', v.dimension_ratings, 'status', v.status,
                'revision', v.revision_number)
        FROM app.resenas r JOIN app.perfiles p ON p.id=r.author_profile_id
        JOIN app.obras w ON w.id=r.work_id
        JOIN LATERAL (SELECT rv.* FROM app.revisiones_resena rv
            WHERE rv.review_id=r.id AND rv.recorded_at < :cutoff
            ORDER BY rv.revision_number DESC LIMIT 1) v ON true
        WHERE p.kind='personal' AND p.owner_user_id=r.created_by_user_id
          AND v.status IN ({statuses})
          AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE
            (d.entity_type='review' AND d.entity_id=r.id) OR
            (d.entity_type='obras' AND d.entity_id=r.work_id))
        UNION ALL
        SELECT p.owner_user_id, w.id, po.id, po.publication_type, po.created_at,
            jsonb_build_object('title', w.title, 'body', po.body)
        FROM app.publicaciones po JOIN app.perfiles p ON p.id=po.author_profile_id
        JOIN app.obras w ON po.work_id=w.id OR (po.work_id IS NULL AND EXISTS (SELECT 1 FROM app.ediciones ed
            JOIN app.fuentes_catalogo s ON s.edition_id=ed.id
            WHERE ed.work_id=w.id AND s.external_id=po.book_ref))
        WHERE p.kind='personal' AND p.owner_user_id=po.user_id
          AND po.publication_type IN ('note','theory') AND NOT po.legacy_content
          AND po.created_at < :cutoff
          AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE
            (d.entity_type='post' AND d.entity_id=po.id) OR
            (d.entity_type='obras' AND d.entity_id=w.id))
    """), {"cutoff": cutoff}).mappings().all()
    # An ambiguous legacy book reference cannot establish book identity.
    counts = {}
    for row in rows:
        key = (row['source_kind'], row['source_id'])
        counts[key] = counts.get(key, 0) + 1
    result = [dict(row) for row in rows if counts[(row['source_kind'], row['source_id'])] == 1]
    from app.modules.books.canonical import enabled, identity_snapshot
    if enabled():
        from app.modules.books.consistency import current_records,review_preferences
        snapshot = identity_snapshot(connection)
        result = [{**r, "physical_work_id": r["work_id"], "work_id": snapshot.root(r["work_id"])} for r in result]
        # Keep latest hidden/draft as a privacy barrier, not an older published revision.
        # This extraction already reconstructs each review as of the cutoff.
        reviews = [r for r in result if r["source_kind"] == "review"]
        selected = current_records(reviews, work=lambda r:r["work_id"], reader=lambda r:r["user_id"], timestamp=lambda r:r["source_at"], identifier=lambda r:r["source_id"],preferred=review_preferences(connection,snapshot,by_owner=True))
        result = [r for r in result if r["source_kind"] != "review"] + [r for r in selected if r["payload"].get("status") != "hidden"]
    return result


def publish_personal(connection, run_id, rows):
    if rows:
        connection.execute(text("""INSERT INTO analytics.evidencia_lectora_personal
            (etl_run_id,user_id,work_id,source_id,source_kind,source_at,provenance,payload)
            VALUES (:run,:user_id,:work_id,:source_id,:source_kind,:source_at,'unclassified',CAST(:payload AS jsonb))"""),
            [{**row, 'run': run_id, 'payload': json.dumps(row['payload'])} for row in rows])
    actual = connection.execute(text("SELECT count(*) FROM analytics.evidencia_lectora_personal WHERE etl_run_id=:run"),
                                {'run': run_id}).scalar_one()
    if actual != len(rows):
        raise ValueError('personal_evidence_reconciliation_failed')


def personal_samples(db, run_id, user_id, provenance):
    rows = db.execute(text("""WITH ranked AS (
            SELECT work_id, source_id, source_kind, source_at, payload,
                row_number() OVER (PARTITION BY source_kind ORDER BY source_at DESC, source_id) AS position,
                count(*) OVER () AS total
            FROM analytics.evidencia_lectora_personal
            WHERE etl_run_id=:run AND user_id=:owner AND provenance=:provenance)
        SELECT * FROM ranked WHERE position <= 8
        ORDER BY source_at DESC, source_kind, source_id LIMIT :limit"""),
        {'run': run_id, 'owner': user_id, 'provenance': provenance, 'limit': MAX_ITEMS + 1}).mappings().all()
    result, remaining = [], MAX_TEXT
    truncated = bool(rows and rows[0]["total"] > min(len(rows), MAX_ITEMS))
    for row in rows[:MAX_ITEMS]:
        payload = dict(row['payload'])
        # Bound free text without cutting JSON or silently inventing a summary.
        for key in ('title', 'body'):
            if isinstance(payload.get(key), str):
                original = payload[key]
                payload[key] = original[:min(2000, remaining)]
                remaining -= len(payload[key])
                truncated |= payload[key] != original
        if isinstance(payload.get('notebook'), dict):
            notebook = {}
            for key in ('characters', 'places', 'summary'):
                original = payload['notebook'].get(key, '')
                if isinstance(original, str) and original.strip():
                    notebook[key] = original[:min(1500, remaining)]
                    remaining -= len(notebook[key])
                    truncated |= notebook[key] != original
            payload['notebook'] = notebook
        result.append({'work_id': str(row['work_id']), 'source_id': str(row['source_id']),
                       'kind': row['source_kind'], 'recorded_at': row['source_at'].isoformat(), **payload})
        if remaining <= 0:
            truncated = True
            break
    return result, truncated
