"""Administrative operations. Caller owns the transaction; lock parent before revision/report."""
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.modules.social.models import Post, PostComment, PostImage, PostBookCover, Review
from app.modules.social.moderation_models import ContentReport, ModerationRevision, ModerationAudit, ModerationAttachment
from app.modules.social.moderation_service import (
    TARGETS, require_active, require_moderation_admin, assert_revision_current,
    validate_proposal, validate_attachments, ProposedAttachment, _comment_parent, public_snapshot,
)
from app.modules.social.activity_access import resolve_activity, visible_comments
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission, Profile


def authorize_admin(db,user):
    # Hold the real account and permission until commit, including against revocation.
    current=db.scalar(select(User).where(User.id==user.id).with_for_update(read=True)
                      .execution_options(populate_existing=True))
    if current is None:raise HTTPException(403,'Cuenta no autorizada')
    permission=db.scalar(select(AccountPermission).where(AccountPermission.user_id==user.id,
        AccountPermission.permission=='admin').with_for_update(read=True).execution_options(populate_existing=True))
    require_moderation_admin(db,current)
    if permission is None:raise HTTPException(403,'Se requiere permiso administrativo vigente')
    return current


def destination(item):
    return next((kind,getattr(item,column)) for kind,(_,column) in TARGETS.items() if getattr(item,column) is not None)


def locked_target(db,kind,identifier,*,public=False):
    if kind not in TARGETS:raise HTTPException(422,'Tipo de contenido no admitido')
    model,_=TARGETS[kind]
    if kind=='comment':
        initial=db.get(PostComment,identifier)
        if initial is None:raise HTTPException(404,'Contenido no encontrado')
        parent_kind,parent_id=_comment_parent(initial)
        # Administrative hiding/restoring may inspect a now-private parent, but
        # comment approval and reports must still authorize that parent.
        if public:resolve_activity(db,parent_kind,parent_id,lock=True)
        else:
            from app.modules.social.activity_access import MODELS
            db.scalar(select(MODELS[parent_kind]).where(MODELS[parent_kind].id==parent_id).with_for_update())
    record=db.scalar(select(model).where(model.id==identifier).with_for_update().execution_options(populate_existing=True))
    if record is None:raise HTTPException(404,'Contenido no encontrado')
    if public:
        if kind=='comment':
            if not db.scalar(select(PostComment.id).where(PostComment.id==identifier,visible_comments())):
                raise HTTPException(404,'Comentario no encontrado')
        else:resolve_activity(db,kind,identifier)
    return record


def ensure_not_removed(record):
    if getattr(record,'deleted_at',None) is not None:
        raise HTTPException(409,'El contenido fue eliminado')


def apply_publication(db,record,proposal,assets,author):
    from app.modules.users.identities import lock_publishing_user, require_influencer_publication_permission
    author = lock_publishing_user(db, author)
    from app.modules.social.publication_management import PublicationEdit, resolve_publication_work
    from app.modules.social.event_service import validate_event_change,sync_event
    from app.modules.users.identities import publication_role, require_actor
    data=PublicationEdit.model_validate(proposal)
    profile=db.get(Profile,record.author_profile_id) if record.author_profile_id else None
    if profile:require_actor(db,author,profile.id,manage=True)
    require_active(author)
    role='admin' if author.role=='admin' and (not profile or profile.kind=='personal') else publication_role(db,profile) if profile else author.role
    require_influencer_publication_permission(author, data.publication_type, data.book_ref or data.work_id, status=409)
    if role=='lector' and not (data.publication_type in ('note','theory') and (data.book_ref or data.work_id)):
        raise HTTPException(409,'El autor ya no puede publicar este tipo de contenido')
    validate_event_change(db,record,data.publication_type,data.event_details,data.title)
    same_book,work_id,edition_id=resolve_publication_work(db,record,data)
    images=list(db.scalars(select(PostImage).where(PostImage.post_id==record.id)))
    selected={image.id for image in images} if data.existing_image_ids is None else set(data.existing_image_ids)
    for image in images:
        if image.id not in selected:db.delete(image)
    for asset in assets:
        if asset.role=='image':db.add(PostImage(post_id=record.id,content_type=asset.content_type,data=asset.data))
    cover=db.get(PostBookCover,record.id)
    new_cover=next((asset for asset in assets if asset.role=='cover'),None)
    if new_cover:
        if cover is None:cover=PostBookCover(post_id=record.id);db.add(cover)
        cover.revision,cover.content_type,cover.data=uuid.uuid4(),new_cover.content_type,new_cover.data
    elif cover and (data.cover_mode=='catalog' or not same_book or not (work_id or data.book_ref)):
        db.delete(cover)
    record.title,record.body,record.source,record.publication_type=data.title,data.body,data.source,data.publication_type
    # Keep the original publication role, including after permission changes.
    record.book_ref,record.book_title,record.work_id,record.edition_id=data.book_ref,data.book_title,work_id,edition_id
    record.updated_at=datetime.now(timezone.utc)
    sync_event(db,record,data.event_details,author)


