"""Phase 0: existing behavior and future contract, without DB/network access."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from sqlalchemy.dialects import postgresql

from app.modules.books.community import public_rating
from app.modules.books.identity import canonical_work_key, identity_matches
from app.modules.library.models import Reading
from tests.catalog_phase0_support import compare, confirmed_root, report, scenarios

APP = Path(__file__).resolve().parents[1] / "app"


def function_source(relative, name):
    source = (APP / relative).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return ast.get_source_segment(source, node)


class OfflineOnly(unittest.TestCase):
    def setUp(self):
        for target in ("sqlalchemy.engine.Engine.connect", "socket.socket.connect", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("Phase 0 forbids DB/network connections"))
            guard.start()
            self.addCleanup(guard.stop)


class LegacyCharacterization(OfflineOnly):
    def test_title_and_author_currently_group_without_external_work_evidence(self):
        result = compare(scenarios()[0])
        self.assertEqual(result["legacy"]["works"], ["A", "B"])
        self.assertEqual(result["legacy"]["average"], "3")

    def test_title_bridge_is_transitive(self):
        self.assertEqual(compare(scenarios()[2])["legacy"]["works"], ["A", "B", "C"])

    def test_unknown_author_is_not_positive_identity(self):
        self.assertIsNone(canonical_work_key("Novel"))
        self.assertFalse(identity_matches("Novel", [], "Novel", ["Test Author"]))
        self.assertEqual(compare(scenarios()[5])["legacy"]["works"], ["A"])

    def test_reading_model_prepares_nullable_storage_in_phase1(self):
        # Phase-0 baseline required an edition. Phase 1 only relaxes storage;
        # the characterization below still checks that API resolution picks one.
        self.assertTrue(Reading.__table__.c.edition_id.nullable)

    def test_google_search_currently_calls_persistence(self):
        source = function_source("modules/books/router.py", "search_books")
        self.assertIn("store_volume(db, item)", source)
        self.assertIn("db.commit()", source)

    def test_opening_external_detail_currently_calls_importers(self):
        source = function_source("modules/books/router.py", "get_book")
        self.assertIn("ensure_edition(db, volume_id)", source)
        self.assertIn("store_volume(db, item, complete=True)", source)

    def test_omitting_edition_currently_selects_first(self):
        source = function_source("modules/library/router.py", "resolve_book")
        self.assertIn("if data.edition_id else db.scalar", source)
        self.assertIn("order_by(Edition.created_at, Edition.id)", source)

    def test_rating_sql_ranks_user_before_visibility(self):
        db = Mock()
        db.execute.return_value.one.return_value = (None, 0)
        public_rating(db, {"A", "B"})
        query = db.execute.call_args.args[0]
        sql = str(query.compile(dialect=postgresql.dialect()))
        self.assertIn("PARTITION BY app.resenas.created_by_user_id", sql)
        inner = next(child for child in query.get_final_froms() if hasattr(child, "element"))
        self.assertNotIn("status =", str(inner.element))
        self.assertIn("anon_1.status =", sql)

    def test_review_listing_currently_has_no_current_review_deduplication(self):
        source = function_source("modules/social/reviews_router.py", "book_reviews")
        self.assertIn("equivalent_work_ids", source)
        self.assertNotIn("row_number", source)
        self.assertNotIn("distinct", source)

    def test_phase4_etl_preserves_an_event_without_edition_or_total(self):
        # Phase 4 intentionally replaces the former mandatory-edition behavior.
        from datetime import datetime, timezone
        from app.modules.analytics.etl import transform
        now = datetime.now(timezone.utc)
        event = dict(id="event", work_id="work", edition_id=None, edition_work=None,
            library_work="work", actor_user_id="reader", user_id="reader", kind="start",
            page=0, previous_page=0, total_pages=None, reading_total=None,
            started_at=now, created_at=now, provenance="unclassified")
        prepared = transform([{"id": "work", "title": "Work"}], [event], [], [])
        self.assertEqual(len(prepared[1]), 1)
        self.assertIsNone(prepared[1][0]["edition_id"])
        self.assertIsNone(prepared[1][0]["total_pages"])

    def test_recommendation_association_currently_uses_physical_work(self):
        source = function_source("modules/analytics/recommendation_profiles.py", "_reader_books")
        self.assertIn('reviews.get(reading["work_id"])', source)
        self.assertIn('reading["edition_updated_at"] < cutoff', source)


class ConfirmedContractComparisons(OfflineOnly):
    def test_title_author_only_splits_and_changes_all_affected_metrics(self):
        result = compare(scenarios()[0])
        self.assertEqual(result["confirmed_contract"]["works"], ["A"])
        self.assertEqual(result["confirmed_contract"]["average"], "5")
        for key in ("review_ids", "ratings_count", "reading_stats", "library_users", "reading_review_associations"):
            self.assertIn(key, result["changed_fields"])

    def test_confirmed_translation_restores_reading_review_association(self):
        result = compare(scenarios()[1])
        self.assertEqual(result["legacy"]["reading_review_associations"], [])
        self.assertEqual(result["confirmed_contract"]["reading_review_associations"], [["l1", "r1"]])

    def test_private_latest_never_exposes_previous_public_rating(self):
        result = compare(scenarios()[3])
        for name in ("legacy", "confirmed_contract"):
            self.assertIsNone(result[name]["average"])
            self.assertEqual(result[name]["ratings_count"], 0)
        self.assertEqual(result["legacy"]["review_ids"], ["r1"])
        self.assertEqual(result["confirmed_contract"]["review_ids"], [])

    def test_overlap_preserves_one_current_rating_and_latest_reading(self):
        result = compare(scenarios()[4])["confirmed_contract"]
        self.assertEqual(result["review_ids"], ["r2"])
        self.assertEqual(result["ratings_count"], 1)
        self.assertEqual(result["reading_stats"], dict(finished=0, reading=1, abandoned=0))
        self.assertEqual(result["library_users"], ["u1"])

    def test_confirmed_redirect_chain_and_cycle_rejection(self):
        self.assertEqual(confirmed_root("C", [["C", "B"], ["B", "A"]]), "A")
        with self.assertRaises(ValueError):
            confirmed_root("A", [["A", "B"], ["B", "A"]])
        with self.assertRaises(ValueError):
            confirmed_root("A", [["A", "B"], ["A", "C"]])

    def test_comparison_is_deterministic_and_preserves_every_input_record(self):
        cases = scenarios()
        before = deepcopy(cases)
        self.assertEqual(report(), report())
        for case in cases:
            compare(case)
        self.assertEqual(cases, before)

    def test_different_known_authors_do_not_group(self):
        case = scenarios()[0]
        case["works"][1]["authors"] = ["Other Author"]
        self.assertEqual(compare(case)["legacy"]["works"], ["A"])

    def test_missing_rating_counts_review_but_not_score(self):
        case = scenarios()[0]
        case["reviews"][0]["rating"] = None
        result = compare(case)["confirmed_contract"]
        self.assertEqual(result["review_ids"], ["r1"])
        self.assertEqual(result["ratings_count"], 0)
        self.assertIsNone(result["average"])

    def test_comparison_preserves_absent_edition_and_pages(self):
        # Preservation contract only: production currently rejects a NULL edition.
        case = scenarios()[1]
        case["readings"][0].update(edition_id=None, total_pages=None, external_reference=None)
        before = deepcopy(case)
        compare(case)
        self.assertEqual(case, before)
        self.assertIsNone(case["readings"][0]["edition_id"])
        self.assertIsNone(case["readings"][0]["total_pages"])


if __name__ == "__main__":
    unittest.main()
