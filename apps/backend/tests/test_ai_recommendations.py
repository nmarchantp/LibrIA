"""Personalized candidates, owner isolation, validated selection and caching."""
from datetime import datetime, timezone
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.analytics.recommendations import prepare, validate_selection
from app.modules.books.models import Work, Edition, CatalogSource
from app.modules.library.models import LibraryEntry
from app.modules.users.models import User
from app.modules.users.identities import create_personal_profile


class RecommendationsTest(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(display_name="Reader one")
        self.other = User(display_name="Reader two")
        self.db.add_all([self.user, self.other])
        self.db.flush()
        create_personal_profile(self.db, self.user)
        create_personal_profile(self.db, self.other)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.owned = self.book("Owned book", author="Unique reader author")
        self.candidate = self.book("New candidate", author="Unique reader author")
        self.foreign = self.book("Foreign history", author="Other author")
        self.client.post("/api/readings/library", json={"book_ref": self.owned, "book_title": "Owned book", "page_count": 100})
        for index in range(9):
            work = Work(title=f"Recommendation prerequisite {index}")
            self.db.add(work)
            self.db.flush()
            self.db.add(LibraryEntry(user_id=self.user.id, work_id=work.id))
        self.db.flush()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def book(self, title, author):
        work = Work(title=title)
        self.db.add(work)
        self.db.flush()
        edition = Edition(work_id=work.id, title=title, language="es", page_count=100)
        self.db.add(edition)
        self.db.flush()
        ref = "recommend-" + uuid.uuid4().hex
        payload = {"id": ref, "volumeInfo": {"title": title, "authors": [author], "categories": ["Unique test category"], "pageCount": 100, "language": "es"}}
        for provider in ("google-books", "libria-feed"):
            self.db.add(CatalogSource(edition_id=edition.id, provider=provider, external_id=ref,
                fetched_at=datetime.now(timezone.utc), payload=payload if provider == "google-books" else None))
        self.db.flush()
        return ref

    def make_positive(self,rating=5):
        work=self.db.execute(text('SELECT ed.work_id FROM app.ediciones ed JOIN app.fuentes_catalogo s ON s.edition_id=ed.id WHERE s.external_id=:ref LIMIT 1'),{'ref':self.owned}).scalar_one()
        response=self.client.post('/api/reviews',json={'work_id':str(work),'body':'Me gustaron los personajes y la historia.','rating':rating,'status':'draft'})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def test_simulated_provenance_is_rejected(self):
        url = "/api/analytics/me/recommendations"
        self.assertEqual(self.client.get(url + "?provenance=simulated").status_code, 422)
        self.assertEqual(self.client.post(url, json={"provenance": "simulated"}).status_code, 422)

    def test_demo_books_are_not_candidates_or_history(self):
        for ref in (self.owned, self.candidate):
            edition_id = self.db.execute(text("SELECT edition_id FROM app.fuentes_catalogo WHERE external_id=:ref LIMIT 1"), {"ref": ref}).scalar_one()
            self.db.execute(text("INSERT INTO app.procedencia_demo (entity_type, entity_id, dataset_version) VALUES ('ediciones', :id, 'test')"), {"id": edition_id})
        context, candidates = prepare(self.db, self.user.id, "unclassified")
        self.assertEqual(context["history"], [])
        self.assertNotIn(self.candidate, [item["metadata"]["id"] for item in candidates])

    def test_history_is_owner_scoped_and_owned_books_excluded(self):
        self.make_positive()
        app.dependency_overrides[get_current_user] = lambda: self.other
        self.client.post("/api/readings/library", json={"book_ref": self.foreign, "book_title": "Foreign history", "page_count": 100})
        context, candidates = prepare(self.db, self.user.id, "unclassified")
        self.assertEqual([item["id"] for item in context["history"]], [self.owned])
        self.assertNotIn(self.owned, [c["metadata"]["id"] for c in candidates])
        candidate = next(c for c in candidates if c["metadata"]["id"] == self.candidate)
        self.assertIn("author", candidate["reasons"])
        self.assertIn("category", candidate["reasons"])

    def test_model_cannot_invent_books_criteria_or_duplicate_choices(self):
        self.make_positive()
        _, candidates = prepare(self.db, self.user.id, "unclassified")
        selection = {"id": self.candidate, "criterion": "author"}
        self.assertEqual(len(validate_selection({"recommendations": [selection]}, candidates)), 1)
        for selections in ([{"id": "imaginary", "criterion": "author"}],
                           [{"id": self.candidate, "criterion": "personality"}], [selection, selection], []):
            with self.assertRaises(ValueError):
                validate_selection({"recommendations": selections}, candidates)

    def test_generation_cached_and_never_shared_between_users(self):
        self.make_positive()
        _, candidates = prepare(self.db, self.user.id, "unclassified")
        generated = validate_selection({"recommendations": [{"id": self.candidate, "criterion": "author"}]}, candidates)
        with patch("app.modules.analytics.recommendations.provider_ready", return_value=True), \
             patch("app.modules.analytics.recommendations.generate", return_value=generated) as provider:
            url = "/api/analytics/me/recommendations"
            self.assertEqual(self.client.get(url).json()["status"], "needs_generation")
            response = self.client.post(url, json={"provenance": "unclassified"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["items"], generated)
            self.assertEqual(self.client.get(url).json()["items"], generated)
            self.assertEqual(self.client.post(url, json={"provenance": "unclassified"}).status_code, 200)
            self.assertEqual(provider.call_count, 1)
            app.dependency_overrides[get_current_user] = lambda: self.other
            other = self.client.get(url).json()
            self.assertEqual(other["items"], [])
            self.assertEqual(other["status"], "locked")

    def test_authentication_required_and_missing_model_has_no_fake_results(self):
        self.make_positive()
        with patch("app.modules.analytics.recommendations.provider_ready", return_value=False):
            self.assertEqual(self.client.post("/api/analytics/me/recommendations", json={"provenance": "unclassified"}).status_code, 503)
        app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get("/api/analytics/me/recommendations").status_code, 401)
        self.assertEqual(self.db.execute(text("SELECT count(*) FROM analytics.recomendaciones_ia WHERE owner_user_id=:id"), {"id": self.user.id}).scalar_one(), 0)

    def test_no_positive_ratings_does_not_call_ollama_or_treat_completion_as_liking(self):
        started=self.client.post('/api/readings/events',json={'book_ref':self.owned,'book_title':'Owned book','page_count':100,'event':'start'})
        self.assertEqual(started.status_code,201,started.text)
        completed=self.client.post('/api/readings/events',json={'book_ref':self.owned,'book_title':'Owned book','page_count':100,'event':'finish','reading_id':started.json()['reading_id']})
        self.assertEqual(completed.status_code,201,completed.text)
        with patch('app.modules.analytics.recommendations.generate') as provider:
            self.assertEqual(self.client.post('/api/analytics/me/recommendations',json={}).json()['status'],'no_positive_ratings')
            provider.assert_not_called()
        self.make_positive(rating=3)
        with patch('app.modules.analytics.recommendations.generate') as provider:
            response=self.client.post('/api/analytics/me/recommendations',json={})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'no_positive_ratings')
        self.assertEqual(response.json()['items'],[])
        provider.assert_not_called()

    def test_more_excludes_shown_works_and_all_their_editions(self):
        self.make_positive()
        _,first=prepare(self.db,self.user.id,'unclassified')
        ids=[item['metadata']['id'] for item in first]
        _,second=prepare(self.db,self.user.id,'unclassified',exclude_ids=ids)
        self.assertTrue(set(ids).isdisjoint(item['metadata']['id'] for item in second))
        work=self.db.execute(text('SELECT ed.work_id FROM app.ediciones ed JOIN app.fuentes_catalogo s ON s.edition_id=ed.id WHERE s.external_id=:ref LIMIT 1'),{'ref':self.candidate}).scalar_one()
        ed=Edition(work_id=work,title='Another edition',language='es',page_count=100)
        self.db.add(ed);self.db.flush()
        self.db.add(CatalogSource(edition_id=ed.id,provider='google-books',external_id='alternate-'+uuid.uuid4().hex,fetched_at=datetime.now(timezone.utc),payload={'volumeInfo':{'title':'Another edition'}}))
        self.db.flush()
        _,remaining=prepare(self.db,self.user.id,'unclassified',exclude_ids=[self.candidate])
        self.assertFalse(any(item['volume']['volumeInfo']['title']=='Another edition' for item in remaining))

    def test_multiple_batches_are_cached_separately_and_can_be_requested_immediately(self):
        self.make_positive()
        def selection(context,candidates):
            return validate_selection({'recommendations':[{'id':c['metadata']['id'],'criterion':next(iter(c['reasons']))} for c in candidates[:4]]},candidates)
        with patch('app.modules.analytics.recommendations.provider_ready',return_value=True),patch('app.modules.analytics.recommendations.generate',side_effect=selection) as provider:
            first=self.client.post('/api/analytics/me/recommendations',json={})
            self.assertEqual(first.status_code,200,first.text)
            ids=[item['volume']['id'] for item in first.json()['items']]
            second=self.client.post('/api/analytics/me/recommendations',json={'exclude_ids':ids})
            self.assertEqual(second.status_code,200,second.text)
            self.assertTrue(set(ids).isdisjoint(item['volume']['id'] for item in second.json()['items']))
            again=self.client.post('/api/analytics/me/recommendations',json={'exclude_ids':ids})
            self.assertEqual(second.json()['items'],again.json()['items'])
            self.assertEqual(provider.call_count,2)
