"""Genera ejemplos según permisos y eventos reales de lectura en desarrollo."""

import argparse
import json
import os
import random
import tempfile
import time
import urllib.error
import urllib.request
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.auth.models import AuthAccount
from app.modules.users.models import User

PEOPLE = [
    ("Camila Rios", "lector"),
    ("Tomas Vidal", "lector"),
    ("Elena del Rio", "autor"),
    ("Sofia Fuentes", "influencer"),
    ("Mateo Araya", "lector"),
    ("Librería Entre Páginas", "libreria"),
    ("Equipo LibrIA", "admin"),
    ("Valentina Mena", "influencer"),
    ("Daniel Castro", "autor"),
    ("Librería Aurora", "libreria"),
]

TEMPLATES = {
    "lector": [
        {"source": "review", "kind": "reviews", "book_ref": "demo:fourth-wing", "book_title": "Fourth Wing", "rating": 4,
         "body": "La aventura me atrapó desde el primer capítulo. Me gustó especialmente el vínculo entre los personajes."},
        {"source": "review", "kind": "reviews", "book_ref": "demo:mistborn", "book_title": "Mistborn", "rating": 5,
         "body": "El sistema de magia es fascinante y el final me dejó pensando en todo lo que había pasado."},
        {"reading_event": "start", "book_ref": "demo:fourth-wing", "book_title": "Fourth Wing", "page_count": 500},
        {"reading_event": "progress", "book_ref": "demo:mistborn", "book_title": "Mistborn", "page_count": 600, "current_page": 300},
        {"reading_event": "finish", "book_ref": "demo:la-vegetariana", "book_title": "La vegetariana", "page_count": 200},
        {"reading_event": "abandon", "book_ref": "demo:otro-libro", "book_title": "Un libro pendiente", "page_count": 320,
         "abandonment_reason": "No era la lectura que buscaba en este momento"},
    ],
    "influencer": [
        {"source": "community", "kind": "community", "title": "Lectura conjunta",
         "body": "Esta semana leeremos los primeros cinco capítulos. Compartan sus impresiones sin spoilers."},
        {"source": "community", "kind": "community", "title": "Tres recomendaciones",
         "body": "Si buscan una lectura para el fin de semana, cuéntenme qué género prefieren y armamos una lista."},
        {"source": "review", "kind": "reviews", "book_ref": "demo:mistborn", "book_title": "Mistborn", "rating": 5,
         "body": "Lo releí para preparar una conversación y encontré detalles que había pasado por alto."},
    ],
    "autor": [
        {"source": "community", "kind": "community", "title": "El primer borrador",
         "body": "Hoy terminé el primer borrador de mi nueva novela. Ahora comienza el trabajo de revisar."},
        {"source": "community", "kind": "community", "title": "Detrás de una historia",
         "body": "Una conversación escuchada al pasar terminó convirtiéndose en la primera escena de mi próxima novela."},
        {"source": "event", "kind": "community", "title": "Encuentro con lectores",
         "body": "El sábado conversaré sobre personajes y procesos creativos. Me encantará escuchar sus preguntas."},
    ],
    "libreria": [
        {"source": "community", "kind": "community", "title": "Fin de semana de fantasía",
         "body": "20 % de descuento en fantasía este fin de semana."},
        {"source": "event", "kind": "community", "title": "Club de lectura",
         "body": "Club de lectura — sábado 18:00. Trae una historia que te haya marcado."},
        {"source": "community", "kind": "community", "title": "Novedades en nuestra mesa",
         "body": "Preparamos narrativa breve y ensayo para quienes buscan su próxima lectura."},
    ],
    "admin": [
        {"source": "community", "kind": "community", "title": "Bienvenidos a LibrIA",
         "body": "Este espacio reúne lectores, autores, influencers y librerías para conversar con respeto sobre libros."},
        {"source": "event", "kind": "community", "title": "Actividad de la comunidad",
         "body": "Este mes destacaremos conversaciones sobre lecturas que nos hicieron cambiar de perspectiva."},
    ],
}


