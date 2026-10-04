"""Genera publicaciones de demostración continuamente a través de la API."""

import argparse
from dataclasses import dataclass
import json
import msvcrt
from pathlib import Path
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from scripts.seed_demo import MANIFEST, main as seed_demo


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"API respondió HTTP {status}: {detail}")
        self.status = status


class ApiUnavailable(Exception):
    pass


@dataclass
class DemoActor:
    account: dict[str, Any]
    profile_id: str
    token: str


class SingleInstance:
    def __enter__(self):
        self.path = Path(tempfile.gettempdir()) / "libria-generate-posts.lock"
        self.file = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            self.file.close()
            raise RuntimeError("Ya hay una instancia del generador de publicaciones activa") from error
        return self

    def __exit__(self, *_: object) -> None:
        self.file.seek(0)
        msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        self.file.close()


def make_post(account: dict[str, Any], profile_id: str, sequence: int) -> dict[str, Any]:
    """Construye un payload admitido por POST /api/posts."""
    books = (
        ("demo:papel-y-tinta", "Papel y tinta"),
        ("demo:mapa-de-invierno", "Mapa de invierno"),
        ("demo:la-casa-del-rio", "La casa del río"),
        ("demo:ciudades-de-luz", "Ciudades de luz"),
    )
    topics = (
        "Una lectura que invita a conversar y descubrir nuevas historias.",
        "Hoy compartimos una recomendación para quienes disfrutan leer en comunidad.",
        "Una nueva historia se suma a nuestra lista de lecturas por descubrir.",
        "Nos encontramos para compartir libros, ideas y buenas conversaciones.",
    )
    key = account["key"]

    if key == "lector":
        book_ref, book_title = books[sequence % len(books)]
        return {
            "source": "review",
            "kind": "reviews",
            "author_profile_id": profile_id,
            "book_ref": book_ref,
            "book_title": book_title,
            "rating": sequence % 5 + 1,
            "body": f"{book_title}: {topics[sequence % len(topics)]}",
        }

    if sequence % 4 == 0:
        return {
            "source": "event",
            "kind": "community",
            "publication_type": "event",
            "author_profile_id": profile_id,
            "title": "Encuentro de lectura",
            "body": topics[sequence % len(topics)],
        }

    return {
        "source": "community",
        "kind": "community",
        "publication_type": "promotion" if account.get("organization") else "free",
        "author_profile_id": profile_id,
        "title": "Novedades para la comunidad lectora",
        "body": topics[sequence % len(topics)],
    }


class ApiClient:
    def __init__(self, base_url: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.password = password

    def request(self, path: str, payload: dict[str, Any] | None = None,
                token: str | None = None) -> Any:
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(f"{self.base_url}{path}", data=data, headers=headers)
        try:
            with urlopen(request, timeout=10) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code >= 500 or error.code == 429:
                raise ApiUnavailable(f"HTTP {error.code}: {detail}") from error
            raise ApiError(error.code, detail) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ApiUnavailable(str(error)) from error

    def login(self, account: dict[str, Any]) -> str:
        result = self.request("/auth/login", {
            "email": account["email"],
            "password": self.password,
        })
        return result["access_token"]

    def load_actors(self) -> list[DemoActor]:
        actors = []
        for account in MANIFEST["accounts"]:
            token = self.login(account)
            profiles = self.request("/profiles/me", token=token)
            profile_kind = "organization" if account.get("organization") else "personal"
            profile = next(
                (
                    item for item in profiles
                    if item["kind"] == profile_kind
                    and (profile_kind != "organization" or item["organization_type"] == account["key"])
                ),
                None,
            )
            if profile is None:
                raise RuntimeError(f"No se encontró el perfil demo de {account['email']}")
            actors.append(DemoActor(account=account, profile_id=profile["id"], token=token))
        return actors

    def create_post(self, actor: DemoActor, sequence: int) -> dict[str, Any]:
        payload = make_post(actor.account, actor.profile_id, sequence)
        try:
            return self.request("/posts", payload, actor.token)
        except ApiError as error:
            if error.status != 401:
                raise
            actor.token = self.login(actor.account)
            return self.request("/posts", payload, actor.token)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera posts de demostración en la API de LibrIA.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api",
                        help="URL base de la API (por defecto: http://127.0.0.1:8000/api)")
    parser.add_argument("--interval", type=float, default=20,
                        help="Segundos entre publicaciones (por defecto: 20)")
    parser.add_argument("--count", type=int,
                        help="Cantidad finita de posts; si se omite, genera continuamente")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval debe ser mayor que cero")
    if args.count is not None and args.count < 1:
        parser.error("--count debe ser al menos 1")
    return args


def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("El generador de publicaciones solo está habilitado en desarrollo")
    if len(settings.libria_demo_password) < 8:
        raise SystemExit("Configura LIBRIA_DEMO_PASSWORD de al menos 8 caracteres")

    seed_demo()
    client = ApiClient(args.api_url, settings.libria_demo_password)
    actors: list[DemoActor] = []
    generated = 0
    while args.count is None or generated < args.count:
        try:
            if not actors:
                actors = client.load_actors()
            actor = actors[generated % len(actors)]
            post = client.create_post(actor, generated)
        except ApiUnavailable as error:
            print(f"API no disponible; se reintentará en {args.interval:g} s: {error}", flush=True)
            time.sleep(args.interval)
            continue
        except ApiError as error:
            raise SystemExit(f"No se pudo generar el post: {error}") from error

        generated += 1
        print(
            f"Post {generated} guardado: {post['id']} ({post['source']}/{post['kind']}) "
            f"por {post['author']}",
            flush=True,
        )
        if args.count is None or generated < args.count:
            time.sleep(args.interval)


def main() -> None:
    args = parse_args()
    try:
        with SingleInstance():
            run(args)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
