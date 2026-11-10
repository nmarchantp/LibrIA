import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.social.activity_access import resolve_activity, visible_comments
from app.modules.social.moderation_integration import analyze_fields,http_claim,finish_http,receipt,check_version,retire_pending
from app.modules.social.moderation_service import prepare_edit
from app.modules.social.interaction_service import DESTINATIONS, add_comment, like, record_view, stats
from app.modules.social.models import PostComment
from app.modules.social.router import as_comment_response
from app.modules.social.schemas import CommentResponse
from app.modules.users.identities import personal_profile
from app.modules.users.models import User

router = APIRouter(prefix="/activities", tags=["activity interactions"])
Kind = Literal["publication", "review", "reading_event"]
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]


class Capabilities(BaseModel):
    can_like: bool
    can_comment: bool
    can_view: bool
    can_register_view: bool


class InteractionCounts(BaseModel):
    like_count: int
    liked_by_me: bool
    comment_count: int
    view_count: int
    capabilities: Capabilities
    observed_at: str


class ViewIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["open", "open_comments"]


class CommentResult(BaseModel):
    comment: CommentResponse
    interactions: InteractionCounts


class ActivityCommentCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


def validate_comment(kind,body):
    if kind=='reading_event' and len(body.split())>200:
        raise HTTPException(422,'El comentario admite un máximo de 200 palabras.')
    if kind!='reading_event' and len(body)>1000:
        raise HTTPException(422,'El comentario admite un máximo de 1000 caracteres.')


@router.get("/{kind}/{identifier}", response_model=InteractionCounts)
def counts(kind: Kind, identifier: uuid.UUID, db: DB, user: Viewer, response: Response):
    response.headers["Cache-Control"] = "no-store"
    _, owners = resolve_activity(db, kind, identifier)
    return stats(db, kind, identifier, user.id, owners)


@router.put("/{kind}/{identifier}/view", response_model=InteractionCounts)
def view(kind: Kind, identifier: uuid.UUID, intent: ViewIntent, db: DB, user: Viewer):
    _, owners = resolve_activity(db, kind, identifier, lock=True)
    record_view(db, kind, identifier, user.id, owners)
    result = stats(db, kind, identifier, user.id, owners)
    db.commit()
    return result


@router.put("/{kind}/{identifier}/like", response_model=InteractionCounts)
def put_like(kind: Kind, identifier: uuid.UUID, db: DB, user: Viewer):
    result = like(db, kind, identifier, user.id, True)
    db.commit()
    return result


@router.delete("/{kind}/{identifier}/like", response_model=InteractionCounts)
def delete_like(kind: Kind, identifier: uuid.UUID, db: DB, user: Viewer):
    result = like(db, kind, identifier, user.id, False)
    db.commit()
    return result


@router.get("/{kind}/{identifier}/comments", response_model=list[CommentResponse])
def comments(kind: Kind, identifier: uuid.UUID, db: DB, user: Viewer, response:Response,limit: int = Query(100, ge=1, le=100)):
    response.headers['Cache-Control']='private, no-store'
    resolve_activity(db, kind, identifier)
    target = getattr(PostComment, DESTINATIONS[kind][1])
    rows = db.execute(select(PostComment, User.display_name, User.role).join(User, User.id == PostComment.user_id)
        .where(target == identifier,visible_comments()).order_by(PostComment.created_at.desc(), PostComment.id.desc()).limit(limit)).all()
    return [as_comment_response(comment, name, role) for comment, name, role in reversed(rows)]


@router.post("/{kind}/{identifier}/comments", response_model=CommentResult, status_code=201)
def comment(kind: Kind, identifier: uuid.UUID, data: ActivityCommentCreate, db: DB, user: Viewer,request:Request,response:Response):
    # Authorize before checking the commenter's personal identity.
    resolve_activity(db, kind, identifier, lock=True)
    validate_comment(kind,data.body)
    response.headers['Cache-Control']='no-store'
    claim=http_claim(db,user,request,f'create:comment:{kind}:{identifier}',{'body':data.body})
    if claim is not None and claim.result is not None:return claim.result
    profile = personal_profile(db, user)
    item, result = add_comment(db, kind, identifier, user.id, profile.id, data.body)
    value = as_comment_response(item, user.display_name, user.role).model_copy(update=receipt(item,getattr(item,'_pending_revision',None)))
    result={"comment": value, "interactions": result}
    finish_http(db,claim,result)
    return result


def own_comment(db,user,kind,identifier,comment_id):
    _,owners=resolve_activity(db,kind,identifier,lock=True)
    target=getattr(PostComment,DESTINATIONS[kind][1])
    item=db.scalar(select(PostComment).where(PostComment.id==comment_id,target==identifier,PostComment.user_id==user.id,PostComment.deleted_at.is_(None)).with_for_update())
    if item is None:raise HTTPException(404,'Comentario propio no encontrado')
    return item,owners


@router.put('/{kind}/{identifier}/comments/{comment_id}',response_model=CommentResult)
def edit_comment(kind:Kind,identifier:uuid.UUID,comment_id:uuid.UUID,data:ActivityCommentCreate,db:DB,user:Viewer,request:Request,response:Response):
    item,owners=own_comment(db,user,kind,identifier,comment_id)
    validate_comment(kind,data.body)
    response.headers['Cache-Control']='no-store'
    claim=http_claim(db,user,request,f'update:comment:{item.id}',{'body':data.body})
    if claim is not None and claim.result is not None:return claim.result
    check_version(request,item)
    revision=None
    if analyze_fields({'body':data.body}).flagged:
        revision=prepare_edit(db,user,'comment',item.id,{'body':data.body},request_key=uuid.uuid4(),expected_version=item.moderation_version)
    else:
        retire_pending(db,user,item,'comment')
        if item.body!=data.body:item.body,item.edited_at=data.body,datetime.now(timezone.utc)
        item.moderation_status='approved'
        item.moderation_version+=1
    db.flush()
    result={'comment':as_comment_response(item,user.display_name,user.role).model_copy(update=receipt(item,revision)),'interactions':stats(db,kind,identifier,user.id,owners)}
    finish_http(db,claim,result)
    return result


@router.delete('/{kind}/{identifier}/comments/{comment_id}')
def delete_comment(kind:Kind,identifier:uuid.UUID,comment_id:uuid.UUID,db:DB,user:Viewer):
    item,owners=own_comment(db,user,kind,identifier,comment_id)
    item.deleted_at=datetime.now(timezone.utc)
    item.moderation_version+=1
    retire_pending(db,user,item,'comment','withdrawn')
    db.flush()
    result={'interactions':stats(db,kind,identifier,user.id,owners)}
    db.commit()
    return result
