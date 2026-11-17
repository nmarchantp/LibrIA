"""Run onboarding and regression contracts against an explicitly disposable DB.

Local .env rollout/prompt overrides are deliberately excluded from test fixtures.
No provider used by these suites performs remote Gemini calls.
"""
import os
import unittest

from sqlalchemy.engine import make_url


def main():
    url = make_url(os.environ['DATABASE_URL'])
    if url.host not in {'localhost', '127.0.0.1'} or not (url.database or '').startswith('libria_nightly_test_'):
        raise RuntimeError('Use an isolated loopback database named libria_nightly_test_*')
    os.environ['APP_ENV'] = 'test'
    for flag in ('LIBRIA_STAGE5_TEST', 'LIBRIA_GEMINI_FIX_TEST', 'LIBRIA_NIGHTLY_TEST'):
        os.environ[flag] = '1'
    from app.core.config import Settings
    Settings.model_config['env_file'] = None
    from app.core.database import engine
    from sqlalchemy import text
    # Every run starts from the same disposable fixture state, including reruns
    # after committed worker/concurrency cases from a previous invocation.
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE app.usuarios,app.obras,app.autores,analytics.ejecuciones_etl CASCADE'))
        connection.execute(text('TRUNCATE ia.provider_cooldowns'))
    modules = ['test_onboarding', 'test_onboarding_direct', 'test_security', 'test_google_login', 'test_account_management',
               'test_gemini_provider', 'test_literary_preferences', 'test_reading_genres',
               'test_stage5_gemini_worker', 'test_private_analysis_refresh',
               'test_nightly_reading_analysis', 'test_gemini_optimization']
    suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.' + name for name in modules])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
