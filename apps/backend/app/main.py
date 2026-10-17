"""Punto de entrada del único servidor FastAPI de LibrIA."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.social.router import profile_social_router, router as social_router
from app.modules.users.roles_router import router as roles_router
from app.modules.library.router import router as readings_router
from app.modules.users.identities_router import router as profiles_router
from app.modules.analytics.router import router as analytics_router
from app.modules.analytics.insights_router import router as insights_router
from app.modules.analytics.scheduler import daily_scheduler, manual_scheduler, projection_scheduler
from app.modules.social.reviews_router import router as reviews_router
from app.modules.books.router import router as books_router
from app.modules.analytics.adaptive_router import router as adaptive_router

settings = get_settings()

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(daily_scheduler()) if settings.analytics_scheduler_enabled else None
    manual_task = asyncio.create_task(manual_scheduler())
    projection_task = asyncio.create_task(projection_scheduler()) if settings.ai_worker_enabled else None
    from app.modules.analytics.adaptive_worker import worker_loop
    ai_task = asyncio.create_task(worker_loop(profile_only=False)) if settings.ai_worker_enabled else None
    ai_profile_task = asyncio.create_task(worker_loop(profile_only=True)) if settings.ai_worker_enabled else None
    try:
        yield
    finally:
        for worker in (task, manual_task, projection_task, ai_task, ai_profile_task):
            if worker is None:
                continue
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

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
app.include_router(analytics_router, prefix=settings.api_prefix)
app.include_router(insights_router, prefix=settings.api_prefix)
app.include_router(reviews_router, prefix=settings.api_prefix)
app.include_router(books_router, prefix=settings.api_prefix)
app.include_router(adaptive_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Permite verificar que el proceso está funcionando sin consultar datos."""
    return {"status": "ok", "service": "libria-api"}
