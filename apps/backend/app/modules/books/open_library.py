"""Human-triggered, cached Open Library lookups, at most one request/second.

Search projects a specific matching edition; work-level ISBNs/covers/pages are
never copied to it. Catalog persistence belongs to the selection adapter.
"""
import logging
import re
import threading
import time

import httpx
from fastapi import HTTPException
from app.core.config import get_settings
from app.modules.books.policy import provider_remaining, provider_sleep
from app.modules.books.google_books import retry_after

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_last_request = 0.0
PAGE_SIZE = 3
FIELDS = 'key,title,author_name,subject,editions,editions.key,editions.title,editions.language,editions.isbn,editions.cover_i,editions.publisher,editions.publish_date,editions.number_of_pages'


def request_json(path, params=None):
    global _last_request
    contact = get_settings().open_library_contact.strip()
    headers = {'User-Agent': 'LibrIAverse/0.1 (educational reading application' + (f'; {contact}' if contact else '') + ')'}
    with _lock, httpx.Client(timeout=httpx.Timeout(12, connect=3), headers=headers) as client:
        for attempt in range(2):
            pause = max(0, 1.05 - (time.monotonic() - _last_request))
            if pause:
                provider_sleep(pause)
            _last_request = time.monotonic()
            try:
                remaining = provider_remaining(12)
                response = client.get('https://openlibrary.org' + path, params=params,
                                      timeout=httpx.Timeout(remaining, connect=min(3, remaining)))
                delay = retry_after(response)
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    if delay is not None and delay > 2:
                        response.raise_for_status()
                    provider_sleep(max(0.5, delay or 0))
                    continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError('Invalid response')
                return data
            except (httpx.HTTPError, ValueError) as error:
                status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                logger.warning('Open Library lookup failed status=%s type=%s attempt=%s', status, type(error).__name__, attempt + 1)
                if isinstance(error, httpx.RequestError) and attempt == 0:
                    provider_sleep(0.5)
                    continue
                raise HTTPException(502, {'code': 'open_library_unavailable', 'message': 'La búsqueda externa está temporalmente limitada. Inténtalo más tarde.'}) from None


