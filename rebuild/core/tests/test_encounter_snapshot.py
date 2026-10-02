"""Deterministic worker adoption during document resolution; synthetic data only."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core.generation import configuration
from core.jobs import enqueue, run_one
from core.models import Code, CodeSet, CodeSuggestion, Job, TemplateVersion
from core.security import private_path
from documents import DocumentError
from .test_security import SyntheticFixture
from .test_workflow import TEST_SETTINGS
from core.tests.audio_fixtures import wav_bytes


@override_settings(**TEST_SETTINGS)
class EncounterSnapshotTests(SyntheticFixture, TransactionTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(directory.name))
        override.enable(); self.addCleanup(override.disable)
        self.user, _, _, _, template, self.encounter, _ = self.make_scope('snapshot')
        self.encounter.template_version = TemplateVersion.objects.create(
            template=template, number=2, fields=self.encounter.template_version.fields,
            document_backend={'backend': 'synthetic-resolution-boundary'},
            review_requirements=[], created_by=self.user)
        self.encounter.answers = {}
        self.encounter.save(update_fields=['template_version', 'answers'])
        self.client.force_login(self.user)
        self.url = f'/encounters/{self.encounter.pk}/'

    def adoption_during_resolution(self, encounter, actor):
        # This exact boundary runs after answer rows are constructed, before the
        # old lazy jobs/codes querysets are consumed by the template.
        self.assertFalse(connection.in_atomic_block,
                         'Document processing must not hold the encounter transaction.')
        self.assertTrue(run_one())
        raise DocumentError('Synthetic document-resolution boundary; no SDK invoked.')

    def get_without_document_processor(self):
        with patch('core.views.wm_resolve', side_effect=DocumentError('Synthetic boundary.')):
            return self.client.get(self.url)

    def test_generation_completion_cannot_appear_with_pre_adoption_answers(self):
        job = enqueue(self.encounter, self.user)
        with patch('core.views.wm_resolve', side_effect=self.adoption_during_resolution):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')
        self.assertEqual(self.encounter.answers['symptoms']['text'], 'no chest pain')
        self.assertEqual(response.context['encounter'].answers, {})
        self.assertEqual(response.context['answer_rows'][0]['text'], '')
        self.assertEqual([row.state for row in response.context['jobs']], ['queued'])
        # The request list now reads core.doctor_status (the badge carried the raw state word before): the snapshot
        # shows the queued request, never the completion that happened while the page was being built.
        self.assertNotContains(response, 'data-request-status="completed"')
        self.assertContains(response, 'data-request-status="waiting">Waiting to start</span>')
        self.assertNotContains(response, 'Finalize document')

        following = self.get_without_document_processor()
        self.assertEqual(following.context['answer_rows'][0]['text'], 'no chest pain')
        self.assertEqual([row.state for row in following.context['jobs']], ['succeeded'])
        self.assertContains(following, 'Finalize document')

    def test_voice_adoption_cannot_mix_old_source_with_new_jobs_or_deleted_codes(self):
        today = timezone.localdate()
        release = CodeSet.objects.create(system='ICD-10-CM', version='synthetic-snapshot',
            effective_from=today-timedelta(days=1), effective_until=today+timedelta(days=1),
            source_url='https://synthetic.invalid/codes', sha256='0'*64)
        code = Code.objects.create(release=release, code='R00.0', description='Synthetic code')
        suggestion = CodeSuggestion.objects.create(encounter=self.encounter, terminology=code,
            explanation='Synthetic explanation', evidence='no chest pain')
        audio = private_path('audio/synthetic.wav'); audio.parent.mkdir(mode=0o700)
        audio.write_bytes(wav_bytes(tag='snapshot')); audio.chmod(0o600)
        job = enqueue(self.encounter, self.user, kind='transcription', input_path='audio/synthetic.wav',
            config={**configuration(), 'voice_rate_second': '0', 'voice_max_cost': '0'})
        old_notes, old_revision = self.encounter.notes, self.encounter.revision
        transcript = ('SYNTHETIC corrected voice source', Decimal('0'), {'duration_seconds': '1'},
                      {'usd_per_minute': '0'}, 'synthetic-transcription', '', True)
        with patch('core.jobs.transcribe', return_value=transcript), \
                patch('core.views.wm_resolve', side_effect=self.adoption_during_resolution):
            response = self.client.get(self.url)
        job.refresh_from_db(); self.encounter.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')
        self.assertEqual(self.encounter.revision, old_revision+1)
        self.assertFalse(CodeSuggestion.objects.filter(pk=suggestion.pk).exists())
        self.assertEqual(response.context['encounter'].notes, old_notes)
        self.assertEqual(response.context['encounter'].revision, old_revision)
        self.assertEqual([row.state for row in response.context['jobs']], ['queued'])
        self.assertEqual([row.pk for row in response.context['codes']], [suggestion.pk])
        self.assertEqual(response.context['codes'][0].description, 'Synthetic code')

        following = self.get_without_document_processor()
        self.assertIn(transcript[0], following.context['encounter'].notes)
        self.assertEqual(following.context['encounter'].revision, old_revision+1)
        self.assertEqual([row.state for row in following.context['jobs']], ['succeeded'])
        self.assertEqual(list(following.context['codes']), [])
