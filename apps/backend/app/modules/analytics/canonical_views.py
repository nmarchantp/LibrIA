"""Canonical adapters for persisted analytics; no inference and no catalog writes."""
import uuid
from sqlalchemy import select, text
from app.modules.books.canonical import identity_snapshot, canonical_members
from app.modules.books.consistency import current_reviews
from app.modules.books.models import Work
from app.modules.library.models import LibraryEntry, Reading


def owned_entry(db, owner, work):
    from fastapi import HTTPException
    snapshot = identity_snapshot(db)
    root = snapshot.root(work)
    entries = db.scalars(select(LibraryEntry).where(LibraryEntry.user_id == owner,
        LibraryEntry.work_id.in_(canonical_members(db, work)), LibraryEntry.archived_at.is_(None))
        .order_by(LibraryEntry.created_at, LibraryEntry.id)).all()
    demo = set(db.execute(text('SELECT entity_type,entity_id FROM app.procedencia_demo')).all())
    entries = [entry for entry in entries if ('library',entry.id) not in demo and ('obras',entry.work_id) not in demo and ('work',entry.work_id) not in demo]
    if not entries:
        raise HTTPException(404, "Libro propio no encontrado")
    catalog = db.get(Work, root)
    return {"id": entries[0].id, "work_id": root, "entry_ids": [e.id for e in entries], "title": catalog.title, "categories": catalog.categories}


def book_context(db, owner, work):
    from app.modules.analytics.adaptive_ai import feedback_sources
    entry = owned_entry(db, owner, work)
    ids = list(canonical_members(db, work))
    readings = db.scalars(select(Reading).where(Reading.library_entry_id.in_(entry["entry_ids"]))
        .order_by(Reading.created_at, Reading.id)).all()
    demo = set(db.execute(text("SELECT entity_type,entity_id FROM app.procedencia_demo")).all())
    readings = [r for r in readings if ("lecturas", r.id) not in demo and ("reading", r.id) not in demo]
    sources = [{"key": "reading:"+str(r.id), "kind": "reading", "id": str(r.id), "at": r.created_at.isoformat(),
        "data": {"state": r.status, "abandonment_reason": r.abandonment_reason, "notebook": r.notebook or {},
                 "physical_work_id": str(r.work_id), "edition_id": str(r.edition_id) if r.edition_id else None}} for r in readings]
    reviews = current_reviews(db, ids, reader_id=owner)
    current = next((r for r in reviews if r.status != "hidden" and ("review", r.id) not in demo), None)
    if current:
        sources.append({"key": f"review:{current.id}:{current.revision_number}", "kind": "review", "id": str(current.id),
            "at": current.updated_at.isoformat(), "data": {"body": current.body, "rating": float(current.rating) if current.rating else None,
            "dimension_ratings": current.dimension_ratings, "revision_number": current.revision_number, "physical_work_id": str(current.work_id)}})
    events = db.execute(text("""SELECT ev.id,ev.reflection,ev.created_at FROM app.eventos_lectura ev
        JOIN app.lecturas r ON r.id=ev.reading_id JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
        WHERE le.user_id=:owner AND r.work_id=ANY(:works) AND ev.reflection IS NOT NULL ORDER BY ev.created_at,ev.id"""),
        {"owner": owner, "works": ids}).mappings().all()
    sources.extend({"key": "reflection:"+str(r["id"]), "kind": "reflection", "id": str(r["id"]),
        "at": r["created_at"].isoformat(), "data": r["reflection"]} for r in events if ("event", r["id"]) not in demo)
    posts = db.execute(text("""SELECT po.id,po.publication_type,po.body,po.created_at FROM app.publicaciones po
        JOIN app.perfiles p ON p.id=po.author_profile_id
        WHERE p.kind='personal' AND p.owner_user_id=:owner AND po.user_id=:owner AND NOT po.legacy_content
          AND po.publication_type IN ('note','theory') AND (po.work_id=ANY(:works) OR
          (po.work_id IS NULL AND (SELECT count(DISTINCT ed.work_id) FROM app.fuentes_catalogo s JOIN app.ediciones ed ON ed.id=s.edition_id WHERE s.external_id=po.book_ref)=1
          AND EXISTS(SELECT 1 FROM app.fuentes_catalogo s JOIN app.ediciones ed ON ed.id=s.edition_id
             WHERE s.external_id=po.book_ref AND ed.work_id=ANY(:works)))) ORDER BY po.created_at,po.id"""),
        {"owner": owner, "works": ids}).mappings().all()
    sources.extend({"key": str(r["publication_type"])+":"+str(r["id"]), "kind": r["publication_type"], "id": str(r["id"]),
        "at": r["created_at"].isoformat(), "data": {"body": r["body"]}} for r in posts if ("post", r["id"]) not in demo)
    for key in ids:
        sources.extend(feedback_sources(db, owner, "book:"+str(key)))
    return {"title": entry["title"], "categories": entry["categories"] or [], "rated": bool(current and current.rating is not None),
        "state": readings[-1].status if readings else "pending", "sources": sorted(sources, key=lambda s:(s["at"],s["key"]))}


def normalize_reader(db, payload):
    snapshot = identity_snapshot(db)
    grouped = {}
    for row in payload["books"]:
        root = str(snapshot.root(row["work_id"]))
        grouped.setdefault(root, []).append(row)
    books = []
    for root, rows in grouped.items():
        active = next((r for r in rows if not r["archived"]), None)
        if active:
            context = active["context"]
            rating = next((s["data"].get("rating") for s in reversed(context["sources"]) if s["kind"] == "review"), None)
            books.append({**active, "work_id": root, "context": context, "rating": rating,
                "historical_entry_ids": [r["entry_id"] for r in rows]})
        else:
            books.append({**rows[0], "work_id": root, "historical_entry_ids": [r["entry_id"] for r in rows]})
    payload["books"] = books
    for key in ("events", "reviews", "social"):
        payload[key] = [{**r, "physical_work_id": r["work_id"], "work_id": str(snapshot.root(r["work_id"]))}
            if r.get("work_id") else r for r in payload[key]]
    payload["reviews"] = current_records_for_projection(payload["reviews"])
    payload["identity_version"] = snapshot.version
    payload["identity_projection"] = snapshot.provenance()
    return payload


def current_records_for_projection(rows):
    # Reviews here are already selected before visibility by the public ORM selector.
    return list({r["source_id"]: r for r in rows}.values())
