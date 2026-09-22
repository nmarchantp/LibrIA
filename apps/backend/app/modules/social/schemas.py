import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.users.roles import UserRole


class PostCreate(BaseModel):
    source: Literal["community", "review", "event"]
    kind: Literal["community", "reviews"]
    title: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=3000)
    book_ref: str | None = Field(default=None, min_length=1, max_length=200)
    book_title: str | None = Field(default=None, min_length=1, max_length=200)
    rating: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def source_matches_kind(self):
        expected = {"community": "community", "review": "reviews", "event": "community"}
        if self.kind != expected[self.source]:
            raise ValueError("La categoría no corresponde a la fuente")
        if not self.body.strip():
            raise ValueError("El texto no puede estar vacío")
        if self.source == "review" and (not self.book_ref or not self.book_title or self.rating is None):
            raise ValueError("La reseña debe indicar libro y valoración")
        return self


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    author: str
    author_role: UserRole
    source: str
    kind: str
    title: str | None
    body: str
    book_ref: str | None
    book_title: str | None
    rating: int | None
    progress_percent: int | None
    reading_event: str | None
    created_at: datetime


class CommentCreate(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    post_id: uuid.UUID
    user_id: uuid.UUID
    author: str
    author_role: UserRole
    body: str
    created_at: datetime
