import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user, get_optional_current_user
from app.modules.social.models import Post, PostComment, PostImage, PostLike, ProfileFollow, Review, ReviewLike
from app.modules.social.schemas import (
    CommentCreate,
    CommentResponse,
    PostCreate,
    PostLikeResponse,
    PostResponse,
    ProfileFollowResponse,
)
from app.modules.users.models import User
from app.modules.library.models import ReadingEvent, Reading
from app.modules.books.models import Work, CatalogSource, Edition
from app.modules.users.identities import personal_profile, publication_role, require_actor
from app.modules.users.identity_models import Profile

router = APIRouter(prefix="/posts", tags=["posts"])
profile_social_router = APIRouter(prefix="/profiles", tags=["profiles"])
MAX_POST_IMAGES = 10
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_TOTAL_BYTES = 25 * 1024 * 1024


def as_response(post: Post, author: str, author_role: str, image_ids: list[uuid.UUID] | None = None) -> PostResponse:
    return PostResponse(id=post.id, user_id=post.user_id, author=author, author_role=post.author_role or author_role,
                        author_profile_id=post.author_profile_id, publication_type=post.publication_type,
                        images=[f"/posts/{post.id}/images/{image_id}" for image_id in image_ids or []],
                        source=post.source, kind=post.kind, title=post.title,
                        body=post.body, book_ref=post.book_ref, book_title=post.book_title,
                        rating=post.rating, progress_percent=post.progress_percent,
                        reading_event=post.reading_event, created_at=post.created_at)


def image_content_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def as_comment_response(comment: PostComment, author: str, author_role: str) -> CommentResponse:
    return CommentResponse(id=comment.id, post_id=comment.post_id or comment.reading_event_id or comment.review_id, user_id=comment.user_id,
                           author=author, author_role=author_role, body=comment.body, created_at=comment.created_at)


def visible_posts():
    return and_(Post.source.in_(("community", "event")), Post.author_role != "lector")


def require_post(db: Session, post_id: uuid.UUID) -> str:
    if db.scalar(select(Post.id).where(Post.id == post_id, visible_posts())) is not None:
        return "publication"
    if db.scalar(select(ReadingEvent.id).where(ReadingEvent.id == post_id, ReadingEvent.is_public)) is not None:
        return "reading_event"
    if db.scalar(select(Review.id).where(Review.id == post_id, Review.status == "published").with_for_update()) is not None:
        return "review"
    raise HTTPException(status_code=404, detail="Contenido no encontrado")


def as_review_response(db: Session, review: Review) -> PostResponse:
    profile = db.get(Profile, review.author_profile_id)
    work = db.get(Work, review.work_id)
    edition = db.get(Edition, review.edition_id) if review.edition_id else None
    reference = db.scalar(select(CatalogSource.external_id).where(
        CatalogSource.edition_id == review.edition_id, CatalogSource.provider == "libria-feed")) if review.edition_id else None
    return PostResponse(id=review.id, feed_item_type="review", author_profile_id=profile.id,
                        user_id=profile.owner_user_id, author=profile.display_name,
                        author_role=publication_role(db, profile), source="review", kind="reviews",
                        title=None, body=review.body, book_ref=reference, book_title=work.title,
                        book_cover_url=edition.cover_url if edition else None,
                        rating=review.rating, progress_percent=None, reading_event=None,
                        work_id=review.work_id, edition_id=review.edition_id, is_spoiler=review.is_spoiler,
                        status=review.status, published_at=review.published_at, updated_at=review.updated_at,
                        revision_number=review.revision_number, created_at=review.published_at or review.created_at,
                        images=[])


