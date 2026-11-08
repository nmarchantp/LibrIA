"""A dated event is the same publication, never a title-matched copy."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select,func
from sqlalchemy.dialects.postgresql import insert
from app.modules.social.activity_access import resolve_activity
from app.modules.social.models import PublicationEvent,EventAttendance,EventScheduleUpdate


def validate_event_change(db,post,publication_type,details,title):
    existing=db.get(PublicationEvent,post.id)
    if details and (publication_type!='event' or not title):
        raise HTTPException(422,'Los datos del evento requieren tipo Evento y un título')
    if existing and publication_type!='event' and db.scalar(select(EventAttendance.post_id).where(EventAttendance.post_id==post.id,EventAttendance.attending).limit(1)):
        raise HTTPException(422,'Este evento tiene asistentes. Conserva su tipo o elimínalo con confirmación.')


def sync_event(db,post,details,user):
    if details is None:return
    start,end=details.instants()
    event=db.get(PublicationEvent,post.id)
    if event is None:
        event=PublicationEvent(post_id=post.id,starts_at=start,ends_at=end,timezone=details.timezone,
            location=details.location,organizer=details.organizer,category=details.category,schedule_revision=1)
        db.add(event)
    else:
        if (event.starts_at,event.ends_at,event.timezone)!=(start,end,details.timezone):
            event.schedule_revision+=1
            db.add(EventScheduleUpdate(post_id=post.id,changed_by=user.id,revision=event.schedule_revision,
                previous_start=event.starts_at,previous_end=event.ends_at,previous_timezone=event.timezone,
                new_start=start,new_end=end,new_timezone=details.timezone))
        event.starts_at,event.ends_at,event.timezone=start,end,details.timezone
        event.location,event.organizer,event.category=details.location,details.organizer,details.category
    # Attendance belongs to post_id and is deliberately never rewritten here.


def batch_event_details(db,post_ids,viewer_id):
    if not post_ids:return {}
    events=list(db.scalars(select(PublicationEvent).where(PublicationEvent.post_id.in_(post_ids))))
    ids=[event.post_id for event in events]
    if not ids:return {}
    counts=dict(db.execute(select(EventAttendance.post_id,func.count()).where(EventAttendance.post_id.in_(ids),EventAttendance.attending).group_by(EventAttendance.post_id)).all())
    attending=set(db.scalars(select(EventAttendance.post_id).where(EventAttendance.post_id.in_(ids),EventAttendance.user_id==viewer_id,EventAttendance.attending)))
    updates={row.post_id:row for row in db.scalars(select(EventScheduleUpdate).where(EventScheduleUpdate.post_id.in_(ids)).distinct(EventScheduleUpdate.post_id).order_by(EventScheduleUpdate.post_id,EventScheduleUpdate.revision.desc()))}
    result={};observed=datetime.now(timezone.utc).isoformat(timespec='microseconds')
    for event in events:
        zone=ZoneInfo(event.timezone);start=event.starts_at.astimezone(zone);end=event.ends_at.astimezone(zone) if event.ends_at else None
        update=updates.get(event.post_id)
        result[event.post_id]={'id':str(event.post_id),'starts_at':event.starts_at.isoformat(),'ends_at':event.ends_at.isoformat() if event.ends_at else None,
            'start_date':start.date().isoformat(),'start_time':start.strftime('%H:%M'),'end_date':end.date().isoformat() if end else None,'end_time':end.strftime('%H:%M') if end else None,
            'timezone':event.timezone,'location':event.location,'organizer':event.organizer,'category':event.category,
            'attending':event.post_id in attending,'attendee_count':counts.get(event.post_id,0),'observed_at':observed,
            'schedule_revision':event.schedule_revision,'schedule_update':{'changed_at':update.changed_at.isoformat(),
                'previous_start':update.previous_start.isoformat(),'previous_end':update.previous_end.isoformat() if update.previous_end else None,'previous_timezone':update.previous_timezone} if update else None}
    return result


def require_event(db,post_id,lock=False):
    post,_=resolve_activity(db,'publication',post_id,lock=lock)
    if post.publication_type!='event' or post.source!='event' or not db.get(PublicationEvent,post.id):
        raise HTTPException(404,'Evento con fecha no encontrado')
    return post


def set_attendance(db,user,post_id,enabled):
    require_event(db,post_id,lock=True)
    if enabled:
        db.execute(insert(EventAttendance).values(post_id=post_id,user_id=user.id,attending=True)
            .on_conflict_do_update(index_elements=[EventAttendance.post_id,EventAttendance.user_id],set_={'attending':True,'updated_at':datetime.now(timezone.utc)},where=EventAttendance.attending.is_(False)))
    else:
        row=db.get(EventAttendance,(post_id,user.id))
        if row and row.attending:row.attending=False;row.updated_at=datetime.now(timezone.utc)
    db.flush()
    result=batch_event_details(db,[post_id],user.id)[post_id]
    db.commit()
    return result
