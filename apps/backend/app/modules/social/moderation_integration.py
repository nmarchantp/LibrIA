"""Stage 2 adapters. No administrator decisions, reporting or UI."""
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from app.modules.social.moderation_models import ModerationRevision, ModerationAudit
from app.modules.social.moderation_rules import analyze_content, Analysis
from app.modules.social.moderation_service import claim_request, complete_request, prepare_edit

PENDING_MESSAGE = 'Tu contenido fue enviado a revisión. Te avisaremos cuando esté aprobado'


def analyze_fields(payload):
    texts = [str(payload.get(field) or '') for field in ('title','body','book_title')]
    event = payload.get('event_details') or {}
    texts.extend(str(event.get(field) or '') for field in ('location','organizer'))
    try:
        analyses = [analyze_content(value) for value in texts]
    except ValueError as error:
        if 'Text exceeds' in str(error):
            raise HTTPException(422, 'El contenido supera el límite de análisis permitido') from error
        raise HTTPException(503, 'La moderación no está disponible; vuelve a intentarlo') from error
    except OSError as error:
        raise HTTPException(503, 'La moderación no está disponible; vuelve a intentarlo') from error
    findings = {item.rule_id:item for result in analyses for item in result.findings}
    return Analysis(status='pending_review' if findings else 'approved', flagged=bool(findings),
                    findings=tuple(findings.values()), ruleset_version=analyses[0].ruleset_version)


def http_claim(db, user, request, operation, payload):
    raw = request.headers.get('Idempotency-Key') if request else None
    if not raw:
        return None
    try: key = uuid.UUID(raw)
    except ValueError: raise HTTPException(422, 'Idempotency-Key debe ser un UUID') from None
    return claim_request(db, user, operation, key, {'payload':payload,'if_match':request.headers.get('If-Match')})


def check_version(request, record):
    raw = request.headers.get('If-Match')
    if raw is None:
        return  # Existing clients remain compatible; new clients can use CAS.
    try: version = int(raw.strip().strip('"'))
    except ValueError: raise HTTPException(422, 'If-Match debe indicar la versión del contenido') from None
    if version != record.moderation_version:
        raise HTTPException(409, 'El contenido cambió; vuelve a cargarlo antes de editar')


def retire_pending(db, user, record, kind, lifecycle='superseded'):
    field = {'publication':'post_id','review':'review_id','comment':'comment_id'}[kind]
    rows = db.scalars(select(ModerationRevision).where(getattr(ModerationRevision,field)==record.id,
        ModerationRevision.lifecycle=='active',ModerationRevision.status=='pending_review').with_for_update()).all()
    for revision in rows:
        revision.lifecycle = lifecycle
        db.add(ModerationAudit(revision_id=revision.id,actor_user_id=user.id,action=lifecycle,
                               reason='El contenido fue retirado' if lifecycle=='withdrawn' else 'El autor publicó una versión sin alertas'))
    db.flush()


def receipt(record, revision=None):
    return {'moderation_status': 'pending_review' if revision else record.moderation_status,
            'public_moderation_status':record.moderation_status,
            'moderation_version':record.moderation_version,
            'pending_revision_id':revision.id if revision else None,
            'moderation_message':PENDING_MESSAGE if revision else None}


def creation_revision(db, user, kind, record, proposal):
    """The new parent is private; attached parent files are protected by visibility."""
    record.moderation_status = 'pending_review'
    db.flush()
    return prepare_edit(db,user,kind,record.id,proposal,request_key=uuid.uuid4(),
                        expected_version=record.moderation_version)


def finish_http(db, claim, result):
    if claim is not None:
        complete_request(claim, result)
    db.commit()
