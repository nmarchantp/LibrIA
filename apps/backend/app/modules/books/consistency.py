"""Shared current-review selection and canonical read projections, never DML."""
from sqlalchemy import select, text
from app.modules.books.canonical import identity_snapshot


def current_records(rows, *, work, reader, timestamp, identifier, preferred=None):
    """Select BEFORE visibility/rating filters, so private latest never resurfaces."""
    selected = {}
    for row in rows:
        key = (reader(row), work(row))
        choice=(preferred or {}).get(key)
        if choice is not None and str(identifier(row))!=str(choice):
            continue
        order = (str(identifier(row))==str(choice),timestamp(row), str(identifier(row)))
        if key not in selected or order > selected[key][0]:
            selected[key] = (order, row)
    return [item[1] for item in selected.values()]


def review_preferences(db,snapshot,by_owner=False):
    from app.core.config import get_settings
    if not get_settings().catalog_canonical_enabled:
        return {}
    rows=db.execute(text("""SELECT s.work_id,s.profile_id,s.review_id,p.owner_user_id
      FROM app.selecciones_resena_canonica s JOIN app.perfiles p ON p.id=s.profile_id
      JOIN app.operaciones_catalogo o ON o.id=s.operation_id
      JOIN app.redirecciones_obras r ON r.operation_id=o.id AND r.retired_at IS NULL
        AND r.active_from<=statement_timestamp() AND o.operation_type='merge'
      ORDER BY o.identity_version,s.id""")).mappings()
    return {(r['owner_user_id'] if by_owner else r['profile_id'],snapshot.root(r['work_id'])):r['review_id']
            for r in rows if r['work_id'] in snapshot.mapping}


def current_reviews(db, work_ids=None, reader_id=None, public=False):
    from app.modules.social.models import Review
    snapshot = identity_snapshot(db)
    query = select(Review)
    if work_ids is not None:
        roots = {snapshot.root(key) for key in work_ids}
        query = query.where(Review.work_id.in_([key for key in snapshot.mapping if snapshot.root(key) in roots]))
    if reader_id is not None:
        query = query.where(Review.created_by_user_id == reader_id)
    rows = db.scalars(query).all()
    rows = current_records(rows, work=lambda r: snapshot.root(r.work_id), reader=lambda r: r.author_profile_id,
        timestamp=lambda r: r.updated_at, identifier=lambda r: r.id,preferred=review_preferences(db,snapshot))
    return sorted((r for r in rows if not public or r.status == "published"),
                  key=lambda r: (r.published_at or r.created_at, str(r.id)), reverse=True)


def normalize_extract(db, works, events, posts, entries, reviews):
    snapshot = identity_snapshot(db)
    canonical_works = {}
    for row in works:
        root = snapshot.root(row["id"])
        if root not in canonical_works or row["id"] == root:
            canonical_works[root] = {**row, "id": root}
    normalized_events = []
    for row in events:
        mismatch = row["work_id"] != row["library_work"] or (row["edition_id"] is not None and row["work_id"] != row["edition_work"])
        normalized_events.append({**row, "physical_work_id": row["work_id"], "identity_mismatch": mismatch,
            "work_id": snapshot.root(row["work_id"]), "library_work": snapshot.root(row["library_work"]),
            "edition_work": snapshot.root(row["edition_work"]) if row["edition_work"] else None})
    memberships = {}
    earliest = {}
    for stored in db.execute(text("""SELECT le.id,le.user_id,le.work_id,
        CASE WHEN p.entity_id IS NULL THEN 'unclassified' ELSE 'simulated' END AS provenance
        FROM app.entradas_biblioteca le LEFT JOIN app.procedencia_demo p ON p.entity_type='library' AND p.entity_id=le.id
        ORDER BY le.created_at,le.id""")).mappings():
        earliest.setdefault((stored['user_id'],snapshot.root(stored['work_id']),stored['provenance']),stored['id'])
    for row in entries:
        key = (row["user_id"], snapshot.root(row["work_id"]), row["provenance"])
        if earliest.get(key) == row['id']:
            memberships.setdefault(key, {**row, "work_id": key[1]})
    normalized_reviews = [{**r, "physical_work_id": r["work_id"], "work_id": snapshot.root(r["work_id"]),
        "identity_mismatch": bool(r["edition_id"] and r["edition_work"] != r["work_id"]),
        "edition_work": snapshot.root(r["edition_work"]) if r["edition_work"] else None} for r in reviews]
    normalized_reviews = current_records(normalized_reviews, work=lambda r: r["work_id"],
        reader=lambda r: r["owner_user_id"], timestamp=lambda r: r["recorded_at"], identifier=lambda r: r["id"],preferred=review_preferences(db,snapshot,by_owner=True))
    return list(canonical_works.values()), normalized_events, posts, list(memberships.values()), normalized_reviews
