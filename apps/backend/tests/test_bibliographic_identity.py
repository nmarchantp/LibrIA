"""Bibliographic regression tests: isolated SQLite, no real catalog or network."""
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.main import app  # Register metadata, without starting background services.
from app.modules.books.identity import canonical_work_key, duplicate_candidate, identity_matches
from app.modules.books.models import AlternateTitle, Author, CatalogSource, Edition, Work, WorkAuthor
from app.modules.books.router import local_works, store_volume, work_payload, consolidate_catalog_matches
from app.modules.books.open_library_catalog import store_selected
from app.modules.books.service import consolidate_equivalent_works, duplicate_work_candidates, equivalent_work_ids, verified_work_for_import


@compiles(JSONB, "sqlite")
def sqlite_json(element, compiler, **kwargs):
    return "JSON"


class BibliographicIdentityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.connection = self.engine.connect()
        self.connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS app")
        self.connection.connection.driver_connection.create_function("hashtext", 1, lambda value: 1)
        self.connection.connection.driver_connection.create_function("pg_advisory_xact_lock", 1, lambda value: 0)
        for model in (Work, Author, WorkAuthor, Edition, CatalogSource, AlternateTitle):
            model.__table__.create(self.connection)
        self.db = Session(bind=self.connection)
        rating = patch("app.modules.books.router.public_rating", return_value=(None, 0))
        rating.start()
        self.addCleanup(rating.stop)

    def tearDown(self):
        self.db.close()
        self.connection.close()
        self.engine.dispose()

    def volume(self, title="Crep\u00fasculo", authors=None, year="2008", isbn=None):
        info = {"title": title, "authors": authors if authors is not None else ["Stephenie Meyer"],
                "publishedDate": year, "language": "es", "pageCount": 475}
        if isbn:
            info["industryIdentifiers"] = [{"type": "ISBN_13", "identifier": isbn}]
        return {"id": uuid.uuid4().hex, "volumeInfo": info}

    def imported(self, **kwargs):
        source = store_volume(self.db, self.volume(**kwargs))
        return self.db.get(Edition, source.edition_id)

    def test_meyer_editions_share_work_but_preserve_dates_and_isbns(self):
        first = self.imported(year="2008", isbn="9788420471938")
        second = self.imported(year="2015-11-19", isbn="9786073139755")
        self.assertEqual(first.work_id, second.work_id)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual((first.publication_date, second.publication_date), ("2008", "2015-11-19"))
        self.assertNotEqual(first.isbn13, second.isbn13)

    def test_saga_title_is_review_candidate_not_automatic_identity(self):
        first = self.imported()
        saga_title = "Crep\u00fasculo (Saga Crep\u00fasculo 1)"
        saga = self.imported(title=saga_title, year="2010")
        self.assertNotEqual(first.work_id, saga.work_id)
        self.assertEqual(equivalent_work_ids(self.db, first.work_id), {first.work_id})
        self.assertTrue(duplicate_candidate(first.title, ["Stephenie Meyer"], saga.title, ["Stephenie Meyer"]))
        report = duplicate_work_candidates(self.db, first.work_id)
        self.assertEqual([row["workId"] for row in report], [str(saga.work_id)])

    def test_anonymous_1843_document_never_matches_meyer(self):
        novel = self.imported()
        historical = self.imported(title="El crep\u00fasculo", authors=[], year="1843")
        self.assertNotEqual(novel.work_id, historical.work_id)
        self.assertEqual(equivalent_work_ids(self.db, novel.work_id), {novel.work_id})
        self.assertEqual(equivalent_work_ids(self.db, historical.work_id), {historical.work_id})
        self.assertEqual(consolidate_equivalent_works(self.db, novel.work_id), novel.work_id)
        self.assertIsNotNone(self.db.get(Work, historical.work_id))

    def test_equal_titles_different_authors_are_distinct(self):
        first = self.imported()
        second = self.imported(authors=["Other Author"])
        self.assertNotEqual(first.work_id, second.work_id)
        self.assertEqual(equivalent_work_ids(self.db, first.work_id), {first.work_id})

    def test_missing_author_never_supplies_positive_identity(self):
        first = self.imported(authors=[])
        second = self.imported(authors=[])
        third = self.imported()
        self.assertEqual(len({first.work_id, second.work_id, third.work_id}), 3)
        self.assertIsNone(canonical_work_key(first.title, []))
        self.assertIsNone(canonical_work_key(first.title, ["Autor desconocido"]))
        self.assertIsNone(verified_work_for_import(self.db, first.title, []))

    def test_contaminated_work_cannot_inherit_author_for_anonymous_source(self):
        novel = self.imported()
        historical = self.imported(title="El crep\u00fasculo", authors=[], year="1843")
        # Simulate legacy contamination only inside this disposable database.
        historical.work_id = novel.work_id
        self.db.flush()
        self.assertIsNone(verified_work_for_import(self.db, novel.title, ["Stephenie Meyer"]))
        clean = self.imported(year="2015")
        self.assertNotEqual(clean.work_id, novel.work_id)
        self.assertEqual(equivalent_work_ids(self.db, novel.work_id), {novel.work_id})

    def test_legacy_key_is_not_rewritten_and_still_resolves_verified_identity(self):
        edition = self.imported()
        work = self.db.get(Work, edition.work_id)
        work.identity_key = "crepusculo::meyer stephenie"
        self.db.flush()
        next_edition = self.imported(year="2015")
        self.assertEqual(next_edition.work_id, work.id)
        self.assertEqual(work.identity_key, "crepusculo::meyer stephenie")

    def test_subtitles_volume_numbers_and_articles_are_not_identity_shortcuts(self):
        for title in ("Crep\u00fasculo: otro relato", "Crep\u00fasculo (otra historia)",
                      "Crep\u00fasculo tomo 1", "El crep\u00fasculo"):
            with self.subTest(title=title):
                self.assertFalse(identity_matches("Crep\u00fasculo", ["Stephenie Meyer"], title, ["Stephenie Meyer"]))

    def test_search_is_accent_and_case_insensitive(self):
        self.imported()
        results = local_works(self.db, "CREPUSCULO", "title")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["volumeInfo"]["title"], "Crep\u00fasculo")

    def test_unverified_original_year_is_omitted_but_edition_date_remains(self):
        edition = self.imported(year="2015-11-19")
        work = self.db.get(Work, edition.work_id)
        self.assertIsNone(work.first_publication_date)
        work.first_publication_date = "1843"  # Legacy value is not trusted.
        self.db.flush()
        payload = work_payload(self.db, work.id)
        self.assertIsNone(payload["libria"]["firstPublicationDate"])
        self.assertFalse(payload["libria"]["originalPublicationVerified"])
        self.assertEqual(payload["volumeInfo"]["publishedDate"], "2015-11-19")
        self.assertEqual(payload["libria"]["earliestEditionDate"], "2015-11-19")

    def test_verified_original_uses_existing_field_and_editorial_evidence(self):
        edition = self.imported(year="2015")
        work = self.db.get(Work, edition.work_id)
        work.first_publication_date = "2005"
        self.db.add(CatalogSource(edition_id=edition.id, provider="libria-verification",
            external_id=str(work.id), fetched_at=datetime.now(timezone.utc), payload={
                "originalPublication": {"workId": str(work.id), "date": "2005", "verifiedBy": "test-editor",
                    "verifiedAt": "2026-10-24", "evidenceUrl": "https://publisher.example/twilight"}}))
        self.db.flush()
        payload = work_payload(self.db, work.id)
        self.assertEqual(payload["libria"]["firstPublicationDate"], "2005")
        self.assertTrue(payload["libria"]["originalPublicationVerified"])
        self.assertEqual(payload["volumeInfo"]["publishedDate"], "2015")
        self.assertEqual(payload["libria"]["editionCount"], 1)

    def test_search_never_executes_physical_consolidation(self):
        with patch("app.modules.books.service.consolidate_equivalent_works") as merge:
            consolidate_catalog_matches(self.db, "Crepusculo", "title")
            merge.assert_not_called()

    def test_logical_grouping_preserves_existing_work_identifiers(self):
        first = self.imported()
        second = self.imported(title="Other title")
        source = self.db.scalar(select(CatalogSource).where(
            CatalogSource.edition_id == second.id, CatalogSource.provider == "google-books"))
        second.title = first.title
        source.payload = self.volume(title=first.title)
        self.db.flush()
        expected = {first.work_id, second.work_id}
        self.assertEqual(equivalent_work_ids(self.db, first.work_id), expected)
        self.assertEqual(equivalent_work_ids(self.db, second.work_id), expected)
        consolidate_catalog_matches(self.db, "crepusculo", "title")
        self.assertEqual({row.id for row in self.db.scalars(select(Work))}, expected)

    def test_explicit_edition_labels_and_comma_author_names_reuse_work(self):
        first = self.imported(title="Caraval", authors=["Garber, Stephanie"])
        second = self.imported(title="Caraval. Ed. Limitada", authors=["Stephanie Garber"])
        self.assertEqual(first.work_id, second.work_id)

    def test_bilingual_label_requires_known_same_author(self):
        first = self.imported(title="La novela / The novel")
        second = self.imported(title="La novela (Ed. Minalima)")
        anonymous = self.imported(title="The novel", authors=[])
        self.assertEqual(first.work_id, second.work_id)
        self.assertNotEqual(first.work_id, anonymous.work_id)

    def test_open_library_work_key_does_not_override_author_evidence(self):
        first = self.volume()
        first["openLibrary"] = {"editionKey": "OL100001M", "workKey": "OL100001W"}
        edition = store_selected(self.db, first)
        anonymous = self.volume(authors=[])
        anonymous["openLibrary"] = {"editionKey": "OL100002M", "workKey": "OL100001W"}
        other = store_selected(self.db, anonymous)
        self.assertNotEqual(edition.work_id, other.work_id)
        self.assertEqual(equivalent_work_ids(self.db, edition.work_id), {edition.work_id})

    def test_open_library_import_reuses_verified_google_identity(self):
        google = self.imported()
        item = self.volume(year="2010")
        item["openLibrary"] = {"editionKey": "OL100003M", "workKey": "OL100001W"}
        edition = store_selected(self.db, item)
        self.assertEqual(edition.work_id, google.work_id)
        self.assertIsNone(self.db.get(Work, google.work_id).first_publication_date)

    def test_separate_provider_subtitle_is_preserved_in_identity(self):
        first = self.volume(title="The story")
        second = self.volume(title="The story")
        first["volumeInfo"]["subtitle"] = "A journey north"
        second["volumeInfo"]["subtitle"] = "A journey south"
        left = store_volume(self.db, first)
        right = store_volume(self.db, second)
        left_edition = self.db.get(Edition, left.edition_id)
        right_edition = self.db.get(Edition, right.edition_id)
        self.assertNotEqual(left_edition.work_id, right_edition.work_id)
        self.assertEqual(equivalent_work_ids(self.db, left_edition.work_id), {left_edition.work_id})


if __name__ == "__main__":
    unittest.main()
