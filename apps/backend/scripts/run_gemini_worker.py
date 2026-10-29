"""Run only the durable Gemini queue: python -m scripts.run_gemini_worker [--once]."""

import asyncio
import sys

from app.core.config import get_settings
from app.modules.analytics.gemini_worker import process_one, worker_loop


if __name__ == "__main__":
    settings = get_settings()
    if not settings.gemini_worker_enabled:
        raise SystemExit("GEMINI_WORKER_ENABLED=false: el worker no esta habilitado")
    free_test_allowed = (
        settings.gemini_free_test_mode
        and settings.app_env in {"development", "test"}
    )
    if not settings.gemini_paid_service_confirmed and not free_test_allowed:
        raise SystemExit("Falta aprobacion pagada o GEMINI_FREE_TEST_MODE permitido solo en development/test")
    if "--once" in sys.argv:
        process_one(settings=settings)
    else:
        asyncio.run(worker_loop())
