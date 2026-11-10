from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from PIL import Image
import uuid
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.demo.models import DemoMode
from app.modules.users.models import User
from app.modules.users.roles_router import get_admin

router = APIRouter(prefix='/admin/demo', tags=['demonstration'])
cover_router = APIRouter(prefix='/demo', tags=['demonstration covers'])
DB = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(get_admin)]


class DemoUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    interval_seconds: int = Field(default=30, ge=10, le=3600)


class DemoStatus(DemoUpdate):
    sequence: int
    last_run_at: datetime | None
    last_error: str | None
    updated_at: datetime
    selected_books: list[str] = Field(default_factory=list)
    missing_books: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


@router.get('', response_model=DemoStatus)
def status(db: DB, admin: Admin, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return describe_mode(db.get(DemoMode, 1))


@router.patch('', response_model=DemoStatus)
def configure(data: DemoUpdate, db: DB, admin: Admin, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    settings = get_settings()
    if data.enabled and (not settings.catalog_discovery_enabled or len(settings.libria_demo_password) < 8):
        raise HTTPException(422, 'Configura el catálogo en modo descubrimiento y LIBRIA_DEMO_PASSWORD de al menos 8 caracteres.')
    mode = db.scalar(select(DemoMode).where(DemoMode.id == 1).with_for_update())
    mode.enabled = data.enabled
    mode.interval_seconds = data.interval_seconds
    mode.updated_by = admin.id
    mode.updated_at = datetime.now(timezone.utc)
    mode.last_error = None
    db.commit()
    return describe_mode(mode)


def describe_mode(mode):
    from app.modules.demo.selection import selection_labels
    labels, missing = selection_labels(mode.catalog_edition_ids)
    return DemoStatus.model_validate(mode).model_copy(update={'selected_books': labels, 'missing_books': missing})


@cover_router.get('/covers/{edition_id}')
def original_cover(edition_id: uuid.UUID):
    from app.modules.demo.covers import cover_path
    path = cover_path(edition_id)
    if not path.is_file():
        raise HTTPException(404, 'Portada no disponible')
    with Image.open(path) as image:
        media_type = Image.MIME[image.format]
    return FileResponse(path, media_type=media_type, headers={'Cache-Control': 'public, max-age=86400'})
