"""ETL-02/03: rebuild only affected readers; consumers read persisted analytics.

The extraction/normalization boundary is here, never inside model prompts.
All historical projection runs remain available for inference provenance.
"""
import hashlib
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text
from app.modules.analytics.transactional_sources import extract_book_context

VERSION='reader-social-etl-v1'


def serial(value):
    return json.loads(json.dumps(value,default=str))


def extract_social(db,owner):
    params={'owner':owner}
    follows=db.execute(text('''SELECT f.profile_id AS source_id,f.created_at AS at,
      p.id AS profile_id,p.kind AS profile_kind,p.organization_type,p.display_name,
      EXISTS(SELECT 1 FROM app.capacidades_perfil c WHERE c.profile_id=p.id AND c.capability='autor') AS is_author
      FROM app.seguimientos_perfil f JOIN app.perfiles p ON p.id=f.profile_id
      WHERE f.user_id=:owner AND p.verification_status NOT IN ('rejected','suspended')'''),params).mappings().all()
    comments=db.execute(text('''SELECT c.id AS source_id,c.created_at AS at,c.body,
      COALESCE(rv.work_id,r.work_id,po.work_id,link.work_id) AS work_id,c.review_id,c.post_id,
      rv.body AS reviewed_text,rv.rating AS reviewed_rating,po.body AS publication_text,po.publication_type
      FROM app.comentarios_publicacion c
      LEFT JOIN app.resenas rv ON rv.id=c.review_id AND rv.status='published'
      LEFT JOIN app.publicaciones po ON po.id=c.post_id AND NOT po.legacy_content
      LEFT JOIN app.eventos_lectura ev ON ev.id=c.reading_event_id AND ev.is_public
      LEFT JOIN app.lecturas r ON r.id=ev.reading_id
      LEFT JOIN LATERAL (SELECT min(ed.work_id::text)::uuid AS work_id FROM app.fuentes_catalogo s
        JOIN app.ediciones ed ON ed.id=s.edition_id WHERE s.external_id=po.book_ref HAVING count(DISTINCT ed.work_id)=1) link ON true
      WHERE c.user_id=:owner AND (rv.id IS NOT NULL OR po.id IS NOT NULL OR ev.id IS NOT NULL)
      AND NOT EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE
        (d.entity_type='post' AND d.entity_id=po.id) OR (d.entity_type='review' AND d.entity_id=rv.id)
        OR (d.entity_type='event' AND d.entity_id=ev.id))'''),params).mappings().all()
    reactions=db.execute(text('''SELECT l.review_id AS source_id,l.created_at AS at,
      rv.work_id,rv.body AS reviewed_text,rv.rating AS reviewed_rating,'review_reaction' AS kind
      FROM app.me_gusta_resena l JOIN app.resenas rv ON rv.id=l.review_id
      WHERE l.user_id=:owner AND rv.status='published'
        AND NOT EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='review' AND d.entity_id=rv.id)
      UNION ALL
      SELECT l.post_id,l.created_at,COALESCE(po.work_id,link.work_id),po.body,NULL,'post_reaction'
      FROM app.me_gusta_publicacion l JOIN app.publicaciones po ON po.id=l.post_id
      LEFT JOIN LATERAL (SELECT min(ed.work_id::text)::uuid AS work_id FROM app.fuentes_catalogo s
        JOIN app.ediciones ed ON ed.id=s.edition_id WHERE s.external_id=po.book_ref HAVING count(DISTINCT ed.work_id)=1) link ON true
      WHERE l.user_id=:owner AND NOT po.legacy_content
        AND NOT EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='post' AND d.entity_id=po.id)'''),params).mappings().all()
    return serial([{'kind':'follow',**dict(r)} for r in follows]+[{'kind':'comment',**dict(r)} for r in comments]+[dict(r) for r in reactions])


