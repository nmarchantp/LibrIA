"""Transaction-owned preparation services. No routes or public mutations in phase 1.

Callers must commit the request, proposal, assets and audit together or roll back
all of them. A prepared 'approved' proposal is not applied to public content here.
"""
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import inspect, select, Numeric
from sqlalchemy.dialects.postgresql import insert
from app.modules.social.models import Post, PostComment, PostImage, PostBookCover, PublicationEvent, Review
from app.modules.social.moderation_models import ModerationRequest, ModerationRevision, ModerationAttachment, ModerationAudit
from app.modules.social.moderation_rules import analyze_content, Analysis
from app.modules.social.activity_access import resolve_activity
from app.modules.users.identities import require_actor
from app.modules.users.roles_router import get_admin

TARGETS = {'publication': (Post, 'post_id'), 'review': (Review, 'review_id'), 'comment': (PostComment, 'comment_id')}


def canonical_json(value):
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def require_active(user):
    if user.account_status != 'active' or user.suspended_at is not None:
        raise HTTPException(403, 'La cuenta no puede enviar contenido')


def require_moderation_admin(db, user):
    require_active(user)
    return get_admin(user, db)


def claim_request(db, user, operation, key, payload):
    """INSERT conflicts wait for the other transaction; no read-then-insert race."""
    require_active(user)
    if not isinstance(key, uuid.UUID) or not operation or len(operation) > 160:
        raise HTTPException(422, 'Identificador de solicitud inválido')
    digest = fingerprint(payload)
    db.execute(insert(ModerationRequest).values(user_id=user.id, operation=operation, key=key, payload_hash=digest)
               .on_conflict_do_nothing())
    request = db.scalar(select(ModerationRequest).where(ModerationRequest.user_id == user.id,
        ModerationRequest.operation == operation, ModerationRequest.key == key)
        .with_for_update().execution_options(populate_existing=True))
    if request.payload_hash != digest:
        raise HTTPException(409, 'La misma clave ya se utilizó con otro contenido')
    return request


def complete_request(request, result):
    encoded = jsonable_encoder(result)
    if request.result is not None and request.result != encoded:
        raise HTTPException(409, 'La solicitud ya tiene otro resultado')
    request.result = encoded


def _comment_parent(comment):
    for kind, column in [('publication','post_id'), ('review','review_id'), ('reading_event','reading_event_id')]:
        if getattr(comment, column) is not None:
            return kind, getattr(comment, column)
    raise HTTPException(404, 'Comentario no encontrado')


def owned_target(db, user, kind, identifier):
    require_active(user)
    if kind not in TARGETS:
        raise HTTPException(422, 'Tipo de contenido no admitido')
    model, _ = TARGETS[kind]
    if kind == 'comment':
        # Match the existing parent-before-comment lock ordering.
        initial = db.get(PostComment, identifier)
        if initial is None or initial.user_id != user.id:
            raise HTTPException(404, 'Comentario propio no encontrado')
        parent_kind, parent_id = _comment_parent(initial)
        resolve_activity(db, parent_kind, parent_id, lock=True)
    record = db.scalar(select(model).where(model.id == identifier).with_for_update()
                       .execution_options(populate_existing=True))
    if record is None:
        raise HTTPException(404, 'Contenido propio no encontrado')
    if kind == 'publication':
        if record.deleted_at is not None:
            raise HTTPException(404, 'Publicación no encontrada')
        if record.author_profile_id:
            require_actor(db, user, record.author_profile_id, manage=True)
        elif record.user_id != user.id:
            raise HTTPException(403, 'No puedes editar esta publicación')
    elif kind == 'review':
        if record.created_by_user_id != user.id:
            raise HTTPException(404, 'Reseña propia no encontrada')
        require_actor(db, user, record.author_profile_id)
        from app.modules.social.reviews_router import require_current_revision
        require_current_revision(db, record)
    elif record.user_id != user.id or record.deleted_at is not None:
        raise HTTPException(404, 'Comentario propio no encontrado')
    return record