def apply_review(db,record,proposal,admin):
    from app.modules.social.schemas import ReviewUpdate
    from app.modules.social.reviews_router import validate_edition,require_current_revision,record_revision
    data=ReviewUpdate.model_validate(proposal)
    require_current_revision(db,record)
    validate_edition(db,record.work_id,data.edition_id)
    now=datetime.now(timezone.utc)
    record.body,record.rating,record.dimension_ratings,record.is_spoiler=data.body,data.rating,data.dimension_ratings,data.is_spoiler
    record.edition_id,record.status=data.edition_id,data.status
    if record.published_at is None:record.published_at=now
    # A newly pending review has no editorial revision yet.
    from app.modules.social.models import ReviewRevision
    if db.get(ReviewRevision,(record.id,record.revision_number)) is not None:record.revision_number+=1
    record.updated_at=now
    record_revision(db,record,admin,now)


def decision_result(revision):
    return {'id':str(revision.id),'status':revision.status,'decided_by':str(revision.decided_by),
            'decided_at':revision.decided_at.astimezone(timezone.utc).isoformat(),'reason':revision.decision_reason}


def decide(db,admin,identifier,action,reason,expected_version):
    admin=authorize_admin(db,admin)
    initial=db.get(ModerationRevision,identifier)
    if initial is None:raise HTTPException(404,'Revisión no encontrada')
    kind,target_id=destination(initial)
    if kind == 'publication':
        from app.modules.users.identities import lock_publishing_user
        lock_publishing_user(db, db.get(User, initial.author_user_id))
    record=locked_target(db,kind,target_id)
    revision=db.scalar(select(ModerationRevision).where(ModerationRevision.id==identifier).with_for_update()
                       .execution_options(populate_existing=True))
    if revision.decided_at is not None:
        if revision.status==action and revision.decision_reason==reason and revision.base_version==expected_version:
            return decision_result(revision)
        raise HTTPException(409,'La revisión ya tiene una decisión definitiva')
    if revision.status!='pending_review' or revision.base_version!=expected_version:
        raise HTTPException(409,'La revisión no está pendiente o su versión cambió')
    ensure_not_removed(record)
    assert_revision_current(db,record,revision)
    if record.moderation_hidden:raise HTTPException(409,'El contenido está oculto preventivamente')
    previous=public_snapshot(db,record)
    if action=='approved':
        if kind=='comment':resolve_activity(db,*_comment_parent(record))
        proposal=validate_proposal(db,record,kind,revision.proposal)
        assets=list(db.scalars(select(ModerationAttachment).where(ModerationAttachment.revision_id==revision.id)
                              .order_by(ModerationAttachment.role,ModerationAttachment.position)))
        validate_attachments(db,record,proposal,[ProposedAttachment(a.role,a.content_type,a.data) for a in assets])
        if kind=='publication':
            author=db.get(User,revision.author_user_id)
            apply_publication(db,record,proposal,assets,author)
        elif kind=='review':
            from app.modules.users.identities import require_actor
            author=db.get(User,revision.author_user_id)
            require_active(author)
            require_actor(db,author,record.author_profile_id)
            apply_review(db,record,proposal,admin)
        else:
            if record.body!=proposal['body']:record.edited_at=datetime.now(timezone.utc)
            record.body=proposal['body']
        record.moderation_status='approved'
        record.moderation_version+=1
    elif record.moderation_status=='pending_review':
        record.moderation_status='rejected'
        record.moderation_version+=1
    revision.status=action
    revision.decided_by=admin.id
    revision.decided_at=datetime.now(timezone.utc)
    revision.decision_reason=reason
    db.flush()
    db.add(ModerationAudit(revision_id=revision.id,actor_user_id=admin.id,action=action,reason=reason,
                          context={'previous':previous,'result':public_snapshot(db,record)}))
    db.flush()
    from app.modules.social.moderation_notifications import notify
    notify(db,revision,action)
    return decision_result(revision)


