import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PostCreate(BaseModel):
    source: Literal["community", "reading", "review", "event"]
    kind: Literal["community", "progress", "reviews"]
    title: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=3000)

    @model_validator(mode="after")
    def source_matches_kind(self):
        expected = {"community": "community", "reading": "progress", "review": "reviews", "event": "community"}
        if self.kind != expected[self.source]:
            raise ValueError("La categoría no corresponde a la fuente")
        if not self.body.strip():
            raise ValueError("El texto no puede estar vacío")
        return self


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    author: str
    source: str
    kind: str
    title: str | None
    body: str
    created_at: datetime
