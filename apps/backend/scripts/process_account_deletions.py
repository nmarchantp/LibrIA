"""Inspect due accounts; --apply executes the approved minimization policy."""
import argparse
from sqlalchemy import select, func
from app.main import app  # load all mapped models
from app.core.database import SessionLocal
from app.modules.users.models import User
from app.modules.users.account_service import now
from app.modules.users.account_lifecycle import process_expired_accounts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.apply:
            count = process_expired_accounts(db)
            db.commit()
            print(f"Anonimizadas: {count}")
        else:
            count = db.scalar(select(func.count()).select_from(User).where(
                User.account_status == "pending_deletion", User.deletion_scheduled_at <= now()))
            print(f"Pendientes vencidas: {count}. Sin cambios; usa --apply para procesar.")
