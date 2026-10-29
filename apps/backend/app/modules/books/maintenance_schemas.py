"""Validated administrator inputs; provenance remains separate from edits."""
from datetime import date
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MaintenanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: str | None = None
    reason: str = Field(min_length=3, max_length=2000)


class WorkInput(MaintenanceInput):
    title: str = Field(min_length=1, max_length=1000)
    authors: list[str] = Field(default_factory=list, max_length=30)
    description: str | None = Field(default=None, max_length=30000)
    categories: list[str] = Field(default_factory=list, max_length=50)
    series_title: str | None = Field(default=None, max_length=500)
    volume_number: str | None = Field(default=None, max_length=50)

    @field_validator("authors", "categories")
    @classmethod
    def clean_list(cls, values):
        if any(not value.strip() or len(value) > 300 for value in values):
            raise ValueError("Cada nombre debe contener entre 1 y 300 caracteres")
        return list(dict.fromkeys(value.strip() for value in values))


class EditionInput(MaintenanceInput):
    title: str = Field(min_length=1, max_length=1000)
    language: str = Field(default="es", min_length=2, max_length=20, pattern=r"^[a-zA-Z-]+$")
    isbn: str | None = Field(default=None, max_length=30)
    publisher_name: str | None = Field(default=None, max_length=500)
    publication_date: str | None = Field(default=None, max_length=10)
    page_count: int | None = Field(default=None, gt=0, le=100000)
    cover_url: str | None = Field(default=None, max_length=3000)
    description: str | None = Field(default=None, max_length=30000)
    format: str | None = Field(default=None, max_length=100)

    @field_validator("publication_date")
    @classmethod
    def valid_date(cls, value):
        if not value:
            return None
        if not re.fullmatch(r"[0-9]{4}(?:-[0-9]{2})?(?:-[0-9]{2})?", value):
            raise ValueError("Usa año, año-mes o año-mes-día")
        date.fromisoformat(value + ("-01-01" if len(value) == 4 else "-01" if len(value) == 7 else ""))
        return value

    @field_validator("cover_url")
    @classmethod
    def valid_cover(cls, value):
        if value:
            from urllib.parse import urlparse
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("La portada debe ser una URL http o https válida")
        return value or None
