"""Professional, ISBN-backed manual catalog creation with atomic audit and replay."""
import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import Field, field_validator
from sqlalchemy import select, or_, func, text
from app.modules.books.maintenance_schemas import EditionInput, WorkInput
from app.modules.books.evidence import normalize_isbns, BibliographicDataError
from app.modules.books.models import Work, Edition, Author, WorkAuthor, CatalogSource
from app.modules.books.catalog_models import CatalogOperation, CatalogOperationEffect
from app.modules.books.canonical import lock_catalog_writes
from app.modules.books.maintenance import editorial_source, row_image
from app.modules.users.account_service import lock_user, require_active


class ManualBookInput(EditionInput):
    isbn: str = Field(min_length=10, max_length=30)
    authors: list[str] = Field(min_length=1, max_length=30)

    @field_validator('authors')
    @classmethod
    def clean_authors(cls, values):
        cleaned = WorkInput.clean_list(values)
        return list({name.casefold(): name for name in cleaned}.values())

    @field_validator('isbn')
    @classmethod
    def valid_isbn(cls, value):
        try:
            normalize_isbns([value])
        except BibliographicDataError:
            raise ValueError('ISBN inválido: revisa los dígitos del ISBN-10 o ISBN-13') from None
        return value


def create_manual_book(db, actor_id, key, data, cover=None):
    actor = lock_user(db, actor_id)
    require_active(actor)
    if actor.role not in {'autor', 'editorial', 'admin'}:
        raise HTTPException(403, 'Solo autores, editoriales y administradores pueden registrar libros')
    lock_catalog_writes(db)
    digest = hashlib.sha256(json.dumps({'manual_book': data.model_dump(mode='json'),
        'cover': hashlib.sha256(cover[1]).hexdigest() if cover else None}, sort_keys=True).encode()).hexdigest()
    previous = db.scalar(select(CatalogOperation).where(CatalogOperation.actor_user_id == actor_id,
        CatalogOperation.operation_type == 'admin_import', CatalogOperation.request_key == key))
    if previous:
        if previous.request_hash != digest:
            raise HTTPException(409, 'La clave de solicitud ya fue utilizada con otros datos')
        return previous.context['result']
    ten, thirteen = normalize_isbns([data.isbn])
    if db.scalar(select(Edition.id).where(or_(Edition.isbn13 == thirteen, Edition.isbn10 == ten if ten else False))):
        raise HTTPException(409, 'Este ISBN ya está en LibrIA. Busca el libro por ISBN para usar su ficha.')
    from app.modules.books.catalog_identity import matching_work
    try:
        work = matching_work(db, data.title, data.authors, reject_ambiguous=True)
    except BibliographicDataError as error:
        raise HTTPException(409, str(error)) from None
    effects = []
    if work is None:
        work = Work(title=data.title, description=data.description, original_language=data.language, created_by_user_id=actor_id)
        db.add(work); db.flush()
        effects.append(('app.obras', work.id, row_image(work)))
        for position, name in enumerate(data.authors, 1):
            author = db.scalar(select(Author).where(func.lower(Author.name) == name.casefold()).order_by(Author.id).limit(1))
            if author is None:
                author = Author(name=name); db.add(author); db.flush()
                effects.append(('app.autores', author.id, row_image(author)))
            membership = WorkAuthor(work_id=work.id, author_id=author.id, position=position)
            db.add(membership); db.flush()
            effects.append(('app.obras_autores', work.id, row_image(membership)))
    edition = Edition(work_id=work.id, created_by_user_id=actor_id, isbn10=ten, isbn13=thirteen,
        **data.model_dump(exclude={'isbn', 'authors', 'reason', 'expected_version'}))
    edition.publication_year = int(data.publication_date[:4]) if data.publication_date else None
    db.add(edition); db.flush()
    if cover:
        from app.modules.books.models import EditionCover
        from app.core.config import get_settings
        db.add(EditionCover(edition_id=edition.id, content_type=cover[0], data=cover[1]))
        edition.cover_url = f'{get_settings().api_prefix}/books/editions/{edition.id}/cover'
        effects.append(('app.portadas_ediciones', edition.id, {'edition_id': str(edition.id), 'content_type': cover[0], 'sha256': hashlib.sha256(cover[1]).hexdigest()}))
    effects.append(('app.ediciones', edition.id, row_image(edition)))
    source = editorial_source(db, edition, data.authors)
    db.flush()
    effects.append(('app.fuentes_catalogo', source.id, row_image(source)))
    alias = CatalogSource(edition_id=edition.id, provider='libria-feed', external_id='manual:' + str(edition.id),
        fetched_at=datetime.now(timezone.utc), payload=source.payload, detail_complete=True)
    db.add(alias); db.flush()
    effects.append(('app.fuentes_catalogo', alias.id, row_image(alias)))
    result = {'work_id': str(work.id), 'edition_id': str(edition.id), 'isbn': thirteen, 'title': work.title}
    operation = CatalogOperation(actor_user_id=actor_id, operation_type='admin_import', request_key=key,
        request_hash=digest, target_work_id=work.id, reason=data.reason, evidence={'manual_registration': True, 'isbn_checksum_valid': True},
        context={'action': 'manual_book_create', 'result': result})
    db.add(operation); db.flush()
    for ordinal, (table, identifier, image) in enumerate(effects, 1):
        db.add(CatalogOperationEffect(operation_id=operation.id, ordinal=ordinal, entity_table=table,
            entity_id=identifier, before_state=None, after_state=image))
    db.execute(text('INSERT INTO analytics.dirty_catalog(work_id) VALUES (:id) ON CONFLICT DO NOTHING'), {'id': work.id})
    return result
