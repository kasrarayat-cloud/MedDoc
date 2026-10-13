"""Input revision and transcript review boundaries; isolated synthetic DB, no provider work."""
import hashlib
import json
import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.jobs import enqueue, run_one
from core.models import AuditEvent, Encounter, Job, LedgerEntry, ProviderReceipt, Reservation, Usage
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes
from core.tests.test_billing_boundary import BoundaryFixture, deepgram
from core.tests.test_billing_policy import STORAGES


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, STORAGES=STORAGES)
class InputWorkflow(BoundaryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.encounter.answers = {}
        self.encounter.save(update_fields=['answers'])
        self.url = f'/encounters/{self.encounter.pk}/'

    def transcript(self, text='Fictional transcript: no immediate complications.'):
        with patch.dict(os.environ, self.VOICE_ENV):
            response = self.client.get(self.url)
            quote = response.context['usage_quote']
            upload = SimpleUploadedFile('synthetic.wav', wav_bytes(seconds=1, tag='review'))
            response = self.client.post(self.url + 'voice/', {'audio': upload, 'consent': 'on', 'usage_quote': quote})
            self.assertEqual(response.status_code, 302)
            job = Job.objects.get(encounter=self.encounter)
            self.assertTrue(job.config['transcript_review_required'])
            with patch('core.jobs.httpx.post', return_value=deepgram(text, 'synthetic-transcript-review', duration=1)) as provider:
                self.assertTrue(run_one())
            self.assertEqual(provider.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        return job

    def apply(self, job, text='Corrected synthetic transcript.', **changes):
        self.encounter.refresh_from_db()
        return self.client.post(self.url + 'notes/', {'revision': self.encounter.revision,
            'transcript_job': str(job.pk), 'corrected_transcript': text,
            'transcript_mode': 'append', 'transcript_reviewed': 'on', **changes})

    def test_new_document_can_start_with_voice_without_placeholder_notes(self):
        response = self.client.post('/encounters/new/', {'patient': self.encounter.patient_id,
            'template_version': self.encounter.template_version_id, 'notes': '',
            'service_date': self.encounter.service_date.isoformat(), 'synthetic_only': 'on'})
        self.assertEqual(response.status_code, 302)
        fresh = Encounter.objects.exclude(pk=self.encounter.pk).get()
        self.assertEqual(fresh.notes, '')
        response = self.client.get(f'/encounters/{fresh.pk}/')
        self.assertContains(response, 'id="source-notes-edit"')
        self.assertNotContains(response, '<summary>Edit source notes</summary>')
        self.assertContains(response, 'data-voice-record')
        self.assertContains(response, 'Save notes or a reviewed transcript to enable generation.')
        with self.assertRaisesMessage(ValidationError, 'Type and save source notes'):
            enqueue(fresh, self.user, expected_revision=fresh.revision)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())

    def test_quote_revision_is_rechecked_under_enqueue_lock(self):
        stale = self.encounter.revision
        Encounter.objects.filter(pk=self.encounter.pk).update(notes='New saved facts', revision=stale + 1)
        with self.assertRaisesMessage(ValidationError, 'Source notes changed after the quote'):
            enqueue(self.encounter, self.user, expected_revision=stale)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())

    def test_generation_post_race_does_not_queue_later_notes_under_older_quote(self):
        from core.views import usage_quote as original_quote
        def quote_then_edit(request, encounter, **kwargs):
            result = original_quote(request, encounter, **kwargs)
            Encounter.objects.filter(pk=encounter.pk).update(notes='Concurrent source revision', revision=encounter.revision + 1)
            return result
        with patch('core.views.usage_quote', side_effect=quote_then_edit):
            self.assertEqual(self.client.post(self.url + 'generate/').status_code, 302)
        self.assertFalse(Job.objects.exists())

    @override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='synthetic-model', AI_INPUT_RATE='3', AI_OUTPUT_RATE='15', AI_CACHED_RATE='.3')
    def test_duplicate_generation_reuses_one_job_and_reservation(self):
        first = enqueue(self.encounter, self.user, expected_revision=self.encounter.revision)
        second = enqueue(self.encounter, self.user, expected_revision=self.encounter.revision)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Job.objects.count(), 1)
        self.assertEqual(Reservation.objects.filter(job=first).count(), 1)
        response = self.client.get(self.url)
        self.assertContains(response, 'data-pending-job')
        self.assertEqual(self.client.post(self.url + 'notes/', {'notes': 'Changed while queued', 'revision': self.encounter.revision}).status_code, 409)

    def test_transcript_never_silently_changes_saved_notes_or_review(self):
        original = self.encounter.notes
        revision = self.encounter.revision
        self.encounter.template_review = {'synthetic_retained_review': True}
        self.encounter.save(update_fields=['template_review'])
        job = self.transcript()
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, original)
        self.assertEqual(self.encounter.revision, revision)
        self.assertEqual(self.encounter.template_review, {'synthetic_retained_review': True})
        response = self.client.get(self.url)
        self.assertContains(response, 'Review the returned transcript')
        self.assertContains(response, 'Original provider transcript (retained unchanged)')
        self.assertContains(response, 'Choose how to add it')
        raw = private_path(job.result_path).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), job.result_sha256)
        self.assertEqual(json.loads(raw)['raw_transcript'], 'Fictional transcript: no immediate complications.')
        self.assertEqual(ProviderReceipt.objects.filter(job=job).count(), 1)
        self.assertEqual(Usage.objects.filter(job=job).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(job=job, kind='usage').count(), 1)

    def test_explicit_reviewed_append_preserves_raw_and_queues_corrected_source_once(self):
        job = self.transcript()
        original = self.encounter.notes
        raw = private_path(job.result_path).read_bytes()
        self.assertEqual(self.apply(job, 'Blood loss: less than one millilitre.').status_code, 302)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, original + '\n\nBlood loss: less than one millilitre.')
        self.assertEqual(self.encounter.answers, {})
        self.assertEqual(private_path(job.result_path).read_bytes(), raw)
        event = AuditEvent.objects.get(action='transcription.applied', target=str(job.pk))
        self.assertTrue(event.details['corrected'])
        self.assertEqual(event.details['mode'], 'append')
        self.assertEqual(self.apply(job).status_code, 409)
        generated = enqueue(self.encounter, self.user, expected_revision=self.encounter.revision)
        self.assertEqual(generated.revision, self.encounter.revision)
        self.assertEqual(Usage.objects.filter(job=job).count(), 1)

    def test_replace_requires_explicit_choice_and_review_and_rejects_stale_revision(self):
        job = self.transcript()
        old = self.encounter.notes
        for changes, code in [({'transcript_mode': ''}, 400), ({'transcript_reviewed': ''}, 400), ({'revision': 999}, 409)]:
            self.assertEqual(self.apply(job, **changes).status_code, code)
            self.encounter.refresh_from_db()
            self.assertEqual(self.encounter.notes, old)
        self.assertEqual(self.apply(job, 'Explicit reviewed replacement.', transcript_mode='replace').status_code, 302)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, 'Explicit reviewed replacement.')

    def test_transcript_cannot_cross_encounters_or_bypass_result_integrity_or_limit(self):
        job = self.transcript()
        foreign = self.make_scope('transcript-other')[5]
        payload = {'revision': foreign.revision, 'transcript_job': str(job.pk), 'corrected_transcript': 'Wrong scope',
                   'transcript_mode': 'append', 'transcript_reviewed': 'on'}
        self.assertEqual(self.client.post(f'/encounters/{foreign.pk}/notes/', payload).status_code, 404)
        self.assertEqual(self.apply(job, 'x' * 50000).status_code, 400)
        path = private_path(job.result_path)
        path.write_bytes(b'{"raw_transcript":"tampered","transcript":"tampered"}')
        self.assertEqual(self.apply(job).status_code, 409)
        self.assertNotContains(self.client.get(self.url), 'Review the returned transcript')

    def test_old_transcription_contract_still_appends_for_already_queued_jobs(self):
        original = self.encounter.notes
        job = self.transcription_job('prior-contract', deepgram('Historical configured append.', 'historical-contract', duration=1))
        self.assertEqual(job.state, 'succeeded', job.error)
        self.encounter.refresh_from_db()
        self.assertTrue(self.encounter.notes.startswith(original + '\n\nHistorical configured append.'))
