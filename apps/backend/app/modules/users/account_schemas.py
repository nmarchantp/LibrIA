from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Biography = Annotated[str, StringConstraints(max_length=70)]
Password = Annotated[str, Field(min_length=8, max_length=128)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicAccountUpdate(StrictInput):
    display_name: Name
    biography: Biography | None = None


class PasswordChange(StrictInput):
    current_password: str = Field(min_length=1, max_length=128, repr=False)
    new_password: Password = Field(repr=False)


class IdentityConfirmation(StrictInput):
    current_password: str = Field(min_length=1, max_length=128, repr=False)


class EmailStart(IdentityConfirmation):
    email: EmailStr


class EmailRequest(StrictInput):
    email: EmailStr


class TokenInput(StrictInput):
    token: str = Field(min_length=32, max_length=128, repr=False)


class ResetPassword(TokenInput):
    new_password: Password = Field(repr=False)


class AdminState(StrictInput):
    suspended: bool
    reason: Reason


class AdminUsername(StrictInput):
    username: str = Field(pattern=r"^[a-z0-9_]{3,64}$")
    reason: Reason


class AdminRole(StrictInput):
    role: Literal["lector", "autor", "influencer", "libreria", "admin"]
    reason: Reason


class AdminVerification(StrictInput):
    requested_role: Literal["autor", "influencer", "libreria"]
    note: Reason
