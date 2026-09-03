"""Punto de entrada del único servidor FastAPI de LibrIA."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.auth.router import router as auth_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

# Solo los orígenes configurados pueden consumir la API desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Todos los módulos se incorporan al mismo servidor bajo el prefijo /api.
app.include_router(auth_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Permite verificar que el proceso está funcionando sin consultar datos."""
    return {"status": "ok", "service": "libria-api"}