def strings(value):
    return [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def isbn(value):
    value = re.sub(r'[\s-]', '', str(value)).upper()
    if len(value) == 13 and value.isdigit() and sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0:
        return value
    if re.fullmatch(r'\d{9}[\dX]', value) and sum((10 - i) * (10 if c == 'X' else int(c)) for i, c in enumerate(value)) % 11 == 0:
        return value
    return None


def key(value, kind):
    match = re.fullmatch(r'(?:/(?:books|works)/)?(OL\d+' + kind + ')', value or '') if isinstance(value, str) else None
    return match.group(1) if match else None


def normalize_edition(work, edition):
    edition_id = key(edition.get('key'), 'M')
    work_id = key(work.get('key'), 'W')
    languages = strings(edition.get('language'))
    # Edition API uses references, while Search API uses language codes.
    languages += [v['key'].rsplit('/', 1)[-1] for v in edition.get('languages', []) if isinstance(v, dict) and isinstance(v.get('key'), str)] if isinstance(edition.get('languages'), list) else []
    if not edition_id or not work_id or not any(v in {'spa', 'es'} for v in languages):
        return None
    title = edition.get('title')
    if not isinstance(title, str) or not title.strip():
        return None
    identifiers = list(dict.fromkeys(v for v in (isbn(i) for i in strings(edition.get('isbn')) + strings(edition.get('isbn_10')) + strings(edition.get('isbn_13'))) if v))
    covers = edition.get('covers') or []
    cover = edition.get('cover_i')
    if not isinstance(cover, int) or isinstance(cover, bool) or cover <= 0:
        cover = next((v for v in covers if isinstance(v, int) and not isinstance(v, bool) and v > 0), None) if isinstance(covers, list) else None
    date = edition.get('publish_date')
    date = date[0] if isinstance(date, list) and date else date
    pages = edition.get('number_of_pages')
    publishers = strings(edition.get('publishers')) or strings(edition.get('publisher'))
    description = edition.get('description')
    if isinstance(description, dict):
        description = description.get('value')
    info = {'title': title.strip(), 'authors': strings(work.get('author_name')), 'language': 'es',
            'categories': strings(work.get('subject'))[:20],
            'industryIdentifiers': [{'type': 'ISBN_13' if len(v) == 13 else 'ISBN_10', 'identifier': v} for v in identifiers]}
    if isinstance(date, str) and date.strip():
        info['publishedDate'] = date.strip()
    if isinstance(pages, int) and not isinstance(pages, bool) and pages > 0:
        info['pageCount'] = pages
    if publishers:
        info['publisher'] = ', '.join(publishers)
    if isinstance(description, str) and description.strip():
        info['description'] = description.strip()
    if cover:
        info['imageLinks'] = {'thumbnail': f'https://covers.openlibrary.org/b/id/{cover}-M.jpg?default=false'}
    return {'id': 'openlibrary:' + edition_id, 'kind': 'books#volume', 'volumeInfo': info,
            'openLibrary': {'workKey': work_id, 'editionKey': edition_id},
            'libria': {'catalogOrigin': 'open_library', 'externalWorkId': work_id, 'externalEditionId': edition_id}}


def search(query, search_by='all', page=1):
    params = {'q': 'language:spa', 'lang': 'es', 'page': page, 'limit': PAGE_SIZE, 'fields': FIELDS}
    if search_by in {'title', 'author', 'isbn'}:
        params[search_by] = query
    else:
        params['q'] = query + ' language:spa'
    data = request_json('/search.json', params)
    docs = data.get('docs') or []
    items = []
    for work in docs if isinstance(docs, list) else []:
        if not isinstance(work, dict):
            continue
        editions = work.get('editions') or {}
        editions = (editions.get('docs') or []) if isinstance(editions, dict) else []
        for edition in editions if isinstance(editions, list) else []:
            item = normalize_edition(work, edition) if isinstance(edition, dict) else None
            if item:
                items.append(item)
                break
    total = data.get('numFound', data.get('num_found', 0))
    more = isinstance(total, int) and total > page * PAGE_SIZE
    return {'items': items, 'active_provider': 'open_library', 'has_more': more,
            'next_page': page + 1 if more else None, 'next_start_index': None}


def detail(edition_id, cached=None):
    if not key(edition_id, 'M'):
        raise HTTPException(404, 'Edición no encontrada')
    edition = request_json('/books/' + edition_id + '.json')
    works = edition.get('works') or []
    work_ids = [key(v.get('key'), 'W') for v in works if isinstance(v, dict) and key(v.get('key'), 'W')]
    cached_work = (cached or {}).get('openLibrary', {}).get('workKey')
    work_id = cached_work if cached_work in work_ids else next(iter(work_ids), None)
    if not work_id:
        raise HTTPException(502, 'Open Library no identifica la obra de esta edición')
    context = {'key': '/works/' + work_id, 'author_name': (cached or {}).get('volumeInfo', {}).get('authors', []) if cached_work == work_id else []}
    work = request_json('/works/' + work_id + '.json')
    context['subject'] = work.get('subjects') or []
    if not context['author_name']:
        names = []
        authors = work.get('authors') or []
        for author in authors[:3] if isinstance(authors, list) else []:
            author_key = (author.get('author') or {}).get('key') if isinstance(author, dict) else None
            if isinstance(author_key, str) and re.fullmatch(r'/authors/OL\d+A', author_key):
                name = request_json(author_key + '.json').get('name')
                if isinstance(name, str):
                    names.append(name)
        context['author_name'] = names
    item = normalize_edition(context, edition)
    if item is None:
        raise HTTPException(404, 'No se encontró esta edición en español')
    if not item['volumeInfo'].get('description'):
        description = work.get('description')
        description = description.get('value') if isinstance(description, dict) else description
        if isinstance(description, str):
            item['volumeInfo']['description'] = description
    return item
