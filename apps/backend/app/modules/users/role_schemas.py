"""Solicitudes de verificación y alta administrativa de librerías."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.modules.users.roles import UserRole


class VerificationCreate(BaseModel):
    requested_role: Literal["influencer", "autor"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class VerificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    email: EmailStr
    requested_role: str
    note: str
    status: str
    created_at: datetime


class BookstoreCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=100)


class AdminProfile(BaseModel):
    id: uuid.UUID
    display_name: str
    email: EmailStr
    role: UserRole
    biography: str | None
    created_at: datetime
    pending_role: Literal["influencer", "autor"] | None = None


class AdminProfilePage(BaseModel):
    items: list[AdminProfile]
    total: int


class AdminProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    biography: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class RoleRevocation(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class RoleChangeResponse(BaseModel):
    id: uuid.UUID
    previous_role: UserRole
    new_role: UserRole
    reason: str
    created_at: datetime
    admin_name: str
