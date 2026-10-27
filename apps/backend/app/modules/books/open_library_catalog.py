"""Selection-time import with stable internal IDs and conservative ISBN reuse."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from app.modules.books import open_library
from app.modules.books.identity import bibliographic_title, canonical_author_name, canonical_work_key
from app.modules.books.models import Author, CatalogQuery, CatalogSource, Edition, Work, WorkAuthor


def identifiers(item):
    values = {entry.get('type'): open_library.isbn(entry.get('identifier'))
              for entry in item.get('volumeInfo', {}).get('industryIdentifiers', []) if isinstance(entry, dict)}
    ten, thirteen = values.get('ISBN_10'), values.get('ISBN_13')
    if ten and not thirteen:
        base = '978' + ten[:9]
        thirteen = base + str((-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))) % 10)
    if thirteen and thirteen.startswith('978') and not ten:
        base = thirteen[3:12]
        digit = (-sum((10 - i) * int(c) for i, c in enumerate(base))) % 11
        ten = base + ('X' if digit == 10 else str(digit))
    return ten, thirteen


def find_existing(db, item):
    external = item.get('openLibrary', {}).get('editionKey')
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == 'open-library', CatalogSource.external_id == external))
    if source:
        return db.get(Edition, source.edition_id)
    ten, thirteen = identifiers(item)
    clauses = ([Edition.isbn10 == ten] if ten else []) + ([Edition.isbn13 == thirteen] if thirteen else [])
    if not clauses:
        return None
    editions = db.scalars(select(Edition).where(or_(*clauses))).all()
    if len(editions) != 1:
        return None
    edition = editions[0]
    # Conflicting named authors are evidence against an automatic ISBN match.
    names = db.scalars(select(Author.name).join(WorkAuthor, WorkAuthor.author_id == Author.id)
                       .where(WorkAuthor.work_id == edition.work_id)).all()
    offered = item.get('volumeInfo', {}).get('authors') or []
    if names and offered and not {canonical_author_name(n) for n in names}.intersection(canonical_author_name(n) for n in offered):
        return None
    return edition


def existing_work(db, item):
    # An external work key alone must not bypass conflicting/unknown authors.
    info = item.get('volumeInfo', {})
    names = info.get('authors') or []
    from app.modules.books.service import verified_work_for_import
    return verified_work_for_import(db, bibliographic_title(info), names)


def present(db, item, match_work=True):
    edition = find_existing(db, item)
    work = db.get(Work, edition.work_id) if edition else existing_work(db, item) if match_work else None
    if work is None:
        return item
    from app.modules.books.router import work_payload
    sources = db.scalars(select(CatalogSource).join(Edition, CatalogSource.edition_id == Edition.id).where(Edition.work_id == work.id)).all()
    preferred = next((s.external_id for s in sources if s.provider == 'google-books'), None)
    return work_payload(db, work.id, preferred_source=preferred) or item


def ensure_edition(db, reference):
    edition_id = open_library.key(reference.removeprefix('openlibrary:'), 'M')
    if not edition_id:
        raise HTTPException(404, 'Edición no encontrada')
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext('catalog:open-library:' + edition_id))))
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == 'open-library', CatalogSource.external_id == edition_id))
    if source:
        return db.get(Edition, source.edition_id)
    cached = db.scalar(select(CatalogQuery).where(CatalogQuery.payload['items'].contains([{'id': 'openlibrary:' + edition_id}]))
                       .order_by(CatalogQuery.fetched_at.desc()).limit(1))
    cached_item = next((v for v in cached.payload.get('items', []) if v.get('id') == 'openlibrary:' + edition_id), None) if cached else None
    try:
        item = open_library.detail(edition_id, cached_item)
    except HTTPException as error:
        if error.status_code != 502 or cached_item is None:
            raise
        item = cached_item
    return store_selected(db, item)


def store_selected(db, item):
    info = item['volumeInfo']
    edition_id = item['openLibrary']['editionKey']
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext('catalog:open-library:' + edition_id))))
    existing = find_existing(db, item)
    names = info.get('authors') or []
    identity = canonical_work_key(bibliographic_title(info), names) if names else None
    ten, thirteen = identifiers(item)
    # Serialize cross-provider imports using the same edition identifier.
    if ten or thirteen:
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext('catalog:isbn:' + (thirteen or ten)))))
        existing = find_existing(db, item)
    if identity:
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext('catalog:work:' + identity))))
    edition = existing
    if edition is None:
        work = existing_work(db, item)
        if work is None:
            if identity and db.scalar(select(Work.id).where(Work.identity_key == identity)):
                identity = None
            work = Work(title=info['title'], identity_key=identity, original_language=None)
            db.add(work)
            db.flush()
        edition = Edition(work_id=work.id, title=info['title'], language='es')
        db.add(edition)
        db.flush()
    work = db.get(Work, edition.work_id)
    values = {'description': info.get('description'), 'page_count': info.get('pageCount'),
              'publisher_name': info.get('publisher'), 'publication_date': info.get('publishedDate'),
              'cover_url': info.get('imageLinks', {}).get('thumbnail')}
    for field, value in values.items():
        if not getattr(edition, field) and value:
            setattr(edition, field, value)
    if not work.description and info.get('description'):
        work.description = info['description']
    if not work.categories and info.get('categories'):
        work.categories = info['categories']
    for field, value in [('isbn10', ten), ('isbn13', thirteen)]:
        if value and not getattr(edition, field) and not db.scalar(select(Edition.id).where(getattr(Edition, field) == value, Edition.id != edition.id)):
            setattr(edition, field, value)
    existing_names = {canonical_author_name(name) for name in db.scalars(select(Author.name).join(WorkAuthor, WorkAuthor.author_id == Author.id).where(WorkAuthor.work_id == work.id))}
    for position, name in enumerate(names, 1):
        if canonical_author_name(name) in existing_names:
            continue
        author = db.scalar(select(Author).where(func.lower(Author.name) == name.casefold()))
        if author is None:
            author = Author(name=name)
            db.add(author)
            db.flush()
        if db.get(WorkAuthor, (work.id, author.id)) is None:
            db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=position))
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == 'open-library', CatalogSource.external_id == edition_id))
    if source is None:
        now = datetime.now(timezone.utc)
        db.add(CatalogSource(edition_id=edition.id, provider='open-library', external_id=edition_id,
                             payload=item, fetched_at=now, synced_at=now, detail_complete=True))
    if not db.scalar(select(CatalogSource.id).where(CatalogSource.edition_id == edition.id, CatalogSource.provider == 'libria-feed')):
        db.add(CatalogSource(edition_id=edition.id, provider='libria-feed', external_id='openlibrary:' + edition_id,
                             fetched_at=datetime.now(timezone.utc)))
    db.flush()
    return edition
