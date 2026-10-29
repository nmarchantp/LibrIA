"""User-facing catalog rules, with remote providers mocked."""
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.books.edition_discovery import discover_editions
from app.modules.books.evidence import ExternalReference, evidence_from_snapshot
from app.modules.books.catalog_models import CatalogOperation, WorkReference
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor
from app.modules.books.identity import identity_matches
from tests import test_catalog_phase3 as phase3


def evidence(item):
    return evidence_from_snapshot(ExternalReference("google-books", "volume", item["id"]), item)


class EditionTitleIdentity(unittest.TestCase):
    def test_screenshot_novel_variants_match(self):
        base = "Una corte de rosas y espinas"
        variants = [base, base + " (NE): #1", base + ". Nueva presentación (Edición española)",
            "Una Corte de Rosas y Espinas. Edición Especial Tapa Dura / a Court of Thorns and Roses (a Court of Thorns and Roses 1)",
            "Una Corte de Rosas Y Espinas. Edición Tapa Dura / / a Court of Thorns and Roses (ACOTAR 1)"]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(identity_matches(base, ["Sarah J. Maas"], variant, ["Sarah J Maas"]))

    def test_companion_books_meaningful_subtitles_and_other_volumes_stay_distinct(self):
        base = "Una corte de rosas y espinas"
        for variant in [base + ". Libro para colorear / A Court of Thorns and Roses. Coloring Book",
                        base + ". Edición especial: libro para colorear", base + " (adaptación gráfica)",
                        "Resumen de " + base, base + ": otra historia", base + " #2", base + " tomo 1",
                        "Una corte de niebla y furia", "Una corte de hielo y estrellas"]:
            with self.subTest(variant=variant):
                self.assertFalse(identity_matches(base, ["Sarah J. Maas"], variant, ["Sarah J Maas"]))
        self.assertFalse(identity_matches(base, ["Sarah J. Maas"], base, ["Otro autor"]))


class EditionDiscovery(unittest.TestCase):
    def test_pages_verified_editions_and_rejects_homonyms(self):
        selected = phase3.volume(title="Una novela", isbn="9780306406157")
        second = phase3.volume(title="Una novela", isbn="9780140328721")
        third = phase3.volume(title="Una novela", isbn="9788478884452")
        homonym = phase3.volume(title="Una novela", isbn="9788478884452")
        homonym["volumeInfo"]["authors"] = ["Otro autor"]
        with patch("app.modules.books.edition_discovery.google_request", side_effect=[
                {"items": [selected, second, homonym], "has_more": True, "next_start_index": 40},
                {"items": [third], "has_more": False}]) as search, patch(
                "app.modules.books.edition_discovery.fetch_edition_evidence",
                side_effect=[evidence(second), evidence(third)]) as detail:
            found = discover_editions(evidence(selected))
        self.assertEqual([item.isbn13 for item in found], ["9780140328721", "9788478884452"])
        self.assertEqual(search.call_args_list[1].kwargs["start_index"], 40)
        self.assertEqual(detail.call_count, 2)

    def test_quota_failure_preserves_editions_already_verified(self):
        selected = phase3.volume(title="Una novela")
        second = phase3.volume(title="Una novela", isbn="9780140328721")
        with patch("app.modules.books.edition_discovery.google_request", side_effect=[
                {"items": [second], "has_more": True, "next_start_index": 40}, HTTPException(502)]), patch(
                "app.modules.books.edition_discovery.fetch_edition_evidence", return_value=evidence(second)):
            self.assertEqual(len(discover_editions(evidence(selected))), 1)