def request(base, path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def register_or_login(base, email, password, name):
    try:
        return request(base, "/auth/register", {"email": email, "password": password, "display_name": name})
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
        return request(base, "/auth/login", {"email": email, "password": password})


def bootstrap_demo_admin(user_id: str, email: str) -> None:
    """Única elevación local: crea el admin de muestra sin exponer una ruta pública."""
    with SessionLocal() as db:
        account = db.scalar(select(AuthAccount).where(
            AuthAccount.user_id == uuid.UUID(user_id), AuthAccount.email == email,
        ))
        if account is None:
            raise RuntimeError("El administrador de ejemplo no pertenece a la base local")
        user = db.get(User, account.user_id)
        if user.role != "admin":
            user.role = "admin"
            db.commit()


def ensure_person(base, index, password, admin_token):
    name, role = PEOPLE[index]
    email = f"sim.reader{index + 1}@example.com"
    if role == "libreria":
        try:
            session = request(base, "/auth/login", {"email": email, "password": password})
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise
            request(base, "/roles/bookstores", {"email": email, "password": password, "display_name": name}, admin_token)
            session = request(base, "/auth/login", {"email": email, "password": password})
    else:
        session = register_or_login(base, email, password, name)
        if role in {"autor", "influencer"} and session["user"]["role"] == "lector":
            pending = next((item for item in request(base, "/roles/requests/me", token=session["access_token"])
                            if item["status"] == "pending" and item["requested_role"] == role), None)
            if pending is None:
                pending = request(base, "/roles/requests", {"requested_role": role,
                    "note": "Perfil de ejemplo generado para pruebas locales de LibrIA."}, session["access_token"])
            request(base, f"/roles/requests/{pending['id']}/approve", {}, admin_token)
            session = request(base, "/auth/login", {"email": email, "password": password})
    if session["user"]["role"] != role:
        raise RuntimeError(f"El perfil {email} no tiene el tipo {role}")
    return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000/api")
    parser.add_argument("--count", type=int, help="Número de ejemplos; sin esta opción funciona continuamente")
    parser.add_argument("--interval", type=float, default=30, help="Segundos entre ejemplos (predeterminado: 30)")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if (args.count is not None and args.count < 1) or args.interval <= 0:
        parser.error("count debe ser positivo e interval mayor que cero")
    settings = get_settings()
    password = os.environ.get("LIBRIA_DEMO_PASSWORD") or settings.libria_demo_password
    if not password or len(password) < 8:
        parser.error("Define LIBRIA_DEMO_PASSWORD con al menos 8 caracteres")
    if settings.app_env != "development":
        parser.error("Los perfiles de prueba solo funcionan en APP_ENV=development")
    admin_email = "sim.reader7@example.com"
    admin_session = register_or_login(args.url, admin_email, password, "Equipo LibrIA")
    bootstrap_demo_admin(admin_session["user"]["id"], admin_email)
    admin_token = admin_session["access_token"]
    rng = random.Random(args.seed)
    index = 0
    while args.count is None or index < args.count:
        started = time.monotonic()
        person_index = index % len(PEOPLE)
        name, role = PEOPLE[person_index]
        try:
            if role == "admin":
                session = request(args.url, "/auth/login", {"email": admin_email, "password": password})
            else:
                session = ensure_person(args.url, person_index, password, admin_token)
            template = rng.choice(TEMPLATES[role]).copy()
            if "reading_event" in template:
                template["book_ref"] += f":{person_index}:{uuid.uuid4().hex[:8]}"
                template["event"] = template.pop("reading_event")
                result = request(args.url, "/readings/events", template, session["access_token"])["post"]
            else:
                if template["source"] == "review":
                    template["title"] = f'Reseña de "{template["book_title"]}"'
                result = request(args.url, "/posts", template, session["access_token"])
            index += 1
            print(f"{index}: {result['id']} ({role}, {result['source']}, {name})", flush=True)
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            print(f"No se pudo publicar; reintentando: {exc}", flush=True)
        if args.count is None or index < args.count:
            time.sleep(max(0, args.interval - (time.monotonic() - started)))


if __name__ == "__main__":
    lock_path = os.path.join(tempfile.gettempdir(), "libria-post-generator.lock")
    with open(lock_path, "a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        try:
            if os.name == "nt":
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("El generador ya está en ejecución") from None
        main()
