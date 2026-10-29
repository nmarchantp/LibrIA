"""Bounded source-state fingerprints; derived caches are invalidated, not identity evidence."""
import hashlib
import json
from sqlalchemy import text
from app.modules.books.canonical import identity_snapshot


def scope_state(db, work_ids):
    snapshot=identity_snapshot(db,work_ids)
    ids=list(snapshot.mapping)
    checks={
      'obras':'t.id=ANY(:ids)',
      'ediciones':'t.work_id=ANY(:ids)',
      'obras_autores':'t.work_id=ANY(:ids)',
      'autores':'t.id IN (SELECT author_id FROM app.obras_autores WHERE work_id=ANY(:ids))',
      'titulos_alternativos':'t.work_id=ANY(:ids)',
      'fuentes_catalogo':'t.edition_id IN (SELECT id FROM app.ediciones WHERE work_id=ANY(:ids))',
      'referencias_obras':'t.work_id=ANY(:ids)',
      'entradas_biblioteca':'t.work_id=ANY(:ids)',
      'lecturas':'t.work_id=ANY(:ids)',
      'eventos_lectura':'t.reading_id IN (SELECT id FROM app.lecturas WHERE work_id=ANY(:ids))',
      'progreso_lectura':'t.reading_id IN (SELECT id FROM app.lecturas WHERE work_id=ANY(:ids))',
      'selecciones_edicion_lectura':'t.work_id=ANY(:ids)',
      'resenas':'t.work_id=ANY(:ids)',
      'perfiles':'t.id IN (SELECT author_profile_id FROM app.resenas WHERE work_id=ANY(:ids))',
      'revisiones_resena':'t.review_id IN (SELECT id FROM app.resenas WHERE work_id=ANY(:ids))',
      'publicaciones':'''t.work_id=ANY(:ids) OR (t.work_id IS NULL AND t.book_ref IN
        (SELECT s.external_id FROM app.fuentes_catalogo s JOIN app.ediciones e ON e.id=s.edition_id WHERE e.work_id=ANY(:ids)))''',
      'incorporaciones_catalogo':'t.work_id=ANY(:ids)',
      'selecciones_resena_canonica':'t.work_id=ANY(:ids)',
      'redirecciones_obras':'t.source_work_id=ANY(:ids) OR t.target_work_id=ANY(:ids)',
    }
    result={}
    for table,condition in checks.items():
        physical="to_jsonb(t)->>'work_id'"
        if table=='obras':physical='t.id::text'
        if table in ('eventos_lectura','progreso_lectura'):
            physical='(SELECT r.work_id::text FROM app.lecturas r WHERE r.id=t.reading_id)'
        if table=='fuentes_catalogo':physical='(SELECT e.work_id::text FROM app.ediciones e WHERE e.id=t.edition_id)'
        if table=='revisiones_resena':physical='(SELECT r.work_id::text FROM app.resenas r WHERE r.id=t.review_id)'
        for row in db.execute(text(f"""SELECT coalesce(to_jsonb(t)->>'id',concat_ws(':',to_jsonb(t)->>'work_id',to_jsonb(t)->>'author_id',to_jsonb(t)->>'review_id',to_jsonb(t)->>'revision_number')) record_key,
            {physical} physical_work_id,
            encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') digest FROM app.{table} t WHERE {condition}"""),dict(ids=ids)).mappings():
            result[table+':'+row['record_key']]=dict(hash=row['digest'],physical_work_id=row['physical_work_id'])
    return result


def scope_fingerprint(db,work_ids):
    return hashlib.sha256(json.dumps(scope_state(db,work_ids),sort_keys=True,separators=(',',':')).encode()).hexdigest()
