"""Aplica migraciones autorizadas y carga la cuenta inicial de desarrollo."""

from alembic import command
from alembic.config import Config
import sys

from app.core.config import get_settings

from scripts.seed_default_admin import main as seed_default_admin


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    args = sys.argv[1:]
    if not args and get_settings().catalog_discovery_enabled:
        args = ['--account-only']
    seed_default_admin(args)


if __name__ == "__main__":
    main()