def public_snapshot(db, record):
    """Fingerprint includes old-route edits, event metadata, cover and attachments."""
    def columns(item):
        values = {}
        for column in inspect(type(item)).columns:
            value = getattr(item, column.key)
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).isoformat(timespec='microseconds')
            elif value is not None and isinstance(column.type, Numeric):
                value = format(Decimal(str(value)).normalize(), 'f')
            values[column.key] = value
        return values
    values = columns(record)
    if isinstance(record, Post):
        values['images'] = [{'id': str(image.id), 'sha256': hashlib.sha256(image.data).hexdigest(),
                            'content_type': image.content_type,
                            'created_at': image.created_at.astimezone(timezone.utc).isoformat(timespec='microseconds')}
            for image in db.scalars(select(PostImage).where(PostImage.post_id == record.id).order_by(PostImage.id))]
        cover = db.get(PostBookCover, record.id)
        values['cover'] = {'revision': str(cover.revision), 'sha256': hashlib.sha256(cover.data).hexdigest(), 'content_type':cover.content_type} if cover else None
        event = db.get(PublicationEvent, record.id)
        values['event'] = columns(event) if event else None
    return jsonable_encoder(values)


def validate_proposal(db, record, kind, proposal):
    if not isinstance(proposal, dict):
        raise HTTPException(422, 'La propuesta debe ser un objeto')
    try:
        if kind == 'publication':
            from app.modules.social.publication_management import PublicationEdit
            parsed = PublicationEdit.model_validate(proposal)
            if parsed.author_profile_id and parsed.author_profile_id != record.author_profile_id:
                raise HTTPException(403, 'No puedes cambiar la autoría')
            if (parsed.publication_type == 'event') != (parsed.source == 'event'):
                raise HTTPException(422, 'El tipo no corresponde al contenido')
        elif kind == 'review':
            from app.modules.social.schemas import ReviewUpdate
            parsed = ReviewUpdate.model_validate(proposal)
            if parsed.status != 'published':
                raise HTTPException(422, 'La moderación preventiva prepara contenido público, no borradores privados')
        else:
            from app.modules.social.interactions_router import ActivityCommentCreate, validate_comment
            parsed = ActivityCommentCreate.model_validate(proposal)
            validate_comment(_comment_parent(record)[0], parsed.body)
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_context=False)) from error
    return parsed.model_dump(mode='json', exclude_unset=True)


@dataclass(frozen=True)
class ProposedAttachment:
    role: str
    content_type: str
    data: bytes


def validate_attachments(db, record, proposal, attachments):
    if not isinstance(record, Post) and attachments:
        raise HTTPException(422, 'Solo las publicaciones admiten adjuntos de propuesta')
    from app.modules.social.router import image_content_type, MAX_IMAGE_BYTES, MAX_IMAGES_TOTAL_BYTES, MAX_POST_IMAGES
    total = 0
    images = covers = 0
    for item in attachments:
        if item.role not in ('image', 'cover'):
            raise HTTPException(422, 'Tipo de adjunto inválido')
        if not item.data or len(item.data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, 'Cada imagen admite hasta 5 MB')
        if image_content_type(item.data) != item.content_type:
            raise HTTPException(415, 'La imagen no corresponde al formato declarado')
        total += len(item.data)
        images += item.role == 'image'
        covers += item.role == 'cover'
    if covers > 1:
        raise HTTPException(422, 'Solo se admite una portada')
    if isinstance(record, Post):
        existing = list(db.scalars(select(PostImage).where(PostImage.post_id == record.id)))
        selected = {uuid.UUID(value) for value in proposal['existing_image_ids']} if proposal.get('existing_image_ids') is not None else {image.id for image in existing}
        if not selected.issubset({image.id for image in existing}):
            raise HTTPException(422, 'Una imagen no pertenece a esta publicación')
        if len(selected) + images > MAX_POST_IMAGES:
            raise HTTPException(422, 'Puedes conservar hasta 10 fotografías')
        total += sum(len(image.data) for image in existing if image.id in selected)
        cover = db.get(PostBookCover, record.id)
        mode = proposal.get('cover_mode', 'keep')
        if covers and mode != 'custom':
            raise HTTPException(422, 'Selecciona el modo de portada personalizada')
        if mode == 'custom' and not (covers or cover):
            raise HTTPException(422, 'Selecciona una portada personalizada')
        if covers and not (proposal.get('work_id') or proposal.get('book_ref') or record.work_id or record.book_ref):
            raise HTTPException(422, 'Enlaza una obra antes de personalizar la portada')
        total += len(cover.data) if cover and not covers and mode in ('keep', 'custom') else 0
    if total > MAX_IMAGES_TOTAL_BYTES:
        raise HTTPException(413, 'Los adjuntos no pueden superar 25 MB')


