"""Canonical catalog inventory and audited, optimistic administrator edits."""
from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, inspect, or_, select, text

from app.core.config import get_settings
from app.modules.books.canonical import identity_snapshot, lock_catalog_writes
from app.modules.books.catalog_models import CatalogOperation, CatalogOperationEffect
from app.modules.books.evidence import BibliographicDataError, normalize_isbns
from app.modules.books.identity import canonical_author_name, canonical_book_title, canonical_title_variants, work_form
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor


def require_maintenance(db, actor):
    from app.modules.books.merge_preview import require_admin
    require_admin(db, actor)
    settings = get_settings()
    if not settings.catalog_discovery_enabled or not settings.catalog_admin_preview_enabled:
        raise HTTPException(404, "Mantenedor de libros deshabilitado")


def row_image(entity):
    def serialize(value):
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        return str(value)
    return json.loads(json.dumps({column.key: getattr(entity, column.key) for column in inspect(type(entity)).columns}, default=serialize))


def inventory_data(db):
    snapshot = identity_snapshot(db)
    works = {work.id: work for work in db.scalars(select(Work))}
    authors = {}
    for work_id, name in db.execute(select(WorkAuthor.work_id, Author.name).join(Author, Author.id == WorkAuthor.author_id).order_by(WorkAuthor.position)):
        authors.setdefault(work_id, []).append(name)
    editions = {}
    for edition in db.scalars(select(Edition).order_by(Edition.created_at, Edition.id)):
        editions.setdefault(snapshot.root(edition.work_id), []).append(edition)
    summaries = {}
    keys = {}
    for root in {snapshot.root(key) for key in works}:
        work = works[root]
        rows = editions.get(root, [])
        names = authors.get(root, [])
        names_key = tuple(sorted({canonical_author_name(name) for name in names}))
        item = dict(id=str(root), title=work.title, authors=names, edition_count=len(rows),
                    cover_url=next((row.cover_url for row in rows if row.cover_url), None),
                    isbn_count=sum(bool(row.isbn13 or row.isbn10) for row in rows),
                    updated_at=work.updated_at.isoformat(), duplicate_count=0)
        summaries[root] = item
        if names_key and all(names_key):
            for title in [work.title, *(row.title for row in rows)]:
                for variant in canonical_title_variants(title):
                    keys.setdefault((variant, names_key, tuple(sorted(work_form(title)))), set()).add(root)
    duplicates = {root: set() for root in summaries}
    for group in keys.values():
        for root in group:
            duplicates[root].update(group - {root})
    for root, group in duplicates.items():
        summaries[root]["duplicate_count"] = len(group)
    return snapshot, works, authors, editions, summaries, duplicates


def inventory(db, query="", offset=0, limit=20, filter_by="all"):
    _, works, _, editions, summaries, _ = inventory_data(db)
    needle = canonical_book_title(query)
    isbn_query = query.replace("-", "").replace(" ", "")
    result = []
    for root, item in summaries.items():
        rows = editions.get(root, [])
        fields = [item["title"], *item["authors"], *(row.title for row in rows)]
        if needle and not any(needle in canonical_book_title(value) for value in fields) and not any(
                isbn_query in value for row in rows for value in [row.isbn10, row.isbn13] if value):
            continue
        if filter_by == "duplicates" and not item["duplicate_count"]:
            continue
        if filter_by == "no_isbn" and rows and all(row.isbn13 or row.isbn10 for row in rows):
            continue
        if filter_by == "no_cover" and item["cover_url"]:
            continue
        result.append(item)
    result.sort(key=lambda item: (canonical_book_title(item["title"]), item["id"]))
    return {"items": result[offset:offset + limit], "total": len(result), "offset": offset, "limit": limit,
            "stats": {"works": len(summaries), "editions": sum(map(len, editions.values())),
                      "possible_duplicates": sum(bool(item["duplicate_count"]) for item in summaries.values())}}


