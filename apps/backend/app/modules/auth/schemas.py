"""Contratos de entrada y salida de Auth."""

from typing import Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from app.modules.users.schemas import UserResponse


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
