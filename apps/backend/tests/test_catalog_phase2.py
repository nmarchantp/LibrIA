"""Central service tests. Writes only in the phase-1 harness's owned tmpfs DB."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.books.canonical import CanonicalIdentityError, canonical_mapping, canonical_members, resolve_canonical_work
from app.modules.books.catalog_models import CatalogOperation, CatalogIncorporation, WorkReference, WorkRedirect
from app.modules.books.evidence import BibliographicDataError, ExternalReference, fetch_edition_evidence, normalize_isbns
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.resolution import AdditionCommand, EditionSelectionRequired, IncorporationConflict, incorporate_book
from app.modules.library.models import LibraryEntry, Reading
from tests import test_catalog_phase1 as phase1_tests


def publication(external=None, title="Phase2 novel", authors=("Phase2 Author",), isbns=(), work_key=None, pages=100):
    external = external or "phase2-" + uuid.uuid4().hex
    provider = "open-library" if work_key else "google-books"
    reference = ExternalReference(provider, "edition" if work_key else "volume", external)
    payload = {"id": external, "volumeInfo": {"title": title, "authors": list(authors), "language": "es",
               "pageCount": pages, "industryIdentifiers": [{"type": "ISBN_13", "identifier": i} for i in isbns]}}
    if work_key:
        payload["openLibrary"] = {"editionKey": reference.external_id, "workKey": work_key}
        target = "app.modules.books.evidence.open_library.detail"
    else:
        target = "app.modules.books.evidence.google_request"
    with patch(target, return_value=payload) as provider_call:
        result = fetch_edition_evidence(reference)
        provider_call.assert_called_once()
    return result


class EvidenceContract(unittest.TestCase):
    def test_equivalent_isbns_normalize_to_one_publication(self):
        self.assertEqual(normalize_isbns(["0-306-40615-2", "978 0 306 40615 7"]), ("0306406152", "9780306406157"))

    def test_invalid_isbn_and_different_publications_rejected(self):
        for values in (["9780306406158"], ["0306406153"], ["0000000000000"], ["9780306406157", "9780140328721"]):
            with self.subTest(values=values), self.assertRaises(BibliographicDataError):
                normalize_isbns(values)

    def test_missing_isbn_and_unknown_author_are_not_fabricated(self):
        evidence = publication(authors=(), pages=None)
        self.assertEqual(evidence.authors, ())
        self.assertEqual((evidence.isbn10, evidence.isbn13, evidence.page_count), (None, None, None))
        self.assertIsNone(evidence.verified_work)

    def test_provider_identifier_mismatch_rejected(self):
        reference = ExternalReference("google-books", "volume", "expected")
        with patch("app.modules.books.evidence.google_request", return_value={"id": "other"}), self.assertRaises(BibliographicDataError):
            fetch_edition_evidence(reference)

    def test_malformed_authors_are_not_interpreted_as_individual_characters(self):
        reference = ExternalReference("google-books", "volume", "expected")
        with patch("app.modules.books.evidence.google_request", return_value={"id": "expected", "volumeInfo": {"title": "Novel", "authors": "An Author"}}), self.assertRaises(BibliographicDataError):
            fetch_edition_evidence(reference)

    def test_open_library_reference_normalization_and_work_evidence(self):
        evidence = publication("/books/OL70001M", work_key="/works/OL70001W")
        self.assertEqual(evidence.reference.external_id, "OL70001M")
        self.assertEqual(evidence.verified_work.external_id, "OL70001W")


class Phase2Postgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the exact ownership-marker guard, not the application DATABASE_URL.
        phase1_tests.Phase1Postgres.setUpClass.__func__(cls)
        cls.engine = create_engine(cls.url.replace("postgresql://", "postgresql+psycopg://", 1))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.db.execute(text("SET LOCAL statement_timeout='10s'"))

    def tearDown(self):
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def command(self, evidence=None, actor=None, key=None, work=None, edition=None, selected=True):
        return AdditionCommand(uuid.UUID(actor or self.ids["user"]), key or str(uuid.uuid4()),
                               uuid.UUID(str(work)) if work else None, uuid.UUID(str(edition)) if edition else None,
                               evidence.reference if evidence else None, selected)

    def new_actor(self, db=None):
        actor = uuid.uuid4()
        (db or self.db).execute(text("INSERT INTO app.usuarios(id,display_name,role) VALUES(:id,'Phase2 synthetic','lector')"), {"id": actor})
        return str(actor)

    def counts(self):
        tables = ("obras", "ediciones", "autores", "obras_autores", "fuentes_catalogo", "entradas_biblioteca", "lecturas",
                  "operaciones_catalogo", "referencias_obras", "incorporaciones_catalogo", "efectos_operacion_catalogo")
        return {name: self.db.scalar(text("SELECT count(*) FROM app." + name)) for name in tables}

    def test_same_key_returns_exact_committed_result(self):
        evidence = publication()
        command = self.command(evidence)
        first = incorporate_book(self.db, command, evidence)
        counts = self.counts()
        self.assertEqual(incorporate_book(self.db, command, evidence), first)
        self.assertEqual(self.counts(), counts)

    def test_committed_retry_requires_no_provider_evidence(self):
        evidence = publication()
        command = self.command(evidence)
        first = incorporate_book(self.db, command, evidence)
        with patch("app.modules.books.evidence.google_request", side_effect=AssertionError("no HTTP during retry")):
            self.assertEqual(incorporate_book(self.db, command), first)

    def test_identical_reference_new_key_reuses_work_edition_library_and_reading(self):
        evidence = publication(authors=())
        first = incorporate_book(self.db, self.command(evidence), evidence)
        second = incorporate_book(self.db, self.command(evidence), evidence)
        for attr in ("physical_work_id", "edition_id", "library_entry_id", "reading_id"):
            self.assertEqual(getattr(first, attr), getattr(second, attr))
        self.assertNotEqual(first.incorporation_id, second.incorporation_id)
        self.assertEqual(second.identity_status, "insufficient")

    def test_key_reuse_for_other_reference_rejected_without_side_effects(self):
        first, second = publication(), publication()
        key = str(uuid.uuid4())
        incorporate_book(self.db, self.command(first, key=key), first)
        counts = self.counts()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(second, key=key), second)
        self.assertEqual(self.counts(), counts)

    def test_equivalent_isbn_reuses_publication_across_external_references(self):
        first = publication(isbns=("0306406152",))
        second = publication(isbns=("9780306406157",))
        a = incorporate_book(self.db, self.command(first), first)
        b = incorporate_book(self.db, self.command(second), second)
        self.assertEqual((a.physical_work_id, a.edition_id), (b.physical_work_id, b.edition_id))
        self.assertEqual(b.identity_status, "confirmed")

    def test_google_and_open_library_reuse_same_isbn_without_reassigning_work(self):
        google = publication(isbns=("9780306406157",))
        a = incorporate_book(self.db, self.command(google), google)
        ol = publication("OL74001M", work_key="OL74001W", isbns=("0306406152",))
        b = incorporate_book(self.db, self.command(ol), ol)
        self.assertEqual((a.physical_work_id, a.edition_id), (b.physical_work_id, b.edition_id))
        self.assertEqual(self.db.get(Edition, uuid.UUID(a.edition_id)).work_id, uuid.UUID(a.physical_work_id))
        self.assertEqual(self.db.scalar(text("SELECT count(*) FROM app.fuentes_catalogo WHERE edition_id=:id AND provider='libria-feed'"), {"id": a.edition_id}), 1)

    def test_same_title_author_reuses_work_without_isbn(self):
        first, second = publication(), publication()
        a = incorporate_book(self.db, self.command(first), first)
        b = incorporate_book(self.db, self.command(second, actor=self.new_actor()), second)
        self.assertEqual(a.physical_work_id, b.physical_work_id)
        self.assertNotEqual(a.edition_id, b.edition_id)
        self.assertTrue(b.work_reused)
        self.assertIsNone(self.db.get(Work, uuid.UUID(b.physical_work_id)).identity_key)

    def test_different_isbns_same_title_author_are_editions_of_same_work(self):
        first, second = publication(isbns=("9780306406157",)), publication(isbns=("9780140328721",))
        a = incorporate_book(self.db, self.command(first), first)
        b = incorporate_book(self.db, self.command(second, actor=self.new_actor()), second)
        self.assertEqual(a.physical_work_id, b.physical_work_id)
        self.assertNotEqual(a.edition_id, b.edition_id)

    def test_isbn_conflicting_authors_rejected_without_rewriting_publication(self):
        first = publication(isbns=("9780306406157",))
        a = incorporate_book(self.db, self.command(first), first)
        second = publication(isbns=("9780306406157",), authors=("Other author",))
        counts = self.counts()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(second), second)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(self.db.get(Edition, uuid.UUID(a.edition_id)).isbn13, "9780306406157")

    def test_same_reference_changed_isbn_is_conflict(self):
        first = publication(isbns=("9780306406157",))
        incorporate_book(self.db, self.command(first), first)
        second = publication(first.reference.external_id, isbns=("9780140328721",))
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(second), second)

    def test_split_isbn10_and_isbn13_in_legacy_rows_are_ambiguous(self):
        works = [Work(title="Phase2 novel"), Work(title="Phase2 novel")]
        self.db.add_all(works)
        self.db.flush()
        self.db.add_all([Edition(work_id=works[0].id, title="Phase2 novel", language="es", isbn10="0306406152"),
                         Edition(work_id=works[1].id, title="Phase2 novel", language="es", isbn13="9780306406157")])
        self.db.flush()
        evidence, before = publication(isbns=("9780306406157",)), self.counts()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(evidence), evidence)
        self.assertEqual(self.counts(), before)

    def test_recorded_contradictory_reference_is_not_silently_rebound(self):
        evidence = publication()
        operation = CatalogOperation(actor_user_id=uuid.UUID(self.ids["user"]), operation_type="admin_import",
                                     request_key=str(uuid.uuid4()), request_hash="a"*64,
                                     target_work_id=uuid.UUID(self.ids["work"]), reason="Synthetic prior contradiction", evidence={}, context={})
        self.db.add(operation)
        self.db.flush()
        self.db.add(WorkReference(work_id=uuid.UUID(self.ids["work"]), provider="google-books", reference_type="volume",
                                  external_id=evidence.reference.external_id, verification_status="contradictory", evidence={}, operation_id=operation.id))
        self.db.flush()
        before = self.counts()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(evidence), evidence)
        self.assertEqual(self.counts(), before)

    def test_verified_external_work_groups_distinct_editions_without_isbn(self):
        first = publication("OL71001M", title="La novela", work_key="OL71001W")
        second = publication("OL71002M", title="The novel", work_key="OL71001W", pages=200)
        a = incorporate_book(self.db, self.command(first), first)
        b = incorporate_book(self.db, self.command(second, actor=self.new_actor()), second)
        self.assertEqual(a.physical_work_id, b.physical_work_id)
        self.assertNotEqual(a.edition_id, b.edition_id)
        self.assertEqual(b.identity_status, "confirmed")

    def test_external_work_reference_conflicting_authors_rejected(self):
        first = publication("OL72001M", work_key="OL72001W")
        incorporate_book(self.db, self.command(first), first)
        second = publication("OL72002M", work_key="OL72001W", authors=("Other author",))
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(second), second)

    def test_external_work_and_isbn_pointing_to_different_works_rejected(self):
        first = publication("OL73001M", work_key="OL73001W")
        second = publication(title="Another novel", isbns=("9780306406157",))
        incorporate_book(self.db, self.command(first), first)
        incorporate_book(self.db, self.command(second), second)
        conflict = publication("OL73002M", title="Another novel", work_key="OL73001W", isbns=("9780306406157",))
        counts = self.counts()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(conflict), conflict)
        self.assertEqual(self.counts(), counts)

    def test_explicit_internal_edition_is_preserved_without_default(self):
        work = uuid.UUID(self.ids["work"])
        edition = Edition(work_id=work, title="Selected synthetic edition", language="es")
        self.db.add(edition)
        self.db.flush()
        result = incorporate_book(self.db, self.command(actor=self.new_actor(), work=work, edition=edition.id))
        self.assertEqual(result.edition_id, str(edition.id))

    def test_edition_of_unrelated_work_is_rejected(self):
        work = Work(title="Unrelated synthetic")
        self.db.add(work)
        self.db.flush()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(work=work.id, edition=self.ids["edition"]))

    def test_existing_reading_other_edition_is_not_overwritten(self):
        work = uuid.UUID(self.ids["work"])
        edition = Edition(work_id=work, title="Other edition", language="es")
        self.db.add(edition)
        self.db.flush()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(work=work, edition=edition.id))
        self.assertEqual(str(self.db.get(Reading, uuid.UUID(self.ids["reading"])).edition_id), self.ids["edition"])

    def test_editionless_command_rejected_without_writes(self):
        evidence, before = publication(), self.counts()
        with self.assertRaises(EditionSelectionRequired):
            incorporate_book(self.db, self.command(evidence, selected=False), evidence)
        self.assertEqual(self.counts(), before)

    def test_failure_after_provenance_flush_rolls_back_all_service_writes(self):
        evidence, before = publication(), self.counts()
        with patch("app.modules.books.resolution.CatalogOperationEffect", side_effect=RuntimeError("injected failure")), self.assertRaises(RuntimeError):
            incorporate_book(self.db, self.command(evidence), evidence)
        self.assertEqual(self.counts(), before)

    def test_service_does_not_commit_outer_transaction(self):
        evidence = publication()
        with Session(self.engine) as owner:
            result = incorporate_book(owner, self.command(evidence), evidence)
            with self.engine.connect() as observer:
                self.assertEqual(observer.scalar(text("SELECT count(*) FROM app.obras WHERE id=:id"), {"id": result.physical_work_id}), 0)
            owner.rollback()
        self.assertIsNone(self.db.get(Work, uuid.UUID(result.physical_work_id)))

    def test_provenance_receipt_snapshot_and_effects_are_recorded(self):
        evidence = publication()
        result = incorporate_book(self.db, self.command(evidence), evidence)
        operation = self.db.get(CatalogOperation, uuid.UUID(result.operation_id))
        receipt = self.db.get(CatalogIncorporation, uuid.UUID(result.incorporation_id))
        self.assertEqual(operation.evidence["snapshot"], evidence.snapshot())
        self.assertEqual(operation.context["canonical_at_incorporation"], result.canonical_work_id)
        self.assertTrue(receipt.edition_selected)
        self.assertEqual(str(receipt.edition_id), result.edition_id)
        self.assertGreater(self.db.scalar(text("SELECT count(*) FROM app.efectos_operacion_catalogo WHERE operation_id=:id"), {"id": result.operation_id}), 0)

    def test_existing_historical_rows_are_unchanged(self):
        tables = ("obras", "ediciones", "fuentes_catalogo", "entradas_biblioteca", "lecturas", "eventos_lectura", "resenas", "revisiones_resena")
        def snapshot():
            return {table: self.db.execute(text("SELECT to_jsonb(t)::text FROM app."+table+" t ORDER BY to_jsonb(t)::text")).scalars().all() for table in tables}
        before = snapshot()
        incorporate_book(self.db, self.command(work=self.ids["work"], edition=self.ids["edition"]))
        self.assertEqual(snapshot(), before)

    def test_unknown_uuid_does_not_create_work(self):
        before = self.counts()
        with self.assertRaises(CanonicalIdentityError):
            incorporate_book(self.db, self.command(work=uuid.uuid4(), edition=self.ids["edition"]))
        self.assertEqual(self.counts(), before)

    def test_single_and_bulk_resolution_share_valid_redirects_and_preserve_uuid(self):
        source, target = Work(title="Historical synthetic"), Work(title="Canonical synthetic")
        self.db.add_all([source, target])
        self.db.flush()
        operation = CatalogOperation(actor_user_id=uuid.UUID(self.ids["user"]), operation_type="merge",
                                     request_key=str(uuid.uuid4()), request_hash="a"*64, source_work_id=source.id,
                                     target_work_id=target.id, reason="Synthetic graph fixture only", evidence={}, context={})
        self.db.add(operation)
        self.db.flush()
        self.db.add(WorkRedirect(source_work_id=source.id, target_work_id=target.id, operation_id=operation.id))
        self.db.flush()
        resolved = resolve_canonical_work(self.db, source.id)
        self.assertEqual(resolved.canonical_work_id, target.id)
        self.assertEqual(canonical_mapping(self.db)[source.id], resolved)
        self.assertEqual(canonical_members(self.db, target.id), frozenset([source.id, target.id]))
        self.assertIsNotNone(self.db.get(Work, source.id))

    def test_incorporation_through_historical_uuid_preserves_physical_fk(self):
        source, target = Work(title="Historical selection"), Work(title="Canonical selection")
        self.db.add_all([source, target])
        self.db.flush()
        edition = Edition(work_id=source.id, title="Historical selection", language="es")
        operation = CatalogOperation(actor_user_id=uuid.UUID(self.ids["user"]), operation_type="merge",
                                     request_key=str(uuid.uuid4()), request_hash="a"*64, source_work_id=source.id,
                                     target_work_id=target.id, reason="Synthetic graph fixture", evidence={}, context={})
        self.db.add_all([edition, operation])
        self.db.flush()
        self.db.add(WorkRedirect(source_work_id=source.id, target_work_id=target.id, operation_id=operation.id))
        self.db.flush()
        result = incorporate_book(self.db, self.command(actor=self.new_actor(), work=source.id, edition=edition.id))
        self.assertEqual(result.physical_work_id, str(source.id))
        self.assertEqual(result.canonical_work_id, str(target.id))
        self.assertEqual(self.db.get(Edition, edition.id).work_id, source.id)
        self.assertEqual(self.db.get(Reading, uuid.UUID(result.reading_id)).work_id, source.id)
        # Another physical member must not create a duplicate canonical library
        # membership or silently replace the explicitly selected edition.
        other_edition = Edition(work_id=target.id, title="Canonical selection", language="es")
        self.db.add(other_edition)
        self.db.flush()
        before = self.counts()
        with self.assertRaises(IncorporationConflict):
            incorporate_book(self.db, self.command(actor=str(self.db.get(LibraryEntry, uuid.UUID(result.library_entry_id)).user_id),
                                                     work=target.id, edition=other_edition.id))
        self.assertEqual(self.counts(), before)

    def test_z_concurrent_same_reference_different_users_reuse_one_publication(self):
        evidence = publication(title="Concurrent synthetic " + uuid.uuid4().hex)
        with Session(self.engine) as setup:
            actors = [self.new_actor(setup), self.new_actor(setup)]
            setup.commit()
        barrier = Barrier(2)
        def attempt(actor):
            with Session(self.engine) as db, db.begin():
                db.execute(text("SET LOCAL statement_timeout='10s'"))
                barrier.wait(timeout=5)
                return incorporate_book(db, self.command(evidence, actor=actor), evidence)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(attempt, actors))
        self.assertEqual(first.physical_work_id, second.physical_work_id)
        self.assertEqual(first.edition_id, second.edition_id)
        self.assertNotEqual(first.library_entry_id, second.library_entry_id)

    def test_z_concurrent_equivalent_isbns_across_providers_reuse_one_edition(self):
        title = "Concurrent ISBN synthetic " + uuid.uuid4().hex
        records = [publication(title=title, isbns=("0306406152",)),
                   publication("OL75001M", title=title, work_key="OL75001W", isbns=("9780306406157",))]
        with Session(self.engine) as setup:
            actors = [self.new_actor(setup), self.new_actor(setup)]
            setup.commit()
        barrier = Barrier(2)
        def attempt(pair):
            actor, evidence = pair
            with Session(self.engine) as db, db.begin():
                db.execute(text("SET LOCAL statement_timeout='10s'"))
                barrier.wait(timeout=5)
                return incorporate_book(db, self.command(evidence, actor=actor), evidence)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = list(pool.map(attempt, zip(actors, records)))
        self.assertEqual((a.physical_work_id, a.edition_id), (b.physical_work_id, b.edition_id))

    def test_z_concurrent_identical_command_returns_same_receipt(self):
        evidence = publication(title="Concurrent same actor " + uuid.uuid4().hex)
        command = self.command(evidence)
        barrier = Barrier(2)
        def attempt(_):
            with Session(self.engine) as db, db.begin():
                db.execute(text("SET LOCAL statement_timeout='10s'"))
                barrier.wait(timeout=5)
                return incorporate_book(db, command, evidence)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(attempt, range(2)))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
