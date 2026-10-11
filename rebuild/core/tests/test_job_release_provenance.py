"""A queued request and its executing worker may belong to different releases."""
from django.test import TestCase, override_settings
from core.jobs import enqueue, run_one
from core.models import AuditEvent
from core.tests import test_ai_stages as stage_fixtures


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture',
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    ADMIN_SITE=False, STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class JobReleaseProvenanceTests(TestCase):
    setUp = stage_fixtures.IndependentStageTests.setUp

    def test_actual_worker_release_is_retained_and_replays_never_relabel_it(self):
        with override_settings(RELEASE_SHA='a' * 40):
            job = enqueue(self.encounter, self.user)
        self.assertEqual(job.config['queued_release_sha'], 'a' * 40)
        self.assertNotIn('executing_release_sha', job.config)
        with override_settings(RELEASE_SHA='b' * 40):
            replay = enqueue(self.encounter, self.user)
            self.assertEqual(replay.pk, job.pk)
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.config['queued_release_sha'], 'a' * 40)
        executing = AuditEvent.objects.get(action='job.running', target=str(job.pk))
        self.assertEqual(executing.details['executing_release_sha'], 'b' * 40)
        self.assertEqual(executing.details['queued_release_sha'], 'a' * 40)
        count = job.ai_stage_receipts.count()
        with override_settings(RELEASE_SHA='c' * 40):
            self.assertEqual(enqueue(self.encounter, self.user).pk, job.pk)
            self.assertFalse(run_one())
        job.refresh_from_db()
        self.assertEqual(job.config['queued_release_sha'], 'a' * 40)
        self.assertNotIn('executing_release_sha', job.config)
        self.assertEqual(AuditEvent.objects.filter(action='job.running', target=str(job.pk)).count(), 1)
        executing.refresh_from_db()
        self.assertEqual(executing.details['executing_release_sha'], 'b' * 40)
        self.assertEqual(job.ai_stage_receipts.count(), count)
