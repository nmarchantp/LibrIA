"""Preview or repair an explicitly selected local catalog group, preserving history."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.books.canonical import identity_snapshot
from app.modules.books.identity import identity_matches
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor


def group_plan(db, target_id, source_ids):
    snapshot = identity_snapshot(db, [target_id, *source_ids])
    target = db.get(Work, snapshot.root(target_id))
    members = list(snapshot.mapping)
    works = db.scalars(select(Work).where(Work.id.in_(members)).order_by(Work.id)).all()
    names = {}
    for work_id, name in db.execute(select(WorkAuthor.work_id, Author.name).join(
            Author, WorkAuthor.author_id == Author.id).where(WorkAuthor.work_id.in_(members))):
        names.setdefault(work_id, []).append(name)
    target_authors = names.get(target.id, [])
    for work in works:
        if not identity_matches(target.title, target_authors, work.title, names.get(work.id, [])):
            raise ValueError("Selected works have different titles, authors or publication forms")
    editions = db.scalars(select(Edition).where(Edition.work_id.in_(members)).order_by(Edition.id)).all()
    for edition in editions:
        if not identity_matches(target.title, target_authors, edition.title, names.get(edition.work_id, [])):
            raise ValueError("A stored edition is not compatible with the selected novel")
    for source in db.scalars(select(CatalogSource).where(CatalogSource.edition_id.in_([e.id for e in editions]))):
        info = (source.payload or {}).get("volumeInfo") or {}
        if info.get("authors") and not identity_matches(target.title, target_authors,
                                                       info.get("title", ""), info["authors"]):
            raise ValueError("A provider source contradicts the requested grouping")
    collisions = db.execute(text("""SELECT author_profile_id FROM app.resenas
        WHERE work_id=ANY(:ids) GROUP BY author_profile_id HAVING count(*)>1"""), {"ids": members}).first()
    if collisions:
        raise ValueError("Review collisions require an explicit selection in catalog administration")
    return {"target_work_id": str(target.id), "title": target.title,
            "physical_work_count": len(works), "canonical_work_count": len({snapshot.root(w.id) for w in works}),
            "edition_count": len(editions), "isbn_count": len({e.isbn13 or e.isbn10 for e in editions if e.isbn13 or e.isbn10}),
            "members": [{"id": str(w.id), "title": w.title} for w in works]}


def repair_group(engine, actor, target_id, source_ids):
    from app.modules.books.admin_router import preview_transaction
    from app.modules.books.merge_execution import execute_merge
    from app.modules.books.merge_preview import preview_merge
    from app.modules.books.policy import execute_catalog_command

    with Session(engine) as db:
        plan = group_plan(db, target_id, source_ids)
    operations = []
    for source in source_ids:
        with Session(engine) as db:
            current = identity_snapshot(db, [source, target_id])
            if current.root(source) == current.root(target_id):
                continue
            preview = preview_transaction(db, lambda: preview_merge(db, actor, source, target_id))
            if preview["conflicts"]:
                raise ValueError("Review conflict appeared; resolve it in catalog administration")
            decisions = {"confirmation": "FUSIONAR", "reason": "User-requested grouping of matching title/author edition variants",
                         "metadata_policy": "preserve_destination", "library_policy": "preserve_all", "review_ids": []}
            result = execute_catalog_command(db, lambda: execute_merge(
                db, actor, uuid.UUID(preview["preview_id"]), "repair-group:" + preview["preview_id"], decisions))
            operations.append(result["operation_id"])
    with Session(engine) as db:
        after = group_plan(db, target_id, source_ids)
    return {"before": plan, "after": after, "operation_ids": operations, "historical_records_preserved": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=uuid.UUID, required=True)
    parser.add_argument("--source", type=uuid.UUID, action="append", required=True)
    parser.add_argument("--actor", type=uuid.UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    url = make_url(settings.database_url)
    if settings.app_env != "development" or url.host not in {"127.0.0.1", "localhost"} or url.database != "libria":
        raise SystemExit("This maintenance command only targets the configured local development LibrIA database")
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        plan = group_plan(db, args.target, args.source)
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=True, indent=2))
        return
    if not args.actor:
        raise SystemExit("--apply requires an existing administrator UUID in --actor")
    from app.modules.books.merge_preview import require_admin
    with Session(engine) as db:
        require_admin(db, args.actor)
    backup_dir = Path(__file__).resolve().parents[3] / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / ("catalog-group-" + stamp + ".dump")
    binaries = Path(r"C:\Program Files\PostgreSQL\17\bin")
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    subprocess.run([str(binaries / "pg_dump.exe"), "-h", url.host, "-p", str(url.port or 5432),
                    "-U", url.username, "-Fc", "-f", str(backup), url.database], env=env, check=True, capture_output=True)
    subprocess.run([str(binaries / "pg_restore.exe"), "--list", str(backup)], check=True, capture_output=True)
    result = repair_group(engine, args.actor, args.target, args.source)
    report = backup_dir / ("catalog-group-" + stamp + ".json")
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    print("Backup and report: " + str(backup_dir))


if __name__ == "__main__":
    main()
