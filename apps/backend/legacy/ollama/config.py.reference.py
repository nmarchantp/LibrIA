# Frozen Ollama reference from commit 8fe48f7.
# This file is documentation only and must never be imported or executed.
# Every preserved source line is intentionally commented.
# """Carga centralizada de configuración desde variables de entorno."""
#
# from functools import lru_cache
#
# from pydantic import Field, model_validator
# from urllib.parse import urlparse
# from pydantic_settings import BaseSettings, SettingsConfigDict
#
#     smtp_password: str = ""
#     smtp_from: str = ""
#     libria_demo_password: str = ""
#     analytics_scheduler_enabled: bool = True
#     ai_worker_enabled: bool = True
#     ollama_base_url: str = "http://127.0.0.1:11434"
#     ai_model: str = "qwen3:1.7b"
#     ai_timeout_seconds: int = Field(default=180, ge=5, le=300)
#
#     model_config = SettingsConfigDict(env_file=".env", extra="ignore")
#
#     @model_validator(mode="after")
#     def production_security(self):
#         ollama_url = urlparse(self.ollama_base_url)
#         if (ollama_url.scheme != "http" or ollama_url.hostname not in {"localhost", "127.0.0.1", "::1"}
#                 or ollama_url.username or ollama_url.password or ollama_url.query or ollama_url.fragment
#                 or ollama_url.path not in {"", "/"}):
#             raise ValueError("OLLAMA_BASE_URL debe apuntar a Ollama en este equipo")
#         if self.jwt_algorithm != "HS256":
#             raise ValueError("JWT_ALGORITHM debe ser HS256")
#         if self.app_env not in {"development", "test"}:
#             if self.jwt_secret == "development-only-change-this-secret" or len(self.jwt_secret) < 32:
