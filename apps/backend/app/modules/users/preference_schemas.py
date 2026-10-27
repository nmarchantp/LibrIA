"""Separate public projection and strict owner-only PATCH contract."""
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictInt, field_validator

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class PreferenceOption(BaseModel):
    id: str
    name: str


class GenreOption(PreferenceOption):
    group: str = "Otros"


class TropeOption(PreferenceOption):
    group: str = "Otras temáticas"


class IntensityOption(PreferenceOption):
    icon: str
    color: str
    levels: list[str] = Field(min_length=5, max_length=5)


class SelectedIntensity(IntensityOption):
    level: int


class InterestOption(PreferenceOption):
    group: str


class IntensitySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: Identifier
    level: Annotated[StrictInt, Field(ge=1, le=5)]


class LiteraryPreferences(BaseModel):
    profile_id: uuid.UUID
    biography: str | None
    genres: list[GenreOption]
    tropes: list[TropeOption]
    intensities: list[SelectedIntensity]
    featured_category_id: str | None
    interests: list[InterestOption]


class PublicProfile(BaseModel):
    # Deliberate allowlist: no user ID, email, roles, capabilities, or private data.
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    biography: str | None
    genres: list[GenreOption]
    tropes: list[TropeOption]
    intensities: list[SelectedIntensity]
    featured_category_id: str | None
    interests: list[InterestOption]


class PreferenceCatalogs(BaseModel):
    genres: list[GenreOption]
    tropes: list[TropeOption]
    intensities: list[IntensityOption]
    interests: list[InterestOption]


class ReadingGenre(BaseModel):
    name: str
    assignments: int
    percentage: float


class ReadingGenreStatistics(BaseModel):
    status: str
    finished_books: int
    classified_books: int
    unclassified_books: int
    total_assignments: int
    genres: list[ReadingGenre]


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    biography: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    genre_ids: list[Identifier] | None = Field(default=None, max_length=5)
    trope_ids: list[Identifier] | None = None
    intensities: list[IntensitySelection] | None = Field(default=None, max_length=5)
    interest_ids: list[Identifier] | None = None
    featured_category_id: Identifier | None = None

    @field_validator("genre_ids", "trope_ids", "interest_ids")
    @classmethod
    def explicit_selections(cls, value):
        if value is None:
            raise ValueError("Envía una lista; usa [] para borrar la selección")
        if len(value) != len(set(value)):
            raise ValueError("La selección no puede contener duplicados")
        return value

    @field_validator("intensities")
    @classmethod
    def explicit_intensities(cls, value):
        if value is None:
            raise ValueError("Envía una lista; usa [] para borrar la selección")
        ids = [item.category_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Las categorías no pueden repetirse")
        return value
