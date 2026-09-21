"""Genera actividad de demostracion usando exclusivamente la API publica."""

import argparse
import json
import os
import random
import tempfile
import time
import urllib.error
import urllib.request

from app.core.config import get_settings

PEOPLE = ["Camila Rios", "Tomas Vidal", "Elena del Rio", "Sofia Fuentes", "Mateo Araya"]
TEMPLATES = [
    ("community", "community", "¿Qué están leyendo?", "Hoy quiero conocer nuevas lecturas. ¿Qué libro recomendarían?"),
    ("reading", "progress", None, "Retomé mi lectura esta tarde y encontré un capítulo que me dejó pensando."),
    ("review", "reviews", "Una lectura para conversar", "Terminé este libro y me quedé con ganas de compartir mis impresiones."),
    ("event", "community", "Encuentro de lectores", "Esta semana podríamos conversar sobre nuestras historias favoritas."),
]


def request(base, path, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000/api")
    parser.add_argument("--count", type=int, help="Cantidad máxima; sin esta opción funciona continuamente")
    parser.add_argument("--interval", type=float, default=30, help="Segundos entre publicaciones (predeterminado: 30)")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if (args.count is not None and args.count < 1) or args.interval <= 0:
        parser.error("count debe ser positivo e interval mayor que cero")
    password = os.environ.get("LIBRIA_DEMO_PASSWORD") or get_settings().libria_demo_password
    if not password or len(password) < 8:
        parser.error("Define LIBRIA_DEMO_PASSWORD con al menos 8 caracteres")
    rng = random.Random(args.seed)
    index = 0
    while args.count is None or index < args.count:
        started = time.monotonic()
        person_index = index % len(PEOPLE)
        email = f"sim.reader{person_index + 1}@example.com"
        try:
            try:
                session = request(args.url, "/auth/register", {"email": email, "password": password, "display_name": PEOPLE[person_index]})
            except urllib.error.HTTPError as exc:
                if exc.code != 409:
                    raise
                session = request(args.url, "/auth/login", {"email": email, "password": password})
            source, kind, title, body = rng.choice(TEMPLATES)
            result = request(args.url, "/posts", {"source": source, "kind": kind, "title": title, "body": body}, session["access_token"])
            index += 1
            print(f"{index}: {result['id']} ({source}, {email})", flush=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"API no disponible; reintentando: {exc}", flush=True)
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
