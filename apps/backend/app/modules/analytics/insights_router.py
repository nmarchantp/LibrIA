"""Interpretation is initiated by the owner or an authorized professional."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.modules.analytics.insights import MIN_GROUP, cached_interpretation, group_access, group_evidence, interpret, personal_evidence, require_group_access
from app.modules.analytics.interpretation_provider import provider_ready
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.analytics.recommendations import recommendations
from app.modules.analytics.eligibility import reader_eligibility, require_reader_eligibility, locked_reader_access

router = APIRouter(prefix="/analytics", tags=["interpretations"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]
Provenance = Literal["unclassified", "operational"]


class InterpretationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provenance: Provenance = "unclassified"


class RecommendationsRequest(InterpretationRequest):
    exclude_ids: list[Annotated[str, Field(min_length=1,max_length=200)]] = Field(default_factory=list,max_length=1000)


@router.get("/me/recommendations")
def my_recommendations(response: Response, user: CurrentUser, db: Database, provenance: Provenance = "unclassified"):
    response.headers["Cache-Control"] = "no-store"
    eligibility = reader_eligibility(db, user.id)
    if not eligibility["eligible"]:
        return locked_reader_access(eligibility)
    return recommendations(db, user.id, provenance)


@router.post("/me/recommendations")
def generate_recommendations(payload: RecommendationsRequest, response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    require_reader_eligibility(db, user.id)
    return recommendations(db, user.id, payload.provenance, create=True, exclude_ids=payload.exclude_ids)


@router.get("/access")
def access(response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    eligibility = reader_eligibility(db, user.id)
    return {"personal": eligibility["eligible"], "reader_eligibility": eligibility, "group": group_access(db, user.id)}


def overview(db, user_id, evidence, scope):
    return {"status": "ready" if evidence else "insufficient_group" if scope == "group" else "no_data",
            "evidence": evidence, "interpretation": cached_interpretation(db, evidence, scope, user_id) if evidence else None,
            "ai_ready": provider_ready(), "provider": "ollama", "model": get_settings().ai_model,
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
    evidence = personal_evidence(db, user.id, payload.provenance)
    if evidence is None:
        raise HTTPException(status_code=422, detail="No hay indicadores propios para esta procedencia")
    return interpret(db, evidence, "personal", user.id)


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
    evidence = group_evidence(db, payload.provenance)
    if evidence is None:
        raise HTTPException(status_code=422, detail="El conjunto no cumple el mínimo de participantes para publicar resultados")
    return interpret(db, evidence, "group", user.id)
