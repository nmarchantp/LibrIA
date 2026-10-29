"""Carga inicial repetible del administrador y su biblioteca de ejemplo."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import uuid

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.books.identity import canonical_author_name, canonical_work_key
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor
from app.modules.books.service import verified_work_for_import
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent, ReadingProgress
from app.modules.social.models import Review, ReviewRevision
from scripts.seed_demo import seed as seed_demo_accounts
from scripts.seed_demo import stable_id as account_id


MANIFEST = json.loads(
    Path(__file__).with_name("default_admin_library.json").read_text(encoding="utf-8")
)
NAMESPACE = uuid.UUID(MANIFEST["namespace"])


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def _catalog_payload(spec: dict) -> dict:
    return {
        "kind": "books#volume",
        "id": f"default-admin:{spec['key']}",
        "volumeInfo": {
            "title": spec["title"],
            "authors": [spec["author"]],
            "language": "es",
            "pageCount": spec["pages"],
            "categories": spec["categories"],
        },
    }


def _ensure_author(db, work: Work, author_name: str) -> None:
    from app.modules.books.policy import reject_legacy_writer
    reject_legacy_writer()
    normalized = canonical_author_name(author_name)
    author = next(
        (
            item
            for item in db.scalars(select(Author)).all()
            if canonical_author_name(item.name) == normalized
        ),
        None,
    )
    if author is None:
        author = Author(id=stable_id(f"author:{normalized}"), name=author_name)
        db.add(author)
        db.flush()
    if db.get(WorkAuthor, (work.id, author.id)) is None:
        position = db.scalar(
            select(func.coalesce(func.max(WorkAuthor.position), 0)).where(
                WorkAuthor.work_id == work.id
            )
        )
        db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=position + 1))


def _ensure_catalog_book(db, spec: dict, created_at: datetime) -> tuple[Work, Edition]:
    if get_settings().catalog_discovery_enabled:
        # Demo metadata is not verified bibliographic evidence. Reuse a selected
        # existing edition or the seed's exact historical source; never title-match.
        selected = db.get(Edition, uuid.UUID(spec["catalog_edition_id"])) if spec.get("catalog_edition_id") else None
        if selected is None:
            known = db.scalar(select(CatalogSource).where(CatalogSource.provider == "libria-feed",
                CatalogSource.external_id == f"default-admin:{spec['key']}"))
            selected = db.get(Edition, known.edition_id) if known else None
        if selected is None:
            raise ValueError("Importa una publicación autorizada y proporciona --catalog-map; la semilla no crea obras en modo descubrimiento")
        return db.get(Work, selected.work_id), selected
    reference = f"default-admin:{spec['key']}"
    source = db.scalar(
        select(CatalogSource).where(
            CatalogSource.provider == "libria-feed",
            CatalogSource.external_id == reference,
        )
    )
    if source is not None:
        edition = db.get(Edition, source.edition_id)
        return db.get(Work, edition.work_id), edition

    candidate_titles = [spec["title"], *spec.get("aliases", [])]
    identity_keys = [
        key
        for title in candidate_titles
        if (key := canonical_work_key(title, [spec["author"]]))
    ]
    identity_key = identity_keys[0] if identity_keys else None
    work = next(
        (
            match
            for title in candidate_titles
            if (match := verified_work_for_import(db, title, [spec["author"]])) is not None
        ),
        None,
    )
    if work is None and identity_keys and db.scalar(
        select(Work.id).where(Work.identity_key.in_(identity_keys)).limit(1)
    ):
        # Una clave histórica aislada no basta para fusionar obras. Evita la
        # colisión sin adjudicarle a la semilla una identidad no verificada.
        identity_key = None
    if work is None:
        work = Work(
            id=stable_id(f"work:{spec['key']}"),
            title=spec["title"],
            identity_key=identity_key,
            original_language="es",
            categories=spec["categories"],
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(work)
        db.flush()
    _ensure_author(db, work, spec["author"])

    edition = db.scalar(
        select(Edition)
        .where(Edition.work_id == work.id, Edition.language == "es")
        .order_by(Edition.created_at, Edition.id)
    )
    if edition is None:
        edition = Edition(
            id=stable_id(f"edition:{spec['key']}"),
            work_id=work.id,
            title=spec["title"],
            language="es",
            page_count=spec["pages"],
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(edition)
        db.flush()
    # Las importaciones de Google ya crean su espejo ``libria-feed``. Reutilizarlo
    # evita que una misma lectura aparezca dos veces con referencias distintas.
    existing_feed = db.scalar(
        select(CatalogSource)
        .where(
            CatalogSource.edition_id == edition.id,
            CatalogSource.provider == "libria-feed",
        )
        .order_by(CatalogSource.created_at, CatalogSource.id)
    )
    if existing_feed is not None:
        return work, edition
    source = CatalogSource(
        id=stable_id(f"source:{spec['key']}"),
        edition_id=edition.id,
        provider="libria-feed",
        external_id=reference,
        fetched_at=created_at,
        synced_at=created_at,
        validation_status="validated",
        consolidation_status="automatic",
        payload=_catalog_payload(spec),
        detail_complete=True,
        created_at=created_at,
    )
    db.add(source)
    db.flush()
    return work, edition


def _ensure_finished_reading(
    db, spec: dict, work: Work, edition: Edition, user_id: uuid.UUID, finished_at: datetime
) -> None:
    entry = db.scalar(
        select(LibraryEntry).where(
            LibraryEntry.user_id == user_id, LibraryEntry.work_id == work.id
        )
    )
    if entry is None:
        entry = LibraryEntry(
            id=stable_id(f"library:{spec['key']}"),
            user_id=user_id,
            work_id=work.id,
            created_at=finished_at - timedelta(days=7),
            updated_at=finished_at,
        )
        db.add(entry)
        db.flush()
    # Si alguien ya usó esta entrada, su actividad tiene prioridad sobre la semilla.
    if db.scalar(select(Reading.id).where(Reading.library_entry_id == entry.id)) is not None:
        return

    started_at = finished_at - timedelta(days=5)
    reading = Reading(
        id=stable_id(f"reading:{spec['key']}"),
        library_entry_id=entry.id,
        work_id=work.id,
        edition_id=edition.id,
        status="finished",
        current_page=spec["pages"],
        total_pages=spec["pages"],
        started_at=started_at,
        finished_at=finished_at,
        created_at=started_at,
        updated_at=finished_at,
    )
    db.add(reading)
    db.flush()
    db.add_all(
        [
            ReadingEvent(
                id=stable_id(f"event:{spec['key']}:start"),
                reading_id=reading.id,
                actor_user_id=user_id,
                kind="start",
                previous_page=0,
                page=0,
                total_pages=spec["pages"],
                is_public=False,
                created_at=started_at,
            ),
            ReadingEvent(
                id=stable_id(f"event:{spec['key']}:finish"),
                reading_id=reading.id,
                actor_user_id=user_id,
                kind="finish",
                previous_page=0,
                page=spec["pages"],
                total_pages=spec["pages"],
                is_public=False,
                created_at=finished_at,
            ),
            ReadingProgress(
                id=stable_id(f"progress:{spec['key']}:finish"),
                reading_id=reading.id,
                page=spec["pages"],
                recorded_at=finished_at,
                created_at=finished_at,
            ),
        ]
    )


def _ensure_review(
    db, spec: dict, work: Work, edition: Edition, user_id: uuid.UUID, profile_id: uuid.UUID,
    published_at: datetime,
) -> None:
    existing = db.scalar(
        select(Review).where(
            Review.author_profile_id == profile_id, Review.work_id == work.id
        )
    )
    if existing is not None:
        return
    review = Review(
        id=stable_id(f"review:{spec['key']}"),
        author_profile_id=profile_id,
        created_by_user_id=user_id,
        work_id=work.id,
        edition_id=edition.id,
        body=spec["review"],
        rating=Decimal(str(spec["rating"])),
        dimension_ratings={},
        is_spoiler=False,
        status="published",
        published_at=published_at,
        created_at=published_at,
        updated_at=published_at,
        revision_number=1,
    )
    db.add(review)
    db.flush()
    db.add(
        ReviewRevision(
            review_id=review.id,
            revision_number=1,
            recorded_by_user_id=user_id,
            body=review.body,
            rating=review.rating,
            dimension_ratings={},
            is_spoiler=False,
            status="published",
            edition_id=edition.id,
            recorded_at=published_at,
        )
    )


def seed_default_admin(db, password: str, now: datetime | None = None, catalog_map: dict | None = None) -> dict:
    seed_demo_accounts(db, password, keys={"admin"})
    user_id = account_id("user:admin")
    profile_id = account_id("profile:admin")
    reference_time = now or datetime.now(timezone.utc)
    for index, spec in enumerate(MANIFEST["books"]):
        if catalog_map and spec["key"] in catalog_map:
            spec = {**spec, "catalog_edition_id": catalog_map[spec["key"]]}
        finished_at = reference_time - timedelta(days=(len(MANIFEST["books"]) - index) * 3)
        work, edition = _ensure_catalog_book(db, spec, finished_at - timedelta(days=7))
        _ensure_finished_reading(db, spec, work, edition, user_id, finished_at)
        _ensure_review(
            db, spec, work, edition, user_id, profile_id, finished_at + timedelta(hours=1)
        )
        db.flush()
    return {
        "dataset": MANIFEST["version"],
        "administrator": "demo.admin@example.com",
        "books": len(MANIFEST["books"]),
        "reviews": len(MANIFEST["books"]),
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-map", help="JSON object mapping demo book keys to explicitly selected, already imported edition UUIDs")
    args = parser.parse_args()
    catalog_map = json.loads(Path(args.catalog_map).read_text(encoding="utf-8")) if args.catalog_map else None
    settings = get_settings()
    if len(settings.libria_demo_password) < 8:
        raise SystemExit("Configura LIBRIA_DEMO_PASSWORD con al menos 8 caracteres")
    with SessionLocal.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(963470053)"))
        result = seed_default_admin(db, settings.libria_demo_password, catalog_map=catalog_map)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
