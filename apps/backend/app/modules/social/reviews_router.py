"""Reseñas por perfil y obra; las ediciones conservan primera publicación."""
from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.service import equivalent_work_ids
from app.modules.social.models import Review, ReviewRevision
from app.modules.social.schemas import PostResponse, ReviewCreate, ReviewUpdate
from app.modules.social.router import as_review_response
from app.modules.users.identities import personal_profile, require_actor
from app.modules.users.models import User

router = APIRouter(prefix="/reviews", tags=["reviews"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


async def parse_review_request(request, schema):
    uploads = []
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("application/json"):
            try:
                payload = await request.json()
            except ValueError:
                raise HTTPException(status_code=422, detail="El JSON no es válido") from None
        elif content_type.startswith("multipart/form-data"):
            try:
                form = await request.form(max_files=1, max_fields=len(schema.model_fields) + 1)
            except MultiPartException:
                raise HTTPException(status_code=422, detail="Las reseñas solo admiten texto, sin archivos") from None
            uploads = [value for key, value in form.multi_items() if isinstance(value, UploadFile)]
            if uploads:
                raise HTTPException(status_code=422, detail="Las reseñas solo admiten texto, sin archivos")
            payload = dict(form.items())
            for field in ("rating", "edition_id", "author_profile_id"):
                if payload.get(field) == "":
                    payload[field] = None
        else:
            raise HTTPException(status_code=415, detail="Usa JSON o multipart/form-data")
        try:
            data = schema.model_validate(payload)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors(include_context=False)) from error
        return data
    finally:
        for upload in uploads:
            await upload.close()


def validate_edition(db, work_id, edition_id):
    if db.get(Work, work_id) is None:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    if edition_id:
        edition = db.get(Edition, edition_id)
        if edition is None or edition.work_id not in equivalent_work_ids(db, work_id):
            raise HTTPException(status_code=422, detail="La edición debe pertenecer a la obra")


def record_revision(db, review, user, now):
    db.add(ReviewRevision(review_id=review.id, revision_number=review.revision_number,
                         recorded_by_user_id=user.id, body=review.body, rating=review.rating,
                         dimension_ratings=review.dimension_ratings or {},
                         is_spoiler=review.is_spoiler, status=review.status,
                         edition_id=review.edition_id, recorded_at=now))


@router.get("/me", response_model=list[PostResponse])
def own_reviews(response: Response, user: CurrentUser, db: Database, work_id: uuid.UUID | None = None):
    response.headers["Cache-Control"] = "no-store"
    profile = personal_profile(db, user)
    query = select(Review).where(Review.author_profile_id == profile.id)
    if work_id:
        query = query.where(Review.work_id.in_(equivalent_work_ids(db, work_id)))
    reviews = db.scalars(query.order_by(Review.updated_at.desc()).limit(100)).all()
    return [as_review_response(db, review) for review in reviews]


@router.get("/by-book/{book_ref}")
def book_reviews(book_ref: str, response: Response, db: Database,
                 offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=50)):
    response.headers["Cache-Control"] = "no-store"
    try:
        internal_work_id = uuid.UUID(book_ref)
    except ValueError:
        internal_work_id = None
    work_id = internal_work_id if internal_work_id and db.get(Work, internal_work_id) else db.scalar(
        select(Edition.work_id).join(CatalogSource, CatalogSource.edition_id == Edition.id)
        .where(CatalogSource.external_id == book_ref,
               CatalogSource.provider.in_(["google-books", "libria-feed"]))
        .order_by(CatalogSource.provider).limit(1))
    if work_id is None:
        return {"items": [], "has_more": False}
    reviews = db.scalars(select(Review).where(Review.work_id.in_(equivalent_work_ids(db, work_id)), Review.status == "published")
                         .order_by(Review.published_at.desc(), Review.id.desc())
                         .offset(offset).limit(limit + 1)).all()
    return {"items": [as_review_response(db, review) for review in reviews[:limit]],
            "has_more": len(reviews) > limit}


@router.post("", response_model=PostResponse, status_code=201)
async def create_review(request: Request, response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    data = await parse_review_request(request, ReviewCreate)
    profile_id = data.author_profile_id or personal_profile(db, user).id
    profile = require_actor(db, user, profile_id)
    if profile.kind != "personal":
        raise HTTPException(status_code=403, detail="Las reseñas requieren tu perfil personal")
    validate_edition(db, data.work_id, data.edition_id)
    existing = db.scalar(select(Review).where(Review.author_profile_id == profile.id,
                                               Review.work_id.in_(equivalent_work_ids(db, data.work_id))))
    if existing:
        raise HTTPException(status_code=409, detail="Ya tienes una reseña de esta obra; edítala para conservar su historial")
    now = datetime.now(timezone.utc)
    review = Review(author_profile_id=profile.id, created_by_user_id=user.id, work_id=data.work_id,
                    edition_id=data.edition_id, body=data.body, rating=data.rating,
                    dimension_ratings=data.dimension_ratings, is_spoiler=data.is_spoiler,
                    status=data.status, published_at=now if data.status == "published" else None,
                    created_at=now, updated_at=now, revision_number=1)
    db.add(review)
    try:
        db.flush()
        record_revision(db, review, user, now)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise HTTPException(status_code=409, detail="Ya existe una reseña de esta obra") from None
        raise
    return as_review_response(db, review)


@router.get("/{review_id}", response_model=PostResponse)
def public_review(review_id: uuid.UUID, response: Response, db: Database):
    response.headers["Cache-Control"] = "no-store"
    review = db.scalar(select(Review).where(Review.id == review_id, Review.status == "published"))
    if review is None:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    return as_review_response(db, review)


@router.put("/{review_id}", response_model=PostResponse)
async def update_review(review_id: uuid.UUID, request: Request, response: Response, user: CurrentUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    data = await parse_review_request(request, ReviewUpdate)
    review = db.scalar(select(Review).where(Review.id == review_id, Review.created_by_user_id == user.id).with_for_update())
    if review is None:
        raise HTTPException(status_code=404, detail="Reseña propia no encontrada")
    require_actor(db, user, review.author_profile_id)
    validate_edition(db, review.work_id, data.edition_id)
    if data.status == "draft" and review.published_at is not None:
        raise HTTPException(status_code=422, detail="Una reseña publicada puede ocultarse, pero no volver a borrador")
    if data.status == "hidden" and review.published_at is None:
        raise HTTPException(status_code=422, detail="Un borrador todavía no tiene una publicación para ocultar")
    now = datetime.now(timezone.utc)
    review.body, review.rating, review.dimension_ratings, review.is_spoiler = data.body, data.rating, data.dimension_ratings, data.is_spoiler
    review.edition_id, review.status = data.edition_id, data.status
    review.updated_at = now
    review.revision_number += 1
    if data.status == "published" and review.published_at is None:
        review.published_at = now
    record_revision(db, review, user, now)
    db.commit()
    return as_review_response(db, review)
