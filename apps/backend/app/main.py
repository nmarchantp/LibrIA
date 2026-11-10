"""Punto de entrada HTTP de LibrIA.

ETL, proyecciones y Gemini se ejecutan como procesos separados para que
escalar la API no multiplique consumidores ni cierres nocturnos.
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.modules.books.canonical import CanonicalIdentityError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.environment_admin import router as environment_admin_router
from app.modules.auth.router import router as auth_router
from app.modules.users.account_router import router as account_router
from app.modules.social.router import profile_social_router, router as social_router
from app.modules.social.feed_router import router as feed_router
from app.modules.social.interactions_router import router as interactions_router
from app.modules.social.post_covers import router as post_covers_router
from app.modules.social.publication_management import router as publication_management_router
from app.modules.social.events_router import router as events_router
from app.modules.social.moderation_private_router import router as moderation_private_router
from app.modules.social.profile_events_router import router as profile_events_router
from app.modules.users.roles_router import router as roles_router
from app.modules.library.router import router as readings_router
from app.modules.library.challenge_router import router as challenge_router
from app.modules.users.identities_router import router as profiles_router
from app.modules.users.preferences_router import router as preferences_router
from app.modules.analytics.router import router as analytics_router
from app.modules.analytics.insights_router import router as insights_router
from app.modules.social.reviews_router import router as reviews_router
from app.modules.books.router import router as books_router
from app.modules.books.admin_router import router as catalog_admin_router
from app.modules.analytics.adaptive_router import router as adaptive_router

settings = get_settings()

@asynccontextmanager
async def lifespan(application):
    from app.modules.demo.worker import run_worker
    task = asyncio.create_task(run_worker(application))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


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
app.include_router(account_router, prefix=settings.api_prefix)
app.include_router(social_router, prefix=settings.api_prefix)
app.include_router(feed_router, prefix=settings.api_prefix)
app.include_router(interactions_router, prefix=settings.api_prefix)
app.include_router(post_covers_router, prefix=settings.api_prefix)
app.include_router(publication_management_router, prefix=settings.api_prefix)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(moderation_private_router, prefix=settings.api_prefix)
app.include_router(profile_events_router, prefix=settings.api_prefix)
app.include_router(profile_social_router, prefix=settings.api_prefix)
from app.modules.social.stories_router import router as stories_router
app.include_router(stories_router, prefix=settings.api_prefix)
from app.modules.social.connections_router import router as connections_router
app.include_router(connections_router, prefix=settings.api_prefix)
app.include_router(roles_router, prefix=settings.api_prefix)
app.include_router(environment_admin_router, prefix=settings.api_prefix)
from app.modules.demo.router import router as demo_router, cover_router as demo_cover_router
app.include_router(demo_router, prefix=settings.api_prefix)
app.include_router(demo_cover_router, prefix=settings.api_prefix)
app.include_router(readings_router, prefix=settings.api_prefix)
app.include_router(challenge_router, prefix=settings.api_prefix)
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

from app.modules.social.moderation_admin_router import router as moderation_admin_router
app.include_router(moderation_admin_router, prefix=settings.api_prefix)

from app.modules.social.moderation_notifications import router as moderation_notifications_router
app.include_router(moderation_notifications_router, prefix=settings.api_prefix)
