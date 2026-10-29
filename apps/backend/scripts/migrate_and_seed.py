"""Aplica migraciones autorizadas y carga la cuenta inicial de desarrollo."""

from alembic import command
from alembic.config import Config

from scripts.seed_default_admin import main as seed_default_admin


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    seed_default_admin()


if __name__ == "__main__":
    main()
