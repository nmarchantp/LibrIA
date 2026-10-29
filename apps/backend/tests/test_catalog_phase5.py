"""Confirmed identity comparisons through actual HTTP, PostgreSQL and ETL."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.books.canonical import canonical_members, identity_snapshot, resolve_canonical_work, CanonicalIdentityError
from app.modules.books.models import Work, Author, WorkAuthor, Edition
from app.modules.books.catalog_models import CatalogOperation, WorkRedirect
from app.modules.library.models import LibraryEntry, Reading, ReadingEvent
from app.modules.social.models import Review, ReviewRevision
from app.modules.users.identity_models import Profile
from tests import test_catalog_phase4 as phase4


class Phase5HTTP(unittest.TestCase):
    setUpClass = classmethod(phase4.Phase4HTTP.setUpClass.__func__)
    tearDownClass = classmethod(phase4.Phase4HTTP.tearDownClass.__func__)
    new_actor = phase4.Phase4HTTP.new_actor
    counts = phase4.Phase4HTTP.counts
    add_work = phase4.Phase4HTTP.add_work
    event = phase4.Phase4HTTP.event
    start = phase4.Phase4HTTP.start

    def setUp(self):
        phase4.Phase4HTTP.setUp(self)
        flag = patch.object(get_settings(), 'catalog_canonical_enabled', True)
        flag.start()
        self.addCleanup(flag.stop)
        self.base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.sequence = 0
        with Session(self.engine) as db, db.begin():
            work = db.get(Work, uuid.UUID(self.work_id))
            other = Work(title=work.title, categories=['Fiction'])
            author = Author(name='Shared synthetic author')
            db.add_all([other, author]); db.flush()
            db.add_all([WorkAuthor(work_id=work.id, author_id=author.id, position=1), WorkAuthor(work_id=other.id, author_id=author.id, position=1)])
            edition = Edition(work_id=other.id, title=other.title, language='es')
            db.add(edition); db.flush()
            self.other_id, self.other_edition = str(other.id), str(edition.id)

    def review(self, work, rating=5, status='published', actor=None):
        self.sequence += 1
        when = self.base + timedelta(minutes=self.sequence)
        with Session(self.engine) as db, db.begin():
            owner = uuid.UUID(actor or self.actor)
            profile = db.scalar(select(Profile).where(Profile.owner_user_id == owner))
            if profile is None:
                from app.modules.users.identities import create_personal_profile
                from app.modules.users.models import User
                profile = create_personal_profile(db, db.get(User, owner))
            review = Review(work_id=uuid.UUID(work), author_profile_id=profile.id, created_by_user_id=owner,
                body='Synthetic review', rating=Decimal(str(rating)), status=status, revision_number=1,
                published_at=when if status != 'draft' else None, created_at=when, updated_at=when)
            db.add(review); db.flush()
            db.add(ReviewRevision(review_id=review.id, revision_number=1, recorded_by_user_id=owner,
                body=review.body, rating=review.rating, status=status, is_spoiler=False, recorded_at=when))
            return str(review.id)

    def reading(self, work, edition=None, status='finished'):
        self.sequence += 1
        when = self.base + timedelta(minutes=self.sequence)
        with Session(self.engine) as db, db.begin():
            entry = db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == uuid.UUID(self.actor), LibraryEntry.work_id == uuid.UUID(work)))
            if entry is None:
                entry = LibraryEntry(user_id=uuid.UUID(self.actor), work_id=uuid.UUID(work), created_at=when)
                db.add(entry); db.flush()
            reading = Reading(library_entry_id=entry.id, work_id=uuid.UUID(work), edition_id=uuid.UUID(edition) if edition else None,
                status=status, current_page=42 if status == 'finished' else 0, total_pages=None,
                started_at=when-timedelta(seconds=30), finished_at=when if status == 'finished' else None, created_at=when)
            db.add(reading); db.flush()
            if status == 'finished':
                db.add(ReadingEvent(reading_id=reading.id, actor_user_id=uuid.UUID(self.actor), kind='finish',
                    previous_page=0, page=42, total_pages=None, is_public=True, created_at=when))
            return str(reading.id)

    def redirect(self, source=None, target=None, db=None):
        source, target = source or self.work_id, target or self.other_id
        def insert(session):
            operation = CatalogOperation(actor_user_id=uuid.UUID(self.actor), operation_type='merge',
                request_key=str(uuid.uuid4()), request_hash='a'*64, source_work_id=uuid.UUID(source), target_work_id=uuid.UUID(target),
                reason='Synthetic confirmed relationship fixture; no consolidation', evidence={'synthetic':True}, context={'reviewed':True})
            session.add(operation); session.flush()
            session.add(WorkRedirect(source_work_id=uuid.UUID(source), target_work_id=uuid.UUID(target), operation_id=operation.id))
            session.flush()
        if db is not None:
            insert(db)
        else:
            with Session(self.engine) as session, session.begin():
                insert(session)

    def metrics(self, canonical):
        from app.modules.books.service import equivalent_work_ids
        from app.modules.books.community import public_rating, reading_statistics
        from app.modules.analytics.etl import extract, transform
        from app.modules.analytics.reader_evidence import extract_personal
        from app.modules.analytics.recommendation_profiles import _finished_readings, _reader_books
        cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)
        with patch.object(get_settings(), 'catalog_canonical_enabled', canonical), Session(self.engine) as db:
            group = equivalent_work_ids(db, uuid.UUID(self.work_id))
            rating, count = public_rating(db, group)
            listing = self.client.get('/api/reviews/by-book/'+self.work_id).json()['items']
            library = self.client.get('/api/readings/me').json()
            prepared = transform(*extract(db, self.base-timedelta(days=1), cutoff))
            evidence = extract_personal(db, cutoff)
            books = _reader_books(uuid.UUID(self.actor), _finished_readings(db, cutoff), evidence, cutoff)
            label = lambda key: 'A' if str(key)==self.work_id else 'B' if str(key)==self.other_id else 'other'
            return {'groups':sorted(label(k) for k in group), 'public_reviews':len(listing),
                'rating':str(Decimal(str(rating)).normalize()) if rating is not None else None, 'rated_readers':count,
                'statistics':{k:v for k,v in reading_statistics(db, group).items() if k!='readerPreview'},
                'library_memberships':len(library), 'profile_books':len(books),
                'profile_work_ids':sorted(label(b['work_id']) for b in books),
                'etl_finished_attempts':sum(str(r['user_id'])==self.actor and r['event_kind']=='finish' for r in prepared[1]),
                'etl_review_work_ids':sorted(label(r['work_id']) for r in prepared[6] if str(r['user_id'])==self.actor)}

    def test_a_reproducible_comparison_before_any_public_activation(self):
        self.review(self.work_id, 5); self.review(self.other_id, 1)
        self.reading(self.work_id); self.reading(self.other_id)
        independent = {'legacy':self.metrics(False), 'confirmed':self.metrics(True)}
        self.assertEqual(independent['legacy']['groups'], ['A','B'])
        self.assertEqual(independent['confirmed']['groups'], ['A'])
        self.assertEqual(independent['confirmed']['public_reviews'], 1)
        self.redirect()
        confirmed = {'legacy':self.metrics(False), 'confirmed':self.metrics(True)}
        self.assertEqual(confirmed['confirmed']['profile_books'], 0)
        self.assertEqual(confirmed['confirmed']['public_reviews'], 1)
        report = {'scope':'synthetic_owned_postgresql_http_and_etl', 'classification':'expected_change',
            'scenarios':{'same_title_author_without_confirmation':independent, 'confirmed_redirect_same_reader_low_latest_rating':confirmed},
            'notes':[
                'Title/author coincidence splits without confirmed evidence; both physical works and reviews remain.',
                'Confirmed redirect selects latest review before visibility and rating filters; rereads stay separate.',
                'Phase 3 library already used confirmed grouping, unlike legacy reviews; unchanged counts are expected.',
                'No anonymized persistent dataset was authorized or accessed.']}
        report['comparison_sha256'] = hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()
        (Path(__file__).resolve().parents[3]/'docs/catalog-canonical-phase5-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

    def test_same_title_author_never_groups_without_confirmation(self):
        from app.modules.books.service import equivalent_work_ids
        with Session(self.engine) as db:
            self.assertEqual(equivalent_work_ids(db, uuid.UUID(self.work_id)), {uuid.UUID(self.work_id)})
            self.assertNotEqual(resolve_canonical_work(db, uuid.UUID(self.work_id)).canonical_work_id,
                                resolve_canonical_work(db, uuid.UUID(self.other_id)).canonical_work_id)

    def test_confirmed_uuid_library_attempts_editions_and_history_preserved(self):
        first = self.reading(self.work_id, self.edition_id)
        second = self.reading(self.other_id)
        self.redirect()
        library = self.client.get('/api/readings/me').json()
        self.assertEqual(len(library), 1)
        self.assertEqual(library[0]['catalog_volume']['libria']['canonicalWorkId'], self.other_id)
        attempts = self.client.get(f'/api/readings/library/{self.work_id}/attempts').json()
        self.assertEqual({r['reading_id'] for r in attempts}, {first,second})
        self.assertEqual(next(r for r in attempts if r['reading_id']==first)['edition_id'], self.edition_id)
        self.assertEqual(self.client.get('/api/books/'+self.work_id).json()['libria']['workId'], self.other_id)

    def test_current_reviews_rating_list_and_hidden_privacy_barrier(self):
        old = self.review(self.work_id, 5)
        self.review(self.other_id, 1, 'hidden')
        self.redirect()
        from app.modules.books.community import public_rating
        with Session(self.engine) as db:
            self.assertEqual(public_rating(db, {uuid.UUID(self.work_id)}), (None,0))
            self.assertEqual(db.scalar(select(text('count(*)')).select_from(Review).where(Review.created_by_user_id==uuid.UUID(self.actor))), 2)
        self.assertEqual(self.client.get('/api/reviews/by-book/'+self.work_id).json()['items'], [])
        self.assertEqual(self.client.get('/api/reviews/'+old).status_code, 404)
        own = self.client.get('/api/reviews/me', params={'work_id':self.work_id}).json()
        self.assertEqual(len(own), 2)

    def test_draft_latest_does_not_resurrect_old_public_or_high_profile_rating(self):
        self.review(self.work_id,5); self.review(self.other_id,1,'draft')
        self.reading(self.work_id); self.redirect()
        values = self.metrics(True)
        self.assertEqual(values['public_reviews'],0)
        self.assertEqual(values['rated_readers'],0)
        self.assertEqual(values['profile_books'],0)

    def test_newer_low_rating_replaces_older_high_rating_on_both_reading_uuids(self):
        self.review(self.work_id,5); self.review(self.other_id,2)
        self.reading(self.work_id); self.reading(self.other_id); self.redirect()
        result = self.metrics(True)
        self.assertEqual((result['public_reviews'],result['rated_readers'],Decimal(result['rating'])), (1,1,Decimal('2')))
        self.assertEqual(result['profile_books'],0)
        self.assertEqual(result['etl_finished_attempts'],2)
        self.assertEqual(result['etl_review_work_ids'],['B'])

    def test_rating_per_reader_not_per_alias(self):
        self.review(self.work_id,5); self.review(self.other_id,1)
        other = self.new_actor(); self.review(self.work_id,3,actor=other)
        self.redirect()
        result = self.metrics(True)
        self.assertEqual((result['public_reviews'],result['rated_readers'],Decimal(result['rating'])), (2,2,Decimal('2')))

    def test_shared_projection_rebuilds_when_graph_changes_and_rollback_restores_version(self):
        from app.modules.analytics.projections import refresh_reader
        self.review(self.work_id,5); self.review(self.other_id,4)
        self.reading(self.work_id); self.reading(self.other_id)
        with Session(self.engine) as db, db.begin():
            first = refresh_reader(db, uuid.UUID(self.actor))
            before = identity_snapshot(db).version
            try:
                with db.begin_nested():
                    self.redirect(db=db)
                    self.assertNotEqual(identity_snapshot(db).version,before)
                    raise RuntimeError('injected')
            except RuntimeError:
                pass
            self.assertEqual(identity_snapshot(db).version,before)
            self.assertEqual(refresh_reader(db, uuid.UUID(self.actor))['id'],first['id'])
        self.redirect()
        with Session(self.engine) as db, db.begin():
            current = refresh_reader(db, uuid.UUID(self.actor))
            self.assertNotEqual(first['id'],current['id'])
            self.assertEqual(len(current['payload']['books']),1)
            self.assertEqual(len(current['payload']['events']),2)
            self.assertEqual(current['payload']['identity_version'],identity_snapshot(db).version)

    def test_cycles_fail_closed_without_rewriting_any_historical_ids(self):
        from sqlalchemy.exc import IntegrityError
        with Session(self.engine) as db, db.begin():
            self.redirect(db=db)
            with self.assertRaises(IntegrityError):
                self.redirect(self.other_id,self.work_id,db=db)
            db.rollback()
        with Session(self.engine) as db:
            self.assertEqual(resolve_canonical_work(db,uuid.UUID(self.work_id)).canonical_work_id,uuid.UUID(self.work_id))

    def test_no_ai_calls_during_identity_resolution_or_graph_dirty_marking(self):
        self.redirect()
        with patch('app.modules.analytics.gemini_worker._invoke',side_effect=AssertionError('No AI')):
            with Session(self.engine) as db:
                self.assertEqual(len(canonical_members(db,uuid.UUID(self.work_id))),2)
                self.assertEqual(db.execute(text('SELECT count(*) FROM analytics.dirty_readers WHERE owner_id=:owner'), {'owner':self.actor}).scalar(),1)

    def test_flags_off_by_default_and_merges_still_blocked(self):
        settings = Settings(_env_file=None)
        self.assertFalse(settings.catalog_canonical_enabled)
        self.assertFalse(settings.catalog_discovery_enabled)
        with self.assertRaises(ValueError):
            Settings(_env_file=None,catalog_admin_merge_enabled=True)
        self.assertTrue(Settings(_env_file=None,catalog_discovery_enabled=True,catalog_canonical_enabled=True).catalog_canonical_enabled)

    def test_add_historical_alias_reuses_effective_membership_and_latest_attempt(self):
        self.reading(self.work_id,self.edition_id)
        latest = self.reading(self.other_id)
        self.redirect()
        before = self.counts()
        response = self.add_work()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['reading_id'],latest)
        self.assertEqual(self.counts(),before)
        self.assertEqual(len(self.client.get('/api/readings/me').json()),1)

    def test_canonical_etl_publication_profile_version_and_stale_identity(self):
        from app.modules.analytics.etl import extract, transform, publish
        from app.modules.analytics.reader_evidence import extract_personal
        from app.modules.analytics.recommendation_sync import _latest_state
        self.review(self.work_id,3); self.review(self.other_id,5)
        one = self.reading(self.work_id,self.edition_id); two = self.reading(self.other_id)
        self.redirect()
        cutoff = datetime.now(timezone.utc)+timedelta(seconds=1)
        with Session(self.engine) as db, db.begin():
            run = uuid.uuid4()
            db.execute(text("""INSERT INTO analytics.ejecuciones_etl
                (id,status,started_at,source_cutoff_at,transform_version,business_date,period_start,run_kind,phase)
                VALUES (:id,'running',now(),:cutoff,'phase5-test','2092-01-01',:start,'daily','running')"""),
                {'id':run,'cutoff':cutoff,'start':self.base-timedelta(days=1)})
            prepared = transform(*extract(db,self.base-timedelta(days=1),cutoff))
            publish(db.connection(),run,prepared,personal=extract_personal(db,cutoff))
            facts = db.execute(text('SELECT work_id,edition_id FROM analytics.hechos_lectura WHERE etl_run_id=:run AND user_id=:owner'),{'run':run,'owner':self.actor}).all()
            self.assertEqual(len(facts),2)
            self.assertTrue(all(str(r.work_id)==self.other_id for r in facts))
            self.assertEqual({str(r.edition_id) if r.edition_id else None for r in facts},{self.edition_id,None})
            profile = db.execute(text('SELECT payload,identity_version FROM ia.reader_profile_versions WHERE etl_run_id=:run AND owner_id=:owner'),{'run':run,'owner':self.actor}).mappings().one()
            self.assertEqual(len(profile['payload']['books']),2)
            self.assertEqual({b['work_id'] for b in profile['payload']['books']},{self.other_id})
            self.assertEqual(profile['identity_version'],identity_snapshot(db).version)
            from app.modules.analytics.gemini_context import profile_evidence_units
            units = profile_evidence_units(profile['payload'])
            self.assertEqual(sum(u.source_kind=='review' for u in units),1)
            self.assertEqual(sum(u.source_kind=='reading' for u in units),2)
            self.assertIsNotNone(_latest_state(db,uuid.UUID(self.actor)))
            self.assertEqual(_latest_state(db,uuid.UUID(self.actor))['eligible_books_count'],1)
            third = Work(title='Synthetic third root'); db.add(third); db.flush()
            self.redirect(self.other_id,str(third.id),db=db)
            self.assertIsNone(_latest_state(db,uuid.UUID(self.actor)))
            self.assertEqual(str(db.get(Reading,uuid.UUID(one)).work_id),self.work_id)
            self.assertEqual(str(db.get(Reading,uuid.UUID(two)).work_id),self.other_id)
            db.rollback()  # do not pollute unrelated monitoring regression fixtures

    def test_ai_access_threshold_counts_unique_canonical_works(self):
        from app.modules.analytics.eligibility import reader_eligibility
        self.reading(self.work_id); self.reading(self.other_id); self.redirect()
        with Session(self.engine) as db:
            self.assertEqual(reader_eligibility(db,uuid.UUID(self.actor))['book_count'],1)

    def test_worker_context_uses_canonical_work_and_current_review(self):
        from app.modules.analytics.gemini_worker import _individual_context
        self.review(self.work_id,5); latest = self.review(self.other_id,3)
        reading = self.reading(self.work_id); self.redirect()
        with Session(self.engine) as db:
            event = db.scalar(select(ReadingEvent).where(ReadingEvent.reading_id==uuid.UUID(reading)))
            payload, units = _individual_context(db,{'reading_event_id':event.id,'owner_id':uuid.UUID(self.actor)})
            self.assertEqual(payload['work_id'],self.other_id)
            self.assertTrue(all(str(u.work_id)==self.other_id for u in units))
            self.assertEqual([str(u.source_id) for u in units if u.source_kind=='review'],[latest])

    def test_community_cached_release_is_not_served_under_another_identity_version(self):
        from app.modules.analytics.community import community_release
        from app.modules.analytics.etl import ZONE
        day = datetime.now(timezone.utc).astimezone(ZONE).date()
        with Session(self.engine) as db, db.begin():
            db.execute(text("""INSERT INTO analytics.community_releases(release_date,payload,source_run_ids)
                VALUES (:day,'{"status":"ready","identity_version":"old-fixture"}','{}') ON CONFLICT DO NOTHING"""), {'day':day})
            stored = db.execute(text('SELECT payload FROM analytics.community_releases WHERE release_date=:day'),{'day':day}).scalar_one()
            with patch.object(db,'commit'):
                current = community_release(db)
            self.assertEqual(current['identity_version'],identity_snapshot(db).version)
            self.assertEqual(db.execute(text('SELECT payload FROM analytics.community_releases WHERE release_date=:day'),{'day':day}).scalar_one(),stored)
            db.rollback()

    def test_reviews_resolve_external_reference_without_an_imported_edition(self):
        from tests.test_catalog_phase3 import volume
        item = volume()
        with patch('app.modules.books.evidence.google_request',return_value=item):
            added = self.client.post('/api/readings/library',json={'book_ref':item['id'],'book_title':'Display',
                'external_reference':{'provider':'google-books','reference_type':'volume','external_id':item['id']},
                'edition_selected':False},headers={'Idempotency-Key':str(uuid.uuid4())})
        self.assertEqual(added.status_code,200,added.text)
        self.assertIsNone(added.json()['edition_id'])
        self.review(added.json()['work_id'],5)
        listed = self.client.get('/api/reviews/by-book/'+item['id'])
        self.assertEqual(listed.status_code,200,listed.text)
        self.assertEqual(len(listed.json()['items']),1)

    def test_exact_external_references_do_not_cross_provider_namespaces(self):
        from app.modules.books.models import CatalogSource
        from app.modules.books.canonical import reference_work
        reference = 'OL'+str(uuid.uuid4().int % 10**12)+'M'
        with Session(self.engine) as db, db.begin():
            db.add(CatalogSource(edition_id=uuid.UUID(self.edition_id),provider='libria-feed',external_id=reference,fetched_at=self.base))
            db.flush()
            self.assertEqual(str(reference_work(db,reference)),self.work_id)
            self.assertIsNone(reference_work(db,'openlibrary:'+reference))
