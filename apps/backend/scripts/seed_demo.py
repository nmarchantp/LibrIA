"""Carga finita de seis identidades ficticias con claves estables y sin borrar datos."""

import json
from pathlib import Path
import uuid

from sqlalchemy import select, delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission, Profile, ProfileCapability, ProfileMember

MANIFEST = json.loads(Path(__file__).with_name("demo_accounts.json").read_text(encoding="utf-8"))
NAMESPACE = uuid.UUID(MANIFEST["namespace"])


def stable_id(key):
    return uuid.uuid5(NAMESPACE, key)


def configured_passwords(settings, fallback=None):
    """Return credentials only to the seeder, never to logs or public responses."""
    common = settings.libria_demo_password if fallback is None else fallback
    return {entry['key']: getattr(settings, f"libria_demo_{entry['key']}_password", '') or common
            for entry in MANIFEST['accounts']}


def seed(db, password, keys=None, *, passwords=None):
    accounts = []
    entries = MANIFEST["accounts"]
    if keys is not None:
        entries = [entry for entry in entries if entry["key"] in set(keys)]
    credentials = {entry['key']: (passwords or {}).get(entry['key'], password) for entry in entries}
    for key, credential in credentials.items():
        if not isinstance(credential, str) or len(credential) < 8:
            raise ValueError(f"Configura LIBRIA_DEMO_{key.upper()}_PASSWORD o LIBRIA_DEMO_PASSWORD con al menos 8 caracteres")
    for entry in entries:
        key = entry["key"]
        credential = credentials[key]
        user_id, profile_id = stable_id(f"user:{key}"), stable_id(f"profile:{key}")
        account = db.scalar(select(AuthAccount).where(AuthAccount.email == entry["email"]))
        if account and account.user_id != user_id:
            raise ValueError("Un correo del manifiesto ya pertenece a otra cuenta; no se modifica")
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        changed = False
        if user is None:
            user = User(id=user_id, display_name=entry["name"], role=key)
            user.auth_account = AuthAccount(id=stable_id(f"auth:{key}"), email=entry["email"], password_hash=hash_password(credential))
            db.add(user)
            db.flush()
        elif account is None:
            raise ValueError("La identidad demo existente no coincide con el manifiesto")
        elif not verify_password(credential, account.password_hash):
            # Son identidades ficticias y estables, exclusivas del entorno de
            # desarrollo. Sincronizar su clave permite regenerar el .env sin
            # perder perfiles, publicaciones ni datos de demostracion.
            account.password_hash = hash_password(credential)
            changed = True
        if user.role != key:
            from app.modules.users.account_service import audit
            audit(db, user, None, 'demo_role_synchronized', before={'role': user.role}, after={'role': key},
                  reason='Sincronización explícita de una identidad ficticia del manifiesto', origin='demo_seed')
            user.role = key
            changed = True
        if changed:
            from app.modules.users.account_service import revoke_all
            revoke_all(db, user.id, 'demo_credentials_or_role_changed')
        profile = db.get(Profile, profile_id)
        if profile is None:
            profile = Profile(id=profile_id, kind="personal", owner_user_id=user.id, display_name=user.display_name)
            db.add(profile)
            db.flush()
        for capability in entry["capabilities"]:
            if db.get(ProfileCapability, (profile.id, capability)) is None:
                db.add(ProfileCapability(profile_id=profile.id, capability=capability))
        db.execute(delete(ProfileCapability).where(ProfileCapability.profile_id == profile.id,
            ProfileCapability.capability.not_in(entry['capabilities'])))
        if entry.get("admin") and db.get(AccountPermission, (user.id, "admin")) is None:
            db.add(AccountPermission(user_id=user.id, permission="admin"))
        elif not entry.get('admin'):
            db.execute(delete(AccountPermission).where(AccountPermission.user_id == user.id, AccountPermission.permission == 'admin'))
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
    import argparse
    parser = argparse.ArgumentParser(description='Prepara solo las seis cuentas demo, sin libros ni generaciones IA')
    parser.add_argument('--role', action='append', choices=[entry['key'] for entry in MANIFEST['accounts']], help='Sincroniza únicamente este perfil; se puede repetir')
    args = parser.parse_args()
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("La carga demo solo está habilitada en desarrollo")
    with SessionLocal.begin() as db:
        # Evita carreras entre dos cargas del mismo manifiesto.
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(96347)"))
        accounts = seed(db, settings.libria_demo_password, keys=args.role, passwords=configured_passwords(settings))
    print("Cuentas demo listas. Usan LIBRIA_DEMO_<PERFIL>_PASSWORD o, si está vacía, LIBRIA_DEMO_PASSWORD:")
    for email in accounts:
        print(email)


if __name__ == "__main__":
    main()