def extract_reader(db,owner):
    from app.modules.analytics.adaptive_ai import feedback_sources
    entries=db.execute(text('''SELECT le.id,le.work_id,le.archived_at FROM app.entradas_biblioteca le
      WHERE le.user_id=:owner AND NOT EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE
      (d.entity_type='library' AND d.entity_id=le.id) OR (d.entity_type='obras' AND d.entity_id=le.work_id))
      ORDER BY le.created_at,le.id'''),{'owner':owner}).mappings().all()
    books=[]
    for entry in entries:
        if entry['archived_at'] is not None:
            books.append({'work_id':str(entry['work_id']),'entry_id':str(entry['id']),'archived':True})
            continue
        context=extract_book_context(db,owner,entry['work_id'])
        ratings=[s['data'].get('rating') for s in context['sources'] if s['kind']=='review']
        books.append({'work_id':str(entry['work_id']),'entry_id':str(entry['id']),'archived':False,
                      'rating':ratings[-1] if ratings else None,'context':context})
    events=db.execute(text('''SELECT ev.id AS source_id,r.id AS reading_id,r.work_id,ev.kind,ev.created_at AS at,
      r.started_at,ev.reflection FROM app.eventos_lectura ev JOIN app.lecturas r ON r.id=ev.reading_id
      JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id WHERE le.user_id=:owner
      AND NOT EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE
        (d.entity_type='event' AND d.entity_id=ev.id) OR (d.entity_type='lecturas' AND d.entity_id=r.id)
        OR (d.entity_type='library' AND d.entity_id=le.id) OR (d.entity_type='obras' AND d.entity_id=r.work_id))
      ORDER BY ev.created_at,ev.id'''),{'owner':owner}).mappings().all()
    reviews=db.execute(text('''SELECT rv.id AS source_id,rv.work_id,rv.rating,rv.published_at AS at
      FROM app.resenas rv JOIN app.perfiles p ON p.id=rv.author_profile_id
      WHERE p.owner_user_id=:owner AND rv.created_by_user_id=:owner AND p.kind='personal' AND rv.status='published'
      AND NOT EXISTS(SELECT 1 FROM app.procedencia_demo d WHERE (d.entity_type='review' AND d.entity_id=rv.id)
        OR (d.entity_type='obras' AND d.entity_id=rv.work_id))'''),{'owner':owner}).mappings().all()
    payload = serial({'books':books,'events':[dict(e) for e in events],'reviews':[dict(r) for r in reviews],
                   'social':extract_social(db,owner),'profile_feedback':feedback_sources(db,owner,'profile')})
    from app.modules.books.canonical import enabled
    if enabled():
        from app.modules.books.consistency import current_reviews
        from app.modules.analytics.canonical_views import normalize_reader
        payload['reviews'] = serial([{'source_id':r.id,'work_id':r.work_id,'rating':r.rating,'at':r.published_at}
            for r in current_reviews(db, reader_id=owner, public=True)])
        payload = normalize_reader(db, payload)
    return payload


def refresh_reader(db,owner,force=False):
    # The dirty row is locked across extraction and publication. A concurrent
    # mutation marks it again after commit, so no change is silently lost.
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':'etl-reader:'+str(owner)})
    dirty=db.execute(text('SELECT owner_id FROM analytics.dirty_readers WHERE owner_id=:owner FOR UPDATE'),{'owner':owner}).first()
    previous=db.execute(text('''SELECT r.* FROM analytics.reader_current c JOIN analytics.projection_runs r ON r.id=c.run_id
      WHERE c.owner_id=:owner'''),{'owner':owner}).mappings().first()
    from app.modules.books.canonical import enabled, identity_version
    version = identity_version(db) if enabled() else None
    if previous and not dirty and not force and previous['payload'].get('identity_version') == version:
        return previous
    payload=extract_reader(db,owner)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    if previous and previous['source_hash']==digest and previous['transform_version']==VERSION:
        db.execute(text('DELETE FROM analytics.dirty_readers WHERE owner_id=:owner'),{'owner':owner})
        return previous
    run=uuid.uuid4()
    db.execute(text('''INSERT INTO analytics.projection_runs(id,owner_id,transform_version,source_hash,payload,source_cutoff_at,processed_at)
      VALUES(:id,:owner,:version,:hash,CAST(:payload AS jsonb),clock_timestamp(),clock_timestamp())'''),
      {'id':run,'owner':owner,'version':VERSION,'hash':digest,'payload':json.dumps(payload)})
    if version:
        db.execute(text('UPDATE analytics.projection_runs SET identity_version=:version WHERE id=:id'), {'version':version,'id':run})
    db.execute(text('''INSERT INTO analytics.reader_current(owner_id,run_id) VALUES(:owner,:id)
      ON CONFLICT(owner_id) DO UPDATE SET run_id=excluded.run_id'''),{'owner':owner,'id':run})
    db.execute(text('DELETE FROM analytics.dirty_readers WHERE owner_id=:owner'),{'owner':owner})
    return db.execute(text('SELECT * FROM analytics.projection_runs WHERE id=:id'),{'id':run}).mappings().one()


