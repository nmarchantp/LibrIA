"""Notification privacy, persistence and atomicity for profile applications."""
import uuid
from sqlalchemy import select, func
import tests.test_influencer_access as access_tests
from app.modules.users.verification_models import RoleNotification, VerificationRequest
from app.modules.users.identity_models import AccountPermission


class RoleNotificationTest(access_tests.InfluencerAccessTest):
    def inbox(self, account=None, query=''):
        response = self.client.get('/api/me/notification-inbox' + query, headers=self.headers(account))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_new_application_alerts_admins_and_not_other_readers(self):
        other = self.register()
        request = self.submit()
        self.assertEqual(request.status_code, 201, request.text)
        admin = self.inbox(self.admin)
        self.assertEqual(admin['unread_count'], 1)
        self.assertEqual(admin['items'][0]['kind'], 'requested')
        self.assertEqual(admin['items'][0]['href'], '/admin/profiles?tab=requests')
        self.assertEqual(self.inbox()['items'], [])
        self.assertEqual(self.inbox(other)['items'], [])
        self.assertEqual(self.submit().status_code, 409)
        self.assertEqual(self.inbox(self.admin)['unread_count'], 1)

    def test_rejection_notifies_applicant_with_reason_and_closes_admin_alert(self):
        identifier = self.submit().json()['id']
        response = self.decide(identifier, 'reject', reason='Falta evidencia pública de actividad literaria.')
        self.assertEqual(response.status_code, 200, response.text)
        inbox = self.inbox()
        self.assertEqual(inbox['unread_count'], 1)
        notice = inbox['items'][0]
        self.assertEqual(notice['kind'], 'rejected')
        self.assertEqual(notice['decision_reason'], response.json()['decision_reason'])
        self.assertEqual(notice['href'], '/settings')
        self.assertEqual(self.inbox(self.admin)['unread_count'], 0)
        self.assertEqual(self.decide(identifier, 'reject').status_code, 409)
        self.assertEqual(self.inbox()['unread_count'], 1)

    def test_approval_notification_survives_session_invalidation(self):
        self.promote()
        result = self.inbox()
        self.assertEqual(result['unread_count'], 1)
        self.assertEqual(result['items'][0]['kind'], 'approved')

    def test_read_requires_recipient_and_is_idempotent(self):
        identifier = self.submit().json()['id']
        self.decide(identifier, 'reject')
        item = self.inbox()['items'][0]
        path = f"/api/me/notification-inbox/role/{item['id']}/read"
        self.assertEqual(self.client.put(path, headers=self.headers(self.admin)).status_code, 404)
        self.assertEqual(self.client.put(path).status_code, 401)
        first = self.client.put(path, headers=self.headers())
        second = self.client.put(path, headers=self.headers())
        self.assertEqual(first.json(), second.json())
        self.assertEqual(self.inbox()['unread_count'], 0)

    def test_revoked_admin_permission_hides_application_information(self):
        self.submit()
        item = self.inbox(self.admin)['items'][0]
        self.db.delete(self.db.get(AccountPermission, (self.user(self.admin).id, 'admin')))
        self.db.commit()
        self.assertEqual(self.inbox(self.admin)['items'], [])
        self.assertEqual(self.client.put(f"/api/me/notification-inbox/role/{item['id']}/read", headers=self.headers(self.admin)).status_code, 404)

    def test_notifications_rollback_with_application_and_pagination_does_not_change_unread_count(self):
        self.submit()
        notification = self.db.scalar(select(RoleNotification).where(RoleNotification.recipient_user_id == self.user(self.admin).id))
        self.assertIsNotNone(notification)
        page = self.inbox(self.admin, '?limit=1&offset=20')
        self.assertEqual(page['items'], [])
        self.assertEqual(page['unread_count'], 1)
        self.assertEqual(self.client.get('/api/me/notification-inbox').status_code, 401)
        self.assertEqual(self.client.put(f'/api/me/notification-inbox/role/{uuid.uuid4()}/read', headers=self.headers()).status_code, 404)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(RoleNotification).where(RoleNotification.request_id == notification.request_id)), 1)
        from app.modules.users.role_notifications import notify_request
        pending = VerificationRequest(user_id=self.user(self.admin).id, requested_role='autor', note='Solicitud en transacción temporal.')
        with self.db.begin_nested() as transaction:
            self.db.add(pending)
            # Give the reader admin rights solely within this rolled-back transaction.
            self.db.add(AccountPermission(user_id=self.user(self.reader).id, permission='admin'))
            notify_request(self.db, pending)
            self.assertIsNotNone(self.db.scalar(select(RoleNotification.id).where(RoleNotification.request_id == pending.id)))
            transaction.rollback()
        self.assertIsNone(self.db.get(VerificationRequest, pending.id))
        self.assertIsNone(self.db.scalar(select(RoleNotification.id).where(RoleNotification.request_id == pending.id)))

    def test_follow_notifications_share_the_inbox_and_read_counter(self):
        from app.modules.social.models import FollowNotification
        other = self.register()
        follow = FollowNotification(recipient_user_id=self.user(self.reader).id, actor_user_id=self.user(other).id)
        self.db.add(follow); self.db.commit()
        identifier = self.submit().json()['id']
        self.decide(identifier, 'reject')
        inbox = self.inbox()
        self.assertEqual(inbox['unread_count'], 2)
        self.assertEqual({item['source'] for item in inbox['items']}, {'follow', 'role'})
        self.assertEqual(self.client.put(f'/api/me/notification-inbox/follow/{follow.id}/read', headers=self.headers()).status_code, 200)
        self.assertEqual(self.inbox()['unread_count'], 1)
