from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.social.models import Post
from app.modules.social.schemas import PostCreate, PostResponse
from app.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["posts"])


def as_response(post: Post, author: str) -> PostResponse:
    return PostResponse(id=post.id, user_id=post.user_id, author=author,
                        source=post.source, kind=post.kind, title=post.title,
                        body=post.body, created_at=post.created_at)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, user: Annotated[User, Depends(get_current_user)],
                db: Annotated[Session, Depends(get_db)]) -> PostResponse:
    post = Post(user_id=user.id, **data.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    return as_response(post, user.display_name)


@router.get("", response_model=list[PostResponse])
def list_posts(db: Annotated[Session, Depends(get_db)], limit: int = Query(50, ge=1, le=100)) -> list[PostResponse]:
    rows = db.execute(select(Post, User.display_name).join(User, Post.user_id == User.id)
                      .order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)).all()
    return [as_response(post, name) for post, name in rows]
