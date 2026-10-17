"""Run independently: python -m scripts.run_ai_worker [--once]."""
import sys
import time
import logging
from app.modules.analytics.adaptive_ai import process_one

if __name__ == '__main__':
    profile_only=True if '--profiles-only' in sys.argv else False if '--books-only' in sys.argv else None
    if '--once' in sys.argv:
        process_one(profile_only=profile_only)
    else:
        while True:
            try:
                worked = process_one(profile_only=profile_only)
            except Exception:
                logging.warning('Private AI queue unavailable; retrying')
                worked = False
            if not worked:
                time.sleep(2)
