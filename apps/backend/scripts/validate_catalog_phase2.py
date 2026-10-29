"""Reuse the owned, ephemeral PostgreSQL validator; never accept a target URL."""
from scripts.validate_catalog_phase1 import main


if __name__ == "__main__":
    raise SystemExit(main(extra_test_modules=("tests.test_catalog_phase2",), phase="phase2"))
