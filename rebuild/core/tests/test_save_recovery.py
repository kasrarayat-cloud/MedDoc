"""Ordinary save views, durable attempt reconciliation and revision conflicts."""
from copy import deepcopy
import uuid
from urllib.parse import urlencode

from django.http import QueryDict
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core import save_recovery as recovery, semantic_preparation as workflow
from core.models import AuditEvent
from core.tests import test_component_review as component_tests
from core.tests import test_inline_component_review as inline_tests


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class SaveRecoveryTests(TestCase):
    def setUp(self):
        component_tests.ComponentReviewDatabaseTests.setUp(self)
        self.url = reverse('template_definitions_components', args=[self.prep.pk, self.field['key']])
        current = workflow.corrected_definitions(self.prep)[self.field['key']]
        self.post = component_tests.editor_post(self.prep, self.field, current, self.user)
        self.post['field_'+self.field['key']+'_meaning'] = 'The complete documented presenting concern.'
        self.post['part_0_meaning'] = 'The complete documented presenting concern.'
        self.headers = self.identity(self.post)

    def identity(self, post):
        data = QueryDict(urlencode(post, doseq=True))
        return {'HTTP_X_QUILLMD_SAVE': recovery.CONTRACT,
            'HTTP_X_QUILLMD_SAVE_ATTEMPT': str(uuid.uuid4()),
            'HTTP_X_QUILLMD_SAVE_DIGEST': recovery.controls_sha256(data),
            'HTTP_X_QUILLMD_SAVE_BINDING': recovery.binding(self.prep, getattr(self, 'kind', 'definitions')),
            'HTTP_X_QUILLMD_SAVE_REVISION': str(self.prep.revision)}

    def attempts(self):
        return AuditEvent.objects.filter(action=recovery.ACTION, target=str(self.prep.pk))

    def test_committed_response_loss_reconciles_without_a_second_mutation(self):
        original = deepcopy((self.source.fields, self.prep.proposal, self.prep.checker))
        response = self.client.post(self.url, self.post, **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state'], 'committed')
        # The response can be lost outside the server. Only a GET follows.
        result = self.client.get(self.url, **self.headers)
        self.assertEqual(result.json()['state'], 'committed')
        self.assertEqual(result.json()['saved_revision'], 1)
        self.assertIn('no-store', {part.strip() for part in result['Cache-Control'].split(',')})
        self.prep.refresh_from_db(); self.source.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(len(self.prep.correction_history), 1)
        self.assertEqual(self.attempts().count(), 1)
        self.assertEqual((self.source.fields, self.prep.proposal, self.prep.checker), original)

    def test_explicit_retry_after_noncommit_uses_one_ordinary_save(self):
        self.assertEqual(self.client.get(self.url, **self.headers).json()['state'], 'not_recorded_at_read')
        self.assertEqual(self.attempts().count(), 0)  # GET cannot write a disposition.
        self.assertEqual(self.client.post(self.url, self.post, **self.headers).json()['state'], 'committed')
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(len(self.prep.correction_history), 1)

    def test_late_original_or_double_click_reads_same_commit(self):
        for _ in range(2):
            self.assertEqual(self.client.post(self.url, self.post, **self.headers).json()['state'], 'committed')
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(len(self.prep.correction_history), 1)
        self.assertEqual(self.attempts().count(), 1)

    def test_changed_controls_cannot_reuse_an_attempt(self):
        self.client.post(self.url, self.post, **self.headers)
        self.post['reason'] = 'Different draft must not reuse a committed save identity.'
        self.assertEqual(self.client.post(self.url, self.post, **self.headers).status_code, 409)
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(self.attempts().count(), 1)

    def test_stale_revision_conflicts_instead_of_overwriting_native_save(self):
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        response = self.client.post(self.url, self.post, **self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['state'], 'changed')
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(self.attempts().count(), 0)

    def test_validation_refusal_is_recorded_and_unchanged_attempt_is_not_reexecuted(self):
        self.post['part_0_question_quote'] = 'These words are absent from the original form.'
        headers = self.identity(self.post)
        self.assertEqual(self.client.post(self.url, self.post, **headers).status_code, 409)
        self.assertEqual(self.client.get(self.url, **headers).json()['state'], 'rejected')
        self.assertEqual(self.client.post(self.url, self.post, **headers).json()['state'], 'rejected')
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 0)
        self.assertEqual(self.prep.correction_history, [])
        self.assertEqual(self.attempts().count(), 1)

    def test_csrf_denial_cannot_be_bypassed_by_transport_headers(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for _ in range(2):
            self.assertEqual(client.post(self.url, self.post, **self.headers).status_code, 403)
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 0)
        self.assertEqual(self.attempts().count(), 0)

    def test_wrong_actor_and_missing_controls_do_not_establish_a_commit(self):
        from core.models import User
        other = User.objects.create_user('other-save@example.test', password='fixture-only')
        self.client.force_login(other)
        self.assertIn(self.client.get(self.url, **self.headers).status_code, (302, 403, 404))
        self.client.force_login(self.user)
        headers = dict(self.headers); headers.pop('HTTP_X_QUILLMD_SAVE_DIGEST')
        self.assertEqual(self.client.post(self.url, self.post, **headers).status_code, 409)
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 0)

    def test_plain_get_and_native_form_keep_existing_contract(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'data-recoverable-save="all"')
        self.assertContains(response, 'data-save-revision="0"')
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        self.assertEqual(self.attempts().count(), 0)


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class InlineSaveRecoveryTests(TestCase):
    kind = 'inline'
    identity = SaveRecoveryTests.identity
    attempts = SaveRecoveryTests.attempts
    fresh = inline_tests.InlineComponentReviewDatabaseTests.fresh
    whole_form_post = inline_tests.InlineComponentReviewDatabaseTests.whole_form_post

    def setUp(self):
        inline_tests.InlineComponentReviewDatabaseTests.setUp(self)

    def test_custom_word_component_response_loss_keeps_approval_separate(self):
        from core import word_contract
        self.fresh()
        post = inline_tests.part_post(self.prep, self.field, self.current, self.user)
        post['part_0_meaning'] = 'The complete documented presenting concern.'
        headers = self.identity(post)
        self.assertEqual(self.client.post(self.url, post, **headers).json()['state'], 'committed')
        self.assertEqual(self.client.get(self.url, **headers).json()['state'], 'committed')
        self.assertEqual(self.client.post(self.url, post, **headers).json()['state'], 'committed')
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(self.attempts().count(), 1)
        self.assertEqual(self.prep.receipts.count(), 2)
        self.assertEqual(self.template.versions.count(), 0)
        self.assertEqual(word_contract.fully_reviewed_keys(self.prep), set())
        self.assertEqual((self.prep.inventory, self.prep.proposal, self.prep.checker,
            self.prep.candidate_path, self.prep.candidate_sha256, self.prep.candidate_info), self.original)

    def test_custom_word_whole_form_save_reconciles_without_approving(self):
        self.fresh()
        post = self.whole_form_post()
        headers = self.identity(post)
        url = reverse('template_preparation_correct', args=[self.template.pk])
        self.assertEqual(self.client.post(url, post, **headers).json()['state'], 'committed')
        self.assertEqual(self.client.get(url, **headers).json()['state'], 'committed')
        self.prep.refresh_from_db()
        self.assertEqual(self.prep.revision, 1)
        self.assertEqual(self.attempts().count(), 1)
        self.assertEqual(self.template.versions.count(), 0)