def work_detail(db, work_id):
    snapshot, works, authors, editions, summaries, duplicates = inventory_data(db)
    if work_id not in works:
        raise HTTPException(404, "Libro no encontrado")
    root = snapshot.root(work_id)
    work = works[root]
    members = [key for key in snapshot.mapping if snapshot.root(key) == root]
    rows = editions.get(root, [])
    sources = db.scalars(select(CatalogSource).where(CatalogSource.edition_id.in_([row.id for row in rows])).order_by(CatalogSource.provider, CatalogSource.id)).all()
    images = [row_image(works[key]) for key in sorted(members)]
    version = hashlib.sha256(json.dumps([images, authors.get(root, []), [row_image(row) for row in rows],
        [row_image(source) for source in sources if source.provider == "libria-editorial"]], sort_keys=True).encode()).hexdigest()
    changes = db.scalars(select(CatalogOperation).where(CatalogOperation.target_work_id.in_(members),
        CatalogOperation.operation_type == "admin_import").order_by(CatalogOperation.identity_version.desc()).limit(12)).all()
    return {**summaries[root], "version": version, "description": work.description or "", "categories": work.categories or [],
            "series_title": work.series_title or "", "volume_number": work.volume_number or "",
            "editions": [{**row_image(row), "sources": [{"provider": source.provider, "external_id": source.external_id}
                for source in sources if source.edition_id == row.id]} for row in rows],
            "possible_duplicates": [summaries[key] for key in sorted(duplicates[root])],
            "members": [{"id": str(key), "title": works[key].title} for key in sorted(members)],
            "changes": [{"action": operation.context.get("action", "import"), "reason": operation.reason,
                         "created_at": operation.created_at.isoformat()} for operation in changes]}


def editorial_source(db, edition, authors):
    source = db.scalar(select(CatalogSource).where(CatalogSource.edition_id == edition.id, CatalogSource.provider == "libria-editorial"))
    if source is None:
        source = CatalogSource(edition_id=edition.id, provider="libria-editorial", external_id=str(edition.id))
        db.add(source)
    source.fetched_at = datetime.now(timezone.utc)
    source.payload = {"volumeInfo": {"title": edition.title, "authors": authors, "language": edition.language,
        "description": edition.description, "pageCount": edition.page_count, "publisher": edition.publisher_name,
        "publishedDate": edition.publication_date, "printType": edition.format,
        "imageLinks": {"thumbnail": edition.cover_url} if edition.cover_url else {},
        "industryIdentifiers": [*([{"type": "ISBN_13", "identifier": edition.isbn13}] if edition.isbn13 else []),
                                *([{"type": "ISBN_10", "identifier": edition.isbn10}] if edition.isbn10 else [])]}}
    return source


