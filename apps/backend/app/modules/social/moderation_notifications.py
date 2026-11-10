"""Notification events share the transaction of their revision or decision."""
import uuid
from datetime import datetime,timezone
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from sqlalchemy import select,func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.social.moderation_models import ModerationNotification,ModerationRevision
from app.modules.social.moderation_service import require_active

MESSAGES={
    'pending_review':'Tu contenido fue enviado a revisión. Te avisaremos cuando esté aprobado',
    'approved':'Tu publicación fue aprobada y ya está disponible en LibrIAverse',
    'rejected':'Tu contenido no fue aprobado porque incumple nuestras normas de convivencia',
}


def notify(db,revision,kind):
    db.execute(insert(ModerationNotification).values(id=uuid.uuid4(),recipient_user_id=revision.author_user_id,
        revision_id=revision.id,kind=kind).on_conflict_do_nothing())


router=APIRouter(prefix='/me/notifications',tags=['private moderation notifications'])
DB=Annotated[Session,Depends(get_db)]
Viewer=Annotated[User,Depends(get_current_user)]


@router.get('')
def inbox(db:DB,user:Viewer,response:Response,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0)):
    require_active(user)
    response.headers['Cache-Control']='private, no-store'
    own=ModerationNotification.recipient_user_id==user.id
    unread=db.scalar(select(func.count()).select_from(ModerationNotification).where(own,ModerationNotification.read_at.is_(None)))
    rows=db.execute(select(ModerationNotification,ModerationRevision).join(ModerationRevision,
        ModerationRevision.id==ModerationNotification.revision_id).where(own,ModerationRevision.author_user_id==user.id)
        .order_by(ModerationNotification.created_at.desc(),ModerationNotification.id.desc()).offset(offset).limit(limit+1)).all()
    return {'items':[{'id':n.id,'revision_id':n.revision_id,'kind':n.kind,'message':MESSAGES[n.kind],
        'created_at':n.created_at,'read_at':n.read_at,'decision_reason':r.decision_reason if n.kind=='rejected' else None}
        for n,r in rows[:limit]],'has_more':len(rows)>limit,'unread_count':unread}


@router.put('/{identifier}/read')
def mark_read(identifier:uuid.UUID,db:DB,user:Viewer,response:Response):
    require_active(user)
    response.headers['Cache-Control']='private, no-store'
    row=db.scalar(select(ModerationNotification).where(ModerationNotification.id==identifier,
        ModerationNotification.recipient_user_id==user.id).with_for_update())
    if row is None:raise HTTPException(404,'Notificación no encontrada')
    if row.read_at is None:row.read_at=datetime.now(timezone.utc)
    result={'id':row.id,'read_at':row.read_at}
    db.commit()
    return result
