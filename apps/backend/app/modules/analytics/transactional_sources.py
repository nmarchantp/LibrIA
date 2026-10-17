"""Transactional extraction belongs to ETL; inference consumes analytics projections."""
from sqlalchemy import text


def extract_book_context(db, owner, work):
    from app.modules.analytics.adaptive_ai import owned_entry, has_rating, feedback_sources, hash_data
    entry = owned_entry(db, owner, work)
    readings = db.execute(text("""SELECT r.* FROM app.lecturas r WHERE r.library_entry_id=:entry
        AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='lecturas' AND d.entity_id=r.id)
        ORDER BY r.created_at,r.id"""), {'entry': entry['id']}).mappings().all()
    sources = []
    for r in readings:
        sources.append({'key': 'reading:'+str(r['id']), 'kind': 'reading', 'id': str(r['id']),
            'at': r['created_at'].isoformat(), 'data': {'state': r['status'],
            'abandonment_reason': r['abandonment_reason'], 'notebook': r['notebook'] or {}}})
    reviews = db.execute(text("""SELECT rv.id,v.body,v.rating,v.dimension_ratings,v.recorded_at AS updated_at,v.revision_number
        FROM app.resenas rv JOIN app.perfiles p ON p.id=rv.author_profile_id
        JOIN app.revisiones_resena v ON v.review_id=rv.id
        WHERE p.kind='personal' AND p.owner_user_id=:owner AND rv.created_by_user_id=:owner AND rv.work_id=:work
        AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='review' AND d.entity_id=rv.id)
        ORDER BY v.recorded_at,v.revision_number,rv.id"""),
        {'owner': owner, 'work': work}).mappings().all()
    previous_reviews = {}
    for r in reviews:
        signature = hash_data({key:r[key] for key in ('body','rating','dimension_ratings')})
        if previous_reviews.get(r['id']) == signature:
            continue
        previous_reviews[r['id']] = signature
        sources.append({'key': 'review:'+str(r['id'])+':'+str(r['revision_number']), 'kind': 'review', 'id': str(r['id']),
                        'at': r['updated_at'].isoformat(), 'data': {k: r[k] for k in ('body','rating','dimension_ratings','revision_number')}})
    events = db.execute(text("""SELECT ev.id,ev.reflection,ev.created_at FROM app.eventos_lectura ev
        JOIN app.lecturas r ON r.id=ev.reading_id JOIN app.entradas_biblioteca le ON le.id=r.library_entry_id
        WHERE le.user_id=:owner AND le.work_id=:work AND ev.reflection IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='event' AND d.entity_id=ev.id)
        ORDER BY ev.created_at,ev.id"""), {'owner': owner, 'work': work}).mappings().all()
    for r in events:
        sources.append({'key': 'reflection:'+str(r['id']), 'kind': 'reflection', 'id': str(r['id']),
                        'at': r['created_at'].isoformat(), 'data': r['reflection']})
    posts = db.execute(text("""SELECT po.id,po.publication_type,po.body,po.created_at FROM app.publicaciones po
        JOIN app.perfiles p ON p.id=po.author_profile_id
        WHERE p.kind='personal' AND p.owner_user_id=:owner AND po.user_id=:owner
          AND po.publication_type IN ('note','theory') AND NOT po.legacy_content
          AND (po.work_id=:work OR (po.work_id IS NULL AND (SELECT count(DISTINCT ed.work_id) FROM app.fuentes_catalogo s
               JOIN app.ediciones ed ON ed.id=s.edition_id WHERE s.external_id=po.book_ref)=1
          AND EXISTS (SELECT 1 FROM app.fuentes_catalogo s JOIN app.ediciones ed ON ed.id=s.edition_id
                      WHERE s.external_id=po.book_ref AND ed.work_id=:work)))
          AND NOT EXISTS (SELECT 1 FROM app.procedencia_demo d WHERE d.entity_type='post' AND d.entity_id=po.id)
        ORDER BY po.created_at,po.id"""), {'owner': owner, 'work': work}).mappings().all()
    for r in posts:
        sources.append({'key': str(r['publication_type'])+':'+str(r['id']), 'kind': r['publication_type'],
                        'id': str(r['id']), 'at': r['created_at'].isoformat(), 'data': {'body': r['body']}})
    sources += feedback_sources(db, owner, 'book:'+str(work))
    return {'title': entry['title'], 'categories': entry['categories'] or [], 'rated': has_rating(db,owner,work),
            'state': readings[-1]['status'] if readings else 'pending', 'sources': sources}

