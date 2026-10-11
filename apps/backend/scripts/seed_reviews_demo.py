"""Reseñas ficticias repetibles con borrador, edición, ocultamiento y republicación."""
import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.social.models import Review, ReviewRevision
from scripts.seed_analytics_demo import seed_scenarios, stable_id as source_id
from scripts.seed_demo import stable_id as account_id

MANIFEST = json.loads(Path(__file__).with_name("reviews_demo.json").read_text(encoding="utf-8"))
NAMESPACE = uuid.UUID(MANIFEST["namespace"])


def stable_id(key):
    return uuid.uuid5(NAMESPACE, key)


def seed_reviews(db, password):
    seed_scenarios(db, password)
    for spec in MANIFEST["reviews"]:
        versions = spec["revisions"]
        last = versions[-1]
        edition_id = source_id(f"edition:{spec['work']}:{spec['edition']}")
        first_publication = next((datetime.fromisoformat(v["at"]) for v in versions if v["status"] == "published"), None)
        values = {"author_profile_id": account_id(f"profile:{spec['account']}"),
                  "created_by_user_id": account_id(f"user:{spec['account']}"),
                  "work_id": source_id(f"work:{spec['work']}"), "edition_id": edition_id,
                  "body": f"Datos simulados: {spec['key']} / versión {len(versions)}",
                  "rating": last["rating"], "is_spoiler": spec.get("spoiler", False),
                  "status": last["status"], "published_at": first_publication,
                  "created_at": datetime.fromisoformat(versions[0]["at"]),
                  "updated_at": datetime.fromisoformat(last["at"]), "revision_number": len(versions)}
        review_id = stable_id(spec["key"])
        existing = db.get(Review, review_id)
        if existing:
            if any(getattr(existing, key) != value for key, value in values.items()):
                raise ValueError("El escenario existente fue modificado; no se sobrescribe")
        else:
            db.add(Review(id=review_id, **values))
            db.flush()
        for index, version in enumerate(versions, 1):
            snapshot = {"recorded_by_user_id": values["created_by_user_id"],
                        "body": f"Datos simulados: {spec['key']} / versión {index}",
                        "rating": version["rating"], "is_spoiler": values["is_spoiler"],
                        "status": version["status"], "edition_id": edition_id,
                        "recorded_at": datetime.fromisoformat(version["at"])}
            revision = db.get(ReviewRevision, (review_id, index))
            if revision:
                if any(getattr(revision, key) != value for key, value in snapshot.items()):
                    raise ValueError("La revisión ficticia existente no coincide; no se sobrescribe")
            else:
                db.add(ReviewRevision(review_id=review_id, revision_number=index, **snapshot))
        db.execute(text("""INSERT INTO app.procedencia_demo (entity_type, entity_id, dataset_version)
            VALUES ('review', :id, :version) ON CONFLICT DO NOTHING"""), {"id": review_id, "version": MANIFEST["version"]})
        db.flush()
    return {"dataset": MANIFEST["version"], "reviews": len(MANIFEST["reviews"]),
            "revisions": sum(len(r["revisions"]) for r in MANIFEST["reviews"]), "reference_date": MANIFEST["reference_date"]}


def main():
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("La carga ficticia solo está habilitada en desarrollo")
    with SessionLocal.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(963470016)"))
        result = seed_reviews(db, settings.libria_demo_password)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
