"""Carga centralizada de configuración desde variables de entorno."""

from functools import lru_cache

from pydantic import Field, model_validator
from urllib.parse import urlparse
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
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1440)
    google_books_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    libria_demo_password: str = ""
    analytics_scheduler_enabled: bool = True
    ai_worker_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ai_model: str = "qwen3:1.7b"
    ai_timeout_seconds: int = Field(default=180, ge=5, le=300)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def production_security(self):
        ollama_url = urlparse(self.ollama_base_url)
        if (ollama_url.scheme != "http" or ollama_url.hostname not in {"localhost", "127.0.0.1", "::1"}
                or ollama_url.username or ollama_url.password or ollama_url.query or ollama_url.fragment
                or ollama_url.path not in {"", "/"}):
            raise ValueError("OLLAMA_BASE_URL debe apuntar a Ollama en este equipo")
        if self.jwt_algorithm != "HS256":
            raise ValueError("JWT_ALGORITHM debe ser HS256")
        if self.app_env not in {"development", "test"}:
            if self.jwt_secret == "development-only-change-this-secret" or len(self.jwt_secret) < 32:
                raise ValueError("Configura JWT_SECRET aleatorio de al menos 32 caracteres")
            if not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError("Configura orígenes HTTPS explícitos en producción")
        return self

    @property
    def cors_origins(self) -> list[str]:
        """Convierte la lista separada por comas al formato esperado por CORS."""
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Crea una única instancia de configuración durante el proceso."""
    return Settings()
