"""Publication-only cover storage; original attachments and catalog stay intact."""
import io
import uuid
import warnings
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.social.activity_access import resolve_activity
from app.modules.social.models import PostBookCover
from app.modules.users.identities import require_actor
from app.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["publication covers"])
MAX_COVER_BYTES = 5 * 1024 * 1024
FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp"}


def cover_url(cover):
    return f"/posts/{cover.post_id}/book-cover?version={cover.revision}" if cover else None


async def read_cover(upload):
    if not isinstance(upload, UploadFile):
        raise HTTPException(422, "Selecciona un archivo de imagen para la portada")
    try:
        data = await upload.read(MAX_COVER_BYTES + 1)
        if len(data) > MAX_COVER_BYTES:
            raise HTTPException(413, "La portada admite hasta 5 MB")
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                content_type = FORMATS.get(image.format)
                if not content_type:
                    raise HTTPException(415, "Usa JPEG, PNG, GIF o WebP para la portada")
                image.verify()
        return content_type, data
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "La portada no es una imagen válida") from None
    finally:
        await upload.close()


def require_post_editor(db, user, post_id):
    from app.modules.social.moderation_service import owned_target
    return owned_target(db,user,'publication',post_id)


def require_cover_editor(db,user,post_id):
    post=require_post_editor(db,user,post_id)
    if not (post.work_id or post.book_ref):
        raise HTTPException(422, "Enlaza una obra antes de personalizar su portada")
    from sqlalchemy import select
    from app.modules.social.moderation_models import ModerationRevision
    if post.moderation_status!='approved' or db.scalar(select(ModerationRevision.id).where(
        ModerationRevision.post_id==post.id,ModerationRevision.status=='pending_review',
        ModerationRevision.lifecycle=='active')) is not None:
        raise HTTPException(409,'La portada tiene una publicación o edición pendiente de revisión')
    resolve_activity(db,'publication',post_id)
    return post


@router.get('/{post_id}/book-cover')
def get_cover(post_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    # Same visibility checks as the original gallery-image route, on every request.
    resolve_activity(db, 'publication', post_id)
    cover = db.get(PostBookCover, post_id)
    if not cover:
        raise HTTPException(404, "Esta publicación no tiene portada personalizada")
    return Response(cover.data, media_type=cover.content_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.put('/{post_id}/book-cover')
async def put_cover(post_id: uuid.UUID, request: Request, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    post=require_cover_editor(db, user, post_id)
    async with request.form(max_files=1, max_fields=0) as form:
        content_type, data = await read_cover(form.get('book_cover'))
    cover = db.get(PostBookCover, post_id)
    if cover is None:
        cover = PostBookCover(post_id=post_id, revision=uuid.uuid4(), content_type=content_type, data=data)
        db.add(cover)
    else:
        cover.revision, cover.content_type, cover.data = uuid.uuid4(), content_type, data
    db.flush()
    post.moderation_version+=1
    result = {'custom_book_cover_url': cover_url(cover)}
    db.commit()
    return result


@router.delete('/{post_id}/book-cover')
def delete_cover(post_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    post=require_cover_editor(db, user, post_id)
    cover = db.get(PostBookCover, post_id)
    if cover:
        db.delete(cover)
        post.moderation_version+=1
    db.commit()
    return {'custom_book_cover_url': None}
