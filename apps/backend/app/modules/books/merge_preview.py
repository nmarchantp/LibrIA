"""Administrative read-only comparison. Never calls consolidation or AI services."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select, text

from app.modules.books.canonical import identity_snapshot
from app.modules.books.models import Work, Edition, Author, WorkAuthor, AlternateTitle, CatalogSource
from app.modules.books.catalog_models import WorkReference
from app.modules.library.models import LibraryEntry, Reading
from app.modules.social.models import Review
from app.modules.users.identity_models import AccountPermission, Profile
from app.modules.books.evidence import normalize_isbns, BibliographicDataError

VERSION = 2
TTL = timedelta(minutes=15)


def require_admin(db, actor):
    if db.get(AccountPermission, (actor, 'admin'), populate_existing=True) is None:
        raise HTTPException(403, 'Se requiere permiso administrativo efectivo')


def require_snapshot(db):
    if db.scalar(text('SHOW transaction_isolation')) != 'repeatable read':
        raise HTTPException(409,'La simulación requiere una transacción REPEATABLE READ propia')


def fingerprint(db):
    """Conservative global snapshot: unrelated activity can invalidate a preview.

    Hash rows inside PostgreSQL; never disclose private bodies or notebooks.
    All application domain tables and analytical/AI states are covered, excluding
    only this append-only preview log and ephemeral discovery cache.
    """
    tables = db.execute(text("""SELECT table_schema,table_name FROM information_schema.tables
      WHERE table_schema IN ('app','analytics','ia','ai') AND table_type='BASE TABLE'
      AND table_name NOT IN ('simulaciones_fusion','consultas_catalogo')
      ORDER BY table_schema,table_name""")).all()
    hashes = []
    for schema, table in tables:
        # Names originate in the server catalog, quote identifiers defensively.
        name = '.'.join('"'+part.replace('"','""')+'"' for part in (schema, table))
        value = db.scalar(text(f"SELECT encode(sha256(convert_to(coalesce(string_agg(h,',' ORDER BY h),''),'UTF8')),'hex') FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') h FROM {name} t) s"))
        hashes.append((schema, table, value))
    return hashlib.sha256(json.dumps(hashes).encode()).hexdigest()


def row_data(row, fields):
    return {key: str(value) if isinstance(value := getattr(row, key), uuid.UUID) else value.isoformat() if isinstance(value,datetime) else value for key in fields}


def analytical_impact(db, members, readers):
    """Exact stored row counts; no regeneration/enqueueing and no private payloads."""
    columns = db.execute(text("""SELECT table_schema,table_name,column_name FROM information_schema.columns
      WHERE table_schema IN ('analytics','ia','ai') ORDER BY 1,2,3""")).all()
    tables = {}
    for schema,table,column in columns:
        tables.setdefault((schema,table),set()).add(column)
    result = {}
    for (schema,table),names in tables.items():
        clauses=[]
        if 'work_id' in names:
            clauses.append('work_id=ANY(CAST(:works AS uuid[]))')
        for owner in ('owner_id','owner_user_id','user_id'):
            if owner in names:
                clauses.append(f'{owner}=ANY(CAST(:readers AS uuid[]))')
        if not clauses:
            continue
        quoted='.'.join('"'+p.replace('"','""')+'"' for p in (schema,table))
        count=db.scalar(text(f'SELECT count(*) FROM {quoted} WHERE '+ ' OR '.join(clauses)),dict(works=list(members),readers=list(readers)))
        result[schema+'.'+table]=count
    return result


def compare_works(db, actor, source, target):
    require_admin(db, actor)
    require_snapshot(db)
    snapshot = identity_snapshot(db,[source,target])
    source_root, target_root = snapshot.root(source), snapshot.root(target)
    if source_root == target_root:
        raise HTTPException(409, 'Las obras ya comparten identidad canónica')
    groups = [[key for key in snapshot.mapping if snapshot.root(key) == root] for root in (source_root, target_root)]
    sides = []
    for requested, root, members in zip((source,target),(source_root,target_root),groups):
        works = db.scalars(select(Work).where(Work.id.in_(members)).order_by(Work.id)).all()
        editions = db.scalars(select(Edition).where(Edition.work_id.in_(members)).order_by(Edition.id)).all()
        authors = db.execute(select(WorkAuthor.work_id, Author.id, Author.name).join(Author, Author.id==WorkAuthor.author_id).where(WorkAuthor.work_id.in_(members)).order_by(WorkAuthor.work_id,WorkAuthor.position)).all()
        refs = db.scalars(select(WorkReference).where(WorkReference.work_id.in_(members)).order_by(WorkReference.id)).all()
        sides.append(dict(requested_id=str(requested),canonical_id=str(root),member_ids=list(map(str,members)),
            works=[row_data(w,('id','title','original_language','first_publication_date','series_title','volume_number')) for w in works],
            alternate_titles=[row_data(t,('work_id','title','language')) for t in db.scalars(select(AlternateTitle).where(AlternateTitle.work_id.in_(members)))],
            authors=[dict(work_id=str(w),id=str(a),name=n) for w,a,n in authors],
            editions=[row_data(e,('id','work_id','title','language','isbn10','isbn13','publisher_name','publication_date','publication_year','format')) for e in editions],
            references=[dict(**row_data(r,('id','work_id','provider','reference_type','external_id','verification_status','verified_by','verified_at')),
                             operation_id=str(r.operation_id),
                             provenance={key:r.evidence[key] for key in ('provider','reference','work_reference','fetched_at','transport','snapshot_sha256') if key in r.evidence},
                             evidence_sha256=hashlib.sha256(json.dumps(r.evidence,sort_keys=True).encode()).hexdigest()) for r in refs],
            sources=[row_data(s,('edition_id','provider','external_id','validation_status')) for s in db.scalars(select(CatalogSource).where(CatalogSource.edition_id.in_([e.id for e in editions]))) ]))
    members = groups[0]+groups[1]
    entries = db.scalars(select(LibraryEntry).where(LibraryEntry.work_id.in_(members))).all()
    readings = db.scalars(select(Reading).where(Reading.work_id.in_(members))).all()
    reviews = db.scalars(select(Review).where(Review.work_id.in_(members))).all()
    owners = [{e.user_id for e in entries if e.work_id in group} for group in groups]
    profiles = Counter(r.author_profile_id for r in reviews)
    conflicts = [{'code':'review_profile_collision','review_ids':sorted(str(r.id) for r in reviews if r.author_profile_id==profile),
                  'proposed_review_id':str(max((r for r in reviews if r.author_profile_id==profile),key=lambda r:(r.updated_at,str(r.id))).id),
                  'proposal_rule':'latest_updated_at_then_uuid_including_private_states',
                  'decision':'Select one current review explicitly; preserve every revision and privacy state'}
                 for profile,count in profiles.items() if count>1]
    authors = [{a['name'].casefold() for a in side['authors']} for side in sides]
    candidates = ['matching_title_not_identity'] if {w['title'].casefold() for w in sides[0]['works']} & {w['title'].casefold() for w in sides[1]['works']} else []
    contradictions = ['different_author_sets_require_review'] if authors[0] and authors[1] and authors[0]!=authors[1] else []
    isbn_sets=[]
    for side in sides:
        publications=set()
        for edition in side['editions']:
            try:
                _,normalized=normalize_isbns([edition[k] for k in ('isbn10','isbn13') if edition[k]])
                edition['isbn_status']='valid_publication' if normalized else 'absent'
                if normalized:
                    publications.add(normalized)
            except BibliographicDataError:
                edition['isbn_status']='invalid_or_contradictory_requires_review'
                contradictions.append('invalid_or_contradictory_edition_isbn')
        isbn_sets.append(publications)
    if isbn_sets[0]&isbn_sets[1]:
        candidates.append('shared_publication_isbn_requires_review_not_universal_work_identity')
    if isbn_sets[0] and isbn_sets[1] and not isbn_sets[0]&isbn_sets[1]:
        contradictions.append('different_publications_not_proof_of_different_works')
    readers = set.union(*owners) | set(db.scalars(select(Profile.owner_user_id).where(Profile.id.in_(profiles),Profile.owner_user_id.is_not(None))))
    entry_owners={entry.id:entry.user_id for entry in entries}
    attempts=Counter((entry_owners[r.library_entry_id],snapshot.root(r.work_id)) for r in readings)
    return dict(version=VERSION,source=sides[0],target=sides[1],identity_version=snapshot.version,
        evidence=dict(confirmed_relationships={k:v for k,v in snapshot.provenance().items() if uuid.UUID(k) in members},candidates=candidates,contradictions=contradictions,
                      automatic_merge_allowed=False),conflicts=conflicts,
        impact=dict(library_entries=len(entries),shared_libraries=len(owners[0]&owners[1]),unique_readers=len(readers),
            active_library_entries=sum(e.archived_at is None for e in entries),archived_library_entries=sum(e.archived_at is not None for e in entries),
            reading_attempts=len(readings),rereads=sum(max(0,n-1) for n in attempts.values()),
            editions=sum(len(s['editions']) for s in sides),reviews=len(reviews),ratings=sum(r.rating is not None for r in reviews),
            review_states=dict(Counter(r.status for r in reviews)),reviews_without_body=[dict(id=str(r.id),status=r.status,rating=str(r.rating) if r.rating is not None else None) for r in reviews],
            stored_analytical_rows=analytical_impact(db,members,readers),
            invalidation=dict(reader_statistics=len(readers),reader_profiles=len(readers),recommendations=len(readers),
                catalog_projections=list(map(str,(source_root,target_root))),etl='Rebuild coherent canonical snapshot; preserve historical runs',
                global_identity_version='All versioned caches become stale; do not call Gemini')),
        decisions=['Confirm bibliographic evidence independently','Resolve shared memberships preserving attempts',
                   'Resolve each review collision explicitly without making private content public',
                   'Define reversible append-only execution and handling of subsequent activity'],
        expected_effects=dict(canonical_work_count_delta=-1,physical_work_count_delta=0,
            retained_reading_attempts=len(readings),retained_review_histories=len(reviews),
            projected_rereads=sum(max(0,n-1) for n in Counter(entry_owners[r.library_entry_id] for r in readings).values()),
            effective_library_memberships=len(set.union(*owners)),
            current_review_slots=len(profiles),rating_result='Requires explicit collision decisions' if conflicts else 'No profile collisions',
            historical_uuid_policy='Preserve all UUIDs and store confirmed redirects only in a future authorized phase'),
        execution_available=False)


def preview_merge(db, actor, source, target):
    result = compare_works(db,actor,source,target)
    from app.modules.books.merge_scope import scope_fingerprint
    digest = scope_fingerprint(db,[source,target])
    preview_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result.update(preview_id=str(preview_id),fingerprint=digest,created_at=now.isoformat(),expires_at=(now+TTL).isoformat())
    db.execute(text("""INSERT INTO app.simulaciones_fusion
        (id,actor_user_id,version,source_work_id,target_work_id,fingerprint,result,created_at,expires_at)
        VALUES (:id,:actor,2,:source,:target,:fingerprint,CAST(:result AS jsonb),:now,:expiry)"""),
        dict(id=preview_id,actor=actor,source=source,target=target,fingerprint=digest,result=json.dumps(result),now=now,expiry=now+TTL))
    return result  # transaction belongs to caller


def validate_preview(db, actor, preview_id, now=None):
    require_admin(db,actor)
    require_snapshot(db)
    row = db.execute(text('SELECT * FROM app.simulaciones_fusion WHERE id=:id'),dict(id=preview_id)).mappings().first()
    if not row:
        raise HTTPException(404,'Simulación no encontrada')
    if row['version'] != VERSION or row['expires_at'] <= (now or datetime.now(timezone.utc)):
        raise HTTPException(409,'Simulación caducada')
    from app.modules.books.merge_scope import scope_fingerprint
    if row['fingerprint'] != scope_fingerprint(db,[row['source_work_id'],row['target_work_id']]):
        raise HTTPException(409,'Los datos cambiaron; genere otra simulación')
    return dict(valid=True,preview_id=str(preview_id),execution_available=False)
