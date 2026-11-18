"""Mocked ADN v2 regression suites in a disposable, isolated PostgreSQL cluster.

No application DB migrations and no real Gemini calls. Local rollout overrides
must not silently change the original worker/event fixture contracts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import Settings, get_settings
from scripts.test_nightly_reading import main

if __name__ == '__main__':
    Settings.model_config['env_file'] = None
    get_settings.cache_clear()
    if len(sys.argv) == 1:
        sys.argv.extend(['tests.test_gemini_only', 'tests.test_worker_configuration_reload',
                         'tests.test_reader_dna_v2', 'tests.test_gemini_optimization',
                         'tests.test_stage5_gemini_worker', 'tests.test_nightly_reading_analysis',
                         'tests.test_private_analysis_refresh'])
    raise SystemExit(main())
