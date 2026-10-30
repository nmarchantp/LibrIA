"""Run ETL recovery, nightly closure and projections outside the web API."""

import asyncio

from app.core.config import get_settings
from app.modules.analytics.scheduler import daily_scheduler, manual_scheduler, projection_scheduler
from app.modules.users.account_lifecycle import account_lifecycle_scheduler


async def main() -> None:
    settings = get_settings()
    tasks = [asyncio.create_task(manual_scheduler()), asyncio.create_task(account_lifecycle_scheduler())]
    if settings.analytics_scheduler_enabled:
        tasks.append(asyncio.create_task(daily_scheduler()))
    if settings.projection_scheduler_enabled:
        tasks.append(asyncio.create_task(projection_scheduler()))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
