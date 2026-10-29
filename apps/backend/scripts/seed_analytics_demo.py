"""Escenarios finitos versionados; ninguna segunda carga modifica entidades."""
import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.books.models import Work, Edition, CatalogSource
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent, ReadingProgress
from app.modules.social.models import Post
from scripts.seed_demo import seed, stable_id as account_id

MANIFEST = json.loads(Path(__file__).with_name("analytics_demo.json").read_text(encoding="utf-8"))
NAMESPACE = uuid.UUID(MANIFEST["namespace"])


def stable_id(key):
    return uuid.uuid5(NAMESPACE, key)


def parse(value):
    return datetime.fromisoformat(value)


def ensure(db, model, key, **values):
    if get_settings().catalog_discovery_enabled and model in {Work, Edition, CatalogSource}:
        from app.modules.books.policy import require_disposable_fixture
        require_disposable_fixture(db)
    entity_id = stable_id(key)
    existing = db.get(model, entity_id)
    if existing is not None:
        if any(getattr(existing, field) != value for field, value in values.items()):
            raise ValueError(f"El escenario {key} ya existe con valores distintos; no se sobrescribe")
    else:
        existing = model(id=entity_id, **values)
        db.add(existing)
        db.flush()
    entity_type = {ReadingEvent: "event", LibraryEntry: "library", Post: "post"}.get(model, model.__tablename__)
    db.execute(text("""INSERT INTO app.procedencia_demo (entity_type, entity_id, dataset_version)
        VALUES (:kind, :id, :version) ON CONFLICT DO NOTHING"""),
        {"kind": entity_type, "id": entity_id, "version": MANIFEST["version"]})
    return existing


def seed_scenarios(db, password):
    if get_settings().catalog_discovery_enabled:
        from app.modules.books.policy import require_disposable_fixture
        require_disposable_fixture(db)
    seed(db, password)
    reader_id = account_id("user:lector")
    author_id = account_id("user:autor")
    base = parse("2026-10-08T08:00:00-03:00")
    works, editions, entries = {}, {}, {}
    for spec in MANIFEST["works"]:
        work = ensure(db, Work, f"work:{spec['key']}", title=spec["title"], created_at=base)
        works[spec["key"]] = work
        for ed in spec["editions"]:
            key = f"edition:{spec['key']}:{ed['key']}"
            edition = ensure(db, Edition, key, work_id=work.id, title=spec["title"],
                             language=ed["language"], page_count=ed["pages"], created_at=base)
            editions[(spec["key"], ed["key"])] = edition
            ensure(db, CatalogSource, f"source:{key}", edition_id=edition.id, provider="libria-feed",
                   external_id=f"analytics-demo:{spec['key']}:{ed['key']}", fetched_at=base, created_at=base)
    for spec in MANIFEST["readings"]:
        work, edition = works[spec["work"]], editions[(spec["work"], spec["edition"])]
        created = parse(spec["created_at"])
        if work.id not in entries:
            entries[work.id] = ensure(db, LibraryEntry, f"library:{spec['work']}", user_id=reader_id,
                                      work_id=work.id, created_at=created)
        events = spec["events"]
        state = {"start": "reading", "progress": "reading", "correction": "reading",
                 "finish": "finished", "abandon": "abandoned"}[events[-1]["kind"]] if events else "pending"
        reading = ensure(db, Reading, f"reading:{spec['key']}", library_entry_id=entries[work.id].id,
                         work_id=work.id, edition_id=edition.id, status=state,
                         current_page=events[-1]["page"] if events else 0, total_pages=edition.page_count,
                         started_at=parse(events[0]["at"]) if events else None,
                         finished_at=parse(events[-1]["at"]) if state == "finished" else None,
                         abandoned_at=parse(events[-1]["at"]) if state == "abandoned" else None,
                         abandonment_reason="Escenario ficticio de abandono" if state == "abandoned" else None,
                         created_at=created)
        previous = 0
        for index, event in enumerate(events):
            key = f"event:{spec['key']}:{index}"
            ensure(db, ReadingEvent, key, reading_id=reading.id, actor_user_id=reader_id, kind=event["kind"],
                   previous_page=previous, page=event["page"], total_pages=edition.page_count,
                   is_public=False, reason="Corrección ficticia" if event["kind"] == "correction" else None,
                   created_at=parse(event["at"]))
            if event["kind"] in {"progress", "correction", "finish"}:
                ensure(db, ReadingProgress, f"progress:{spec['key']}:{index}", reading_id=reading.id,
                       page=event["page"], recorded_at=parse(event["at"]), created_at=parse(event["at"]))
            previous = event["page"]
    for spec in MANIFEST["posts"]:
        review = spec["source"] == "review"
        ensure(db, Post, f"post:{spec['key']}", user_id=author_id, author_profile_id=account_id("profile:autor"),
               legacy_content=review,
               author_role="autor", source=spec["source"], kind="reviews" if review else "community",
               publication_type=spec["publication_type"], body=f"Datos simulados: {spec['key']}",
               book_ref="analytics-demo:journey:es" if review else None,
               book_title=works["journey"].title if review else None, rating=4 if review else None,
               created_at=parse(spec["at"]))
    return {"dataset": MANIFEST["version"], "reference_date": MANIFEST["reference_date"],
            "readings": len(MANIFEST["readings"]), "events": sum(len(r["events"]) for r in MANIFEST["readings"]),
            "posts": len(MANIFEST["posts"])}


def main():
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("La carga ficticia solo está habilitada en desarrollo")
    with SessionLocal.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(963470015)"))
        result = seed_scenarios(db, settings.libria_demo_password)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
