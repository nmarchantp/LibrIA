"""One private inbox for follows and role application events."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission
from app.modules.users.verification_models import RoleNotification
from app.modules.social.models import FollowNotification

router = APIRouter(prefix='/me/notification-inbox', tags=['notifications'])
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]

INBOX = """
 SELECT n.id,'follow' AS source,'follow' AS kind,
   u.display_name || ' comenzó a seguirte' AS message,
   '/profiles/' || p.id::text AS href, NULL::text AS decision_reason,
   n.created_at,n.read_at
 FROM app.notificaciones_seguimiento n JOIN app.usuarios u ON u.id=n.actor_user_id
 JOIN app.perfiles p ON p.owner_user_id=u.id AND p.kind='personal'
 WHERE n.recipient_user_id=:owner AND u.account_status='active' AND u.suspended_at IS NULL
 UNION ALL
 SELECT n.id,'role',n.kind,
   CASE n.kind WHEN 'requested' THEN u.display_name || ' solicitó el perfil ' || r.requested_role
   WHEN 'approved' THEN 'Tu solicitud de perfil ' || r.requested_role || ' fue aprobada'
   ELSE 'Tu solicitud de perfil ' || r.requested_role || ' fue rechazada' END,
   CASE WHEN n.kind='requested' THEN '/admin/profiles?tab=requests' ELSE '/settings' END,
   CASE WHEN n.kind<>'requested' THEN r.decision_reason ELSE NULL END,
   n.created_at,n.read_at
 FROM app.notificaciones_perfil n JOIN app.solicitudes_verificacion r ON r.id=n.request_id
 JOIN app.usuarios u ON u.id=r.user_id
 WHERE n.recipient_user_id=:owner AND (n.kind<>'requested' OR EXISTS(
   SELECT 1 FROM app.permisos_cuenta p WHERE p.user_id=:owner AND p.permission='admin'))
"""


@router.get('')
def inbox(db: DB, user: Viewer, response: Response, limit: int = Query(30, ge=1, le=50), offset: int = Query(0, ge=0)):
    response.headers['Cache-Control'] = 'private, no-store'
    params = {'owner': user.id, 'limit': limit + 1, 'offset': offset}
    rows = db.execute(text('SELECT * FROM (' + INBOX + ') items ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset'), params).mappings().all()
    unread = db.execute(text('SELECT count(*) FROM (' + INBOX + ') items WHERE read_at IS NULL'), params).scalar_one()
    return {'items': [dict(row) for row in rows[:limit]], 'has_more': len(rows) > limit, 'unread_count': unread}


@router.put('/{source}/{identifier}/read')
def read_notice(source: Literal['follow', 'role'], identifier: uuid.UUID, db: DB, user: Viewer, response: Response):
    response.headers['Cache-Control'] = 'private, no-store'
    model = RoleNotification if source == 'role' else FollowNotification
    row = db.scalar(select(model).where(model.id == identifier, model.recipient_user_id == user.id).with_for_update())
    if row is None or (source == 'role' and row.kind == 'requested' and db.get(AccountPermission, (user.id, 'admin')) is None):
        raise HTTPException(404, 'Notificación no encontrada')
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
    result = {'id': row.id, 'read_at': row.read_at}
    db.commit()
    return result
