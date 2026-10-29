"""Administrator inventory, editorial corrections and reversible work grouping."""
from dataclasses import asdict
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.books.evidence import ExternalReference
from app.modules.books.maintenance_schemas import WorkInput, EditionInput
from app.modules.books.facade import public_import
from app.modules.library.schemas import ExternalBookReference
from app.modules.users.models import User
from app.modules.users.roles_router import get_admin

router = APIRouter(prefix="/admin/catalog", tags=["catalog-administration"])


@router.get('/inventory')
def inventory(admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)],
              q: str = Query('', max_length=200), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
              filter_by: str = Query('all', pattern='^(all|duplicates|no_isbn|no_cover)$')):
    from app.modules.books.maintenance import require_maintenance, inventory as catalog_inventory
    require_maintenance(db, admin.id)
    return catalog_inventory(db, q, offset, limit, filter_by)


@router.get('/works/{work_id}')
def detail(work_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]):
    from app.modules.books.maintenance import require_maintenance, work_detail
    require_maintenance(db, admin.id)
    return work_detail(db, work_id)


def maintenance_command(db, actor, key, action, data, work_id=None, edition_id=None):
    from sqlalchemy.exc import IntegrityError
    from app.modules.books.maintenance import edit_catalog
    from app.modules.books.policy import execute_catalog_command
    try:
        return execute_catalog_command(db, lambda: edit_catalog(db, actor, key, action, data, work_id, edition_id))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'El cambio entra en conflicto con otro registro del catálogo. Actualiza el libro y revisa el ISBN.') from None


@router.post('/works')
def create_work(data: WorkInput, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)],
                idempotency_key: Annotated[str, Header(min_length=1, max_length=200)]):
    return maintenance_command(db, admin.id, idempotency_key, 'work_create', data)


@router.patch('/works/{work_id}')
def update_work(work_id: uuid.UUID, data: WorkInput, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)],
                idempotency_key: Annotated[str, Header(min_length=1, max_length=200)]):
    return maintenance_command(db, admin.id, idempotency_key, 'work_update', data, work_id)


@router.post('/works/{work_id}/editions')
def create_edition(work_id: uuid.UUID, data: EditionInput, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)],
                   idempotency_key: Annotated[str, Header(min_length=1, max_length=200)]):
    return maintenance_command(db, admin.id, idempotency_key, 'edition_create', data, work_id)


@router.patch('/works/{work_id}/editions/{edition_id}')
def update_edition(work_id: uuid.UUID, edition_id: uuid.UUID, data: EditionInput, admin: Annotated[User, Depends(get_admin)],
                   db: Annotated[Session, Depends(get_db)], idempotency_key: Annotated[str, Header(min_length=1, max_length=200)]):
    return maintenance_command(db, admin.id, idempotency_key, 'edition_update', data, work_id, edition_id)


class MergePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_work_id: uuid.UUID
    target_work_id: uuid.UUID


class MergeExecutionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation: str
    reason: str=Field(min_length=1,max_length=2000)
    metadata_policy: str='preserve_destination'
    library_policy: str='preserve_all'
    review_ids: list[uuid.UUID]=Field(default_factory=list)


class ReversalExecutionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation: str
    reason: str=Field(min_length=1,max_length=2000)
    preserve_physical: list[str]=Field(default_factory=list)


@router.post('/merge-previews/{preview_id}/execute')
def execute(preview_id: uuid.UUID,data: MergeExecutionRequest,admin: Annotated[User,Depends(get_admin)],
            db: Annotated[Session,Depends(get_db)],idempotency_key: Annotated[str,Header(min_length=1,max_length=200)]):
    from app.modules.books.merge_execution import execute_merge
    from app.modules.books.policy import execute_catalog_command
    actor=admin.id
    return execute_catalog_command(db,lambda:execute_merge(db,actor,preview_id,idempotency_key,data.model_dump(mode='json')))


