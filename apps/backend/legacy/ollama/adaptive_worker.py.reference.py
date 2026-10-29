# Frozen local-worker reference from commit 8fe48f7.
# """Optional in-process runner; the same durable queue supports a separate worker."""
# import asyncio
# import logging
# from app.modules.analytics.adaptive_ai import process_one
#
#
# async def worker_loop(profile_only=None):
#     while True:
#         try:
#             worked = await asyncio.to_thread(process_one,profile_only=profile_only)
#         except Exception:
#             logging.getLogger(__name__).warning('Private AI queue unavailable; retrying without logging user data')
#             worked = False
#         await asyncio.sleep(0.2 if worked else 2)
