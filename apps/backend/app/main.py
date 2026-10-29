"""Punto de entrada HTTP de LibrIA.

ETL, proyecciones y Gemini se ejecutan como procesos separados para que
escalar la API no multiplique consumidores ni cierres nocturnos.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.modules.books.canonical import CanonicalIdentityError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.social.router import profile_social_router, router as social_router
from app.modules.users.roles_router import router as roles_router
from app.modules.library.router import router as readings_router
from app.modules.users.identities_router import router as profiles_router
from app.modules.users.preferences_router import router as preferences_router
from app.modules.analytics.router import router as analytics_router
from app.modules.analytics.insights_router import router as insights_router
from app.modules.social.reviews_router import router as reviews_router
from app.modules.books.router import router as books_router
from app.modules.books.admin_router import router as catalog_admin_router
from app.modules.analytics.adaptive_router import router as adaptive_router

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.exception_handler(CanonicalIdentityError)
async def canonical_identity_failure(request, error):
    return JSONResponse(status_code=404 if str(error).startswith("Unknown") else 409,
                        content={"detail": {"code": "canonical_identity_invalid", "message": str(error)}})

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
app.include_router(social_router, prefix=settings.api_prefix)
app.include_router(profile_social_router, prefix=settings.api_prefix)
app.include_router(roles_router, prefix=settings.api_prefix)
app.include_router(readings_router, prefix=settings.api_prefix)
app.include_router(profiles_router, prefix=settings.api_prefix)
app.include_router(preferences_router, prefix=settings.api_prefix)
app.include_router(analytics_router, prefix=settings.api_prefix)
app.include_router(insights_router, prefix=settings.api_prefix)
app.include_router(reviews_router, prefix=settings.api_prefix)
app.include_router(books_router, prefix=settings.api_prefix)
app.include_router(catalog_admin_router, prefix=settings.api_prefix)
app.include_router(adaptive_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Permite verificar que el proceso está funcionando sin consultar datos."""
    return {"status": "ok", "service": "libria-api"}
