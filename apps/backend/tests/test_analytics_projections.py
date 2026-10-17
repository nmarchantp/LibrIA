"""Real SQL integration with rolled-back fixtures, never product seed data."""
import unittest
from unittest.mock import patch
from sqlalchemy import text
import test_ai_recommendations as fixtures
from app.modules.analytics.projections import reader_snapshot,refresh_reader,refresh_pending
from app.modules.analytics.adaptive_ai import book_context
from app.modules.analytics.recommendations import prepare
from app.modules.users.identity_models import ProfileCapability,Profile,ProfileMember
from app.modules.social.models import ProfileFollow,ReviewLike
from app.modules.users.identities import personal_profile


class ProjectionIntegrationTest(unittest.TestCase):
    setUp=fixtures.RecommendationsTest.setUp
    tearDown=fixtures.RecommendationsTest.tearDown
    book=fixtures.RecommendationsTest.book
    make_positive=fixtures.RecommendationsTest.make_positive

    def test_profile_refresh_joins_active_request_without_restarting_deadline_or_revision(self):
        first=self.client.post('/api/me/ai/profile/refresh')
        self.assertEqual(first.status_code,202,first.text)
        job=first.json()['job']
        self.db.execute(text("UPDATE ia.jobs SET status='processing' WHERE id=:id"),{'id':job['id']})
        second=self.client.post('/api/me/ai/profile/refresh')
        self.assertEqual(second.status_code,202,second.text)
        joined=second.json()['job']
        self.assertEqual(joined['id'],job['id'])
        self.assertEqual(joined['revision'],job['revision'])
        self.assertEqual(joined['deadline_at'],job['deadline_at'])
        self.assertEqual(joined['status'],'processing')

    def test_profile_polling_never_runs_etl_or_takes_its_reader_lock(self):
        with patch('app.modules.analytics.projections.extract_reader',side_effect=AssertionError('ETL must run in worker')):
            response=self.client.get('/api/me/ai/profile')
        self.assertEqual(response.status_code,200,response.text)

    def test_job_status_does_not_invalidate_clean_analytics_but_source_changes_do(self):
        from app.modules.analytics.adaptive_ai import enqueue
        refresh_reader(self.db,self.user.id)
        enqueue(self.db,self.user.id,'profile')
        self.db.execute(text("UPDATE ia.jobs SET status='processing' WHERE owner_id=:owner"),{'owner':self.user.id})
        self.assertIsNone(self.db.execute(text('SELECT owner_id FROM analytics.dirty_readers WHERE owner_id=:owner'),{'owner':self.user.id}).scalar())
        self.make_positive()
        self.assertEqual(self.db.execute(text('SELECT owner_id FROM analytics.dirty_readers WHERE owner_id=:owner'),{'owner':self.user.id}).scalar(),self.user.id)

    def test_snapshot_is_versioned_owner_scoped_and_rebuilt_after_rating_change(self):
        review=self.make_positive()
        first=refresh_reader(self.db,self.user.id)
        run=first['id'];snapshot=reader_snapshot(self.db,self.user.id)
        book=next(b for b in snapshot['books'] if b.get('rating')==5)
        self.assertEqual(len(snapshot['books']),10)
        self.assertEqual(refresh_reader(self.db,self.user.id)['id'],run)
        self.assertFalse(any(b.get('rating') for b in reader_snapshot(self.db,self.other.id)['books']))
        response=self.client.put('/api/reviews/'+review['id'],json={'body':'Una opinión revisada.','rating':2,'status':'draft'})
        self.assertEqual(response.status_code,200,response.text)
        changed=refresh_reader(self.db,self.user.id)
        self.assertNotEqual(changed['id'],run)
        old=self.db.execute(text('SELECT payload FROM analytics.projection_runs WHERE id=:id'),{'id':run}).scalar_one()
        self.assertEqual(next(b for b in old['books'] if b['work_id']==book['work_id'])['rating'],5)

    def test_inference_reads_analytical_projection_without_transactional_extraction(self):
        self.make_positive();payload=reader_snapshot(self.db,self.user.id)
        work=next(b['work_id'] for b in payload['books'] if b.get('rating'))
        with patch('app.modules.analytics.projections.extract_reader',side_effect=AssertionError('Unexpected transactional read')):
            self.assertTrue(book_context(self.db,self.user.id,work)['rated'])

    def test_social_reaction_preserves_negative_review_context_not_a_positive_rating(self):
        profile=personal_profile(self.db,self.other)
        work=self.db.execute(text('SELECT work_id FROM app.entradas_biblioteca WHERE user_id=:owner LIMIT 1'),{'owner':self.user.id}).scalar()
        from app.main import app
        from app.modules.auth.dependencies import get_current_user
        app.dependency_overrides[get_current_user]=lambda:self.other
        response=self.client.post('/api/reviews',json={'work_id':str(work),'body':'No disfruté este libro.','rating':1,'status':'published'})
        self.assertEqual(response.status_code,201,response.text)
        self.db.add(ReviewLike(review_id=response.json()['id'],user_id=self.user.id));self.db.flush()
        snapshot=reader_snapshot(self.db,self.user.id)
        reaction=next(s for s in snapshot['social'] if s['kind']=='review_reaction')
        self.assertEqual(reaction['reviewed_rating'],1)
        self.assertEqual(reaction['reviewed_text'],'No disfruté este libro.')
        self.assertFalse(any(b.get('rating') for b in snapshot['books']))
        self.db.add(ProfileFollow(profile_id=profile.id,user_id=self.user.id));self.db.flush()
        self.assertIn('follow',[s['kind'] for s in reader_snapshot(self.db,self.user.id)['social']])

    def test_professional_dashboard_rejects_readers_and_influencers_allows_authors_organizations(self):
        endpoint='/api/analytics/group/community'
        self.assertEqual(self.client.get(endpoint).status_code,403)
        profile=personal_profile(self.db,self.user)
        self.db.add(ProfileCapability(profile_id=profile.id,capability='influencer'));self.db.flush()
        self.assertEqual(self.client.get(endpoint).status_code,403)
        payload={'status':'insufficient_group','minimum_participants':10}
        with patch('app.modules.analytics.community.community_release',return_value=payload):
            self.db.add(ProfileCapability(profile_id=profile.id,capability='autor'));self.db.flush()
            self.assertEqual(self.client.get(endpoint).status_code,200)
            self.db.delete(self.db.get(ProfileCapability,(profile.id,'autor')));self.db.flush()
            for kind in ('libreria','editorial'):
                organization=Profile(kind='organization',organization_type=kind,display_name='Organization')
                self.db.add(organization);self.db.flush()
                self.db.add(ProfileMember(profile_id=organization.id,user_id=self.user.id,permission='editor'));self.db.flush()
                self.assertEqual(self.client.get(endpoint).status_code,200)
                organization.verification_status='suspended';self.db.flush()
            self.assertEqual(self.client.get(endpoint).status_code,403)

    def test_rebuild_is_idempotent_and_does_not_duplicate_history(self):
        self.make_positive();refresh_pending(self.db,rebuild=True)
        first=refresh_reader(self.db,self.user.id)['id']
        refresh_pending(self.db,rebuild=True)
        self.assertEqual(refresh_reader(self.db,self.user.id)['id'],first)

    def test_recommendations_consume_social_snapshot_and_current_own_ratings(self):
        self.make_positive()
        context,_=prepare(self.db,self.user.id,'unclassified')
        self.assertEqual(context['history'][0]['rating'],5)
        self.assertIn('social_discovery',context)