def as_reading_response(event: ReadingEvent, title: str, author: User,
                        book_ref: str | None = None, cover_url: str | None = None) -> PostResponse:
    percent = round(event.page * 100 / event.total_pages)
    body = {"start": f'Comenzó a leer "{title}".', "progress": f'Llegó al {percent} % de "{title}".',
            "finish": f'Terminó "{title}".', "abandon": f'Abandonó "{title}".'}.get(event.kind, "")
    return PostResponse(id=event.id, feed_item_type="reading_event", user_id=author.id,
                        author=author.display_name, author_role=author.role, source="reading", kind="progress",
                        title=None, body=body, book_ref=book_ref, book_title=title, book_cover_url=cover_url, rating=None,
                        progress_percent=percent, reading_event=event.kind, created_at=event.created_at)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(request: Request, user: Annotated[User, Depends(get_current_user)],
                      db: Annotated[Session, Depends(get_db)]) -> PostResponse:
    content_type = request.headers.get("content-type", "")
    uploads: list[UploadFile] = []
    if content_type.startswith("multipart/form-data"):
        try:
            form = await request.form(max_files=MAX_POST_IMAGES + 1, max_fields=len(PostCreate.model_fields))
        except MultiPartException as error:
            raise HTTPException(status_code=422, detail=f"Una publicación admite hasta {MAX_POST_IMAGES} imágenes") from error
        payload = {}
        for field in PostCreate.model_fields:
            value = form.get(field)
            if isinstance(value, str) and not value.strip() and field in {"title", "book_ref", "book_title", "publication_type"}:
                value = None
            if value is not None:
                payload[field] = value
        raw_uploads = form.getlist("images")
        if any(not isinstance(image, UploadFile) for image in raw_uploads):
            for image in raw_uploads:
                if isinstance(image, UploadFile):
                    await image.close()
            raise HTTPException(status_code=422, detail="Cada imagen debe ser un archivo")
        uploads = raw_uploads
    elif content_type.startswith("application/json"):
        try:
            payload = await request.json()
        except ValueError as error:
            raise HTTPException(status_code=422, detail="El cuerpo JSON no es válido") from error
    else:
        raise HTTPException(status_code=415, detail="Usa JSON o multipart/form-data")
    try:
        data = PostCreate.model_validate(payload)
    except ValidationError as error:
        for upload in uploads:
            await upload.close()
        raise HTTPException(status_code=422, detail=error.errors(include_context=False)) from error

    if len(uploads) > MAX_POST_IMAGES:
        for upload in uploads:
            await upload.close()
        raise HTTPException(status_code=422, detail=f"Una publicación admite hasta {MAX_POST_IMAGES} imágenes")
    image_data: list[tuple[str, bytes]] = []
    total_image_bytes = 0
    try:
        for upload in uploads:
            content = await upload.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Cada imagen debe pesar como máximo 5 MB")
            detected_type = image_content_type(content)
            if detected_type is None:
                raise HTTPException(status_code=415, detail="Formato de imagen no admitido; usa JPEG, PNG, GIF o WebP")
            total_image_bytes += len(content)
            if total_image_bytes > MAX_IMAGES_TOTAL_BYTES:
                raise HTTPException(status_code=413, detail="Las imágenes de una publicación no pueden superar 25 MB")
            image_data.append((detected_type, content))
    finally:
        for upload in uploads:
            await upload.close()

    profile = require_actor(db, user, data.author_profile_id) if data.author_profile_id else personal_profile(db, user)
    role = "admin" if user.role == "admin" and profile.kind == "personal" else publication_role(db, profile)
    if role == "lector":
        raise HTTPException(status_code=403, detail="Los lectores solo pueden publicar reseñas de libros")
    publication_type = data.publication_type or ("event" if data.source == "event" else "free")
    if (publication_type == "event") != (data.source == "event"):
        raise HTTPException(status_code=422, detail="El tipo no corresponde al contenido")
    post = Post(user_id=user.id, author_role=role, author_profile_id=profile.id,
                publication_type=publication_type,
                **data.model_dump(exclude={"author_profile_id", "publication_type"}))
    db.add(post)
    db.flush()
    images = [PostImage(post_id=post.id, content_type=image_type, data=content)
              for image_type, content in image_data]
    db.add_all(images)
    db.commit()
    db.refresh(post)
    return as_response(post, profile.display_name, role, [image.id for image in images])


