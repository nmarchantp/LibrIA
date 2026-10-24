"""Catalog imports preserve provider data and existing review/reading identities."""
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
import httpx

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.router import google_request, store_volume


class CatalogMirrorTest(unittest.TestCase):
    def setUp(self):
        fallback = patch('app.modules.books.router.open_library.search', return_value={'items': [], 'has_more': False, 'next_page': None})
        self.fallback = fallback.start()
        self.addCleanup(fallback.stop)
        google = patch('app.modules.books.router.google_request', return_value={'items': [], 'has_more': False})
        google.start()
        self.addCleanup(google.stop)
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.volume = {"id": "mirror-" + uuid.uuid4().hex, "kind": "books#volume", "etag": "original",
            "volumeInfo": {"title": "Mirror " + uuid.uuid4().hex, "authors": ["Test Author"], "pageCount": 230,
                "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567890"}],
                "imageLinks": {"thumbnail": "https://example.com/cover.jpg"}, "language": "es"},
            "saleInfo": {"country": "CL", "isEbook": True}, "accessInfo": {"viewability": "PARTIAL"},
            "unknownFutureField": {"preserved": [1, 2]}}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_search_persists_before_response_and_repeat_uses_local_catalog(self):
        result = {"kind": "books#volumes", "totalItems": 34, "items": [self.volume]}
        with patch("app.modules.books.router.google_request", return_value=result) as provider:
            first = self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json()["items"][0]["volumeInfo"], self.volume["volumeInfo"])
            self.assertNotEqual(first.json()["items"][0]["id"], self.volume["id"])
            self.assertEqual(first.json()["items"][0]["libria"]["externalId"], self.volume["id"])
            self.assertEqual(first.json()["items"][0]["libria"]["catalogOrigin"], "google_books")
            self.assertEqual(first.json()["totalItems"], 1)
            self.assertEqual(len(self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]}).json()["items"]), 1)
            self.assertEqual(provider.call_count, 1)
        source = self.db.scalar(select(CatalogSource).where(CatalogSource.external_id == self.volume["id"], CatalogSource.provider == "google-books"))
        self.assertEqual(source.payload, self.volume)

    def test_complete_detail_is_served_offline(self):
        with patch("app.modules.books.router.google_request", return_value=self.volume) as provider:
            url = "/api/books/" + self.volume["id"]
            first = self.client.get(url).json()
            self.assertEqual(first["volumeInfo"], self.volume["volumeInfo"])
            self.assertEqual(first["unknownFutureField"], self.volume["unknownFutureField"])
            self.assertEqual(first["libria"]["externalId"], self.volume["id"])
            self.assertEqual(first["libria"]["ratingsCount"], 0)
            self.assertEqual(first["libria"]["readingStats"]["finished"], 0)
            self.assertEqual(self.client.get(url).json(), first)
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(self.client.get("/api/books").status_code, 200)
            self.assertEqual(provider.call_count, 1)

    def test_exact_local_match_does_not_prevent_external_discovery(self):
        store_volume(self.db, self.volume)
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 1, "items": [self.volume]}) as provider:
            response = self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["items"][0]["libria"]["externalId"], self.volume["id"])
            provider.assert_called_once()

    def test_native_catalog_book_is_identified_as_libria(self):
        title = "Libro LibrIA " + uuid.uuid4().hex
        work = Work(title=title, identity_key="native-" + uuid.uuid4().hex, original_language="es")
        self.db.add(work)
        self.db.flush()
        edition = Edition(work_id=work.id, title=title, language="es")
        self.db.add(edition)
        self.db.flush()
        self.db.add(CatalogSource(edition_id=edition.id, provider="libria-feed",
                                  external_id="native-" + uuid.uuid4().hex,
                                  fetched_at=datetime.now(timezone.utc)))
        self.db.flush()
        response = self.client.get("/api/books", params={"q": title})
        self.assertEqual(response.json()["items"][0]["libria"]["catalogOrigin"], "libria")

    def test_google_search_requests_and_returns_only_spanish_books(self):
        english = {**self.volume, "id": "mirror-" + uuid.uuid4().hex,
                   "volumeInfo": {**self.volume["volumeInfo"], "title": "English only", "language": "en",
                                  "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567891"}]}}
        query = self.volume["volumeInfo"]["title"]
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 2, "items": [english, self.volume]}) as provider:
            response = self.client.get("/api/books", params={"q": query})
        self.assertEqual(response.json()["totalItems"], 1)
        self.assertEqual(response.json()["items"][0]["volumeInfo"]["language"], "es")
        provider.assert_called_once_with(query=query)

    def test_alternate_editions_are_selectable_but_share_one_work(self):
        base = {**self.volume, "volumeInfo": {**self.volume["volumeInfo"], "title": "Erase una vez un corazon roto",
                                              "authors": ["Garber, Stephanie"]}}
        standard = {**self.volume, "id": "standard-" + uuid.uuid4().hex,
                    "volumeInfo": {**self.volume["volumeInfo"], "title": "Érase una vez un corazón roto",
                                   "authors": ["Stephanie Garber"],
                                   "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567891"}]}}
        collector = {**self.volume, "id": "collector-" + uuid.uuid4().hex,
                     "volumeInfo": {**self.volume["volumeInfo"], "title": "Erase una vez un corazón roto - Ed. Limitada",
                                    "authors": ["Stephanie Garber"],
                                    "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567892"}]}}
        query = "erase una vez un corazon roto"
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 3, "items": [collector, standard, base]}):
            response = self.client.get("/api/books", params={"q": query})
        self.assertEqual(response.json()["totalItems"], 1)
        self.assertEqual(response.json()["items"][0]["libria"]["editionCount"], 3)
        sources = self.db.scalars(select(CatalogSource).where(
            CatalogSource.external_id.in_([base["id"], standard["id"], collector["id"]]),
            CatalogSource.provider == "google-books")).all()
        self.assertEqual(len({self.db.get(Edition, source.edition_id).work_id for source in sources}), 1)

    def test_new_presentation_is_an_edition_of_the_clean_main_title(self):
        marker = uuid.uuid4().hex[:10]
        title = f"Una corte de rosas y espinas {marker}"
        standard = {**self.volume, "id": "standard-" + uuid.uuid4().hex,
                    "volumeInfo": {**self.volume["volumeInfo"], "title": title,
                    "authors": ["Sarah J. Test"],
                    "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567821"}]}}
        presentation = {**self.volume, "id": "presentation-" + uuid.uuid4().hex,
                        "volumeInfo": {**self.volume["volumeInfo"],
                        "title": title + ". Nueva presentación (Edición española)",
                        "authors": ["Sarah J. Test"],
                        "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567822"}]}}
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 2, "items": [presentation, standard]}):
            response = self.client.get("/api/books", params={"q": title})
        self.assertEqual(response.json()["totalItems"], 1)
        item = response.json()["items"][0]
        self.assertEqual(item["volumeInfo"]["title"], title)
        self.assertEqual(item["libria"]["editionCount"], 2)

    def test_same_title_by_different_authors_remains_two_suggestions(self):
        first = {**self.volume, "volumeInfo": {**self.volume["volumeInfo"],
                 "title": "El visitante", "authors": ["Autora Uno"]}}
        second = {**self.volume, "id": "homonym-" + uuid.uuid4().hex,
                  "volumeInfo": {**self.volume["volumeInfo"],
                  "title": "El visitante", "authors": ["Autor Dos"],
                  "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567891"}]}}
        query = "El visitante"
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 2, "items": [first, second]}):
            response = self.client.get("/api/books", params={"q": query})
        self.assertEqual(response.json()["totalItems"], 2)
        self.assertEqual({item["volumeInfo"]["authors"][0] for item in response.json()["items"]},
                         {"Autora Uno", "Autor Dos"})
        sources = self.db.scalars(select(CatalogSource).where(
            CatalogSource.external_id.in_([first["id"], second["id"]]),
            CatalogSource.provider == "google-books")).all()
        self.assertEqual(len({self.db.get(Edition, source.edition_id).work_id for source in sources}), 2)

    def test_non_spanish_works_are_excluded_even_if_more_exact(self):
        english = {**self.volume, "volumeInfo": {**self.volume["volumeInfo"], "title": "Harry Potter",
                   "authors": ["English Author"], "language": "en",
                   "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567891"}]}}
        spanish = {**self.volume, "id": "spanish-" + uuid.uuid4().hex,
                   "volumeInfo": {**self.volume["volumeInfo"], "title": "Harry Potter y la piedra filosofal",
                   "authors": ["Spanish Author"], "language": "es",
                   "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567892"}]}}
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 2, "items": [english, spanish]}):
            response = self.client.get("/api/books", params={"q": "Harry Potter"})
        languages = [item["volumeInfo"]["language"] for item in response.json()["items"]]
        self.assertTrue(languages)
        self.assertEqual(set(languages), {"es"})

    def test_works_are_ordered_by_earliest_known_publication_date(self):
        marker = uuid.uuid4().hex[:10]
        books = []
        for suffix, year, isbn in (("Tercero", "2003", "9781234567811"),
                                   ("Primero", "2001-06", "9781234567812"),
                                   ("Segundo", "2002-01-15", "9781234567813")):
            books.append({**self.volume, "id": suffix.lower() + "-" + uuid.uuid4().hex,
                          "volumeInfo": {**self.volume["volumeInfo"],
                          "title": f"Coleccion {marker} {suffix}", "authors": ["Autora Cronologica"],
                          "publishedDate": year,
                          "industryIdentifiers": [{"type": "ISBN_13", "identifier": isbn}]}})
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 3, "items": books}):
            response = self.client.get("/api/books", params={"q": f"Coleccion {marker}"})
        self.assertEqual([item["libria"]["earliestEditionDate"] for item in response.json()["items"]],
                         ["2001-06", "2002-01-15", "2003"])

    def test_bilingual_title_bridges_editions_into_one_result(self):
        marker = uuid.uuid4().hex[:10]
        spanish_title = f"Saga {marker} y la cámara secreta"
        standard = {**self.volume, "volumeInfo": {**self.volume["volumeInfo"],
                    "title": spanish_title, "authors": ["J. K. Test"],
                    "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567891"}]}}
        bilingual = {**self.volume, "id": "bilingual-" + uuid.uuid4().hex,
                     "volumeInfo": {**self.volume["volumeInfo"],
                     "title": spanish_title + f" (Ed. Minalima) / Saga {marker} and the Chamber of Secrets",
                     "authors": ["J. K. Test"],
                     "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567892"}]}}
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 2, "items": [bilingual, standard]}):
            response = self.client.get("/api/books", params={"q": f"Saga {marker}"})
        self.assertEqual(response.json()["totalItems"], 1)
        self.assertEqual(response.json()["items"][0]["libria"]["editionCount"], 2)
        work_id = uuid.UUID(response.json()["items"][0]["libria"]["workId"])
        edition_work_ids = set(self.db.scalars(select(Edition.work_id).where(
            Edition.title.ilike(f"%Saga {marker}%"))).all())
        self.assertEqual(edition_work_ids, {work_id})
        self.assertEqual(self.db.scalar(select(Work).where(Work.id == work_id)).id, work_id)

    def test_enrichment_keeps_library_and_review_work_identity(self):
        account = self.client.post("/api/auth/register", json={"email": uuid.uuid4().hex + "@example.com",
            "password": "test-password", "display_name": "Mirror test"}).json()
        headers = {"Authorization": "Bearer " + account["access_token"]}
        book = {"book_ref": self.volume["id"], "book_title": "Legacy title"}
        original = self.client.post("/api/readings/library", json=book, headers=headers).json()
        with patch("app.modules.books.router.google_request", return_value=self.volume):
            self.assertEqual(self.client.get("/api/books/" + self.volume["id"]).status_code, 200)
        restored = self.client.get("/api/readings/me", headers=headers).json()[0]
        for key in ("work_id", "edition_id", "reading_id"):
            self.assertEqual(original[key], restored[key])
        self.assertEqual(restored["catalog_volume"], self.volume)
        self.assertEqual(restored["total_pages"], 230)
        review = self.client.post("/api/reviews", headers=headers, json={"work_id": original["work_id"],
            "edition_id": original["edition_id"], "body": "Review remains linked to this book", "rating": 4})
        self.assertEqual(review.status_code, 201, review.text)

    def test_empty_result_is_cached(self):
        with patch("app.modules.books.router.google_request", return_value={"totalItems": 0}) as provider:
            query = uuid.uuid4().hex
            result = self.client.get("/api/books", params={"q": query}).json()
            self.assertEqual(result['totalItems'], 0)
            self.assertEqual(result['items'], [])
            self.client.get("/api/books", params={"q": query})
            self.assertEqual(provider.call_count, 1)

    def test_provider_failure_returns_partial_results_with_short_cooldown(self):
        query = "missing-" + uuid.uuid4().hex
        with patch("app.modules.books.router.google_request", side_effect=HTTPException(502, "Unavailable")):
            response = self.client.get("/api/books", params={"q": query})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["partial"])
            self.assertEqual(response.json()["items"], [])
            self.assertIn("limitada", response.json()["warning"])
            self.assertNotIn("pueden faltar libros", response.json()["warning"])
        matching = {**self.volume, "volumeInfo": {**self.volume["volumeInfo"], "title": query}}
        result = {"totalItems": 1, "items": [matching]}
        with patch("app.modules.books.router.google_request", return_value=result) as provider:
            self.assertTrue(self.client.get("/api/books", params={"q": query, "refresh": True}).json()["partial"])
            provider.assert_not_called()
            from app.modules.books.models import CatalogQuery
            from datetime import timedelta
            cached = self.db.get(CatalogQuery, "es-only-v4:all:" + query + ":google_books:0")
            cached.fetched_at -= timedelta(seconds=31)
            self.db.flush()
            self.assertEqual(self.client.get("/api/books", params={"q": query}).json()["totalItems"], 1)
            provider.assert_called_once()

    def test_transient_google_failure_is_retried(self):
        request = httpx.Request("GET", "https://www.googleapis.com/books/v1/volumes")
        with patch("app.modules.books.google_books.httpx.Client") as client:
            transport = client.return_value.__enter__.return_value
            transport.get.side_effect = [httpx.Response(503, request=request),
                httpx.Response(200, request=request, json=self.volume)]
            self.assertEqual(google_request("/" + self.volume["id"]), self.volume)
            self.assertEqual(transport.get.call_count, 2)

    def test_google_search_restricts_provider_results_to_spanish(self):
        request = httpx.Request("GET", "https://www.googleapis.com/books/v1/volumes")
        with patch("app.modules.books.google_books.httpx.Client") as client:
            transport = client.return_value.__enter__.return_value
            transport.get.return_value = httpx.Response(200, request=request, json={"totalItems": 0})
            google_request(query="quijote")
            self.assertEqual(transport.get.call_args.kwargs["params"]["langRestrict"], "es")

    def test_google_search_paginates_full_pages_and_deduplicates(self):
        request = httpx.Request("GET", "https://www.googleapis.com/books/v1/volumes")
        first_page = [{"id": f"book-{index}", "volumeInfo": {"title": str(index)}} for index in range(40)]
        second_page = [first_page[-1], {"id": "book-40", "volumeInfo": {"title": "40"}}]
        with patch("app.modules.books.google_books.httpx.Client") as client:
            transport = client.return_value.__enter__.return_value
            transport.get.side_effect = [httpx.Response(200, request=request, json={"items": first_page}),
                                         httpx.Response(200, request=request, json={"items": second_page})]
            result = google_request(query="harry potter", pages=2)
        self.assertEqual(len(result["items"]), 41)
        self.assertEqual(transport.get.call_args_list[1].kwargs["params"]["startIndex"], 40)

    def test_search_modes_use_discovery_for_title_and_qualify_author(self):
        query = "Alas de sangre " + uuid.uuid4().hex
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 0, "items": []}) as provider:
            response = self.client.get("/api/books", params={"q": query, "search_by": "title"})
        self.assertEqual(response.status_code, 200, response.text)
        provider.assert_called_once_with(query=query)
        with patch("app.modules.books.router.google_request",
                   return_value={"totalItems": 0, "items": []}) as provider:
            response = self.client.get("/api/books", params={"q": query, "search_by": "author"})
        self.assertEqual(response.status_code, 200, response.text)
        provider.assert_called_once_with(query="inauthor:" + query)
