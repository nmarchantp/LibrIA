"""Reglas de registro e inicio de sesión, sin conceptos HTTP."""

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.users.schemas import UserResponse


class AuthService:
    def __init__(self, repository: AuthRepository):
        self.repository = repository

    def register(self, data: RegisterRequest) -> TokenResponse:
        if self.repository.get_account_by_email(data.email):
            raise EmailAlreadyRegisteredError
        user = self.repository.create_account(data.email, hash_password(data.password), data.display_name, "lector")
        return self._token_response(user)

    def login(self, data: LoginRequest) -> TokenResponse:
        account = self.repository.get_account_by_email(data.email)
        if not account or not verify_password(data.password, account.password_hash):
            raise InvalidCredentialsError
        return self._token_response(account.user)

    @staticmethod
    def _google_subject(claims: dict) -> str:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255 or claims.get("email_verified") is not True:
            raise InvalidCredentialsError
        try:
            TypeAdapter(EmailStr).validate_python(claims.get("email"))
        except ValidationError:
            raise InvalidCredentialsError from None
        return subject

    def google_login(self, claims: dict) -> TokenResponse:
        account = self.repository.get_account_by_google_subject(self._google_subject(claims))
        if not account or not account.google_email_verified_at:
            raise InvalidCredentialsError
        return self._token_response(account.user)

    def google_link(self, user_id, claims: dict) -> None:
        subject = self._google_subject(claims)
        user = self.repository.get_user_by_id(user_id)
        account = self.repository.get_account_by_google_subject(subject)
        if not user or (account and account.user_id != user.id):
            raise InvalidCredentialsError
        if (not user.auth_account.google_email_verified_at or
                user.auth_account.google_email != str(claims.get("email", "")).lower()):
            raise InvalidCredentialsError
        if user.auth_account.google_subject and user.auth_account.google_subject != subject:
            raise InvalidCredentialsError
        self.repository.link_google(user.auth_account, subject)

    @staticmethod
    def _token_response(user) -> TokenResponse:
        public_user = UserResponse(
            id=user.id, email=user.auth_account.email, display_name=user.display_name, role=user.role,
            avatar_url=user.avatar_url, biography=user.biography, created_at=user.created_at,
        )
        return TokenResponse(access_token=create_access_token(str(user.id)), user=public_user)