@router.get('/history')
def history(admin: Annotated[User,Depends(get_admin)],db: Annotated[Session,Depends(get_db)]):
    from sqlalchemy import select
    from app.modules.books.catalog_models import CatalogOperation,WorkRedirect
    if not get_settings().catalog_admin_preview_enabled:
        raise HTTPException(404,'Administración deshabilitada')
    rows=db.scalars(select(CatalogOperation).where(CatalogOperation.operation_type.in_(['merge','reversal'])).order_by(CatalogOperation.identity_version.desc()).limit(50)).all()
    return [dict(id=str(o.id),kind=o.operation_type,source_work_id=str(o.source_work_id) if o.source_work_id else None,
        target_work_id=str(o.target_work_id),reason=o.reason,created_at=o.created_at.isoformat(),
        active=bool(db.scalar(select(WorkRedirect.id).where(WorkRedirect.operation_id==o.id,WorkRedirect.retired_at.is_(None))))) for o in rows]


@router.post('/merges/{operation_id}/reversal-preview')
def simulate_reversal(operation_id: uuid.UUID,admin: Annotated[User,Depends(get_admin)],db: Annotated[Session,Depends(get_db)]):
    from app.modules.books.merge_execution import preview_reversal
    actor=admin.id
    return preview_transaction(db,lambda:preview_reversal(db,actor,operation_id))


@router.post('/reversal-previews/{preview_id}/execute')
def reverse(preview_id: uuid.UUID,data: ReversalExecutionRequest,admin: Annotated[User,Depends(get_admin)],
            db: Annotated[Session,Depends(get_db)],idempotency_key: Annotated[str,Header(min_length=1,max_length=200)]):
    from app.modules.books.merge_execution import execute_reversal
    from app.modules.books.policy import execute_catalog_command
    actor=admin.id
    return execute_catalog_command(db,lambda:execute_reversal(db,actor,preview_id,idempotency_key,data.model_dump(mode='json')))


def preview_transaction(db, action):
    if not get_settings().catalog_admin_preview_enabled:
        raise HTTPException(404, 'Simulación administrativa no habilitada')
    db.rollback()  # finish dependency authentication read before snapshot
    from sqlalchemy.exc import DBAPIError
    try:
        with db.begin():
            from sqlalchemy import text
            db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            db.execute(text("SET LOCAL statement_timeout='10s'"))
            db.execute(text("SET LOCAL lock_timeout='2s'"))
            return action()
    except DBAPIError as error:
        if getattr(error.orig,'sqlstate',None) in {'57014','55P03','40001','40P01'}:
            raise HTTPException(503,'Simulación interrumpida; vuelva a intentarlo',headers={'Retry-After':'1'}) from error
        raise


@router.get('/works')
def search_works(admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)], q: str = ''):
    from app.modules.books.maintenance import inventory as catalog_inventory
    if not get_settings().catalog_admin_preview_enabled:
        raise HTTPException(404, 'Simulación administrativa no habilitada')
    if len(q)>200:
        raise HTTPException(422,'Consulta demasiado larga')
    return catalog_inventory(db, q, limit=30)["items"]


@router.post('/compare')
def compare(data: MergePreviewRequest, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]):
    from app.modules.books.merge_preview import compare_works
    actor = admin.id
    return preview_transaction(db,lambda:compare_works(db,actor,data.source_work_id,data.target_work_id))


@router.post('/merge-previews')
def simulate(data: MergePreviewRequest, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]):
    from app.modules.books.merge_preview import preview_merge
    actor = admin.id
    return preview_transaction(db,lambda:preview_merge(db,actor,data.source_work_id,data.target_work_id))


@router.post('/merge-previews/{preview_id}/validate')
def validate(preview_id: uuid.UUID, admin: Annotated[User, Depends(get_admin)], db: Annotated[Session, Depends(get_db)]):
    from app.modules.books.merge_preview import validate_preview
    actor = admin.id
    return preview_transaction(db,lambda:validate_preview(db,actor,preview_id))


class CatalogImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: ExternalBookReference
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/imports")
def authorized_import(data: CatalogImportRequest, admin: Annotated[User, Depends(get_admin)],
                      db: Annotated[Session, Depends(get_db)],
                      idempotency_key: Annotated[str, Header(min_length=1, max_length=200)]):
    if not get_settings().catalog_discovery_enabled:
        raise HTTPException(404, "Flujo de catálogo no habilitado")
    actor_id = admin.id
    return asdict(public_import(db, actor_id, ExternalReference(**data.reference.model_dump()), idempotency_key, data.reason))
