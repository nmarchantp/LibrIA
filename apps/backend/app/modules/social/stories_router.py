"""Authenticated stories shared under the profile's current privacy policy."""
import uuid
from io import BytesIO
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, exists, or_, delete, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from app.modules.users.identities import personal_profile
from app.modules.social.models import ProfileFollow
from app.modules.social.story_models import Story, StoryView
from app.modules.social.router import image_content_type

router = APIRouter(prefix='/stories', tags=['stories'])
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]
MAX_BYTES = 5 * 1024 * 1024


def visible(user):
    # A private owner grants access by following the visitor (same as profiles).
    visitor = select(Profile.id).where(Profile.owner_user_id == user.id, Profile.kind == 'personal').correlate(None).scalar_subquery()
    granted = exists(select(1).where(ProfileFollow.profile_id == visitor, ProfileFollow.user_id == User.id))
    return (User.account_status == 'active', User.suspended_at.is_(None),
            Profile.kind == 'personal', Story.expires_at > func.now(),
            or_(User.id == user.id, User.profile_visibility == 'public', granted))


def query(user):
    return select(Story, Profile, User).join(Profile, Profile.id == Story.profile_id).join(User, User.id == Profile.owner_user_id).where(*visible(user))


def metadata(story, seen=False):
    return {'id': story.id, 'created_at': story.created_at, 'expires_at': story.expires_at,
            'image_url': f'/stories/{story.id}/image', 'seen': seen}


def prepare_image(data):
    if image_content_type(data) not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(422, 'Selecciona una imagen JPEG, PNG o WebP')
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > 25_000_000:
                raise HTTPException(422, 'La imagen no puede superar los 25 megapíxeles')
            source = ImageOps.exif_transpose(source).convert('RGBA')
            source.thumbnail((1080, 1920))
            canvas = Image.new('RGB', (1080, 1920), '#181522')
            canvas.paste(source, ((1080 - source.width) // 2, (1920 - source.height) // 2), source)
            output = BytesIO()
            canvas.save(output, format='JPEG', quality=90)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, 'No se pudo abrir esta imagen. Selecciona otra.') from None


@router.get('')
def listing(db: DB, user: Viewer, response: Response,
            audience: Literal['community', 'contacts'] = 'community', profile_id: uuid.UUID | None = None):
    response.headers['Cache-Control'] = 'private, no-store'
    seen = exists(select(1).where(StoryView.story_id == Story.id, StoryView.user_id == user.id))
    statement = query(user).add_columns(seen)
    if profile_id:
        statement = statement.where(Profile.id == profile_id)
    elif audience == 'contacts':
        statement = statement.where(or_(User.id == user.id, exists(select(1).where(
            ProfileFollow.profile_id == Profile.id, ProfileFollow.user_id == user.id))))
    groups = {}
    for story, profile, owner, was_seen in db.execute(statement.order_by(Story.created_at, Story.id)):
        group = groups.setdefault(profile.id, {'profile_id': profile.id, 'display_name': owner.display_name,
            'avatar_url': owner.avatar_url, 'is_owner': owner.id == user.id, 'stories': []})
        group['stories'].append(metadata(story, was_seen))
    return {'items': list(groups.values())}


@router.post('', status_code=201)
async def publish(request: Request, db: DB, user: Viewer):
    if user.account_status != 'active' or user.suspended_at:
        raise HTTPException(403, 'Tu cuenta no puede publicar historias')
    # Raw binary upload avoids buffering an unbounded multipart request.
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, 'La imagen debe pesar como máximo 5 MB')
        data.extend(chunk)
    image_data = await run_in_threadpool(prepare_image, data)
    profile = personal_profile(db, user)
    # Serialize uploads from a single owner and cap active storage.
    db.execute(select(Profile).where(Profile.id == profile.id).with_for_update())
    now = datetime.now(timezone.utc)
    db.execute(delete(Story).where(Story.profile_id == profile.id, Story.expires_at <= now))
    if db.scalar(select(func.count()).select_from(Story).where(Story.profile_id == profile.id)) >= 20:
        raise HTTPException(409, 'Puedes tener hasta 20 historias activas. Elimina una para publicar otra.')
    story = Story(profile_id=profile.id, content_type='image/jpeg', data=image_data, created_at=now, expires_at=now + timedelta(hours=24))
    db.add(story)
    db.commit()
    return metadata(story)


@router.get('/{story_id}/image')
def image(story_id: uuid.UUID, db: DB, user: Viewer):
    row = db.execute(query(user).where(Story.id == story_id)).first()
    if not row:
        raise HTTPException(404, 'Esta historia ya no está disponible')
    story = row[0]
    return Response(story.data, media_type=story.content_type, headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.delete('/{story_id}', status_code=204)
def remove(story_id: uuid.UUID, db: DB, user: Viewer):
    story = db.scalar(select(Story).join(Profile, Profile.id == Story.profile_id).where(Story.id == story_id, Profile.owner_user_id == user.id))
    if not story:
        raise HTTPException(404, 'Historia no encontrada')
    db.delete(story)
    db.commit()
    return Response(status_code=204)


@router.put('/{story_id}/view', status_code=204)
def mark_viewed(story_id: uuid.UUID, db: DB, user: Viewer):
    # Lock until the view is inserted so expiration cleanup cannot remove its parent.
    row = db.execute(query(user).where(Story.id == story_id).with_for_update(of=Story)).first()
    if not row:
        raise HTTPException(404, 'Esta historia ya no está disponible')
    db.execute(insert(StoryView).values(story_id=story_id, user_id=user.id).on_conflict_do_nothing())
    db.commit()
    return Response(status_code=204)
