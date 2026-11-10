import uuid
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.users.roles import UserRole


class EventDetailsInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    start_date: date
    start_time: time
    end_date: date | None=None
    end_time: time | None=None
    timezone: str=Field(default='America/Santiago',max_length=64)
    location: str=Field(min_length=1,max_length=300)
    organizer: str=Field(min_length=1,max_length=200)
    category: Literal['fair','book_club','workshop','meetup','other']='meetup'

    def instants(self):
        try:zone=ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:raise ValueError('Selecciona una zona horaria IANA válida') from None
        def instant(day,hour):
            if hour.tzinfo:raise ValueError('Introduce la hora local y selecciona la zona horaria')
            local=datetime.combine(day,hour)
            candidates={local.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc) for fold in (0,1)
                if local.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)==local}
            if not candidates:raise ValueError('Esa hora no existe por el cambio de horario; elige otra hora')
            if len(candidates)>1:raise ValueError('Esa hora se repite por el cambio de horario; elige una hora no ambigua')
            return candidates.pop()
        return instant(self.start_date,self.start_time),instant(self.end_date,self.end_time) if self.end_date and self.end_time else None

    @model_validator(mode='after')
    def valid_schedule(self):
        if (self.end_date is None)!=(self.end_time is None):raise ValueError('Completa fecha y hora de término, o deja ambas vacías')
        start,end=self.instants()
        if end and end<start:raise ValueError('El término no puede ser anterior al inicio')
        return self


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    author_profile_id: uuid.UUID | None = None
    publication_type: Literal["free", "event", "promotion", "news", "launch", "institutional", "note", "theory"] | None = None
    source: Literal["community", "event"]
    kind: Literal["community"]
    title: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=3000)
    book_ref: str | None = Field(default=None, min_length=1, max_length=200)
    book_title: str | None = Field(default=None, min_length=1, max_length=200)
    work_id: uuid.UUID | None = None
    edition_id: uuid.UUID | None = None
    event_details: EventDetailsInput | None = None

    @model_validator(mode="after")
    def source_matches_kind(self):
        expected = {"community": "community", "event": "community"}
        if self.kind != expected[self.source]:
            raise ValueError("La categoría no corresponde a la fuente")
        if not self.body.strip():
            raise ValueError("El texto no puede estar vacío")
        if len(self.body) > 500:
            raise ValueError("Las publicaciones deben ser breves (máximo 500 caracteres)")
        if self.event_details and (self.source!='event' or not self.title):
            raise ValueError('Los datos del evento requieren tipo Evento y un título')
        return self


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    moderation_status: str = 'approved'
    public_moderation_status: str | None = None
    moderation_version: int = 1
    pending_revision_id: uuid.UUID | None = None
    moderation_message: str | None = None
    feed_item_type: str = "publication"
    author_profile_id: uuid.UUID | None = None
    publication_type: str | None = None
    images: list[str] = Field(default_factory=list)
    like_count: int = 0
    liked_by_me: bool = False
    following_author: bool = False
    user_id: uuid.UUID
    author: str
    author_role: UserRole
    source: str
    kind: str
    title: str | None
    body: str
    book_ref: str | None
    book_title: str | None
    book_cover_url: str | None = None
    custom_book_cover_url: str | None = None
    can_edit_book_cover: bool = False
    can_manage: bool = False
    event_details: dict | None = None
    rating: float | None
    dimension_ratings: dict[str, float] = Field(default_factory=dict)
    progress_percent: int | None
    reading_event: str | None
    work_id: uuid.UUID | None = None
    edition_id: uuid.UUID | None = None
    is_spoiler: bool = False
    status: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    revision_number: int | None = None
    created_at: datetime


class PostLikeResponse(BaseModel):
    like_count: int
    liked_by_me: bool


class ProfileFollowResponse(BaseModel):
    following: bool


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
    edited_at: datetime | None = None
    moderation_status: str = 'approved'
    public_moderation_status: str | None = None
    moderation_version: int = 1
    pending_revision_id: uuid.UUID | None = None
    moderation_message: str | None = None


RatingDimension = Literal["plot_twist", "tears", "romance", "spicy", "action", "world_building", "pace", "battles", "horror", "boring_moments", "comedy"]


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    work_id: uuid.UUID
    edition_id: uuid.UUID | None = None
    author_profile_id: uuid.UUID | None = None
    body: str = Field(min_length=1, max_length=3000)
    rating: float | None = Field(default=None, ge=0.25, le=5, multiple_of=0.25, allow_inf_nan=False)
    dimension_ratings: dict[RatingDimension, Annotated[float, Field(ge=0.25, le=5, multiple_of=0.25, allow_inf_nan=False)]] = Field(default_factory=dict)
    is_spoiler: bool = False
    status: Literal["draft", "published"] = "published"


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    body: str = Field(min_length=1, max_length=3000)
    rating: float | None = Field(default=None, ge=0.25, le=5, multiple_of=0.25, allow_inf_nan=False)
    dimension_ratings: dict[RatingDimension, Annotated[float, Field(ge=0.25, le=5, multiple_of=0.25, allow_inf_nan=False)]] = Field(default_factory=dict)
    is_spoiler: bool = False
    status: Literal["draft", "published", "hidden"] = "published"
    edition_id: uuid.UUID | None = None
