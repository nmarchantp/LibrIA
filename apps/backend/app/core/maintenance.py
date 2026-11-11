"""Keep public registration open while the social network is closed."""
from fastapi.responses import JSONResponse
from app.core.config import get_settings


async def maintenance_guard(request, call_next):
    settings = get_settings()
    prefix = settings.api_prefix.rstrip("/")
    path = request.url.path.rstrip("/")
    if path == f"{prefix}/status" and request.method == "GET":
        return JSONResponse({"maintenance_mode": settings.maintenance_mode},
                            headers={"Cache-Control": "no-store"})
    registration = path == f"{prefix}/auth/register" and request.method == "POST"
    if (settings.maintenance_mode and request.method != "OPTIONS"
            and (path == prefix or path.startswith(prefix + "/")) and not registration):
        return JSONResponse(status_code=503,
                            content={"detail": {"code": "maintenance_mode", "message": "Estamos construyendo LibrIAverse. Puedes crear tu cuenta, pero el acceso aún no está disponible."}},
                            headers={"Cache-Control": "no-store", "Retry-After": "3600"})
    return await call_next(request)