def prepare_edit(db, user, kind, identifier, proposal, *, request_key, expected_version, attachments=()):
    """Stage a private immutable proposal. Never apply it, even if no flags arise."""
    if type(expected_version) is not int or expected_version < 1:
        raise HTTPException(422, 'Versión de contenido inválida')
    attachments = tuple(attachments)
    payload = {'kind': kind, 'id': str(identifier), 'proposal': proposal, 'version': expected_version,
               'attachments': [{'role': item.role, 'type': item.content_type,
                                'sha256': hashlib.sha256(item.data).hexdigest()} for item in attachments]}
    request = claim_request(db, user, f'edit:{kind}:{identifier}', request_key, payload)
    record = owned_target(db, user, kind, identifier)  # Re-authorize even on replay.
    if request.result is not None:
        revision = db.get(ModerationRevision, uuid.UUID(request.result['revision_id']))
        if revision is None:
            raise HTTPException(409, 'La solicitud no tiene una revisión vigente')
        return revision
    if expected_version != record.moderation_version:
        raise HTTPException(409, 'El contenido cambió; vuelve a cargarlo')
    validated = validate_proposal(db, record, kind, proposal)
    validate_attachments(db, record, validated, attachments)
    # Separate fields so the end of a title cannot create a fake attack in body.
    texts = [str(validated.get(field) or '') for field in ('title','body','book_title')]
    event = validated.get('event_details') or {}
    texts.extend(str(event.get(field) or '') for field in ('location', 'organizer'))
    analyses = [analyze_content(text) for text in texts]
    findings = {finding.rule_id: finding for analysis in analyses for finding in analysis.findings}
    analysis = Analysis(status='pending_review' if findings else 'approved', flagged=bool(findings),
                        findings=tuple(findings.values()), ruleset_version=analyses[0].ruleset_version)
    column = getattr(ModerationRevision, TARGETS[kind][1])
    previous = list(db.scalars(select(ModerationRevision).where(column == identifier,
        ModerationRevision.status == 'pending_review', ModerationRevision.lifecycle == 'active')
        .with_for_update()))
    for item in previous:
        item.lifecycle = 'superseded'
        db.add(ModerationAudit(revision_id=item.id, actor_user_id=user.id, action='superseded',
                               reason='El autor envió otra propuesta'))
    db.flush()  # Release the unique active-pending slot before inserting.
    revision = ModerationRevision(**{TARGETS[kind][1]: identifier}, author_user_id=user.id,
        base_version=record.moderation_version, base_fingerprint=fingerprint(public_snapshot(db, record)),
        proposal=validated, findings=[finding.model_dump() for finding in analysis.findings],
        ruleset_version=analysis.ruleset_version, status=analysis.status)
    db.add(revision); db.flush()
    positions = {'image': 0, 'cover': 0}
    for item in attachments:
        db.add(ModerationAttachment(revision_id=revision.id, role=item.role, position=positions[item.role],
                                   content_type=item.content_type, data=item.data))
        positions[item.role] += 1
    db.add(ModerationAudit(revision_id=revision.id, actor_user_id=user.id, action='prepared',
                          reason='Propuesta privada preparada; todavía no aplicada al contenido público'))
    if revision.status == 'pending_review':
        from app.modules.social.moderation_notifications import notify
        notify(db,revision,'pending_review')
    complete_request(request, {'revision_id': str(revision.id)})
    db.flush()
    return revision


def private_revision(db, user, identifier, *, administrative=False):
    require_active(user)
    if administrative:
        require_moderation_admin(db, user)
    query = select(ModerationRevision).where(ModerationRevision.id == identifier)
    if not administrative:
        query = query.where(ModerationRevision.author_user_id == user.id)
    revision = db.scalar(query)
    if revision is None:
        raise HTTPException(404, 'Revisión no encontrada')
    return revision


def assert_revision_current(db, record, revision):
    """Guard for the future decision service, including old routes not versioned yet."""
    field = 'post_id' if isinstance(record, Post) else 'review_id' if isinstance(record, Review) else 'comment_id'
    if (getattr(revision, field) != record.id or revision.lifecycle != 'active' or revision.base_version != record.moderation_version
            or revision.base_fingerprint != fingerprint(public_snapshot(db, record))):
        raise HTTPException(409, 'La versión pública cambió; esta propuesta necesita una nueva revisión')
