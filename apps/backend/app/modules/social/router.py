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

router = APIRouter(prefix="/posts", tags=["posts"])


def as_response(post: Post, author: str, author_role: str) -> PostResponse:
    return PostResponse(id=post.id, user_id=post.user_id, author=author, author_role=author_role,
                        source=post.source, kind=post.kind, title=post.title,
                        body=post.body, book_ref=post.book_ref, book_title=post.book_title,
                        rating=post.rating, progress_percent=post.progress_percent,
                        reading_event=post.reading_event, created_at=post.created_at)


def as_comment_response(comment: PostComment, author: str, author_role: str) -> CommentResponse:
    return CommentResponse(id=comment.id, post_id=comment.post_id, user_id=comment.user_id,
                           author=author, author_role=author_role, body=comment.body, created_at=comment.created_at)


def require_post(db: Session, post_id: uuid.UUID) -> None:
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, user: Annotated[User, Depends(get_current_user)],
                db: Annotated[Session, Depends(get_db)]) -> PostResponse:
    if user.role == "lector" and data.source != "review":
        raise HTTPException(status_code=403, detail="Los lectores solo pueden publicar reseñas de libros")
    if data.source == "event" and user.role not in {"autor", "libreria", "admin"}:
        raise HTTPException(status_code=403, detail="Esta cuenta no puede publicar eventos")
    post = Post(user_id=user.id, **data.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    return as_response(post, user.display_name, user.role)


@router.get("", response_model=list[PostResponse])
def list_posts(db: Annotated[Session, Depends(get_db)], limit: int = Query(50, ge=1, le=100)) -> list[PostResponse]:
    rows = db.execute(select(Post, User.display_name, User.role).join(User, Post.user_id == User.id)
                      .where(or_(
                          and_(Post.source == "review", Post.book_ref.is_not(None), Post.rating.is_not(None)),
                          and_(Post.source == "reading", Post.reading_event.is_not(None)),
                          and_(Post.source.in_(("community", "event")), User.role != "lector"),
                      ))
                      .order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)).all()
    return [as_response(post, name, role) for post, name, role in rows]


@router.get("/{post_id}/comments", response_model=list[CommentResponse])
def list_comments(post_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                  limit: int = Query(100, ge=1, le=100)) -> list[CommentResponse]:
    require_post(db, post_id)
    rows = db.execute(select(PostComment, User.display_name, User.role)
                      .join(User, PostComment.user_id == User.id)
                      .where(PostComment.post_id == post_id)
                      .order_by(PostComment.created_at.desc(), PostComment.id.desc())
                      .limit(limit)).all()
    return [as_comment_response(comment, name, role) for comment, name, role in reversed(rows)]


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(post_id: uuid.UUID, data: CommentCreate,
                   user: Annotated[User, Depends(get_current_user)],
                   db: Annotated[Session, Depends(get_db)]) -> CommentResponse:
    require_post(db, post_id)
    comment = PostComment(post_id=post_id, user_id=user.id, body=data.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return as_comment_response(comment, user.display_name, user.role)