def report_content(db,user,kind,identifier,reason,detail):
    require_active(user)
    record=locked_target(db,kind,identifier,public=True)
    field=TARGETS[kind][1]
    inserted=db.scalar(insert(ContentReport).values(id=uuid.uuid4(),reporter_user_id=user.id,
        **{field:identifier},reason=reason,detail=detail,content_snapshot=public_snapshot(db,record)).on_conflict_do_nothing().returning(ContentReport.id))
    report=db.scalar(select(ContentReport).where(ContentReport.reporter_user_id==user.id,getattr(ContentReport,field)==identifier))
    if inserted:
        db.add(ModerationAudit(report_id=report.id,actor_user_id=user.id,action='reported',reason=reason))
    db.flush()
    return {'id':str(report.id),'status':report.status}


def resolve_report(db,admin,identifier,action,reason,expected_version):
    admin=authorize_admin(db,admin)
    initial=db.get(ContentReport,identifier)
    if initial is None:raise HTTPException(404,'Reporte no encontrado')
    kind,target_id=destination(initial)
    record=locked_target(db,kind,target_id)
    report=db.scalar(select(ContentReport).where(ContentReport.id==identifier).with_for_update()
                     .execution_options(populate_existing=True))
    if action!='restored' and report.status!='pending':
        if report.status==action and report.resolution_reason==reason:
            return {'id':str(report.id),'status':report.status,'moderation_version':record.moderation_version}
        raise HTTPException(409,'El reporte ya está resuelto')
    previous=public_snapshot(db,record)
    if action in ('hidden','restored'):
        if record.moderation_version!=expected_version:raise HTTPException(409,'El contenido cambió; vuelve a revisarlo')
        ensure_not_removed(record)
        if record.moderation_status!='approved':raise HTTPException(409,'El contenido no tiene una versión aprobada')
        if action=='restored':
            if report.status!='hidden' or not record.moderation_hidden:
                raise HTTPException(409,'No hay una ocultación que restituir')
            # A historical report must not restore a later hold issued for another
            # report. Content versions order visibility actions even when DB times tie.
            field=TARGETS[kind][1]
            last_hold=db.scalar(select(ModerationAudit).join(ContentReport,ContentReport.id==ModerationAudit.report_id)
                .where(getattr(ContentReport,field)==target_id,ModerationAudit.action.in_(['hidden','restored']))
                .order_by(ModerationAudit.context['result']['moderation_version'].as_integer().desc()).limit(1))
            if last_hold is None or last_hold.action!='hidden' or last_hold.report_id!=report.id:
                raise HTTPException(409,'La ocultación vigente corresponde a otro reporte')
            if kind=='review':
                if record.status!='published':raise HTTPException(409,'La reseña ya no está publicada')
                from app.modules.social.reviews_router import require_current_revision
                require_current_revision(db,record)
            if kind=='comment':resolve_activity(db,*_comment_parent(record))
            record.moderation_hidden=False
        else:
            if record.moderation_hidden:raise HTTPException(409,'El contenido ya está oculto')
            record.moderation_hidden=True
            from app.modules.social.moderation_integration import retire_pending
            retire_pending(db,admin,record,kind,'withdrawn')
        record.moderation_version+=1
    if action!='restored':
        report.status=action
        report.resolved_by,report.resolved_at,report.resolution_reason=admin.id,datetime.now(timezone.utc),reason
    db.flush()
    db.add(ModerationAudit(report_id=report.id,actor_user_id=admin.id,action=action,reason=reason,
                          context={'previous':previous,'result':public_snapshot(db,record)}))
    db.flush()
    return {'id':str(report.id),'status':report.status,'moderation_hidden':record.moderation_hidden,
            'moderation_version':record.moderation_version}
