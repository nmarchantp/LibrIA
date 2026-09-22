"""Solicitudes de verificación y alta administrativa de librerías."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints
from typing import Annotated


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
