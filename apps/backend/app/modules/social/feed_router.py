from typing import Annotated, Literal
import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.social.schemas import PostResponse
from app.modules.social import feed_service

router = APIRouter(prefix="/mural", tags=["mural"])
Audience = Literal["contacts", "community"]
Category = Literal["progress", "started", "finished", "reviews", "social", "events", "launches", "announcements", "promotions"]
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]


class FeedItem(PostResponse):
    avatar_url: str | None = None
    book_author: str = ""
    reading_id: uuid.UUID | None = None
    page: int | None = None
    total_pages: int | None = None
    comment_count: int
    view_count: int
    capabilities: dict[str, bool]
    observed_at: str


class FeedPage(BaseModel):
    items: list[FeedItem]
    next_cursor: str | None


class CategoryPreview(BaseModel):
    items: list[FeedItem]
    has_more: bool


class FeedSummary(BaseModel):
    audience: Audience
    categories: dict[str, CategoryPreview]


@router.get("", response_model=FeedSummary)
def summary(db: DB, user: Viewer, audience: Audience = "community", limit: int = Query(9, ge=1, le=12)):
    return feed_service.summary(db, user, audience, limit)


@router.get("/{category}", response_model=FeedPage)
def history(category: Category, db: DB, user: Viewer, audience: Audience = "community",
            limit: int = Query(20, ge=1, le=50), cursor: str | None = Query(None, max_length=2048)):
    return feed_service.page(db, user, audience, category, limit, cursor)
