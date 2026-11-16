"""Book-scoped, curated characters. Readers select; administrators supply portraits."""
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.roles_router import get_admin
from app.modules.users.models import User
from app.modules.books.models import LiteraryCharacter, Work

router = APIRouter(tags=['literary characters'])
DB = Annotated[Session, Depends(get_db)]


def character_image(item):
    return f'/api/books/characters/{item.id}/portrait' if item.portrait_data else item.portrait_url


@router.get('/books/{work_id}/characters')
def list_characters(work_id: uuid.UUID, db: DB, user: Annotated[User, Depends(get_current_user)]):
    work = db.get(Work, work_id)
    if not work:
        raise HTTPException(404, 'Libro no encontrado en LibrIA')
    items = db.scalars(select(LiteraryCharacter).where(LiteraryCharacter.work_id == work_id,
        LiteraryCharacter.active.is_(True)).order_by(LiteraryCharacter.name)).all()
    return {'work_id': work.id, 'title': work.title, 'items': [
        {'id': item.id, 'name': item.name, 'image_url': character_image(item)} for item in items]}


@router.get('/books/characters/{character_id}/portrait')
def portrait(character_id: uuid.UUID, db: DB):
    item = db.get(LiteraryCharacter, character_id)
    if not item or not item.active or not item.portrait_data:
        raise HTTPException(404, 'Retrato no encontrado')
    return Response(item.portrait_data, media_type=item.portrait_type,
        headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'public, max-age=3600'})


@router.post('/admin/catalog/works/{work_id}/characters', status_code=201)
async def add_character(work_id: uuid.UUID, request: Request, db: DB, admin: Annotated[User, Depends(get_admin)]):
    from app.modules.social.post_covers import read_cover
    if not db.get(Work, work_id):
        raise HTTPException(404, 'Libro no encontrado')
    async with request.form(max_files=1, max_fields=1) as form:
        name = str(form.get('name') or '').strip()
        if not name or len(name) > 100:
            raise HTTPException(422, 'Escribe un nombre de hasta 100 caracteres')
        content_type, data = await read_cover(form.get('portrait'))
    if db.scalar(select(LiteraryCharacter.id).where(LiteraryCharacter.work_id == work_id, LiteraryCharacter.name == name)):
        raise HTTPException(409, 'Este personaje ya está registrado para el libro')
    item = LiteraryCharacter(work_id=work_id, name=name, portrait_type=content_type, portrait_data=data)
    db.add(item)
    db.commit()
    return {'id': item.id, 'name': item.name, 'image_url': character_image(item)}
