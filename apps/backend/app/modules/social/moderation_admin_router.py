"""Stage 3 API. Future UI belongs inside existing admin Configuration (stage 4)."""
import uuid
from typing import Annotated, Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.social.models import PostImage,PostBookCover
from app.modules.social.moderation_models import ModerationRevision,ModerationAudit,ModerationAttachment,ContentReport
from app.modules.social.moderation_private_router import entry
from app.modules.social.moderation_service import TARGETS,public_snapshot
from app.modules.social.moderation_decisions import authorize_admin,destination,decide,report_content,resolve_report
from app.modules.social.moderation_integration import http_claim,finish_http

router=APIRouter(tags=['moderation administration'])
DB=Annotated[Session,Depends(get_db)]
Viewer=Annotated[User,Depends(get_current_user)]
Kind=Literal['publication','review','comment']


def admin_dependency(db:DB,user:Viewer):return authorize_admin(db,user)


Admin=Annotated[User,Depends(admin_dependency)]


@router.get('/admin/moderation')
def queue(db:DB,admin:Admin,response:Response,kind:Kind|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    response.headers['Cache-Control']='private, no-store'
    conditions=[ModerationRevision.status=='pending_review',ModerationRevision.lifecycle=='active']
    if kind:conditions.append(getattr(ModerationRevision,TARGETS[kind][1]).is_not(None))
    total=db.scalar(select(func.count()).select_from(ModerationRevision).where(*conditions))
    rows=db.execute(select(ModerationRevision,User.display_name).join(User,User.id==ModerationRevision.author_user_id)
        .where(*conditions).order_by(ModerationRevision.created_at,ModerationRevision.id).offset(offset).limit(limit)).all()
    reports=db.scalar(select(func.count()).select_from(ContentReport).where(ContentReport.status=='pending'))
    return {'items':[{**entry(row),'author':name,'findings':row.findings,'title':row.proposal.get('title'),
        'excerpt':row.proposal.get('body','')[:240]} for row,name in rows],
        'total':total,'pending_reports':reports,'has_more':offset+len(rows)<total}


def content_context(db,item):
    kind,identifier=destination(item)
    record=db.get(TARGETS[kind][0],identifier)
    snapshot=public_snapshot(db,record) if record else None
    from app.modules.social.activity_access import resolve_activity,visible_comments
    from app.modules.social.moderation_service import _comment_parent
    visible=False
    try:
        if kind=='comment':
            resolve_activity(db,*_comment_parent(record))
            visible=bool(db.scalar(select(TARGETS[kind][0].id).where(TARGETS[kind][0].id==identifier,visible_comments())))
        else:
            resolve_activity(db,kind,identifier)
            visible=True
    except HTTPException as error:
        if error.status_code!=404:raise
    return {'kind':kind,'content_id':identifier,'current_content':snapshot,
            'public_version':snapshot if visible else None}


@router.get('/admin/moderation/history')
def history(db:DB,admin:Admin,response:Response,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    response.headers['Cache-Control']='private, no-store'
    query=select(ModerationAudit).where(ModerationAudit.action.in_(['approved','rejected','hidden','restored','dismissed']))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(ModerationAudit.created_at.desc(),ModerationAudit.id.desc()).offset(offset).limit(limit)).all()
    names=dict(db.execute(select(User.id,User.display_name).where(User.id.in_({r.actor_user_id for r in rows}))).all())
    return {'items':[{'id':r.id,'revision_id':r.revision_id,'report_id':r.report_id,'actor_user_id':r.actor_user_id,
                     'action':r.action,'reason':r.reason,'created_at':r.created_at,'context':r.context,
                     'administrator':names.get(r.actor_user_id,'Cuenta administradora')} for r in rows],
            'total':total,'has_more':offset+len(rows)<total}


@router.get('/admin/moderation/reports')
def reports(db:DB,admin:Admin,response:Response,status:Literal['pending','dismissed','hidden']='pending',
            limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    response.headers['Cache-Control']='private, no-store'
    total=db.scalar(select(func.count()).select_from(ContentReport).where(ContentReport.status==status))
    rows=db.scalars(select(ContentReport).where(ContentReport.status==status).order_by(ContentReport.created_at,ContentReport.id).offset(offset).limit(limit)).all()
    return {'items':enrich_reports(db,rows),'total':total,'has_more':offset+len(rows)<total}


def enrich_reports(db,rows):
    # Fetch authors and counts once per source, never once per report.
    authors={};counts={}
    for kind,(model,field) in TARGETS.items():
        ids={getattr(r,field) for r in rows if getattr(r,field) is not None}
        if not ids:continue
        owner=model.created_by_user_id if kind=='review' else model.user_id
        authors.update({(kind,key):name for key,name in db.execute(select(model.id,User.display_name)
            .join(User,User.id==owner).where(model.id.in_(ids))).all()})
        counts.update({(kind,key):count for key,count in db.execute(select(getattr(ContentReport,field),func.count())
            .where(getattr(ContentReport,field).in_(ids)).group_by(getattr(ContentReport,field))).all()})
    return [{**report_entry(r),'author':authors.get(destination(r),'Cuenta no disponible'),
             'report_count':counts.get(destination(r),0),'excerpt':r.content_snapshot.get('body','')[:240]} for r in rows]


def report_entry(r):
    kind,identifier=destination(r)
    return {'id':r.id,'kind':kind,'content_id':identifier,'reporter_user_id':r.reporter_user_id,
            'reason':r.reason,'detail':r.detail,'status':r.status,'created_at':r.created_at,
            'resolved_by':r.resolved_by,'resolved_at':r.resolved_at,'resolution_reason':r.resolution_reason}


@router.get('/admin/moderation/reports/{identifier}')
def report_detail(identifier:uuid.UUID,db:DB,admin:Admin,response:Response):
    response.headers['Cache-Control']='private, no-store'
    report=db.get(ContentReport,identifier)
    if report is None:raise HTTPException(404,'Reporte no encontrado')
    return {**enrich_reports(db,[report])[0],**content_context(db,report),'reported_content':report.content_snapshot}


@router.get('/admin/moderation/{identifier}')
def revision_detail(identifier:uuid.UUID,db:DB,admin:Admin,response:Response):
    response.headers['Cache-Control']='private, no-store'
    revision=db.get(ModerationRevision,identifier)
    if revision is None:raise HTTPException(404,'Revisión no encontrada')
    assets=db.scalars(select(ModerationAttachment).where(ModerationAttachment.revision_id==identifier)
                     .order_by(ModerationAttachment.role,ModerationAttachment.position)).all()
    author=db.get(User,revision.author_user_id)
    return {**entry(revision,True),'author':author.display_name if author else 'Cuenta no disponible',**content_context(db,revision),
            'attachments':[{'id':a.id,'role':a.role,'position':a.position,
              'url':f'/admin/moderation/{identifier}/attachments/{a.id}'} for a in assets]}


@router.get('/admin/moderation/{identifier}/attachments/{asset_id}')
def attachment(identifier:uuid.UUID,asset_id:uuid.UUID,db:DB,admin:Admin):
    asset=db.scalar(select(ModerationAttachment).where(ModerationAttachment.revision_id==identifier,ModerationAttachment.id==asset_id))
    if asset is None:raise HTTPException(404,'Adjunto no encontrado')
    return Response(asset.data,media_type=asset.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.get('/admin/moderation/content/publication/{identifier}/images/{asset_id}')
def original_image(identifier:uuid.UUID,asset_id:uuid.UUID,db:DB,admin:Admin):
    asset=db.scalar(select(PostImage).where(PostImage.post_id==identifier,PostImage.id==asset_id))
    if asset is None:raise HTTPException(404,'Imagen no encontrada')
    return Response(asset.data,media_type=asset.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.get('/admin/moderation/content/publication/{identifier}/cover')
def original_cover(identifier:uuid.UUID,db:DB,admin:Admin):
    asset=db.get(PostBookCover,identifier)
    if asset is None:raise HTTPException(404,'Portada no encontrada')
    return Response(asset.data,media_type=asset.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    action:Literal['approved','rejected']
    reason:str=Field(min_length=1,max_length=2000)
    expected_version:int=Field(ge=1)


@router.post('/admin/moderation/{identifier}/decision')
def decision(identifier:uuid.UUID,data:Decision,db:DB,admin:Admin,response:Response):
    response.headers['Cache-Control']='private, no-store'
    result=decide(db,admin,identifier,data.action,data.reason,data.expected_version)
    db.commit()
    return result


class ReportInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason:Literal['discrimination','harassment','threats','sexual_content','spam','other']
    detail:str=Field(default='',max_length=2000)


@router.post('/content-reports/{kind}/{identifier}',status_code=201)
def report(kind:Kind,identifier:uuid.UUID,data:ReportInput,db:DB,user:Viewer,response:Response):
    response.headers['Cache-Control']='private, no-store'
    result=report_content(db,user,kind,identifier,data.reason,data.detail)
    db.commit()
    return result


class ReportResolution(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    action:Literal['dismissed','hidden','restored']
    reason:str=Field(min_length=1,max_length=2000)
    expected_version:int=Field(ge=1)


@router.post('/admin/moderation/reports/{identifier}/resolution')
def report_resolution(identifier:uuid.UUID,data:ReportResolution,request:Request,response:Response,db:DB,admin:Admin):
    response.headers['Cache-Control']='private, no-store'
    claim=http_claim(db,admin,request,f'resolve:report:{identifier}',data.model_dump())
    if claim is not None and claim.result is not None:return claim.result
    result=resolve_report(db,admin,identifier,data.action,data.reason,data.expected_version)
    finish_http(db,claim,result)
    return result
