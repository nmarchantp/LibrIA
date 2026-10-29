"""Coupled discovery/incorporation validation in owned, ephemeral PostgreSQL only."""
from scripts.validate_catalog_phase1 import main


if __name__ == "__main__":
    raise SystemExit(main(extra_test_modules=("tests.test_catalog_phase2", "tests.test_google_books_resilience",
        "tests.test_book_search_resilience", "tests.test_default_admin_seed", "tests.test_catalog_phase3"), phase="phase3"))
