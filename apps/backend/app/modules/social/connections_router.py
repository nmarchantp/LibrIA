"""Private connection lists and real follow notifications."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.identity_models import Profile
from app.modules.users.identities import personal_profile
from app.modules.social.models import ProfileFollow, FollowNotification
from app.modules.social.notification_inbox import router as notification_inbox_router

router = APIRouter(tags=['connections'])
router.include_router(notification_inbox_router)
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]


@router.get('/profiles/me/social-summary')
def social_summary(db: DB, user: Viewer, response: Response):
    from app.modules.library.models import LibraryEntry, Reading
    response.headers['Cache-Control'] = 'private, no-store'
    mine = personal_profile(db, user)
    active = (User.account_status == 'active', User.suspended_at.is_(None), Profile.kind == 'personal')
    followers = db.scalar(select(func.count()).select_from(ProfileFollow)
        .join(User, User.id == ProfileFollow.user_id).join(Profile, Profile.owner_user_id == User.id)
        .where(ProfileFollow.profile_id == mine.id, *active))
    following = db.scalar(select(func.count()).select_from(ProfileFollow)
        .join(Profile, Profile.id == ProfileFollow.profile_id).join(User, User.id == Profile.owner_user_id)
        .where(ProfileFollow.user_id == user.id, *active))
    finished = db.scalar(select(func.count(func.distinct(Reading.work_id))).join(LibraryEntry, LibraryEntry.id == Reading.library_entry_id)
        .where(LibraryEntry.user_id == user.id, Reading.status == 'finished'))
    return {'profile_id': mine.id, 'finished_books': finished, 'followers': followers, 'following': following}


@router.get('/profiles/discover/people')
def discover_people(db: DB, user: Viewer, response: Response,
                    q: str = Query('', max_length=100), offset: int = Query(0, ge=0), limit: int = Query(12, ge=1, le=30)):
    response.headers['Cache-Control'] = 'private, no-store'
    followed = select(ProfileFollow.profile_id).where(ProfileFollow.user_id == user.id)
    query = select(Profile, User).join(User, User.id == Profile.owner_user_id).where(
        Profile.kind == 'personal', User.id != user.id, User.account_status == 'active', User.suspended_at.is_(None), Profile.id.not_in(followed))
    if q.strip():
        query = query.where(User.display_name.icontains(q.strip(), autoescape=True))
    rows = db.execute(query.order_by(User.display_name, Profile.id).offset(offset).limit(limit + 1)).all()
    return {'items': [{'id': p.id, 'display_name': u.display_name, 'avatar_url': u.avatar_url} for p, u in rows[:limit]], 'has_more': len(rows) > limit}


@router.get('/profiles/me/connections')
def connections(db: DB, user: Viewer, response: Response,
                kind: Literal['followers', 'following'] = 'following',
                offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=50)):
    response.headers['Cache-Control'] = 'private, no-store'
    mine = personal_profile(db, user)
    if kind == 'following':
        query = select(Profile, User).join(User, User.id == Profile.owner_user_id).join(ProfileFollow, ProfileFollow.profile_id == Profile.id).where(ProfileFollow.user_id == user.id)
    else:
        query = select(Profile, User).join(User, User.id == Profile.owner_user_id).join(ProfileFollow, ProfileFollow.user_id == User.id).where(ProfileFollow.profile_id == mine.id)
    rows = db.execute(query.where(Profile.kind == 'personal', User.account_status == 'active', User.suspended_at.is_(None))
        .order_by(User.display_name, Profile.id).offset(offset).limit(limit + 1)).all()
    return {'items': [{'id': p.id, 'display_name': u.display_name, 'avatar_url': u.avatar_url} for p, u in rows[:limit]], 'has_more': len(rows) > limit}


@router.get('/me/follow-notifications')
def notifications(db: DB, user: Viewer, response: Response,
                  offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=50)):
    response.headers['Cache-Control'] = 'private, no-store'
    rows = db.execute(select(FollowNotification, Profile, User).join(User, User.id == FollowNotification.actor_user_id)
        .join(Profile, (Profile.owner_user_id == User.id) & (Profile.kind == 'personal'))
        .where(FollowNotification.recipient_user_id == user.id, User.account_status == 'active', User.suspended_at.is_(None))
        .order_by(FollowNotification.created_at.desc(), FollowNotification.id.desc()).offset(offset).limit(limit + 1)).all()
    return {'items': [{'id': n.id, 'profile_id': p.id, 'display_name': u.display_name, 'read_at': n.read_at,
                      'created_at': n.created_at, 'message': f'{u.display_name} comenzó a seguirte. Visita su perfil para seguirle y permitirle ver tu perfil privado.'}
                     for n, p, u in rows[:limit]], 'has_more': len(rows) > limit}


@router.put('/me/follow-notifications/{identifier}/read')
def read_notification(identifier: uuid.UUID, db: DB, user: Viewer):
    row = db.scalar(select(FollowNotification).where(FollowNotification.id == identifier, FollowNotification.recipient_user_id == user.id).with_for_update())
    if row is None:
        raise HTTPException(404, 'Notificación no encontrada')
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
    db.commit()
    return {'id': row.id, 'read_at': row.read_at}
