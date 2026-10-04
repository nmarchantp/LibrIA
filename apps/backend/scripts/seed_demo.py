"""Carga finita de seis identidades ficticias con claves estables y sin borrar datos."""

import json
from pathlib import Path
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission, Profile, ProfileCapability, ProfileMember

MANIFEST = json.loads(Path(__file__).with_name("demo_accounts.json").read_text(encoding="utf-8"))
NAMESPACE = uuid.UUID(MANIFEST["namespace"])


def stable_id(key):
    return uuid.uuid5(NAMESPACE, key)


def seed(db, password):
    if len(password) < 8:
        raise ValueError("Configura LIBRIA_DEMO_PASSWORD de al menos 8 caracteres")
    accounts = []
    for entry in MANIFEST["accounts"]:
        key = entry["key"]
        user_id, profile_id = stable_id(f"user:{key}"), stable_id(f"profile:{key}")
        account = db.scalar(select(AuthAccount).where(AuthAccount.email == entry["email"]))
        if account and account.user_id != user_id:
            raise ValueError("Un correo del manifiesto ya pertenece a otra cuenta; no se modifica")
        user = db.get(User, user_id)
        if user is None:
            user = User(id=user_id, display_name=entry["name"], role=key if key in {"autor", "influencer", "admin"} else "lector")
            user.auth_account = AuthAccount(id=stable_id(f"auth:{key}"), email=entry["email"], password_hash=hash_password(password))
            db.add(user)
            db.flush()
        elif account is None:
            raise ValueError("La identidad demo existente no coincide con el manifiesto")
        profile = db.get(Profile, profile_id)
        if profile is None:
            profile = Profile(id=profile_id, kind="personal", owner_user_id=user.id, display_name=user.display_name)
            db.add(profile)
            db.flush()
        for capability in entry["capabilities"]:
            if db.get(ProfileCapability, (profile.id, capability)) is None:
                db.add(ProfileCapability(profile_id=profile.id, capability=capability))
        if entry.get("admin") and db.get(AccountPermission, (user.id, "admin")) is None:
            db.add(AccountPermission(user_id=user.id, permission="admin"))
        if entry.get("organization"):
            organization_id = stable_id(f"organization:{key}")
            if db.get(Profile, organization_id) is None:
                db.add(Profile(id=organization_id, kind="organization", organization_type=key, display_name=entry["organization"]))
                db.flush()
            if db.get(ProfileMember, (organization_id, user.id)) is None:
                db.add(ProfileMember(profile_id=organization_id, user_id=user.id, permission="admin"))
        accounts.append(entry["email"])
        db.flush()
    return accounts


def main():
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("La carga demo solo está habilitada en desarrollo")
    with SessionLocal.begin() as db:
        # Evita carreras entre dos cargas del mismo manifiesto.
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(96347)"))
        accounts = seed(db, settings.libria_demo_password)
    print("Cuentas demo listas (contraseña: LIBRIA_DEMO_PASSWORD local; no se reemplazan claves existentes):")
    for email in accounts:
        print(email)


if __name__ == "__main__":
    main()
