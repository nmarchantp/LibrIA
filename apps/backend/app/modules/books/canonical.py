"""Shared, read-only canonical identity. No title/author inference or graph writes.

The same projection powers both one-UUID and bulk resolution. Public consumers
are intentionally not switched to this service until their rollout phase.
"""
from dataclasses import dataclass
import hashlib
import json
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


class CanonicalIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalIdentity:
    requested_work_id: uuid.UUID
    canonical_work_id: uuid.UUID
    path: tuple[uuid.UUID, ...]
    operation_ids: tuple[uuid.UUID, ...]


def canonical_projection():
    """One SQL definition, including cycle/depth diagnostics; caller must validate."""
    return text("""
      WITH RECURSIVE active AS (
        SELECT r.source_work_id,r.target_work_id,r.operation_id
        FROM app.redirecciones_obras r JOIN app.operaciones_catalogo o
          ON o.id=r.operation_id AND o.operation_type='merge'
          AND o.source_work_id=r.source_work_id AND o.target_work_id=r.target_work_id
        WHERE r.retired_at IS NULL AND r.active_from<=statement_timestamp()
      ), paths(original_id,current_id,path,operations,cycle) AS (
        SELECT w.id,w.id,ARRAY[w.id],ARRAY[]::uuid[],false FROM app.obras w
        WHERE CAST(:requested_id AS uuid) IS NULL OR w.id=CAST(:requested_id AS uuid)
        UNION ALL
        SELECT p.original_id,a.target_work_id,p.path||a.target_work_id,
               p.operations||a.operation_id,a.target_work_id=ANY(p.path)
        FROM paths p JOIN active a ON a.source_work_id=p.current_id
        WHERE NOT p.cycle AND cardinality(p.path)<256
      )
      SELECT original_id,current_id,path,operations,cycle,
             EXISTS(SELECT 1 FROM active a WHERE a.source_work_id=p.current_id) AS has_next
      FROM paths p WHERE p.cycle OR cardinality(p.path)>=256
        OR NOT EXISTS(SELECT 1 FROM active a WHERE a.source_work_id=p.current_id)
      ORDER BY original_id
    """)


def canonical_mapping(db: Session, requested_id: uuid.UUID | None = None):
    rows = db.execute(canonical_projection(), {"requested_id": requested_id}).mappings().all()
    result = {}
    for row in rows:
        if row["cycle"] or row["has_next"]:
            raise CanonicalIdentityError("Invalid canonical graph: cycle or depth limit")
        if row["original_id"] in result:
            raise CanonicalIdentityError("Contradictory canonical paths")
        result[row["original_id"]] = CanonicalIdentity(row["original_id"], row["current_id"],
                                                       tuple(row["path"]), tuple(row["operations"]))
    return result


def enabled():
    from app.core.config import get_settings
    return get_settings().catalog_canonical_enabled


@dataclass(frozen=True)
class IdentitySnapshot:
    mapping: dict
    version: str

    def root(self, work_id):
        key = uuid.UUID(str(work_id))
        if key not in self.mapping:
            raise CanonicalIdentityError("Unknown historical work UUID")
        return self.mapping[key].canonical_work_id

    def provenance(self):
        return {str(key): {"root": str(value.canonical_work_id), "path": [str(k) for k in value.path],
                "operations": [str(k) for k in value.operation_ids]} for key, value in self.mapping.items() if value.operation_ids}


def identity_snapshot(db, work_ids=None):
    mapping = canonical_mapping(db) if work_ids is None else scoped_mapping(db,work_ids)
    # Only confirmed active paths define graph version. Adding an unrelated work
    # must not invalidate every reader's profile.
    graph = sorted((str(key), [str(v) for v in value.path], [str(v) for v in value.operation_ids])
                   for key, value in mapping.items() if value.operation_ids)
    retired = db.execute(text('SELECT operation_id,retirement_operation_id FROM app.redirecciones_obras WHERE retired_at IS NOT NULL ORDER BY operation_id')).all()
    version = "confirmed-v1:" + hashlib.sha256(json.dumps([graph,[list(map(str,r)) for r in retired]], separators=(",", ":")).encode()).hexdigest()
    return IdentitySnapshot(mapping, version)


