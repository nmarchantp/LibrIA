import uuid
from typing import Annotated
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.social.models import Post,PublicationEvent
from app.modules.social.activity_access import visible_posts
from app.modules.social.event_service import require_event,batch_event_details,set_attendance

router=APIRouter(prefix='/events',tags=['calendar events'])
DB=Annotated[Session,Depends(get_db)]
Viewer=Annotated[User,Depends(get_current_user)]


@router.get('')
def calendar_events(db:DB,user:Viewer,response:Response,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    from app.modules.social.feed_service import hydrate
    response.headers['Cache-Control']='no-store'
    rows=list(db.scalars(select(Post).join(PublicationEvent,PublicationEvent.post_id==Post.id).where(visible_posts(),Post.source=='event',Post.publication_type=='event')
        .order_by(PublicationEvent.starts_at,Post.id).offset(offset).limit(limit+1)))
    data=hydrate(db,rows[:limit],user)
    return {'items':[data[('publication',row.id)] for row in rows[:limit]],'has_more':len(rows)>limit}


@router.get('/{post_id}/attendance')
def attendance(post_id:uuid.UUID,db:DB,user:Viewer,response:Response):
    response.headers['Cache-Control']='no-store'
    require_event(db,post_id)
    return batch_event_details(db,[post_id],user.id)[post_id]


@router.put('/{post_id}/attendance')
def attend(post_id:uuid.UUID,db:DB,user:Viewer):return set_attendance(db,user,post_id,True)


@router.delete('/{post_id}/attendance')
def cancel(post_id:uuid.UUID,db:DB,user:Viewer):return set_attendance(db,user,post_id,False)
