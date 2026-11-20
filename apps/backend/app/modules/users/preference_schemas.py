"""Separate public projection and strict owner-only PATCH contract."""
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictInt, field_validator

ProfileCard = Literal['history', 'crush', 'essentials', 'genres', 'tropes', 'featured', 'statistics', 'recommendations', 'interests']
StoryIllustration = Literal["flowers", "books", "cat", "none"]
ProfileSection = Literal['biography', 'genres', 'tropes', 'intensities', 'interests', 'favorite_quotes', 'library', 'activity', 'events', 'analyses']

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


class FavoriteQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    source: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] = ""


ImageUrl = Annotated[str, StringConstraints(max_length=2000, pattern=r'^(https?://|/api/|/images/characters/)')]


class LiteraryCrush(BaseModel):
    character_id: uuid.UUID | None = None
    work_id: uuid.UUID | None = None
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    book: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ''
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ''
    image_url: ImageUrl | None = None


class EssentialBook(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    image_url: ImageUrl | None = None


class CharacterChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    character_id: uuid.UUID
    work_id: uuid.UUID
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ''


class LiteraryPreferences(BaseModel):
    card_order: list[ProfileCard] = Field(default_factory=list, max_length=9)
    literary_crush: 'LiteraryCrush | None' = None
    essential_books: list['EssentialBook'] = Field(default_factory=list)
    profile_visibility: Literal['public', 'private'] = 'public'
    public_sections: list[ProfileSection] = Field(default_factory=list)
    story_illustration: StoryIllustration = "flowers"
    favorite_quotes: list[FavoriteQuote | str] = Field(default_factory=list)
    profile_id: uuid.UUID
    biography: str | None
    genres: list[GenreOption]
    tropes: list[TropeOption]
    intensities: list[SelectedIntensity]
    featured_category_id: str | None
    interests: list[InterestOption]


class PublicProfile(BaseModel):
    card_order: list[ProfileCard] = Field(default_factory=list, max_length=9)
    literary_crush: 'LiteraryCrush | None' = None
    essential_books: list['EssentialBook'] = Field(default_factory=list)
    profile_visibility: Literal['public', 'private'] = 'public'
    visible_sections: list[ProfileSection] = Field(default_factory=list)
    can_view: bool = True
    is_owner: bool = False
    following: bool = False
    follows_you: bool = False
    favorite_quotes: list[FavoriteQuote | str] = Field(default_factory=list)
    story_illustration: StoryIllustration = "flowers"
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
    card_order: list[ProfileCard] = Field(default_factory=list, max_length=9)
    literary_crush: CharacterChoice | None = None
    essential_books: list[EssentialBook] = Field(default_factory=list, max_length=4)
    profile_visibility: Literal['public', 'private'] = 'public'
    public_sections: list[ProfileSection] = Field(default_factory=list, max_length=10)
    story_illustration: StoryIllustration = "flowers"
    model_config = ConfigDict(extra="forbid")
    favorite_quotes: list[FavoriteQuote | Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]] = Field(default_factory=list, max_length=4)
    biography: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    genre_ids: list[Identifier] | None = Field(default=None, max_length=5)
    trope_ids: list[Identifier] | None = None
    intensities: list[IntensitySelection] | None = Field(default=None, max_length=5)
    interest_ids: list[Identifier] | None = None
    featured_category_id: Identifier | None = None

    @field_validator('card_order')
    @classmethod
    def unique_cards(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Las cards no pueden repetirse')
        return value

    @field_validator('essential_books')
    @classmethod
    def unique_essential_books(cls, value):
        if len({item.id for item in value}) != len(value):
            raise ValueError('No puedes repetir libros imprescindibles')
        return value

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
