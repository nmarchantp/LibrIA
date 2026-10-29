"""Phase 6 validation exclusively in a label-owned disposable PostgreSQL."""
from scripts.validate_catalog_phase1 import main

if __name__ == '__main__':
    raise SystemExit(main(extra_test_modules=('tests.test_catalog_phase2','tests.test_google_books_resilience',
        'tests.test_book_search_resilience','tests.test_default_admin_seed','tests.test_catalog_phase3',
        'tests.test_catalog_phase4','tests.test_daily_etl','tests.test_nightly_recommendation_profiles',
        'tests.test_reading_genres','tests.test_reading_reflections','tests.test_catalog_phase5','tests.test_catalog_phase6'),
        phase='phase6',target_head='0059_merge_previews'))
