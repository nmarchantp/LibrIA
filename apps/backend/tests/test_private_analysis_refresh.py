"""Regression coverage for completed analyses hidden by catalog changes."""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, Response

from app.core.config import Settings
from app.modules.analytics import adaptive_router as routes


class PrivateAnalysisRefreshTest(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(id=uuid.uuid4())
        self.work = uuid.uuid4()
        self.db = MagicMock()
        self.job = {'id': uuid.uuid4(), 'status': 'completed', 'attempts': 1}
        self.settings = Settings(_env_file=None)

    def refresh(self, analysis=None, force=False):
        with patch.object(routes, 'owned_entry'), \
             patch('app.modules.books.canonical.enabled', return_value=False), \
             patch.object(routes, 'get_settings', return_value=self.settings), \
             patch.object(routes, 'enqueue_reading_event_analysis', return_value=self.job), \
             patch.object(routes, 'book_analysis', return_value={'analysis': analysis}):
            self.db.execute.return_value.mappings.return_value.one.return_value = {
                **self.job, 'status': 'pending',
            }
            return routes.refresh_book(self.work, Response(), self.owner, self.db, force)

    def test_completed_hidden_result_is_queued_again(self):
        result = self.refresh()
        self.assertEqual(result['status'], 'pending')
        self.assertTrue(any("status='pending'" in str(call.args[0]) for call in self.db.execute.call_args_list))
        self.db.commit.assert_called_once()

    def test_completed_visible_result_is_reused(self):
        result = self.refresh(analysis={'id': uuid.uuid4()})
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any('UPDATE ia.jobs' in str(call.args[0]) for call in self.db.execute.call_args_list))

    def test_reader_without_admin_permission_can_request_own_analysis(self):
        self.db.get.return_value = None
        self.assertEqual(self.refresh(analysis={'id': uuid.uuid4()})['status'], 'completed')

    def test_reader_cannot_force_regeneration(self):
        self.db.get.return_value = None
        with self.assertRaises(HTTPException) as error:
            self.refresh(force=True)
        self.assertEqual(error.exception.status_code, 403)

    def test_recommendation_button_requests_only_authenticated_owner_with_bounded_retry(self):
        from app.modules.analytics import insights_router
        with patch.object(insights_router, 'recommendation_state', return_value={'status':'pending'}) as state:
            result = insights_router.sync_recommendations(Response(), self.owner, self.db)
        self.assertEqual(result['status'], 'pending')
        state.assert_called_once_with(self.db, self.owner.id, enqueue=True, retry_failed=True)

    def test_hidden_result_does_not_bypass_attempt_limit(self):
        self.job['attempts'] = self.settings.ai_job_max_attempts
        with self.assertRaises(HTTPException) as error:
            self.refresh()
        self.assertEqual(error.exception.status_code, 409)
        self.db.commit.assert_not_called()

    def test_hidden_completed_result_is_reported_obsolete(self):
        analysis = MagicMock()
        analysis.get.return_value = None
        rows = [analysis, {**self.job, 'error_code': None}]
        self.db.execute.return_value.mappings.return_value.first.side_effect = rows
        with patch.object(routes, 'owned_entry'), \
             patch('app.modules.books.canonical.enabled', return_value=True), \
             patch('app.modules.books.canonical.canonical_members', return_value={self.work}), \
             patch('app.modules.books.canonical.identity_version', return_value='current'):
            result = routes.book_analysis(self.work, Response(), self.owner, self.db)
        self.assertEqual(result['status'], 'obsolete')
        self.assertIsNone(result['analysis'])