def edit_catalog(db, actor, key, action, data, work_id=None, edition_id=None):
    require_maintenance(db, actor)
    lock_catalog_writes(db)
    payload = {"action": action, "work_id": str(work_id), "edition_id": str(edition_id), "data": data.model_dump(mode="json")}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    previous = db.scalar(select(CatalogOperation).where(CatalogOperation.actor_user_id == actor,
        CatalogOperation.operation_type == "admin_import", CatalogOperation.request_key == key))
    if previous:
        if previous.request_hash != digest:
            raise HTTPException(409, "La solicitud ya se utilizó para otro cambio")
        return previous.context["result"]
    detail = work_detail(db, work_id) if work_id else None
    if detail and data.expected_version != detail["version"]:
        raise HTTPException(409, "El libro cambió mientras lo editabas. Vuelve a abrirlo antes de guardar.")
    before = {}
    if detail:
        work_id = uuid.UUID(detail["id"])
        work = db.get(Work, work_id)
        before["work"] = row_image(work)
        before["authors"] = {"names": detail["authors"]}
    else:
        from app.modules.books.catalog_identity import matching_work
        try:
            existing = matching_work(db, data.title, data.authors, reject_ambiguous=True)
        except BibliographicDataError as error:
            raise HTTPException(409, str(error)) from None
        if existing:
            raise HTTPException(409, "Ya existe una obra con este título y autores. Búscala para editar su ficha o añadir otra edición.")
        work = Work(title=data.title, created_by_user_id=actor)
        db.add(work)
        db.flush()
        work_id = work.id
    changes = []
    if action in {"work_create", "work_update"}:
        for field in ("title", "description", "categories", "series_title", "volume_number"):
            setattr(work, field, getattr(data, field))
        # Identity keys are derived hints; they must not keep identifying the old title/author.
        work.identity_key = None
        db.execute(delete(WorkAuthor).where(WorkAuthor.work_id == work.id))
        normalized = set()
        for name in data.authors:
            token = canonical_author_name(name)
            if not token or token in normalized:
                continue
            normalized.add(token)
            author = db.scalar(select(Author).where(func.lower(Author.name) == name.casefold()).order_by(Author.id).limit(1))
            if author is None:
                author = Author(name=name)
                db.add(author)
                db.flush()
            db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=len(normalized)))
        db.flush()
        changes.append(("app.obras", work.id, before.get("work"), row_image(work)))
        changes.append(("app.obras_autores", work.id, before.get("authors"), {"names": data.authors}))
    else:
        rows = detail["editions"]
        if edition_id:
            if not any(row["id"] == str(edition_id) for row in rows):
                raise HTTPException(404, "La edición no pertenece a este libro")
            edition = db.get(Edition, edition_id)
            old = row_image(edition)
        else:
            edition = Edition(work_id=work.id, title=data.title, language=data.language, created_by_user_id=actor)
            db.add(edition)
            old = None
        try:
            ten, thirteen = normalize_isbns([data.isbn] if data.isbn else [])
        except BibliographicDataError:
            raise HTTPException(422, "El ISBN no es válido. Revisa los dígitos y utiliza un ISBN-10 o ISBN-13.") from None
        clauses = ([Edition.isbn10 == ten] if ten else []) + ([Edition.isbn13 == thirteen] if thirteen else [])
        if clauses and db.scalar(select(Edition.id).where(or_(*clauses), Edition.id != edition_id if edition_id else True).limit(1)):
            raise HTTPException(409, "Ese ISBN ya pertenece a otra edición. Busca el libro y revisa si corresponde agruparlo.")
        for field in ("title", "language", "publisher_name", "publication_date", "page_count", "cover_url", "description", "format"):
            setattr(edition, field, getattr(data, field))
        edition.isbn10, edition.isbn13 = ten, thirteen
        edition.publication_year = int(data.publication_date[:4]) if data.publication_date else None
        db.flush()
        changes.append(("app.ediciones", edition.id, old, row_image(edition)))
    db.flush()
    current = work_detail(db, work.id)
    edition_ids = [uuid.UUID(row["id"]) for row in current["editions"]] if action == "work_update" else [edition.id] if action.startswith("edition_") else []
    for row in db.scalars(select(Edition).where(Edition.id.in_(edition_ids))):
        prior = db.scalar(select(CatalogSource).where(CatalogSource.edition_id == row.id, CatalogSource.provider == "libria-editorial"))
        old = row_image(prior) if prior else None
        source = editorial_source(db, row, current["authors"])
        db.flush()
        changes.append(("app.fuentes_catalogo", source.id, old, row_image(source)))
        if not db.scalar(select(CatalogSource.id).where(CatalogSource.edition_id == row.id,
                CatalogSource.provider.in_(["google-books", "open-library", "libria-feed"])).limit(1)):
            alias = CatalogSource(edition_id=row.id, provider="libria-feed", external_id="manual:" + str(row.id),
                                  fetched_at=datetime.now(timezone.utc))
            db.add(alias)
            db.flush()
            changes.append(("app.fuentes_catalogo", alias.id, None, row_image(alias)))
    result = work_detail(db, work.id)
    result["changes"] = [{"action": action, "reason": data.reason, "created_at": datetime.now(timezone.utc).isoformat()}, *result["changes"]][:12]
    operation = CatalogOperation(actor_user_id=actor, operation_type="admin_import", request_key=key, request_hash=digest,
        target_work_id=work.id, reason=data.reason, evidence={"administrator_edit": True}, context={"action": action, "result": result})
    db.add(operation)
    db.flush()
    for ordinal, (table, identifier, old, new) in enumerate(changes, 1):
        db.add(CatalogOperationEffect(operation_id=operation.id, ordinal=ordinal, entity_table=table,
                                     entity_id=identifier, before_state=old, after_state=new))
    db.execute(text("INSERT INTO analytics.dirty_catalog(work_id) VALUES (:id) ON CONFLICT DO NOTHING"), {"id": work.id})
    members = [uuid.UUID(member["id"]) for member in result["members"]]
    db.execute(text("""INSERT INTO analytics.dirty_readers(owner_id)
        SELECT DISTINCT user_id FROM app.entradas_biblioteca WHERE work_id=ANY(:ids) ON CONFLICT DO NOTHING"""), {"ids": members})
    return result
