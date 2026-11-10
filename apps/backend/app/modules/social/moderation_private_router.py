"""Author-only status/proposal access. Administrative workflow is not implemented."""
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.social.moderation_models import ModerationRevision, ModerationAttachment
from app.modules.social.moderation_service import private_revision

router=APIRouter(prefix='/me/moderation',tags=['own moderation status'])
DB=Annotated[Session,Depends(get_db)]
Viewer=Annotated[User,Depends(get_current_user)]


def entry(revision, detail=False):
    kind,identifier=next((kind,getattr(revision,field)) for kind,field in (
        ('publication','post_id'),('review','review_id'),('comment','comment_id')) if getattr(revision,field))
    result={'id':revision.id,'kind':kind,'content_id':identifier,'status':revision.status,
        'lifecycle':revision.lifecycle,'created_at':revision.created_at,
        'base_version':revision.base_version,'decision_reason':revision.decision_reason,
        'title':revision.proposal.get('title'),'excerpt':revision.proposal.get('body','')[:240],
        'decided_at':revision.decided_at}
    if detail:result.update(proposal=revision.proposal,findings=revision.findings,ruleset_version=revision.ruleset_version)
    return result


@router.get('')
def own_status(db:DB,user:Viewer,response:Response,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0)):
    response.headers['Cache-Control']='private, no-store'
    rows=list(db.scalars(select(ModerationRevision).where(ModerationRevision.author_user_id==user.id)
        .order_by(ModerationRevision.created_at.desc(),ModerationRevision.id.desc()).offset(offset).limit(limit+1)))
    return {'items':[entry(item) for item in rows[:limit]],'has_more':len(rows)>limit}


@router.get('/{identifier}')
def own_detail(identifier:uuid.UUID,db:DB,user:Viewer,response:Response):
    response.headers['Cache-Control']='private, no-store'
    revision=private_revision(db,user,identifier)
    assets=db.scalars(select(ModerationAttachment).where(ModerationAttachment.revision_id==revision.id)
        .order_by(ModerationAttachment.role,ModerationAttachment.position)).all()
    return {**entry(revision,True),'attachments':[{'id':asset.id,'role':asset.role,'position':asset.position,
        'url':f'/me/moderation/{revision.id}/attachments/{asset.id}'} for asset in assets]}


@router.get('/{identifier}/attachments/{asset_id}')
def own_asset(identifier:uuid.UUID,asset_id:uuid.UUID,db:DB,user:Viewer):
    private_revision(db,user,identifier)
    asset=db.scalar(select(ModerationAttachment).where(ModerationAttachment.id==asset_id,ModerationAttachment.revision_id==identifier))
    if asset is None:raise HTTPException(404,'Adjunto no encontrado')
    return Response(asset.data,media_type=asset.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
