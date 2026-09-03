"""Representaciones públicas; nunca incluyen password_hash."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None
    biography: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
