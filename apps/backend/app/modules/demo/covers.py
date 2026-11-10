"""Download original provider images once; never generate or alter book covers."""
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import uuid

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

COVER_DIR = Path(__file__).resolve().parents[3] / 'var' / 'demo-covers'
HOSTS = {'books.google.com', 'books.googleusercontent.com', 'covers.openlibrary.org', 'imagessl4.casadellibro.com'}
SOURCES = {isbn: data for spec in json.loads(Path(__file__).with_name('curated_books.json').read_text(encoding='utf-8'))
           for isbn, data in spec.get('cover_sources', {}).items()}


def cover_path(edition_id):
    return COVER_DIR / (str(uuid.UUID(str(edition_id))) + '.img')


def valid_image(content):
    if not 2000 <= len(content) <= 5 * 1024 * 1024:
        return False
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width < 96 or image.height < 130:
                return False
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return False


def download_cover(url):
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url)
        allowed = parts.hostname in HOSTS and not parts.username and not parts.password and parts.port in (None, 80, 443)
    except ValueError:
        return None
    if not allowed:
        return None
    # Provider metadata often still supplies HTTP links; use HTTPS for retrieval.
    url = urlunsplit(('https', parts.hostname, parts.path, parts.query, ''))
    try:
        with httpx.Client(timeout=httpx.Timeout(12, connect=4), follow_redirects=False) as client:
            with client.stream('GET', url) as response:
                if response.status_code != 200:
                    return None
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 5 * 1024 * 1024:
                        return None
                    chunks.append(chunk)
        content = b''.join(chunks)
        return content if valid_image(content) else None
    except httpx.HTTPError:
        return None


def save_cover(edition_id, content):
    path = cover_path(edition_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)


def edition_cover_content(edition):
    content = download_cover(edition.cover_url)
    if content:
        return content
    # ISBNs come from the imported, verified edition, never a guessed title.
    for isbn in (edition.isbn13, edition.isbn10):
        if isbn:
            content = download_cover(f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false')
            if content:
                return content
            source = SOURCES.get(isbn)
            if source:
                content = download_cover(source['url'])
                if content:
                    return content
    return None


def cached_cover_url(edition_id):
    if edition_id and cover_path(edition_id).is_file():
        return f'{get_settings().api_prefix}/demo/covers/{edition_id}'
    return None
