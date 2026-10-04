import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post, PostComment
from app.modules.social.schemas import CommentCreate, CommentResponse, PostCreate, PostResponse
from app.modules.users.models import User
from app.modules.library.models import ReadingEvent, Reading
from app.modules.books.models import Work
from app.modules.users.identities import personal_profile, publication_role, require_actor
from app.modules.users.identity_models import Profile

router = APIRouter(prefix="/posts", tags=["posts"])


def as_response(post: Post, author: str, author_role: str) -> PostResponse:
    return PostResponse(id=post.id, user_id=post.user_id, author=author, author_role=post.author_role or author_role,
                        author_profile_id=post.author_profile_id, publication_type=post.publication_type,
                        source=post.source, kind=post.kind, title=post.title,
                        body=post.body, book_ref=post.book_ref, book_title=post.book_title,
                        rating=post.rating, progress_percent=post.progress_percent,
                        reading_event=post.reading_event, created_at=post.created_at)


def as_comment_response(comment: PostComment, author: str, author_role: str) -> CommentResponse:
    return CommentResponse(id=comment.id, post_id=comment.post_id or comment.reading_event_id, user_id=comment.user_id,
                           author=author, author_role=author_role, body=comment.body, created_at=comment.created_at)


def visible_posts():
    return or_(
                          and_(Post.source == "review", Post.book_ref.is_not(None), Post.rating.is_not(None)),
                          and_(Post.source == "reading", Post.reading_event.is_not(None)),
                          and_(Post.source.in_(("community", "event")), Post.author_role != "lector"),
                      )


def require_post(db: Session, post_id: uuid.UUID) -> str:
    if db.scalar(select(Post.id).where(Post.id == post_id, visible_posts())) is not None:
        return "publication"
    if db.scalar(select(ReadingEvent.id).where(ReadingEvent.id == post_id, ReadingEvent.is_public)) is not None:
        return "reading_event"
    raise HTTPException(status_code=404, detail="Contenido no encontrado")


def as_reading_response(event: ReadingEvent, title: str, author: User) -> PostResponse:
    percent = round(event.page * 100 / event.total_pages)
    body = {"start": f'Comenzó a leer "{title}".', "progress": f'Llegó al {percent} % de "{title}".',
            "finish": f'Terminó "{title}".', "abandon": f'Abandonó "{title}".'}.get(event.kind, "")
    return PostResponse(id=event.id, feed_item_type="reading_event", user_id=author.id,
                        author=author.display_name, author_role=author.role, source="reading", kind="progress",
                        title=None, body=body, book_ref=None, book_title=title, rating=None,
                        progress_percent=percent, reading_event=event.kind, created_at=event.created_at)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, user: Annotated[User, Depends(get_current_user)],
                db: Annotated[Session, Depends(get_db)]) -> PostResponse:
    profile = require_actor(db, user, data.author_profile_id) if data.author_profile_id else personal_profile(db, user)
    role = publication_role(db, profile)
    if role == "lector" and data.source != "review":
        raise HTTPException(status_code=403, detail="Los lectores solo pueden publicar reseñas de libros")
    if data.source == "review" and profile.kind != "personal":
        raise HTTPException(status_code=403, detail="Las reseñas requieren un perfil personal")
    publication_type = data.publication_type or ("event" if data.source == "event" else "free")
    if (publication_type == "event") != (data.source == "event") or (data.source == "review" and data.publication_type):
        raise HTTPException(status_code=422, detail="El tipo no corresponde al contenido")
    post = Post(user_id=user.id, author_role=role, author_profile_id=profile.id,
                publication_type=publication_type if data.source != "review" else None,
                **data.model_dump(exclude={"author_profile_id", "publication_type"}))
    db.add(post)
    db.commit()
    db.refresh(post)
    return as_response(post, profile.display_name, role)


@router.get("", response_model=list[PostResponse])
def list_posts(db: Annotated[Session, Depends(get_db)], limit: int = Query(50, ge=1, le=100)) -> list[PostResponse]:
    rows = db.execute(select(Post, User.display_name, User.role).join(User, Post.user_id == User.id)
                      .where(visible_posts())
                      .order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)).all()
    profile_ids = {post.author_profile_id for post, _, _ in rows if post.author_profile_id}
    names = dict(db.execute(select(Profile.id, Profile.display_name).where(Profile.id.in_(profile_ids))).all())
    items = [as_response(post, names.get(post.author_profile_id, name), role) for post, name, role in rows]
    events = db.execute(select(ReadingEvent, Work.title, User)
                        .join(Reading, Reading.id == ReadingEvent.reading_id)
                        .join(Work, Work.id == Reading.work_id)
                        .join(User, User.id == ReadingEvent.actor_user_id)
                        .where(ReadingEvent.is_public)
                        .order_by(ReadingEvent.created_at.desc(), ReadingEvent.id.desc()).limit(limit)).all()
    items.extend(as_reading_response(event, title, author) for event, title, author in events)
    return sorted(items, key=lambda item: (item.created_at, str(item.id)), reverse=True)[:limit]


@router.get("/{post_id}/comments", response_model=list[CommentResponse])
def list_comments(post_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                  limit: int = Query(100, ge=1, le=100)) -> list[CommentResponse]:
    require_post(db, post_id)
    rows = db.execute(select(PostComment, User.display_name, User.role)
                      .join(User, PostComment.user_id == User.id)
                      .where(or_(PostComment.post_id == post_id, PostComment.reading_event_id == post_id))
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
                          user_id=user.id, author_profile_id=profile.id, body=data.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return as_comment_response(comment, user.display_name, user.role)
