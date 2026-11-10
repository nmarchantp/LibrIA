"""A fixed user-approved reading list, matched by title AND author."""
import json
import logging
from pathlib import Path
import re
import unicodedata
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.books.identity import canonical_author_name
from app.modules.books.models import Author, CatalogSource, Edition, WorkAuthor
from app.modules.demo.covers import cover_path, edition_cover_content, save_cover

logger = logging.getLogger(__name__)
CURATED_BOOKS = json.loads(Path(__file__).with_name('curated_books.json').read_text(encoding='utf-8'))


def normalized(value):
    text = ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))


def matches(spec, title, authors):
    title = normalized(title)
    if any(word in title.split() for word in ('resumen', 'diario', 'summary', 'journal', 'notebook', 'cuaderno', 'colorear')):
        return False
    if not any(title == normalized(alias) or title.startswith(normalized(alias) + ' ')
               for alias in spec['aliases']):
        return False
    wanted = {canonical_author_name(name) for name in [spec['author'], *spec.get('author_aliases', [])]}
    return bool(wanted.intersection(canonical_author_name(name) for name in authors))


def local_candidates(spec, edition_ids=None):
    with SessionLocal() as db:
        query = select(Edition, Author.name).join(WorkAuthor, WorkAuthor.work_id == Edition.work_id)
        query = query.join(Author, Author.id == WorkAuthor.author_id).where(Edition.language == 'es',
            select(CatalogSource.id).where(CatalogSource.edition_id == Edition.id,
                CatalogSource.provider.in_(('google-books', 'open-library')),
                CatalogSource.validation_status == 'validated').exists())
        if edition_ids:
            query = query.where(Edition.id.in_([uuid.UUID(value) for value in edition_ids]))
        else:
            surname = spec['author'].split()[-1]
            pattern = ''.join('_' if unicodedata.normalize('NFD', c) != c else c for c in surname)
            query = query.where(Author.name.ilike('%' + pattern + '%'))
        rows = db.execute(query.order_by(Edition.id)).all()
        editions, authors = {}, {}
        for edition, author in rows:
            editions[edition.id] = edition
            authors.setdefault(edition.id, []).append(author)
        return [e for key, e in editions.items() if matches(spec, e.title, authors[key])]


def select_with_cover(spec, check_active):
    for edition in local_candidates(spec):
        check_active()
        if cover_path(edition.id).is_file():
            return str(edition.id)
        content = edition_cover_content(edition)
        if content:
            save_cover(edition.id, content)
            return str(edition.id)
    return None


def import_selection(spec, admin_id, check_active):
    from app.modules.books.google_books import google_request
    from app.modules.books.policy import provider_budget
    from app.modules.books.evidence import ExternalReference
    from app.modules.books.facade import public_import
    from app.modules.books import open_library
    for provider, alias in [('google-books', alias) for alias in spec['aliases'][:2]] + [('open-library', spec['aliases'][0])]:
        check_active()
        try:
            with provider_budget():
                result = (google_request(query=f'intitle:"{alias}" inauthor:"{spec["author"]}"')
                          if provider == 'google-books' else open_library.search(alias, search_by='title'))
        except Exception as error:
            from app.modules.demo.service import DemoPaused
            if isinstance(error, DemoPaused):
                raise
            logger.warning('Curated search failed provider=%s key=%s', provider, spec['key'])
            continue
        candidates = [item for item in result.get('items', []) if matches(spec,
            (item.get('volumeInfo') or {}).get('title', ''), (item.get('volumeInfo') or {}).get('authors', []))
            and (item.get('volumeInfo') or {}).get('language') == 'es']
        for item in candidates[:3]:
            check_active()
            with SessionLocal() as db:
                external_id = item['id'].removeprefix('openlibrary:')
                reference = ExternalReference(provider, 'volume' if provider == 'google-books' else 'edition', external_id)
                imported = public_import(db, admin_id, reference,
                    f'showcase-curated-v2:{provider}:{external_id}', 'Selección demo solicitada por el administrador: ' + spec['title'])
                edition = db.get(Edition, uuid.UUID(imported.edition_id))
                # Re-read trusted imported data: never assign a cover to a title
                # selected only from client metadata or to a mismatched edition.
                authors = list(db.scalars(select(Author.name).join(WorkAuthor, WorkAuthor.author_id == Author.id)
                    .where(WorkAuthor.work_id == edition.work_id)))
                if not matches(spec, edition.title, authors):
                    continue
                trusted_cover = edition_cover_content(edition)
                if trusted_cover:
                    save_cover(edition.id, trusted_cover)
                    return str(edition.id)
    return None


def prepare_selection(admin_id, check_active):
    selected, missing = [], []
    for spec in CURATED_BOOKS:
        check_active()
        edition_id = select_with_cover(spec, check_active)
        if edition_id is None:
            try:
                edition_id = import_selection(spec, admin_id, check_active)
            except Exception as error:
                # A provider outage for one book must not select unrelated books.
                from app.modules.demo.service import DemoPaused
                if isinstance(error, DemoPaused):
                    raise
                logger.warning('Could not prepare curated demo title key=%s', spec['key'])
        if edition_id:
            selected.append(edition_id)
        else:
            missing.append(spec['title'])
    if not selected:
        raise ValueError('No se pudo obtener ninguna edición de la lista con portada. Revisa Google Books y reintenta.')
    return selected, missing


def selection_labels(edition_ids):
    selected = set(edition_ids)
    labels, missing = [], []
    if not edition_ids:
        return [], [spec['title'] for spec in CURATED_BOOKS]
    for spec in CURATED_BOOKS:
        if any(str(e.id) in selected and cover_path(e.id).is_file() for e in local_candidates(spec, edition_ids)):
            labels.append(spec['title'])
        else:
            missing.append(spec['title'])
    return labels, missing


def valid_selection(edition_ids):
    if not edition_ids:
        return False
    allowed = {str(e.id) for spec in CURATED_BOOKS for e in local_candidates(spec, edition_ids)
               if cover_path(e.id).is_file()}
    return all(value in allowed for value in edition_ids)
