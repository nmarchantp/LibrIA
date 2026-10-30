"""Regression coverage for completed analyses hidden by catalog changes."""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import Response

from app.core.config import Settings
from app.modules.analytics import adaptive_router as routes


class PrivateAnalysisRefreshTest(unittest.TestCase):
    def test_profile_recommendation_shapes_return_success_with_cors(self):
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.testclient import TestClient
        from app.core.database import get_db
        from app.modules.auth.dependencies import get_current_user
        app = FastAPI()
        app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173'])
        app.include_router(routes.router, prefix='/api')
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.owner
        self.db.execute.return_value.mappings.return_value.first.return_value = None
        self.db.execute.return_value.scalar.return_value = None
        items = [{'work_id': str(self.work), 'title': 'Recomendación guardada'}]
        for stored, expected in ((items, items), ({'recommendations': items}, items),
                                 ([], []), (None, None)):
            with self.subTest(stored=stored), \
                 patch.object(routes, 'recommendation_state', return_value={'status': 'ready', 'recommendations': stored}) as state, \
                 patch('app.modules.analytics.reader_dna.read_current_dna', return_value=None), \
                 patch('app.modules.books.canonical.enabled', return_value=False), TestClient(app) as client:
                response = client.get('/api/me/ai/profile', headers={'Origin': 'http://localhost:5173'})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
                self.assertEqual(response.json()['recommendations'], expected)
                state.assert_called_once_with(self.db, self.owner.id, enqueue=False)
        self.db.commit.assert_not_called()

    def setUp(self):
        self.owner = SimpleNamespace(id=uuid.uuid4())
        self.work = uuid.uuid4()
        self.db = MagicMock()
        self.job = {'id': uuid.uuid4(), 'status': 'completed', 'attempts': 1}
        self.settings = Settings(_env_file=None)

    def refresh(self, analysis=None, force=False):
        status = 'completed' if analysis else 'waiting_nightly_processing'
        with patch.object(routes, 'book_analysis', return_value={'analysis': analysis, 'status': status}):
            return routes.refresh_book(self.work, Response(), self.owner, self.db, force)

    def test_completed_hidden_result_waits_for_nightly_preparation(self):
        self.assertEqual(self.refresh()['status'], 'waiting_nightly_processing')
        self.db.execute.assert_not_called()
        self.db.commit.assert_not_called()

    def test_completed_visible_result_is_reused(self):
        self.assertEqual(self.refresh(analysis={'id': uuid.uuid4()})['status'], 'completed')
        self.db.execute.assert_not_called()

    def test_reader_without_admin_permission_can_consult_own_analysis(self):
        self.db.get.return_value = None
        self.assertEqual(self.refresh(analysis={'id': uuid.uuid4()})['status'], 'completed')

    def test_force_cannot_bypass_nightly_preparation(self):
        self.assertEqual(self.refresh(force=True)['status'], 'waiting_nightly_processing')
        self.db.execute.assert_not_called()

    def test_recommendation_button_requests_only_authenticated_owner_with_bounded_retry(self):
        from app.modules.analytics import insights_router
        with patch.object(insights_router, 'recommendation_state', return_value={'status':'pending'}) as state:
            result = insights_router.sync_recommendations(Response(), self.owner, self.db)
        self.assertEqual(result['status'], 'pending')
        state.assert_called_once_with(self.db, self.owner.id, enqueue=True, retry_failed=True)

    def test_hidden_result_does_not_reset_attempt_limit(self):
        self.job['attempts'] = self.settings.ai_job_max_attempts
        self.refresh()
        self.db.execute.assert_not_called()
        self.db.commit.assert_not_called()

    def test_book_route_delegates_canonical_policy_with_owner(self):
        with patch.object(routes, 'owned_entry'), \
             patch('app.modules.books.canonical.enabled', return_value=True), \
             patch('app.modules.books.canonical.canonical_members', return_value={self.work}), \
             patch('app.modules.analytics.reading_analysis.book_state', return_value={'status':'update_pending'}) as state:
            result = routes.book_analysis(self.work, Response(), self.owner, self.db)
        self.assertEqual(result['status'], 'update_pending')
        state.assert_called_once_with(self.db, self.owner.id, [self.work])