def scoped_mapping(db, work_ids):
    members=db.scalars(text("""WITH RECURSIVE edges AS (
      SELECT source_work_id a,target_work_id b FROM app.redirecciones_obras
      WHERE retired_at IS NULL AND active_from<=statement_timestamp()
      UNION SELECT target_work_id,source_work_id FROM app.redirecciones_obras
      WHERE retired_at IS NULL AND active_from<=statement_timestamp()
    ), members(id) AS (SELECT unnest(CAST(:ids AS uuid[])) UNION SELECT e.b FROM edges e JOIN members m ON e.a=m.id)
    SELECT id FROM members"""),dict(ids=list(work_ids))).all()
    query=str(canonical_projection()).replace('CAST(:requested_id AS uuid) IS NULL OR w.id=CAST(:requested_id AS uuid)',
                                             'w.id=ANY(CAST(:requested_ids AS uuid[]))')
    result={}
    for row in db.execute(text(query),dict(requested_ids=members)).mappings():
        if row['cycle'] or row['has_next'] or row['original_id'] in result:
            raise CanonicalIdentityError('Invalid canonical graph: cycle or contradictory path')
        result[row['original_id']]=CanonicalIdentity(row['original_id'],row['current_id'],tuple(row['path']),tuple(row['operations']))
    return result


def identity_version(db):
    return identity_snapshot(db).version


def reference_work(db, reference):
    """Resolve a stored UUID/publication reference, checking all exact evidence.

    Never fetch a provider, persist metadata, or use title/author similarity.
    """
    from sqlalchemy import select
    from app.modules.books.models import Work, Edition, CatalogSource
    from app.modules.books.catalog_models import WorkReference
    try:
        key = uuid.UUID(str(reference))
    except ValueError:
        key = None
    if key:
        work = db.get(Work,key)
        edition = db.get(Edition,key)
        return resolve_canonical_work(db,work.id if work else edition.work_id).canonical_work_id if work or edition else None
    provider = 'open-library' if str(reference).startswith('openlibrary:') else 'google-books'
    external = str(reference).removeprefix('openlibrary:').removeprefix('googlebooks:')
    if provider == 'open-library':
        external = external.rsplit('/',1)[-1]
    bindings = db.scalars(select(WorkReference).where(WorkReference.provider==provider,
        WorkReference.external_id==external)).all()
    if any(b.verification_status in {'contradictory','rejected'} for b in bindings) and not any(b.verification_status=='confirmed' for b in bindings):
        raise CanonicalIdentityError('Contradictory external work reference')
    candidates = [b.work_id for b in bindings if b.verification_status in {'provisional','confirmed'} and
        (b.reference_type!='work' or b.verification_status=='confirmed')]
    feed_ref = ('openlibrary:' if provider=='open-library' else '') + external
    sources = db.scalars(select(CatalogSource).where(((CatalogSource.provider==provider)&(CatalogSource.external_id==external)) |
        ((CatalogSource.provider=='libria-feed') & (CatalogSource.external_id==feed_ref)))).all()
    if any(source.validation_status!='validated' for source in sources):
        raise CanonicalIdentityError('Unvalidated historical publication reference')
    candidates.extend(db.get(Edition,source.edition_id).work_id for source in sources)
    roots = {resolve_canonical_work(db,key).canonical_work_id for key in candidates}
    if len(roots)>1:
        raise CanonicalIdentityError('Contradictory publication and work bindings')
    return next(iter(roots),None)


def resolve_canonical_work(db: Session, work_id: uuid.UUID) -> CanonicalIdentity:
    key = uuid.UUID(str(work_id))
    identity = canonical_mapping(db, key).get(key)
    if identity is None:
        raise CanonicalIdentityError("Unknown historical work UUID")
    return identity


def canonical_members(db: Session, work_id: uuid.UUID) -> frozenset[uuid.UUID]:
    mapping = canonical_mapping(db)
    key = uuid.UUID(str(work_id))
    if key not in mapping:
        raise CanonicalIdentityError("Unknown historical work UUID")
    root = mapping[key].canonical_work_id
    return frozenset(key for key, value in mapping.items() if value.canonical_work_id == root)


def lock_catalog_writes(db: Session):
    """Same graph lock as phase 1. Coarse serialization is deliberate for safety."""
    if db.get_bind().dialect.name != "postgresql":
        raise CanonicalIdentityError("Catalog writes require PostgreSQL")
    if db.scalar(text("SHOW transaction_isolation")) != "read committed":
        raise CanonicalIdentityError("Catalog writes require READ COMMITTED")
    db.execute(text("SELECT pg_advisory_xact_lock(73155,1)"))


def lock_publication(db: Session, provider: str, external_id: str, isbn13: str | None):
    """Coordinate with existing single-publication import locks, without changing them."""
    prefix = "catalog:libria-feed:" if provider == "google-books" else "catalog:open-library:"
    keys = [prefix + external_id]
    if isbn13:
        keys.append("catalog:isbn:" + isbn13)
    for key in keys:
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})
