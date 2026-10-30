"""Carga centralizada de configuración desde variables de entorno."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    session_inactivity_hours: int = Field(default=24, ge=1, le=168)
    session_absolute_hours: int = Field(default=168, ge=24, le=720)
    session_activity_write_interval_seconds: int = Field(default=300, ge=30, le=3600)
    session_refresh_cookie_name: str = "libria_refresh"
    session_cookie_secure: bool | None = None
    google_books_api_key: str = ""
    open_library_contact: str = ""
    # Storage preparation only. No phase-1 flag may activate unimplemented consumers.
    catalog_canonical_enabled: bool = False
    catalog_editionless_enabled: bool = False
    catalog_admin_merge_enabled: bool = False
    catalog_admin_preview_enabled: bool = False
    # Phase 3 is a single, opt-in bundle: discovery + incorporation + writer guards.
    catalog_discovery_enabled: bool = False
    catalog_lock_timeout_ms: int = Field(default=2000, ge=50, le=30000)
    catalog_statement_timeout_ms: int = Field(default=10000, ge=100, le=60000)
    catalog_write_attempts: int = Field(default=3, ge=1, le=5)
    catalog_provider_timeout_seconds: int = Field(default=45, ge=5, le=120)
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
    projection_scheduler_enabled: bool = True
    gemini_worker_enabled: bool = False
    gemini_paid_service_confirmed: bool = False
    gemini_free_test_mode: bool = False
    ai_free_daily_token_pool: int = Field(default=0, ge=0)
    ai_provider: Literal["gemini"] = "gemini"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash-lite"
    ai_timeout_seconds: int = Field(default=180, ge=5, le=300)
    recommendation_prompt_version: str = "recommendations-v5-es"
    reader_dna_prompt_version: str = "reader-dna-v1-es"
    reading_analysis_prompt_version: str = "reading-event-v3-es"
    reading_analysis_delay_minutes: int = Field(default=30, ge=0, le=1440)
    ai_max_concurrent_requests: int = Field(default=2, ge=1, le=16)
    ai_requests_per_minute: int = Field(default=10, ge=1, le=600)
    ai_job_max_attempts: int = Field(default=3, ge=1, le=10)
    ai_job_lease_seconds: int = Field(default=600, ge=30, le=3600)
    ai_worker_poll_seconds: float = Field(default=2.0, ge=0.1, le=60)
    ai_retry_base_seconds: float = Field(default=5.0, ge=0.1, le=600)
    ai_context_token_budget: int = Field(default=12_000, ge=1_000, le=1_000_000)
    ai_chunk_token_budget: int = Field(default=6_000, ge=500, le=250_000)
    ai_output_token_budget: int = Field(default=2_048, ge=128, le=65_536)
    ai_job_token_budget: int = Field(default=100_000, ge=1_000, le=5_000_000)
    ai_max_calls_per_job: int = Field(default=24, ge=1, le=500)
    ai_recommendation_candidate_limit: int = Field(default=200, ge=4, le=2_000)
    # Tarifas standard pagadas de Gemini 3.5 Flash-Lite verificadas 2026-10-27.
    ai_input_cost_per_million_usd: float = Field(default=0.30, gt=0)
    ai_output_cost_per_million_usd: float = Field(default=2.50, gt=0)
    ai_monthly_budget_usd: float = Field(default=10.0, gt=0)
    ai_pricing_model: str = "gemini-3.5-flash-lite"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def catalog_phase1_disabled(self):
        if self.catalog_admin_merge_enabled:
            if self.app_env not in ('development','test') or not (self.catalog_canonical_enabled and self.catalog_admin_preview_enabled):
                raise ValueError('Administrative merges require development/test, canonical consumers and previews')
        if self.catalog_canonical_enabled and not self.catalog_discovery_enabled:
            raise ValueError("Canonical consumers require the discovery/incorporation bundle")
        if self.catalog_editionless_enabled and not self.catalog_discovery_enabled:
            raise ValueError("Editionless readings require the complete discovery/incorporation bundle")
        return self

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("GEMINI_MODEL no puede estar vacío")
        return value

    @model_validator(mode="after")
    def production_security(self):
        if self.gemini_free_test_mode and self.app_env not in {"development", "test"}:
            raise ValueError("GEMINI_FREE_TEST_MODE solo puede activarse en development/test")
        if self.jwt_algorithm != "HS256":
            raise ValueError("JWT_ALGORITHM debe ser HS256")
        if self.session_absolute_hours < self.session_inactivity_hours:
            raise ValueError("SESSION_ABSOLUTE_HOURS no puede ser menor que SESSION_INACTIVITY_HOURS")
        if self.ai_chunk_token_budget > self.ai_context_token_budget:
            raise ValueError("AI_CHUNK_TOKEN_BUDGET no puede superar AI_CONTEXT_TOKEN_BUDGET")
        if self.ai_job_lease_seconds < self.ai_timeout_seconds + 30:
            raise ValueError("AI_JOB_LEASE_SECONDS debe superar AI_TIMEOUT_SECONDS por al menos 30 segundos")
        if self.ai_pricing_model.strip() != self.gemini_model:
            raise ValueError("AI_PRICING_MODEL debe coincidir con GEMINI_MODEL; verifica y configura sus tarifas")
        if self.app_env not in {"development", "test"}:
            if self.jwt_secret == "development-only-change-this-secret" or len(self.jwt_secret) < 32:
                raise ValueError("Configura JWT_SECRET aleatorio de al menos 32 caracteres")
            if not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError("Configura orígenes HTTPS explícitos en producción")
            if self.session_cookie_secure is False:
                raise ValueError("SESSION_COOKIE_SECURE no puede desactivarse en producción")
        return self

    @property
    def secure_session_cookie(self) -> bool:
        """HTTPS cookies are mandatory outside local/test environments."""
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.app_env not in {"development", "test"}

    @property
    def cors_origins(self) -> list[str]:
        """Convierte la lista separada por comas al formato esperado por CORS."""
        origins = [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]
        if self.app_env in {"development", "test"}:
            for origin in list(origins):
                parsed = urlparse(origin)
                if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 5173:
                    alias = "127.0.0.1" if parsed.hostname == "localhost" else "localhost"
                    equivalent = f"http://{alias}:5173"
                    if equivalent not in origins:
                        origins.append(equivalent)
        return origins


@lru_cache
def get_settings() -> Settings:
    """Crea una única instancia de configuración durante el proceso."""
    return Settings()
