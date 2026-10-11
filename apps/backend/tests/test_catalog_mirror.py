"""Catalog imports preserve provider data and existing review/reading identities."""
import unittest
import uuid
from unittest.mock import patch
import httpx

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.books.models import CatalogSource
from app.modules.books.router import google_request, store_volume


class CatalogMirrorTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.volume = {"id": "mirror-" + uuid.uuid4().hex, "kind": "books#volume", "etag": "original",
            "volumeInfo": {"title": "Mirror " + uuid.uuid4().hex, "authors": ["Test Author"], "pageCount": 230,
                "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781234567890"}],
                "imageLinks": {"thumbnail": "https://example.com/cover.jpg"}, "language": "en"},
            "saleInfo": {"country": "CL", "isEbook": True}, "accessInfo": {"viewability": "PARTIAL"},
            "unknownFutureField": {"preserved": [1, 2]}}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_search_response_is_lossless_and_repeat_never_calls_google(self):
        result = {"kind": "books#volumes", "totalItems": 34, "items": [self.volume]}
        with patch("app.modules.books.router.google_request", return_value=result) as provider:
            first = self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json(), result)
            self.assertEqual(self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]}).json(), result)
            self.assertEqual(provider.call_count, 1)
        source = self.db.scalar(select(CatalogSource).where(CatalogSource.external_id == self.volume["id"], CatalogSource.provider == "google-books"))
        self.assertEqual(source.payload, self.volume)

    def test_complete_detail_is_served_offline(self):
        with patch("app.modules.books.router.google_request", return_value=self.volume) as provider:
            url = "/api/books/" + self.volume["id"]
            self.assertEqual(self.client.get(url).json(), self.volume)
            self.assertEqual(self.client.get(url).json(), self.volume)
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(self.client.get("/api/books").status_code, 200)
            self.assertEqual(provider.call_count, 1)

    def test_local_match_does_not_hide_other_search_results(self):
        store_volume(self.db, self.volume)
        second = {**self.volume, "id": "mirror-" + uuid.uuid4().hex,
                  "volumeInfo": {**self.volume["volumeInfo"], "title": self.volume["volumeInfo"]["title"] + " sequel"}}
        result = {"totalItems": 2, "items": [self.volume, second]}
        with patch("app.modules.books.router.google_request", return_value=result) as provider:
            response = self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), result)
            provider.assert_called_once_with(query=self.volume["volumeInfo"]["title"])
            self.assertEqual(self.client.get("/api/books", params={"q": self.volume["volumeInfo"]["title"]}).json(), result)
            self.assertEqual(provider.call_count, 1)

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
            self.assertEqual(self.client.get("/api/books", params={"q": query}).json(), {"totalItems": 0})
            self.client.get("/api/books", params={"q": query})
            self.assertEqual(provider.call_count, 1)

    def test_provider_failure_returns_explicit_partial_results_without_caching(self):
        store_volume(self.db, self.volume)
        query = self.volume["volumeInfo"]["title"]
        with patch("app.modules.books.router.google_request", side_effect=HTTPException(502, "Unavailable")):
            response = self.client.get("/api/books", params={"q": query})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["partial"])
            self.assertEqual(response.json()["items"], [self.volume])
            self.assertIn("pueden faltar libros", response.json()["warning"])
        result = {"totalItems": 1, "items": [self.volume]}
        with patch("app.modules.books.router.google_request", return_value=result) as provider:
            self.assertEqual(self.client.get("/api/books", params={"q": query}).json(), result)
            provider.assert_called_once()

    def test_transient_google_failure_is_retried(self):
        request = httpx.Request("GET", "https://www.googleapis.com/books/v1/volumes")
        with patch("app.modules.books.router.httpx.Client") as client:
            transport = client.return_value.__enter__.return_value
            transport.get.side_effect = [httpx.Response(503, request=request),
                httpx.Response(200, request=request, json=self.volume)]
            self.assertEqual(google_request("/" + self.volume["id"]), self.volume)
            self.assertEqual(transport.get.call_count, 2)