@router.get("", response_model=list[PostResponse])
def list_posts(db: Annotated[Session, Depends(get_db)],
               user: Annotated[User | None, Depends(get_optional_current_user)],
               limit: int = Query(50, ge=1, le=100)) -> list[PostResponse]:
    rows = db.execute(select(Post, User.display_name, User.role).join(User, Post.user_id == User.id)
                      .where(visible_posts())
                      .order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)).all()
    profile_ids = {post.author_profile_id for post, _, _ in rows if post.author_profile_id}
    names = dict(db.execute(select(Profile.id, Profile.display_name).where(Profile.id.in_(profile_ids))).all())
    post_ids = [post.id for post, _, _ in rows]
    image_ids: dict[uuid.UUID, list[uuid.UUID]] = {}
    if post_ids:
        for post_id, image_id in db.execute(
            select(PostImage.post_id, PostImage.id)
            .where(PostImage.post_id.in_(post_ids))
            .order_by(PostImage.created_at, PostImage.id)
        ):
            image_ids.setdefault(post_id, []).append(image_id)
    like_counts = dict(db.execute(
        select(PostLike.post_id, func.count())
        .where(PostLike.post_id.in_(post_ids))
        .group_by(PostLike.post_id)
    ).all()) if post_ids else {}
    liked_ids = set(db.scalars(select(PostLike.post_id).where(
        PostLike.post_id.in_(post_ids), PostLike.user_id == user.id
    ))) if user and post_ids else set()
    followed_ids = set(db.scalars(select(ProfileFollow.profile_id).where(
        ProfileFollow.profile_id.in_(profile_ids), ProfileFollow.user_id == user.id
    ))) if user and profile_ids else set()
    items = []
    for post, name, role in rows:
        item = as_response(post, names.get(post.author_profile_id, name), role, image_ids.get(post.id))
        items.append(item.model_copy(update={
            "like_count": like_counts.get(post.id, 0),
            "liked_by_me": post.id in liked_ids,
            "following_author": post.author_profile_id in followed_ids,
        }))
    book_reference = select(CatalogSource.external_id).where(
        CatalogSource.edition_id == Reading.edition_id,
        CatalogSource.provider == "libria-feed").correlate(Reading).scalar_subquery()
    events = db.execute(select(ReadingEvent, Work.title, User, book_reference, Edition.cover_url)
                        .join(Reading, Reading.id == ReadingEvent.reading_id)
                        .join(Work, Work.id == Reading.work_id)
                        .join(Edition, Edition.id == Reading.edition_id)
                        .join(User, User.id == ReadingEvent.actor_user_id)
                        .where(ReadingEvent.is_public)
                        .order_by(ReadingEvent.created_at.desc(), ReadingEvent.id.desc()).limit(limit)).all()
    items.extend(as_reading_response(event, title, author, reference, cover)
                 for event, title, author, reference, cover in events)
    reviews = db.scalars(select(Review).where(Review.status == "published")
                         .order_by(Review.published_at.desc(), Review.id.desc()).limit(limit)).all()
    review_ids = [review.id for review in reviews]
    review_counts = dict(db.execute(select(ReviewLike.review_id, func.count())
                                   .where(ReviewLike.review_id.in_(review_ids)).group_by(ReviewLike.review_id)).all()) if review_ids else {}
    liked_reviews = set(db.scalars(select(ReviewLike.review_id).where(
        ReviewLike.review_id.in_(review_ids), ReviewLike.user_id == user.id))) if user and review_ids else set()
    review_profiles = {review.author_profile_id for review in reviews}
    followed_reviews = set(db.scalars(select(ProfileFollow.profile_id).where(
        ProfileFollow.profile_id.in_(review_profiles), ProfileFollow.user_id == user.id))) if user and review_profiles else set()
    for review in reviews:
        items.append(as_review_response(db, review).model_copy(update={
            "like_count": review_counts.get(review.id, 0), "liked_by_me": review.id in liked_reviews,
            "following_author": review.author_profile_id in followed_reviews}))
    return sorted(items, key=lambda item: (item.created_at, str(item.id)), reverse=True)[:limit]


