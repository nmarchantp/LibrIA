"""Personal agendas project original publications and attendance, never copies."""
import uuid
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select, exists, or_, func, cast, Date, text
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from app.modules.users.identities import personal_profile, can_create_events
from app.modules.social.models import Post, PublicationEvent, EventAttendance, ProfileFollow
from app.modules.social.activity_access import visible_posts
from app.modules.social.feed_service import hydrate

router = APIRouter(prefix='/profiles', tags=['profile events'])
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]


def subject(db, viewer, profile_id):
    profile = personal_profile(db, viewer) if profile_id == 'me' else db.get(Profile, uuid.UUID(profile_id))
    if not profile or profile.kind != 'personal':
        raise HTTPException(404, 'Perfil personal no encontrado')
    owner = db.get(User, profile.owner_user_id)
    if not owner or owner.account_status != 'active' or owner.suspended_at:
        raise HTTPException(404, 'Perfil personal no encontrado')
    own = owner.id == viewer.id
    follows = owner.events_visibility == 'contacts' and db.get(ProfileFollow, (profile.id, viewer.id)) is not None
    from app.modules.users.profile_access import profile_access
    allowed = profile_access(db, owner, viewer) and (own or owner.events_visibility == 'public' or follows)
    return profile, owner, own, bool(allowed)


@router.get('/{profile_id}/events/access')
def access(profile_id: str, db: DB, user: Viewer, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        _, _, own, allowed = subject(db, user, profile_id)
    except ValueError:
        raise HTTPException(404, 'Perfil no encontrado')
    # No counts, attendance identities or privacy preference for visitors.
    return {'allowed': allowed, 'is_owner': own}


class PrivacyInput(BaseModel):
    visibility: Literal['private', 'contacts', 'public']


@router.patch('/me/events/privacy')
def privacy(data: PrivacyInput, db: DB, user: Viewer):
    personal_profile(db, user)
    user.events_visibility = data.visibility
    db.commit()
    return {'visibility': user.events_visibility}


@router.get('/{profile_id}/events')
def agenda(profile_id: str, db: DB, user: Viewer, response: Response,
           period: Literal['upcoming', 'past'] = 'upcoming',
           participation: Literal['all', 'attending', 'organizing'] = 'all',
           offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        profile, owner, own, allowed = subject(db, user, profile_id)
    except ValueError:
        raise HTTPException(404, 'Perfil no encontrado')
    if not allowed:
        raise HTTPException(403, 'Esta agenda es privada')
    creator = can_create_events(db, owner, profile)
    attending = exists(select(1).where(EventAttendance.post_id == Post.id,
        EventAttendance.user_id == owner.id, EventAttendance.attending.is_(True)))
    organizing = or_(Post.author_profile_id == profile.id,
                     (Post.author_profile_id.is_(None) & (Post.user_id == owner.id)))
    # Readers only project confirmed attendance; creator filters use the policy.
    membership = attending if not creator else or_(attending, organizing)
    if participation == 'attending': membership = attending
    if participation == 'organizing': membership = organizing if creator else text('false')
    base = select(Post).join(PublicationEvent, PublicationEvent.post_id == Post.id).where(
        visible_posts(), Post.source == 'event', Post.publication_type == 'event', membership)
    # Without an explicit end, the event remains current through its local day.
    local_day = cast(func.timezone(PublicationEvent.timezone, PublicationEvent.starts_at), Date)
    day_end = func.timezone(PublicationEvent.timezone, local_day + text("INTERVAL '1 day'"))
    effective_end = func.coalesce(PublicationEvent.ends_at, day_end)
    conditions = {'upcoming': effective_end >= func.now(), 'past': effective_end < func.now()}
    counts = {key: db.scalar(select(func.count()).select_from(base.where(condition).subquery())) for key, condition in conditions.items()}
    filtered = base.where(conditions[period])
    total = counts[period]
    ordering = PublicationEvent.starts_at.asc() if period == 'upcoming' else PublicationEvent.starts_at.desc()
    rows = list(db.scalars(filtered.order_by(ordering, Post.id).offset(offset).limit(limit)))
    data = hydrate(db, rows, user)
    attending_ids = set(db.scalars(select(EventAttendance.post_id).where(
        EventAttendance.post_id.in_([p.id for p in rows]), EventAttendance.user_id == owner.id,
        EventAttendance.attending.is_(True)))) if rows else set()
    items = []
    for post in rows:
        item = data[('publication', post.id)]
        item.update(profile_attending=post.id in attending_ids,
                    profile_organizing=post.author_profile_id == profile.id or (not post.author_profile_id and post.user_id == owner.id))
        items.append(item)
    return {'items': items, 'has_more': offset + len(rows) < total, 'counts': counts,
            'is_owner': own, 'can_organize': creator,
            'visibility': owner.events_visibility if own else None}
