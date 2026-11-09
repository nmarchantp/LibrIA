"""Phase-1 storage and rules. Fixtures roll back; no public routes enable moderation."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.modules.users.models import User
from app.modules.users.identity_models import AccountPermission
from app.modules.social.models import Post, PostComment, PostImage, PostBookCover, PublicationEvent, EventAttendance
from app.modules.social.moderation_models import ModerationRevision, ModerationAudit, ModerationRequest, ModerationAttachment
from app.modules.social.moderation_rules import analyze_content, normalize_text, Moderator, Ruleset
from app.modules.social.moderation_service import (
    prepare_edit, private_revision, assert_revision_current, public_snapshot,
    require_moderation_admin, claim_request, complete_request, ProposedAttachment,
)
from tests import test_mural_feed as fixtures

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=')
RULE_FILE = Path(__file__).parents[1] / 'app/modules/social/moderation_rules.json'


class ModerationRulesTest(unittest.TestCase):
    def test_legitimate_literary_discussion_does_not_trigger_keywords(self):
        for body in [
            'La novela denuncia el racismo, la xenofobia y la misoginia.',
            'Comentamos homofobia, transfobia y derechos de personas trans en la literatura.',
            'El protagonista enfrenta amenazas, violencia y acoso sexual.',
            'No me gustó este libro. El villano es un idiota, pero el final es brillante.',
            'El discurso de odio es un tema central de esta historia.',
            'Me encanta el dark romance y los personajes moralmente grises.',
            'Estoy leyendo una novela con personajes gays y una comunidad de inmigrantes.',
        ]:
            with self.subTest(body=body):
                result = analyze_content(body)
                self.assertEqual(result.status, 'approved')
                self.assertFalse(result.flagged)
                self.assertEqual(result.findings, ())

    def test_all_categories_go_to_review_never_automatic_rejection(self):
        cases = {
            'racism_xenophobia':'Los inmigrantes son una plaga',
            'homophobia_transphobia':'Los gays son enfermos',
            'misogyny_sexism':'Las mujeres son inferiores',
            'hate_speech':'Exterminen a los inmigrantes',
            'harassment_insults':'Eres un idiota',
            'threats':'Te voy a matar',
            'sexual_harassment':'Envíame tus nudes',
            'spam':'compra ' * 12,
        }
        for category, body in cases.items():
            with self.subTest(category=category):
                result = analyze_content(body)
                self.assertEqual(result.status, 'pending_review')
                self.assertTrue(result.flagged)
                self.assertIn(category, [finding.category for finding in result.findings])
                self.assertTrue(all(0 <= finding.confidence <= 1 and finding.rule_id and finding.reason for finding in result.findings))
                self.assertEqual(result.ruleset_version, 'mvp-es-1')

    def test_normalization_preserves_original_and_handles_common_evasion(self):
        for body in ['¡ÉRES UN IMBÉCIL!', 'ＥＲＥＳ un idiota', 'e\u200bres   un idiota', '3r3s un idiota']:
            original = body
            self.assertTrue(analyze_content(body).flagged)
            self.assertEqual(body, original)
        self.assertEqual(normalize_text('  ¡Árbol! \n LIBRO  '), '¡arbol! libro')

    def test_quotes_are_not_a_universal_bypass(self):
        self.assertEqual(analyze_content('Te escribo: "te voy a matar"').status, 'pending_review')

    def test_spam_and_input_limits(self):
        self.assertTrue(analyze_content('https://a.test ' * 5).flagged)
        self.assertTrue(analyze_content('a' * 30).flagged)
        self.assertFalse(analyze_content('¡Holaaaa! https://unlibro.test').flagged)
        with self.assertRaises(ValueError): analyze_content('x' * 20001)
        with self.assertRaises(TypeError): analyze_content(None)

    def test_operator_configuration_is_validated_and_versioned(self):
        config = json.loads(RULE_FILE.read_text(encoding='utf-8'))
        config['version'] = 'test-disabled'
        for rule in config['rules']: rule['enabled'] = False
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rules.json'
            path.write_text(json.dumps(config), encoding='utf-8')
            moderator = Moderator.from_file(path)
            self.assertFalse(moderator.analyze('Eres un idiota').flagged)
            self.assertEqual(moderator.analyze('Hola').ruleset_version, 'test-disabled')
            config['rules'][0]['pattern'] = '('
            path.write_text(json.dumps(config), encoding='utf-8')
            with self.assertRaises(ValidationError): Moderator.from_file(path)
            with self.assertRaises(FileNotFoundError): Moderator.from_file(path.with_name('missing.json'))
        config = json.loads(RULE_FILE.read_text(encoding='utf-8'))
        config['rules'].append(config['rules'][0])
        with self.assertRaises(ValidationError): Ruleset.model_validate(config)
        config = json.loads(RULE_FILE.read_text(encoding='utf-8'))
        config['rules'][0]['pattern'] = '.*'
        with self.assertRaises(ValidationError): Ruleset.model_validate(config)


class ModerationStorageTest(unittest.TestCase):
    setUp = fixtures.MuralFeedTest.setUp
    tearDown = fixtures.MuralFeedTest.tearDown
    make_reading = fixtures.MuralFeedTest.make_reading
    make_event = fixtures.MuralFeedTest.make_event

    def proposal(self, body='Eres un idiota'):
        return {'publication_type':'note', 'source':'community', 'body':body,
                'book_ref':self.post.book_ref, 'book_title':self.post.book_title}

    def prepare(self, proposal=None, key=None, **kwargs):
        return prepare_edit(self.db, self.author, 'publication', self.post.id,
                            proposal or self.proposal(), request_key=key or uuid.uuid4(), expected_version=1, **kwargs)

    def count(self, model):
        return self.db.scalar(select(func.count()).select_from(model))

    def test_compatibility_defaults_do_not_change_public_visibility(self):
        comment = PostComment(user_id=self.author.id, post_id=self.post.id, body='Original')
        self.db.add(comment); self.db.flush()
        for item in [self.post, self.review, comment]:
            self.assertEqual(item.moderation_status, 'approved')
            self.assertEqual(item.moderation_version, 1)
        self.assertIsNone(comment.deleted_at)
        self.assertEqual(self.review.status, 'published')
        self.assertTrue(any(item['id'] == str(self.post.id) for item in self.client.get('/api/posts').json()))
        self.assertEqual(self.count(ModerationRevision), 0)
        self.assertEqual(self.client.get('/api/admin/moderation').status_code,403)

    def test_pending_edit_preserves_approved_content_and_private_payload(self):
        original = public_snapshot(self.db, self.post)
        revision = self.prepare()
        self.assertEqual(revision.status, 'pending_review')
        self.assertEqual(revision.proposal['body'], 'Eres un idiota')
        self.assertEqual(public_snapshot(self.db, self.post), original)
        self.assertEqual(self.post.moderation_status, 'approved')
        self.assertEqual(self.count(ModerationAudit), 1)
        public = self.client.get('/api/posts').json()
        self.assertEqual(next(item['body'] for item in public if item['id'] == str(self.post.id)), 'Public note')
        self.assertEqual(private_revision(self.db,self.author,revision.id).id,revision.id)
        with self.assertRaises(HTTPException) as denied: private_revision(self.db,self.viewer,revision.id)
        self.assertEqual(denied.exception.status_code,404)

    def test_no_flags_prepares_approved_revision_without_applying_it(self):
        revision = self.prepare(self.proposal('Una crítica literaria sobre racismo y violencia.'))
        self.assertEqual(revision.status, 'approved')
        self.assertEqual(revision.findings, [])
        self.assertEqual(self.post.body, 'Public note')

    def test_real_admin_permission_not_role_label(self):
        self.viewer.role = 'admin'; self.db.flush()
        with self.assertRaises(HTTPException): require_moderation_admin(self.db,self.viewer)
        self.db.add(AccountPermission(user_id=self.viewer.id,permission='admin')); self.db.flush()
        self.assertEqual(require_moderation_admin(self.db,self.viewer).id,self.viewer.id)
        revision = self.prepare()
        self.assertEqual(private_revision(self.db,self.viewer,revision.id,administrative=True).id,revision.id)

    def test_ownership_status_and_version_are_enforced(self):
        with self.assertRaises(HTTPException):
            prepare_edit(self.db,self.viewer,'publication',self.post.id,self.proposal(),request_key=uuid.uuid4(),expected_version=1)
        self.post.deleted_at=self.now;self.db.flush()
        with self.assertRaises(HTTPException): self.prepare()
        self.post.deleted_at=None;self.db.flush()
        with self.assertRaises(HTTPException) as conflict:
            prepare_edit(self.db,self.author,'publication',self.post.id,self.proposal(),request_key=uuid.uuid4(),expected_version=2)
        self.assertEqual(conflict.exception.status_code,409)
        with self.assertRaises(HTTPException): self.prepare(attachments=[ProposedAttachment('image','image/png',b'invalid')])
        self.assertEqual(self.count(ModerationRevision),0)

    def test_retries_and_reused_key_with_other_payload(self):
        key=uuid.uuid4()
        first=self.prepare(key=key)
        self.assertEqual(self.prepare(key=key).id,first.id)
        self.assertEqual(self.count(ModerationRevision),1)
        self.assertEqual(self.count(ModerationAudit),1)
        with self.assertRaises(HTTPException) as conflict: self.prepare(self.proposal('Otro texto'),key=key)
        self.assertEqual(conflict.exception.status_code,409)

    def test_later_proposal_supersedes_pending_without_losing_audit(self):
        first=self.prepare()
        second=self.prepare(self.proposal('Te voy a matar'))
        self.assertEqual(first.lifecycle,'superseded')
        self.assertEqual(second.lifecycle,'active')
        self.assertEqual(self.count(ModerationRevision),2)
        self.assertEqual(self.count(ModerationAudit),3)
        assert_revision_current(self.db,self.post,second)
        with self.assertRaises(HTTPException): assert_revision_current(self.db,self.post,first)
        self.post.body='An edit through an existing route';self.db.flush()
        with self.assertRaises(HTTPException): assert_revision_current(self.db,self.post,second)

    def test_review_and_all_comment_destinations(self):
        review_before=public_snapshot(self.db,self.review)
        revision=prepare_edit(self.db,self.author,'review',self.review.id,{'body':'Eres un idiota'},
                              request_key=uuid.uuid4(),expected_version=1)
        self.assertEqual(revision.status,'pending_review')
        self.assertEqual(public_snapshot(self.db,self.review),review_before)
        self.db.expire_all()
        assert_revision_current(self.db,self.review,revision)
        for column,parent in [('post_id',self.post.id),('review_id',self.review.id),('reading_event_id',self.events[0].id)]:
            comment=PostComment(user_id=self.author.id,body='Original comment',**{column:parent})
            self.db.add(comment);self.db.flush()
            item=prepare_edit(self.db,self.author,'comment',comment.id,{'body':'Te voy a matar'},request_key=uuid.uuid4(),expected_version=1)
            self.assertEqual(item.status,'pending_review')
            self.assertEqual(comment.body,'Original comment')
        comment.deleted_at=self.now;self.db.flush()
        with self.assertRaises(HTTPException):
            prepare_edit(self.db,self.author,'comment',comment.id,{'body':'Hola'},request_key=uuid.uuid4(),expected_version=1)

    def test_event_and_images_are_not_changed_by_preparation(self):
        self.post.source='event';self.post.publication_type='event';self.post.author_role='admin'
        image=PostImage(post_id=self.post.id,data=PNG,content_type='image/png')
        cover=PostBookCover(post_id=self.post.id,data=PNG,content_type='image/png')
        event=PublicationEvent(post_id=self.post.id,starts_at=self.now,timezone='America/Santiago',location='Place',organizer='Org',category='fair')
        self.db.add_all([image,cover,event]);self.db.flush()
        self.db.add(EventAttendance(post_id=self.post.id,user_id=self.viewer.id));self.db.flush()
        original=public_snapshot(self.db,self.post)
        payload={'publication_type':'event','source':'event','body':'Eres un idiota',
                 'existing_image_ids':[str(image.id)],'cover_mode':'custom'}
        revision=self.prepare(payload,attachments=[ProposedAttachment('image','image/png',PNG),ProposedAttachment('cover','image/png',PNG)])
        self.assertEqual(public_snapshot(self.db,self.post),original)
        self.assertEqual(self.count(ModerationAttachment),2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EventAttendance).where(EventAttendance.post_id==self.post.id)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(PostImage).where(PostImage.post_id==self.post.id)),1)
        self.assertIsNone(self.client.get(f'/api/posts/{self.post.id}').json().get('pending_proposal'))
        image.data=PNG+b'changed';self.db.flush()
        with self.assertRaises(HTTPException): assert_revision_current(self.db,self.post,revision)

    def test_field_boundaries_cannot_fabricate_an_insult(self):
        payload=self.proposal('idiota');payload['title']='Eres un'
        self.assertEqual(self.prepare(payload).status,'approved')

    def test_other_public_text_and_canonical_review_guard(self):
        payload=self.proposal('Una nota normal');payload['book_title']='Te voy a matar'
        self.assertEqual(self.prepare(payload).status,'pending_review')
        with unittest.mock.patch('app.modules.books.canonical.enabled',return_value=True), unittest.mock.patch('app.modules.books.consistency.current_reviews',return_value=[]):
            with self.assertRaises(HTTPException) as obsolete:
                prepare_edit(self.db,self.author,'review',self.review.id,{'body':'Una reseña'},request_key=uuid.uuid4(),expected_version=1)
            self.assertEqual(obsolete.exception.status_code,409)

    def test_null_image_selection_preserves_originals(self):
        self.db.add(PostImage(post_id=self.post.id,content_type='image/png',data=PNG));self.db.flush()
        payload=self.proposal();payload['existing_image_ids']=None
        revision=self.prepare(payload)
        assert_revision_current(self.db,self.post,revision)

    def test_immutable_proposal_has_one_typed_destination(self):
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(ModerationRevision(post_id=self.post.id,review_id=self.review.id,author_user_id=self.author.id,
                    base_version=1,base_fingerprint='a'*64,proposal={},findings=[],ruleset_version='test',status='pending_review'))
                self.db.flush()

    def test_db_constraints_and_immutable_audit_and_proposal(self):
        revision=self.prepare()
        audit=self.db.scalar(select(ModerationAudit).where(ModerationAudit.revision_id==revision.id))
        for operation in ['update','delete']:
            with self.assertRaises(IntegrityError):
                with self.db.begin_nested():
                    if operation=='update': audit.reason='Changed';self.db.flush()
                    else: self.db.delete(audit);self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                revision.proposal={'body':'Altered after submission'};self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                revision.status='rejected';self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(ModerationRevision(post_id=self.post.id,author_user_id=self.author.id,
                    base_version=1,base_fingerprint='a'*64,proposal={},findings=[],ruleset_version='test',status='pending_review'))
                self.db.flush()
        self.assertEqual(self.post.body,'Public note')

    def test_rollback_is_atomic(self):
        with self.assertRaises(RuntimeError):
            with self.db.begin_nested():
                self.prepare()
                raise RuntimeError('Simulated failure before commit')
        self.assertEqual(self.count(ModerationRevision),0)
        self.assertEqual(self.count(ModerationAudit),0)
        self.assertEqual(self.count(ModerationRequest),0)


class ModerationConcurrencyTest(unittest.TestCase):
    def setUp(self):
        if get_settings().app_env not in {'development','test'}:
            self.skipTest('Isolated committed fixtures require development/test')
        with SessionLocal.begin() as db:
            owner=User(display_name='Isolated moderation foundation fixture')
            db.add(owner);db.flush();self.owner_id=owner.id

    def tearDown(self):
        if not hasattr(self,'owner_id'):return
        with SessionLocal.begin() as db:
            db.execute(delete(ModerationRequest).where(ModerationRequest.user_id==self.owner_id))
            db.execute(delete(Post).where(Post.user_id==self.owner_id))
            db.execute(delete(User).where(User.id==self.owner_id))

    def test_concurrent_request_retries_have_one_result(self):
        key=uuid.uuid4();barrier=Barrier(4)
        def work(_):
            with SessionLocal() as db:
                owner=db.get(User,self.owner_id);barrier.wait(timeout=10)
                request=claim_request(db,owner,'isolated-concurrency',key,{'body':'same'})
                if request.result is None:complete_request(request,{'receipt':str(uuid.uuid4())})
                result=request.result;db.commit();return result
        with ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(work,range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ModerationRequest).where(ModerationRequest.user_id==self.owner_id)),1)

    def test_proposals_serialize_on_parent_and_all_staged_changes_roll_back(self):
        with SessionLocal.begin() as db:
            post=Post(user_id=self.owner_id,author_role='admin',source='community',publication_type='free',kind='community',body='Original')
            db.add(post);db.flush();identifier=post.id
        with SessionLocal() as first,SessionLocal() as second:
            payload={'publication_type':'free','source':'community','body':'Eres un idiota'}
            prepare_edit(first,first.get(User,self.owner_id),'publication',identifier,payload,request_key=uuid.uuid4(),expected_version=1)
            second.execute(text("SET LOCAL lock_timeout='150ms'"))
            with self.assertRaises(OperationalError) as locked:
                prepare_edit(second,second.get(User,self.owner_id),'publication',identifier,payload,request_key=uuid.uuid4(),expected_version=1)
            self.assertEqual(locked.exception.orig.sqlstate,'55P03')
            second.rollback();first.rollback()
            prepare_edit(second,second.get(User,self.owner_id),'publication',identifier,payload,request_key=uuid.uuid4(),expected_version=1)
            second.rollback()
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ModerationRevision).where(ModerationRevision.post_id==identifier)),0)
            self.assertEqual(db.get(Post,identifier).body,'Original')
