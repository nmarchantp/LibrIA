import uuid
from datetime import date
from typing import Annotated
from fastapi import APIRouter,Depends,Query,Response,HTTPException
from sqlalchemy import select,func,cast,Date
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
def calendar_events(db:DB,user:Viewer,response:Response,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),from_date:date|None=None,to_date:date|None=None):
    from app.modules.social.feed_service import hydrate
    response.headers['Cache-Control']='no-store'
    if from_date and to_date and (to_date<from_date or (to_date-from_date).days>366):
        raise HTTPException(422,'Selecciona un rango de fechas válido de hasta un año')
    query=select(Post).join(PublicationEvent,PublicationEvent.post_id==Post.id).where(visible_posts(),Post.source=='event',Post.publication_type=='event')
    # Compare dates in each event's own zone, including events spanning the range.
    local_start=cast(func.timezone(PublicationEvent.timezone,PublicationEvent.starts_at),Date)
    local_end=cast(func.timezone(PublicationEvent.timezone,func.coalesce(PublicationEvent.ends_at,PublicationEvent.starts_at)),Date)
    if from_date:query=query.where(local_end>=from_date)
    if to_date:query=query.where(local_start<=to_date)
    rows=list(db.scalars(query.order_by(PublicationEvent.starts_at,Post.id).offset(offset).limit(limit+1)))
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