@router.get("/{post_id}/images/{image_id}")
def get_post_image(post_id: uuid.UUID, image_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> Response:
    kind = require_post(db, post_id)
    if kind != "publication":
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    image = db.scalar(select(PostImage).where(PostImage.id == image_id, PostImage.post_id == post_id))
    if image is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return Response(image.data, media_type=image.content_type, headers={"X-Content-Type-Options": "nosniff"})


@router.put("/{post_id}/like", response_model=PostLikeResponse)
def like_post(post_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
              db: Annotated[Session, Depends(get_db)]) -> PostLikeResponse:
    kind = require_post(db, post_id)
    if kind == "reading_event":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    model, target, key = (ReviewLike, ReviewLike.review_id, "review_id") if kind == "review" else (PostLike, PostLike.post_id, "post_id")
    db.execute(insert(model).values(**{key: post_id, "user_id": user.id})
               .on_conflict_do_nothing(index_elements=[key, "user_id"]))
    db.commit()
    count = db.scalar(select(func.count()).select_from(model).where(target == post_id)) or 0
    return PostLikeResponse(like_count=count, liked_by_me=True)


@router.delete("/{post_id}/like", response_model=PostLikeResponse)
def unlike_post(post_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
                db: Annotated[Session, Depends(get_db)]) -> PostLikeResponse:
    kind = require_post(db, post_id)
    if kind == "reading_event":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    model, target = (ReviewLike, ReviewLike.review_id) if kind == "review" else (PostLike, PostLike.post_id)
    db.query(model).filter(target == post_id, model.user_id == user.id).delete()
    db.commit()
    count = db.scalar(select(func.count()).select_from(model).where(target == post_id)) or 0
    return PostLikeResponse(like_count=count, liked_by_me=False)


@profile_social_router.post("/{profile_id}/follow", response_model=ProfileFollowResponse)
def follow_profile(profile_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
                   db: Annotated[Session, Depends(get_db)]) -> ProfileFollowResponse:
    if db.scalar(select(Profile.id).where(Profile.id == profile_id)) is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    db.execute(insert(ProfileFollow).values(profile_id=profile_id, user_id=user.id)
               .on_conflict_do_nothing(index_elements=["profile_id", "user_id"]))
    db.commit()
    return ProfileFollowResponse(following=True)


@profile_social_router.delete("/{profile_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_profile(profile_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
                     db: Annotated[Session, Depends(get_db)]) -> Response:
    if db.scalar(select(Profile.id).where(Profile.id == profile_id)) is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    db.query(ProfileFollow).filter(ProfileFollow.profile_id == profile_id, ProfileFollow.user_id == user.id).delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{post_id}/comments", response_model=list[CommentResponse])
def list_comments(post_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                  limit: int = Query(100, ge=1, le=100)) -> list[CommentResponse]:
    require_post(db, post_id)
    rows = db.execute(select(PostComment, User.display_name, User.role)
                      .join(User, PostComment.user_id == User.id)
                      .where(or_(PostComment.post_id == post_id, PostComment.reading_event_id == post_id, PostComment.review_id == post_id))
                      .order_by(PostComment.created_at.desc(), PostComment.id.desc())
                      .limit(limit)).all()
    return [as_comment_response(comment, name, role) for comment, name, role in reversed(rows)]


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(post_id: uuid.UUID, data: CommentCreate,
                   user: Annotated[User, Depends(get_current_user)],
                   db: Annotated[Session, Depends(get_db)]) -> CommentResponse:
    kind = require_post(db, post_id)
    profile = personal_profile(db, user)
    comment = PostComment(post_id=post_id if kind == "publication" else None,
                          reading_event_id=post_id if kind == "reading_event" else None,
                          review_id=post_id if kind == "review" else None,
                          user_id=user.id, author_profile_id=profile.id, body=data.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return as_comment_response(comment, user.display_name, user.role)
