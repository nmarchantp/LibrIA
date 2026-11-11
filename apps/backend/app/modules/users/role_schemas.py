"""Solicitudes de verificación y alta administrativa de librerías."""

import uuid
from datetime import datetime, timezone
import ipaddress
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, HttpUrl, field_validator, model_validator

from app.modules.users.roles import UserRole


class VerificationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requested_role: Literal["influencer", "autor"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)] | None = None
    activity_description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)] | None = None
    topics: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]] | None = Field(default=None, min_length=1, max_length=10)
    motivation: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)] | None = None
    evidence_links: list[Annotated[HttpUrl, Field(max_length=2048)]] | None = Field(default=None, min_length=1, max_length=5)

    @model_validator(mode='after')
    def complete_application(self):
        if self.requested_role == 'influencer' and not all((self.activity_description, self.topics, self.motivation, self.evidence_links)):
            raise ValueError('Completa actividad literaria, temáticas, motivación y al menos un enlace')
        for url in self.evidence_links or []:
            host = (url.host or '').rstrip('.').lower()
            if url.username or url.password or url.port not in (80, 443) or '.' not in host or host.endswith(('.local', '.localhost', '.internal')):
                raise ValueError('Usa enlaces públicos HTTP/HTTPS sin credenciales ni puertos personalizados')
            try:
                ipaddress.ip_address(host.strip('[]'))
            except ValueError:
                pass
            else:
                raise ValueError('Usa un dominio público, no una dirección IP')
        if self.topics:
            self.topics = list(dict.fromkeys(self.topics))
        return self


class VerificationDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class InfluencerSuspension(VerificationDecision):
    until: datetime

    @field_validator('until')
    @classmethod
    def future_date(cls, value):
        if value.tzinfo is None or value <= datetime.now(timezone.utc):
            raise ValueError('La suspensión requiere una fecha futura con zona horaria')
        return value


class VerificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    email: EmailStr
    requested_role: str
    note: str
    status: str
    created_at: datetime
    activity_description: str | None = None
    topics: list[str] | None = None
    motivation: str | None = None
    evidence_links: list[str] | None = None
    decided_at: datetime | None = None
    decided_by_user_id: uuid.UUID | None = None
    decided_by_name: str | None = None
    decision_reason: str | None = None


class BookstoreCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=100)


class AdminProfile(BaseModel):
    influencer_permissions_suspended: bool = False
    influencer_suspended_until: datetime | None = None
    id: uuid.UUID
    display_name: str
    email: str
    role: UserRole
    biography: str | None
    created_at: datetime
    pending_role: Literal["influencer", "autor", "libreria", "editorial"] | None = None


class AdminProfilePage(BaseModel):
    items: list[AdminProfile]
    total: int


class AdminProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    biography: Annotated[str, StringConstraints(strip_whitespace=True, max_length=70)] | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class RoleRevocation(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class RoleChangeResponse(BaseModel):
    id: uuid.UUID
    previous_role: UserRole
    new_role: UserRole
    reason: str
    created_at: datetime
    admin_name: str
