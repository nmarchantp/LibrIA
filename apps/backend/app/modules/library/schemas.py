"""Eventos de lectura que generan avances en el mural."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.modules.social.schemas import PostResponse


class ReadingEventCreate(BaseModel):
    book_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    book_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    page_count: int = Field(ge=1, le=100000)
    event: Literal["start", "progress", "finish", "abandon"]
    current_page: int | None = Field(default=None, ge=0)
    abandonment_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_event(self):
        if self.event == "progress" and self.current_page is None:
            raise ValueError("Indica la página alcanzada")
        if self.event == "abandon" and not (self.abandonment_reason or "").strip():
            raise ValueError("Indica el motivo del abandono")
        return self


class ReadingEventResponse(BaseModel):
    reading_id: uuid.UUID
    status: str
    progress_percent: int
    post: PostResponse


class ReadingState(BaseModel):
    book_ref: str
    book_title: str
    status: str
    current_page: int
    total_pages: int
    progress_percent: int
