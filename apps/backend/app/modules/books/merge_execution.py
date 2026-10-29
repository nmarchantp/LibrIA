"""Explicit administrative graph changes; physical user/bibliographic rows stay put.

Caller owns the transaction. Acquire the exclusive writer barrier before reads;
database BEFORE STATEMENT triggers make every relevant domain writer participate.
"""
from datetime import datetime,timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select,text
from app.core.config import get_settings
from app.modules.books.catalog_models import CatalogOperation,CatalogOperationEffect,WorkRedirect
from app.modules.books.canonical import identity_snapshot
from app.modules.books.merge_preview import VERSION,TTL,require_admin
from app.modules.books.merge_scope import scope_state,scope_fingerprint
from app.modules.social.models import Review


def lock_catalog(db,actor):
    if not get_settings().catalog_admin_merge_enabled:
        raise HTTPException(404,'Fusiones administrativas deshabilitadas')
    if db.scalar(text('SHOW transaction_isolation'))!='read committed':
        raise HTTPException(409,'La ejecución requiere READ COMMITTED')
    db.execute(text('SELECT pg_advisory_xact_lock(73155,1)'))
    require_admin(db,actor)


def request_hash(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def replay(db,actor,kind,key,payload):
    digest=request_hash(payload)
    if not key.strip() or len(key)>200:
        raise HTTPException(422,'Clave de idempotencia inválida')
    op=db.scalar(select(CatalogOperation).where(CatalogOperation.actor_user_id==actor,CatalogOperation.operation_type==kind,CatalogOperation.request_key==key))
    if op:
        if op.request_hash!=digest:
            raise HTTPException(409,'La clave ya identifica otra solicitud')
        return op.context['result'],digest
    return None,digest


def load_preview(db,preview_id,kind):
    row=db.execute(text('SELECT * FROM app.simulaciones_fusion WHERE id=:id'),dict(id=preview_id)).mappings().first()
    if not row:
        raise HTTPException(404,'Simulación no encontrada')
    if row['version']!=VERSION or row['expires_at']<=datetime.now(timezone.utc):
        raise HTTPException(409,'Simulación caducada o de una versión anterior')
    if row['result'].get('kind','merge')!=kind:
        raise HTTPException(409,'Tipo de simulación incorrecto')
    ids=[row['source_work_id'],row['target_work_id']]
    if row['fingerprint']!=scope_fingerprint(db,ids):
        raise HTTPException(409,'Los datos afectados cambiaron; vuelva a simular')
    return row,ids


def execute_merge(db,actor,preview_id,key,decisions):
    lock_catalog(db,actor)
    payload=dict(preview_id=str(preview_id),decisions=decisions)
    previous,digest=replay(db,actor,'merge',key,payload)
    if previous:
        return previous
    if decisions.get('confirmation')!='FUSIONAR' or decisions.get('metadata_policy')!='preserve_destination' or decisions.get('library_policy')!='preserve_all':
        raise HTTPException(422,'Confirme la fusión y las políticas de conservación')
    reason=decisions.get('reason','').strip()
    if not reason or len(reason)>2000:
        raise HTTPException(422,'Indique el motivo bibliográfico, hasta 2000 caracteres')
    row,ids=load_preview(db,preview_id,'merge')
    snapshot=identity_snapshot(db,ids)
    source,target=map(snapshot.root,ids)
    if source==target:
        raise HTTPException(409,'Las obras ya están vinculadas')
    # Re-derive conflicts under the barrier; never trust client metadata or proposals.
    reviews=db.scalars(select(Review).where(Review.work_id.in_(snapshot.mapping))).all()
    groups={}
    for review in reviews:
        groups.setdefault(review.author_profile_id,[]).append(review)
    selected=set(decisions.get('review_ids',[]))
    required=[rows for rows in groups.values() if len(rows)>1]
    chosen=[]
    for rows in required:
        matches=[r for r in rows if str(r.id) in selected]
        if len(matches)!=1:
            raise HTTPException(422,'Seleccione exactamente una reseña vigente por conflicto')
        chosen.extend(matches)
    if selected!={str(r.id) for r in chosen}:
        raise HTTPException(422,'Selecciones de reseña ajenas a los conflictos')
    before=scope_state(db,ids)
    op_id=uuid.uuid4()
    result=dict(operation_id=str(op_id),source_work_id=str(source),canonical_work_id=str(target),status='merged',historical_records_preserved=True)
    op=CatalogOperation(id=op_id,actor_user_id=actor,operation_type='merge',request_key=key,request_hash=digest,
        source_work_id=source,target_work_id=target,reason=reason,
        evidence=dict(preview_id=str(preview_id),fingerprint=row['fingerprint'],administrative_confirmation=True),
        context=dict(result=result,decisions=decisions,requested_ids=list(map(str,ids))))
    db.add(op);db.flush()
    for r in chosen:
        db.execute(text('INSERT INTO app.selecciones_resena_canonica(id,operation_id,work_id,profile_id,review_id) VALUES (:id,:op,:work,:profile,:review)'),
            dict(id=uuid.uuid4(),op=op_id,work=target,profile=r.author_profile_id,review=r.id))
    db.add(WorkRedirect(source_work_id=source,target_work_id=target,operation_id=op_id));db.flush()
    db.add(CatalogOperationEffect(operation_id=op_id,ordinal=1,entity_table='catalog_scope',entity_id=source,
        before_state={'rows':before},after_state={'rows':scope_state(db,ids)}));db.flush()
    return result


def preview_reversal(db,actor,operation_id):
    from app.modules.books.merge_preview import require_snapshot
    require_admin(db,actor);require_snapshot(db)
    op=db.get(CatalogOperation,operation_id)
    if not op or op.operation_type!='merge':
        raise HTTPException(404,'Fusión no encontrada')
    redirect=db.scalar(select(WorkRedirect).where(WorkRedirect.operation_id==op.id,WorkRedirect.retired_at.is_(None)))
    if not redirect:
        raise HTTPException(409,'La fusión ya está revertida')
    effect=db.scalar(select(CatalogOperationEffect).where(CatalogOperationEffect.operation_id==op.id,CatalogOperationEffect.entity_table=='catalog_scope'))
    if not effect:
        raise HTTPException(409,'Fusión histórica sin auditoría suficiente para recuperación segura')
    ids=[op.source_work_id,op.target_work_id]
    baseline=effect.after_state['rows'];current=scope_state(db,ids)
    changes=[]
    blockers=[]
    for key in sorted(baseline.keys()|current.keys()):
        if baseline.get(key)==current.get(key):
            continue
        change=dict(entity=key,change='created' if key not in baseline else 'deleted' if key not in current else 'updated',
            physical_work_id=current.get(key,{}).get('physical_work_id'),required_decision='preserve_physical')
        changes.append(change)
        if key.startswith(('redirecciones_obras:','selecciones_resena_canonica:')) or key not in current:
            blockers.append(dict(entity=key,reason='Dependencia posterior o eliminación; requiere recuperación específica antes de separar'))
    result=dict(kind='reversal',version=VERSION,operation_id=str(op.id),source_work_id=str(op.source_work_id),target_work_id=str(op.target_work_id),
        changes=changes,blockers=blockers,can_execute=not blockers,
        policy='Conservar cada registro posterior con su UUID y atribución física actual; no reasignar silenciosamente',
        provenance=[])
    # Incorporation provenance is summarized without actor/library identifiers.
    receipts=db.execute(text('SELECT id,work_id,requested_reference FROM app.incorporaciones_catalogo WHERE work_id=ANY(:ids) AND created_at>=:when'),dict(ids=ids,when=op.created_at)).mappings()
    result['provenance']=[]
    ambiguous=[]
    for receipt in receipts:
        requested=receipt['requested_reference'].get('internal_work_id')
        physical=str(receipt['work_id'])
        contradiction=bool(requested and requested!=physical)
        item=dict(id=str(receipt['id']),work_id=physical,requested_reference=receipt['requested_reference'],
                  attribution='requested_work_differs_from_physical_work' if contradiction else 'inspect_recorded_provenance')
        result['provenance'].append(item)
        if contradiction:ambiguous.append('incorporaciones_catalogo:'+str(receipt['id']))
    result['ambiguous_attributions']=ambiguous
    for change in changes:
        change['attribution']='requires_explicit_physical_attribution' if change['entity'] in ambiguous else 'physical_lineage_preserved'
    now=datetime.now(timezone.utc);preview_id=uuid.uuid4()
    digest=scope_fingerprint(db,ids)
    result.update(preview_id=str(preview_id),fingerprint=digest,expires_at=(now+TTL).isoformat())
    db.execute(text('''INSERT INTO app.simulaciones_fusion(id,actor_user_id,version,source_work_id,target_work_id,fingerprint,result,created_at,expires_at)
      VALUES (:id,:actor,2,:source,:target,:hash,CAST(:result AS jsonb),:now,:expiry)'''),
      dict(id=preview_id,actor=actor,source=ids[0],target=ids[1],hash=digest,result=json.dumps(result),now=now,expiry=now+TTL))
    return result


def execute_reversal(db,actor,preview_id,key,decisions):
    lock_catalog(db,actor)
    previous,digest=replay(db,actor,'reversal',key,dict(preview_id=str(preview_id),decisions=decisions))
    if previous:
        return previous
    if decisions.get('confirmation')!='REVERTIR' or not decisions.get('reason','').strip():
        raise HTTPException(422,'Confirme la reversión y su motivo')
    row,ids=load_preview(db,preview_id,'reversal')
    preview=row['result']
    if preview['blockers']:
        raise HTTPException(409,dict(message='Separación bloqueada por dependencias posteriores',blockers=preview['blockers']))
    if set(decisions.get('preserve_physical',[]))!={r['entity'] for r in preview['changes']}:
        raise HTTPException(422,'Decida explícitamente la atribución física de cada registro posterior')
    original=db.get(CatalogOperation,uuid.UUID(preview['operation_id']))
    redirect=db.scalar(select(WorkRedirect).where(WorkRedirect.operation_id==original.id,WorkRedirect.retired_at.is_(None)))
    if not redirect:
        raise HTTPException(409,'Fusión ya revertida')
    before=scope_state(db,ids);op_id=uuid.uuid4()
    result=dict(operation_id=str(op_id),reverses_operation_id=str(original.id),status='reversed',historical_records_preserved=True)
    op=CatalogOperation(id=op_id,actor_user_id=actor,operation_type='reversal',request_key=key,request_hash=digest,
        target_work_id=original.target_work_id,reverses_operation_id=original.id,reason=decisions['reason'],
        evidence=dict(preview_id=str(preview_id),fingerprint=row['fingerprint']),context=dict(result=result,decisions=decisions))
    db.add(op);db.flush()
    redirect.retired_at=datetime.now(timezone.utc);redirect.retirement_operation_id=op_id;db.flush()
    db.add(CatalogOperationEffect(operation_id=op_id,ordinal=1,entity_table='catalog_scope',entity_id=original.source_work_id,
        before_state={'rows':before},after_state={'rows':scope_state(db,ids)}));db.flush()
    return result
