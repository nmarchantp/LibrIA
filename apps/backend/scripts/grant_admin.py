"""Otorga el rol administrador a una cuenta existente desde la consola del servidor."""

import argparse

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User  # noqa: F401 - registra la relación ORM


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Correo de la cuenta ya registrada")
    args = parser.parse_args()
    with SessionLocal() as db:
        account = db.scalar(select(AuthAccount).where(AuthAccount.email == args.email.lower()))
        if account is None:
            parser.error("No existe una cuenta con ese correo")
        account.user.role = "admin"
        db.commit()
        print(f"Administrador habilitado: {account.email}")


if __name__ == "__main__":
    main()