class CatalogRulesHTTP(unittest.TestCase):
    setUpClass = classmethod(phase3.Phase3HTTP.setUpClass.__func__)
    tearDownClass = classmethod(phase3.Phase3HTTP.tearDownClass.__func__)
    setUp = phase3.Phase3HTTP.setUp
    new_actor = phase3.Phase3HTTP.new_actor
    counts = phase3.Phase3HTTP.counts
    payload = phase3.Phase3HTTP.payload
    add = phase3.Phase3HTTP.add

    def test_repair_existing_edition_variants_preserves_history_and_groups_search(self):
        from app.modules.books.merge_scope import scope_state
        from app.modules.library.models import LibraryEntry, Reading
        from app.modules.social.models import Review, ReviewRevision
        from app.modules.users.identities import create_personal_profile
        from app.modules.users.identity_models import AccountPermission
        from app.modules.users.models import User
        from scripts.repair_catalog_group import group_plan, repair_group

        base = "Una corte de rosas y espinas " + uuid.uuid4().hex
        titles = [base, base, base + " (NE)", base + ". Edición Tapa Dura / / a Court of Thorns and Roses (ACOTAR 1)"]
        items = [phase3.volume(title=title, isbn=phase3.unique_isbn()) for title in titles]
        now = datetime.now(timezone.utc)
        cover = "https://example.invalid/novel.jpg"
        actor = uuid.UUID(self.actor)
        with Session(self.engine) as db, db.begin():
            db.add(AccountPermission(user_id=actor, permission="admin"))
            author = Author(name="Discovery Author")
            db.add(author)
            db.flush()
            works = []
            for index, item in enumerate(items):
                work = Work(title=item["volumeInfo"]["title"])
                db.add(work)
                db.flush()
                works.append(work.id)
                db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=1))
                edition = Edition(work_id=work.id, title=work.title, language="es",
                                  isbn13=evidence(item).isbn13, cover_url=cover if index == 1 else None)
                db.add(edition)
                db.flush()
                db.add(CatalogSource(edition_id=edition.id, provider="google-books", external_id=item["id"],
                                     payload=item, fetched_at=now))
                if index < 2:
                    entry = LibraryEntry(user_id=actor, work_id=work.id)
                    db.add(entry)
                    db.flush()
                    db.add(Reading(library_entry_id=entry.id, work_id=work.id, status="pending", current_page=0))
            profile = create_personal_profile(db, db.get(User, actor))
            review = Review(author_profile_id=profile.id, created_by_user_id=actor, work_id=works[0],
                            body="Preserve this review", rating=4.75, status="published", published_at=now,
                            created_at=now, updated_at=now)
            db.add(review)
            db.flush()
            db.add(ReviewRevision(review_id=review.id, revision_number=1, recorded_by_user_id=actor,
                                  body=review.body, rating=review.rating, status="published", is_spoiler=False))
        with patch.object(get_settings(), "catalog_editionless_enabled", True), patch.object(
                get_settings(), "catalog_canonical_enabled", True), patch.object(
                get_settings(), "catalog_admin_preview_enabled", True), patch.object(
                get_settings(), "catalog_admin_merge_enabled", True):
            with Session(self.engine) as db:
                before = scope_state(db, works)
            repaired = repair_group(self.engine, actor, works[0], works[1:])
            self.assertEqual(repaired["after"]["canonical_work_count"], 1)
            self.assertEqual(repaired["after"]["edition_count"], 4)
            self.assertEqual(len(repaired["operation_ids"]), 3)
            self.assertEqual(repair_group(self.engine, actor, works[0], works[1:])["operation_ids"], [])
            with Session(self.engine) as db:
                after = scope_state(db, works)
                for key, row in before.items():
                    self.assertEqual(after[key], row, key)
                self.assertEqual(group_plan(db, works[0], works[1:])["canonical_work_count"], 1)
            with patch("app.modules.books.discovery.google_request", return_value={"items": items}):
                result = self.client.get("/api/books", params={"q": base, "search_by": "title"})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(len(result.json()["items"]), 1)
            row = result.json()["items"][0]
            self.assertEqual(row["volumeInfo"]["title"], base)
            self.assertEqual(row["volumeInfo"]["imageLinks"]["thumbnail"], cover)
            self.assertEqual(row["libria"]["editionCount"], 4)
            self.assertEqual(row["libria"]["averageRating"], 4.75)
            self.assertIsNone(row["libria"]["editionId"])
            administrative = self.client.get('/api/admin/catalog/works', params={"q": base})
            self.assertEqual(len(administrative.json()), 1)
            library = self.client.get("/api/readings/me")
            self.assertEqual(len(library.json()), 1)

    def test_previously_saved_editionless_work_recovers_editions_without_another_work(self):
        title = "Anterior " + uuid.uuid4().hex
        selected = phase3.volume(title=title, isbn=phase3.unique_isbn())
        second = phase3.volume(title=title, isbn=phase3.unique_isbn())
        with Session(self.engine) as db, db.begin():
            work = Work(title=title)
            author = Author(name=selected["volumeInfo"]["authors"][0])
            db.add_all([work, author])
            db.flush()
            db.add(WorkAuthor(work_id=work.id, author_id=author.id, position=1))
            operation = CatalogOperation(actor_user_id=uuid.UUID(self.actor), operation_type="library_add",
                request_key=str(uuid.uuid4()), request_hash="a" * 64, target_work_id=work.id,
                reason="Earlier editionless fixture", evidence={}, context={})
            db.add(operation)
            db.flush()
            db.add(WorkReference(work_id=work.id, provider="google-books", reference_type="volume",
                external_id=selected["id"], verification_status="provisional", evidence={}, operation_id=operation.id))
            work_id = str(work.id)
        before = self.counts()
        with patch.object(get_settings(), "catalog_editionless_enabled", True), patch(
                "app.modules.books.evidence.google_request", return_value=selected), patch(
                "app.modules.books.edition_discovery.discover_editions", return_value=(evidence(second),)):
            response = self.client.post("/api/readings/library", json={
                "book_ref": work_id, "book_title": title, "edition_selected": False},
                headers={"Idempotency-Key": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["work_id"], work_id)
        self.assertIsNone(response.json()["edition_id"])
        after = self.counts()
        self.assertEqual(after["obras"], before["obras"])
        self.assertEqual(after["ediciones"], before["ediciones"] + 2)

    def test_save_imports_editions_then_search_groups_local_and_omits_google_duplicates(self):
        title = "Agrupada " + uuid.uuid4().hex
        selected = phase3.volume(title=title, isbn=phase3.unique_isbn())
        second = phase3.volume(title=title, isbn=phase3.unique_isbn())
        unimported = phase3.volume(title=title, isbn=phase3.unique_isbn())
        homonym = phase3.volume(title=title, isbn=phase3.unique_isbn())
        homonym["volumeInfo"]["authors"] = ["Otro autor"]
        before = self.counts()
        key = str(uuid.uuid4())
        with patch.object(get_settings(), "catalog_editionless_enabled", True), patch(
                "app.modules.books.evidence.google_request", return_value=selected), patch(
                "app.modules.books.edition_discovery.discover_editions", return_value=(evidence(second),)):
            response = self.add(selected, key=key, edition_selected=False)
        self.assertEqual(response.status_code, 200, response.text)
        work_id = response.json()["work_id"]
        self.assertIsNone(response.json()["edition_id"])
        after = self.counts()
        self.assertEqual(after["obras"], before["obras"] + 1)
        self.assertEqual(after["ediciones"], before["ediciones"] + 2)
        with Session(self.engine) as db:
            editions = db.scalars(select(Edition).where(Edition.work_id == uuid.UUID(work_id))).all()
            self.assertEqual({item.isbn13 for item in editions}, {evidence(selected).isbn13, evidence(second).isbn13})
        with patch.object(get_settings(), "catalog_editionless_enabled", True), patch(
                "app.modules.books.discovery.google_request", return_value={"items": [selected, second, unimported, homonym]}):
            search = self.client.get("/api/books", params={"q": title, "search_by": "title"})
        self.assertEqual(search.status_code, 200, search.text)
        rows = search.json()["items"]
        self.assertEqual(len(rows), 2)
        local = next(item for item in rows if item["id"] == work_id)
        self.assertEqual(local["libria"]["catalogOrigin"], "libria")
        self.assertEqual(local["libria"]["editionCount"], 2)
        self.assertEqual(len(local["libria"]["editions"]), 2)
        self.assertEqual(next(item for item in rows if item["id"] == homonym["id"])["libria"]["catalogOrigin"], "google_books")
        with patch.object(get_settings(), "catalog_editionless_enabled", True), patch(
                "app.modules.books.evidence.google_request", side_effect=AssertionError("Replay fetched provider")):
            replay = self.add(selected, key=key, edition_selected=False)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(self.counts(), after)
