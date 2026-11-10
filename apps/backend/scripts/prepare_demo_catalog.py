"""Prepare the user-approved demo list without changing its on/off switch."""
import json
import argparse
import time

from app.main import app as _app  # noqa: F401 -- register all ORM models
from app.core.database import SessionLocal
from app.modules.demo.models import DemoMode
from app.modules.demo.service import prepare_catalog
from app.modules.demo.selection import selection_labels
from app.modules.demo.worker import producer_lease


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect-missing', action='store_true')
    args = parser.parse_args()
    if args.inspect_missing:
        from app.modules.demo.selection import CURATED_BOOKS
        from app.modules.books.google_books import google_request
        for spec in CURATED_BOOKS:
            if spec['key'] not in ('mentirosos', 'windy-city', 'destino'):
                continue
            result = google_request(query=f'intitle:"{spec["aliases"][0]}" inauthor:"{spec["author"]}"')
            print(json.dumps({'title': spec['title'], 'items': [dict(id=item['id'], title=item['volumeInfo'].get('title'),
                authors=item['volumeInfo'].get('authors'), language=item['volumeInfo'].get('language'),
                images=item['volumeInfo'].get('imageLinks')) for item in result.get('items', [])[:10]]}, ensure_ascii=False), flush=True)
        return
    with SessionLocal() as db:
        mode = db.get(DemoMode, 1)
        admin_id = mode.updated_by
    if not admin_id:
        raise SystemExit('Primero configura el modo demo con una cuenta administradora.')
    for _ in range(10):
        with producer_lease() as acquired:
            if acquired:
                books = prepare_catalog(admin_id, require_active=False, refresh=True)
                labels, missing = selection_labels([book.edition_id for book in books])
                print(json.dumps({'prepared': labels, 'missing': missing, 'count': len(books)}, ensure_ascii=False), flush=True)
                return
        time.sleep(1)
    raise SystemExit('El generador sigue ocupado. Reintenta cuando termine la operación actual.')


if __name__ == '__main__':
    main()
