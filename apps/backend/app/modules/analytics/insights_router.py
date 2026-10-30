"""Interpretation is initiated by the owner or an authorized professional."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.modules.analytics.insights import MIN_GROUP, cached_interpretation, group_access, group_evidence, personal_evidence, require_group_access
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.analytics.recommendation_sync import recommendation_state
from app.modules.analytics.eligibility import reader_eligibility, require_reader_eligibility, locked_reader_access

router = APIRouter(prefix="/analytics", tags=["interpretations"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


@router.get("/me/free-usage")
def my_free_usage(response: Response, user: CurrentUser, db: Database):
    from app.modules.analytics.free_usage import free_usage
    response.headers["Cache-Control"] = "no-store"
    return free_usage(db, user.id, get_settings())


Provenance = Literal["unclassified", "operational"]


class InterpretationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provenance: Provenance = "unclassified"


class RecommendationsRequest(InterpretationRequest):
    exclude_ids: list[Annotated[str, Field(min_length=1,max_length=200)]] = Field(default_factory=list,max_length=1000)


def _recommendation_compatibility(result: dict) -> dict:
    """Keep the pre-stage-5 list shape while exposing the structured payload."""
    content = result.get("recommendations")
    if not isinstance(content, dict):
        if result.get("status") == "insufficient_data":
            return {**result, "status": "no_positive_ratings", "items": [], "has_more": False}
        return {**result, "items": []}
    items=[]
    for recommendation in content.get("recommendations") or []:
        sources=recommendation.get("sources") or []
        external=next((source.get("external_id") for source in sources
                       if source.get("provider") == "google-books"), None)
        volume={"id":external or recommendation.get("work_id"), "volumeInfo":{
            "title":recommendation.get("title"), "authors":recommendation.get("authors") or [],
            "imageLinks":{"thumbnail":recommendation.get("cover_url")} if recommendation.get("cover_url") else {}}}
        items.append({"volume":volume,"reason":recommendation.get("justification"),
                      "work_id":recommendation.get("work_id"),
                      "evidence_ids":recommendation.get("evidence_ids") or []})
    return {**result,"items":items,"has_more":False,
            "profile_interpretation":content.get("profile"),
            "provider":"gemini","model":get_settings().gemini_model}


@router.get("/me/recommendations/state")
def current_recommendation_state(response: Response, user: CurrentUser, db: Database):
    """Read-only: never creates work and never invokes an AI provider."""
    response.headers["Cache-Control"] = "no-store"
    from app.modules.analytics.generation_runtime import generation_runtime
    return {**_recommendation_compatibility(recommendation_state(db, user.id, enqueue=False)),
            **generation_runtime(get_settings())}


@router.post("/me/recommendations/sync")
def sync_recommendations(response: Response, user: CurrentUser, db: Database):
    """Cheap idempotent check used after login or renewed application use."""
    response.headers["Cache-Control"] = "no-store"
    return recommendation_state(db, user.id, enqueue=True, retry_failed=True)


@router.get("/me/recommendations")
def my_recommendations(response: Response, user: CurrentUser, db: Database, provenance: Provenance = "unclassified"):
    """Read persisted Gemini output; a screen read never invokes a provider."""
    response.headers["Cache-Control"] = "no-store"
    eligibility = reader_eligibility(db, user.id)
    if not eligibility["eligible"]:
        return locked_reader_access(eligibility)
    return recommendation_state(db, user.id, enqueue=False)


@router.post("/me/recommendations")
def generate_recommendations(payload: RecommendationsRequest, response: Response, user: CurrentUser, db: Database):
    """Disabled legacy batching endpoint; sync is the only enqueue boundary."""
    response.headers["Cache-Control"] = "no-store"
    raise HTTPException(status_code=405, detail="Usa la sincronización idempotente posterior al login o actividad")


@router.get("/access")
def access(response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    eligibility = reader_eligibility(db, user.id)
    return {"personal": eligibility["eligible"], "reader_eligibility": eligibility, "group": group_access(db, user.id)}


def overview(db, user_id, evidence, scope):
    cached = cached_interpretation(db, evidence, scope, user_id) if evidence else None
    return {"status": "ready" if evidence else "insufficient_group" if scope == "group" else "no_data",
            "evidence": evidence, "interpretation": cached,
            "ai_ready": False, "generation_status": "not_migrated",
            "provider": cached.get("provider") if cached else None,
            "model": cached.get("model") if cached else None,
            "minimum_participants": MIN_GROUP if scope == "group" else None}


@router.get("/me/insights")
def my_insights(response: Response, user: CurrentUser, db: Database, provenance: Provenance = "unclassified"):
    response.headers["Cache-Control"] = "no-store"
    eligibility = reader_eligibility(db, user.id)
    if not eligibility["eligible"]:
        return locked_reader_access(eligibility)
    return overview(db, user.id, personal_evidence(db, user.id, provenance), "personal")


@router.post("/me/interpretation")
def generate_personal(payload: InterpretationRequest, response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    require_reader_eligibility(db, user.id)
    raise HTTPException(status_code=501, detail="La interpretación clásica aún no tiene contrato Gemini aprobado")


@router.get("/group/insights")
def group_insights(response: Response, user: CurrentUser, db: Database, provenance: Provenance = "unclassified"):
    response.headers["Cache-Control"] = "no-store"
    require_group_access(db, user.id)
    return overview(db, user.id, group_evidence(db, provenance), "group")


@router.get('/group/community')
def community_dashboard(response: Response, user: CurrentUser, db: Database):
    response.headers['Cache-Control']='no-store'
    require_group_access(db,user.id)
    from app.modules.analytics.community import community_release
    return community_release(db)


@router.post("/group/interpretation")
def generate_group(payload: InterpretationRequest, response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    require_group_access(db, user.id)
    raise HTTPException(status_code=501, detail="La interpretación grupal aún no tiene contrato Gemini aprobado")
