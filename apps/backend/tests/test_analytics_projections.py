"""Stage 6 boundaries between projections, HTTP reads and provider work."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


class ProjectionBoundaryTest(unittest.TestCase):
    def test_profile_and_book_gets_never_enqueue(self):
        source=(ROOT / "backend/app/modules/analytics/adaptive_router.py").read_text(encoding="utf-8")
        profile=source[source.index("def profile("):source.index("@router.post('/profile/refresh")]
        book=source[source.index("def book_analysis"):source.index("@router.post('/books")]
        self.assertNotIn("enqueue_recommendation_job",profile)
        self.assertNotIn("enqueue_recommendation_job",book)

    def test_owner_refreshes_enqueue_profile_and_book_work(self):
        source=(ROOT / "backend/app/modules/analytics/adaptive_router.py").read_text(encoding="utf-8")
        profile_refresh=source[source.index("def refresh_profile("):source.index("@router.get('/profile/history')")]
        book_refresh=source[source.index("def refresh_book("):source.index("@router.get('/profile')")]
        self.assertNotIn("AccountPermission",profile_refresh)
        self.assertIn("prepare_administrator_profile",profile_refresh)
        self.assertIn("enqueue_dna",profile_refresh)
        self.assertNotIn("enqueue=True",profile_refresh)
        self.assertIn("AccountPermission",book_refresh)
        self.assertIn("enqueue_reading_event_analysis",book_refresh)
        self.assertIn("delay_minutes=0",book_refresh)

    def test_projections_do_not_import_provider_sdk(self):
        source=(ROOT / "backend/app/modules/analytics/projections.py").read_text(encoding="utf-8")
        self.assertNotIn("google.genai",source)
        self.assertNotIn("build_ai_provider",source)
