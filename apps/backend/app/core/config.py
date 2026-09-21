"""Carga centralizada de configuración desde variables de entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores configurables; los secretos nunca se escriben en el código."""

    app_name: str = "LibrIA API"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://libria:libria@localhost:5432/libria"
    frontend_origins: str = "http://localhost:5173"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    google_books_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_oauth_scope: str = "https://www.googleapis.com/auth/books"
    libria_demo_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        """Convierte la lista separada por comas al formato esperado por CORS."""
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Crea una única instancia de configuración durante el proceso."""
    return Settings()
