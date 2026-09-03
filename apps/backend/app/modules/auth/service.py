"""Reglas de registro e inicio de sesión, sin conceptos HTTP."""

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
        user = self.repository.create_account(data.email, hash_password(data.password), data.display_name)
        return self._token_response(user)

    def login(self, data: LoginRequest) -> TokenResponse:
        account = self.repository.get_account_by_email(data.email)
        if not account or not verify_password(data.password, account.password_hash):
            raise InvalidCredentialsError
        return self._token_response(account.user)

    @staticmethod
    def _token_response(user) -> TokenResponse:
        public_user = UserResponse(
            id=user.id, email=user.auth_account.email, display_name=user.display_name,
            avatar_url=user.avatar_url, biography=user.biography, created_at=user.created_at,
        )
        return TokenResponse(access_token=create_access_token(str(user.id)), user=public_user)