def reader_snapshot(db,owner):
    refresh_reader(db,owner)
    return db.execute(text('''SELECT r.payload FROM analytics.reader_current c
      JOIN analytics.projection_runs r ON r.id=c.run_id WHERE c.owner_id=:owner'''),{'owner':owner}).scalar_one()


def refresh_catalog(db):
    from app.modules.analytics.recommendations import metadata
    from app.modules.books.models import CatalogSource,Edition
    from sqlalchemy import select
    for work in db.execute(text('SELECT work_id FROM analytics.dirty_catalog FOR UPDATE SKIP LOCKED')).scalars().all():
        rows=db.execute(select(Edition,CatalogSource).join(CatalogSource,CatalogSource.edition_id==Edition.id)
          .where(Edition.work_id==work,CatalogSource.provider=='google-books',CatalogSource.validation_status=='validated')
          .order_by(Edition.id)).all()
        demo=set(db.execute(text('SELECT entity_type,entity_id FROM app.procedencia_demo')).all())
        editions=[{'metadata':metadata(e,s),'volume':{**(s.payload or {}),'id':s.external_id}}
                  for e,s in rows if ('obras',work) not in demo and ('ediciones',e.id) not in demo and ('fuentes_catalogo',s.id) not in demo]
        if editions:
            categories=db.execute(text('SELECT categories FROM app.obras WHERE id=:work'),{'work':work}).scalar()
            from app.modules.books.canonical import enabled, identity_snapshot
            snapshot = identity_snapshot(db) if enabled() else None
            identity = {'canonical_work_id':str(snapshot.root(work)), 'physical_work_id':str(work), 'identity_version':snapshot.version} if snapshot else {}
            db.execute(text('''INSERT INTO analytics.catalog_current(work_id,payload) VALUES(:work,CAST(:payload AS jsonb))
              ON CONFLICT(work_id) DO UPDATE SET payload=excluded.payload,processed_at=now()'''),
              {'work':work,'payload':json.dumps({'editions':editions,'categories':categories or [],**identity})})
        else:
            db.execute(text('DELETE FROM analytics.catalog_current WHERE work_id=:work'),{'work':work})
        db.execute(text('DELETE FROM analytics.dirty_catalog WHERE work_id=:work'),{'work':work})


def refresh_pending(db,rebuild=False):
    from app.modules.books.canonical import enabled, identity_version
    if enabled():
        version = identity_version(db)
        db.execute(text("""INSERT INTO analytics.dirty_readers(owner_id)
            SELECT c.owner_id FROM analytics.reader_current c JOIN analytics.projection_runs r ON r.id=c.run_id
            WHERE r.identity_version IS DISTINCT FROM :version ON CONFLICT DO NOTHING"""), {'version':version})
    if rebuild:
        db.execute(text('INSERT INTO analytics.dirty_readers(owner_id) SELECT id FROM app.usuarios ON CONFLICT DO NOTHING'))
        db.execute(text('INSERT INTO analytics.dirty_catalog(work_id) SELECT id FROM app.obras ON CONFLICT DO NOTHING'))
    refresh_catalog(db)
    owners=db.execute(text('SELECT owner_id FROM analytics.dirty_readers')).scalars().all()
    for owner in owners:
        refresh_reader(db,owner,force=rebuild)
    return len(owners)
