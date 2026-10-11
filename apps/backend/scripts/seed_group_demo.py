"""A finite, repeatable cohort for demonstrating protected group analysis."""
import json
import uuid
from datetime import datetime

from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent
from app.modules.social.models import Review, ReviewRevision
from app.modules.users.models import User
from app.modules.users.identity_models import Profile, ProfileCapability
from scripts.seed_analytics_demo import seed_scenarios, stable_id as catalog_id

NAMESPACE = uuid.UUID("6d9d67c3-9d72-456d-9e4f-5fa29bb16c4e")
VERSION = "group-demo-v1"


def stable_id(key):
    return uuid.uuid5(NAMESPACE, key)


def ensure(db, model, key, **values):
    entity_id = stable_id(key)
    entity = db.get(model, entity_id)
    if entity is None:
        entity = model(id=entity_id, **values)
        db.add(entity)
        db.flush()
    elif any(getattr(entity, field) != value for field, value in values.items()):
        raise ValueError(f"El escenario {key} difiere del manifiesto; no se sobrescribe")
    entity_type = {ReadingEvent: "event", LibraryEntry: "library", Review: "review"}.get(model)
    if entity_type:
        db.execute(text("""INSERT INTO app.procedencia_demo (entity_type, entity_id, dataset_version)
            VALUES (:type, :id, :version) ON CONFLICT DO NOTHING"""),
            {"type": entity_type, "id": entity.id, "version": VERSION})
    return entity


def seed_group(db, password):
    seed_scenarios(db, password)
    work_id = catalog_id("work:journey")
    edition_id = catalog_id("edition:journey:es")
    created = datetime.fromisoformat("2026-10-10T08:00:00-03:00")
    started = datetime.fromisoformat("2026-10-10T09:00:00-03:00")
    progressed = datetime.fromisoformat("2026-10-10T10:00:00-03:00")
    finished = datetime.fromisoformat("2026-10-10T11:00:00-03:00")
    published = datetime.fromisoformat("2026-10-10T11:30:00-03:00")
    pages = db.execute(text("SELECT page_count FROM app.ediciones WHERE id=:id"), {"id": edition_id}).scalar_one()
    for index in range(12):
        key = f"reader:{index}"
        user = ensure(db, User, key, display_name=f"Participante ficticio {index + 1}", role="lector", created_at=created)
        profile = ensure(db, Profile, f"profile:{index}", owner_user_id=user.id, kind="personal",
                         display_name=user.display_name, verification_status="pending", created_at=created)
        if db.get(ProfileCapability, (profile.id, "lector")) is None:
            db.add(ProfileCapability(profile_id=profile.id, capability="lector"))
        library = ensure(db, LibraryEntry, f"library:{index}", user_id=user.id, work_id=work_id, created_at=created)
        is_finished = index < 6
        final_page = pages if is_finished else 50 + index
        reading = ensure(db, Reading, f"reading:{index}", library_entry_id=library.id, work_id=work_id,
                         edition_id=edition_id, status="finished" if is_finished else "abandoned", current_page=final_page,
                         total_pages=pages, started_at=started, finished_at=finished if is_finished else None,
                         abandoned_at=None if is_finished else finished,
                         abandonment_reason=None if is_finished else "Escenario ficticio para el comité", created_at=created)
        for number, (kind, previous, page, at) in enumerate((
            ("start", 0, 0, started), ("progress", 0, 50 + index, progressed),
            ("finish" if is_finished else "abandon", 50 + index, final_page, finished),
        )):
            ensure(db, ReadingEvent, f"event:{index}:{number}", reading_id=reading.id, actor_user_id=user.id,
                   kind=kind, previous_page=previous, page=page, total_pages=pages, is_public=False, created_at=at)
        review = ensure(db, Review, f"review:{index}", author_profile_id=profile.id, created_by_user_id=user.id,
                        work_id=work_id, edition_id=edition_id, body="Reseña ficticia para validar el resumen grupal.",
                        rating=3 + index % 3, is_spoiler=False, status="published", published_at=published,
                        revision_number=1, created_at=published, updated_at=published)
        revision = db.get(ReviewRevision, (review.id, 1))
        if revision is None:
            db.add(ReviewRevision(review_id=review.id, revision_number=1, recorded_by_user_id=user.id,
                                 body=review.body, rating=review.rating, is_spoiler=False, status="published",
                                 edition_id=edition_id, recorded_at=published))
        elif revision.rating != review.rating or revision.recorded_at != published:
            raise ValueError("La revisión ficticia ya existe con otros datos")
    db.flush()
    return {"dataset": VERSION, "participants": 12, "events": 36, "reviews": 12,
            "finished_attempts": 6, "abandoned_attempts": 6}


def main():
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("La cohorte ficticia solo se carga en desarrollo")
    with SessionLocal.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(963470017)"))
        print(json.dumps(seed_group(db, settings.libria_demo_password)))


if __name__ == "__main__":
    main()
