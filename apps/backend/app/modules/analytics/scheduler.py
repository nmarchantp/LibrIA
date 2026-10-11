"""El reloj revisa cierres; la base garantiza una sola carga exitosa por fecha."""
import asyncio
import logging

from app.modules.analytics.etl import run_pending, resume_manual_pending

logger = logging.getLogger(__name__)


async def manual_scheduler():
    """Recover persisted web requests even when daily scheduling is disabled."""
    while True:
        try:
            await asyncio.to_thread(resume_manual_pending)
        except Exception:
            logger.exception("No se pudieron recuperar solicitudes manuales del ETL")
        await asyncio.sleep(5)


async def daily_scheduler():
    while True:
        try:
            await asyncio.to_thread(run_pending)
        except Exception:
            # Los detalles técnicos van al log del servidor, no a la pantalla.
            logger.exception("Falló el cierre diario del ETL; se reintentará en cinco minutos")
            await asyncio.sleep(300)
        else:
            await asyncio.sleep(30)
