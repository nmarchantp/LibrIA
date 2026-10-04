"""Eventos de lectura que generan avances en el mural."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.social.schemas import PostResponse


class LibraryBookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    book_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    page_count: int | None = Field(default=None, ge=1, le=100000)


class ReadingEventCreate(LibraryBookCreate):
    reading_id: uuid.UUID | None = None
    share: bool = False
    page_count: int = Field(ge=1, le=100000)
    event: Literal["start", "progress", "correction", "finish", "abandon"]
    current_page: int | None = Field(default=None, ge=0)
    abandonment_reason: str | None = Field(default=None, max_length=1000)
    correction_reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None

    @model_validator(mode="after")
    def validate_event(self):
        if self.event == "start" and self.reading_id is not None:
            raise ValueError("Un inicio crea un intento nuevo")
        if self.event != "start" and self.reading_id is None:
            raise ValueError("Indica el intento de lectura")
        if self.event in {"progress", "correction"} and self.current_page is None:
            raise ValueError("Indica la página alcanzada")
        if self.event == "abandon" and not (self.abandonment_reason or "").strip():
            raise ValueError("Indica el motivo del abandono")
        if self.event == "correction" and not self.correction_reason:
            raise ValueError("Indica el motivo de la corrección")
        return self


class ReadingEventResponse(BaseModel):
    reading_id: uuid.UUID
    event_id: uuid.UUID
    current_page: int
    total_pages: int
    status: str
    progress_percent: int
    post: PostResponse | None = None


class ReadingState(BaseModel):
    reading_id: uuid.UUID
    book_ref: str
    book_title: str
    status: str
    current_page: int
    total_pages: int | None
    progress_percent: int
