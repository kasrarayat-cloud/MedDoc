"""Actual editable review, immutable ASR and mismatched-source refusal; fake transcription only."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import TestCase, override_settings

from core import transcript_context
from core.models import AuditEvent, Job, TranscriptReview, Usage
from core.security import private_path
from core.tests.test_billing_boundary import BoundaryFixture
from core.tests.test_billing_policy import STORAGES
from core.tests.test_transcript_context import ReviewVersion
from ops import provider_campaign as pc, standing_qa as st, standing_qa_transcription as tr
from ops import standing_qa_voice_review as vr


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, STORAGES=STORAGES)
class ActualProspectiveVoiceReview(BoundaryFixture, TestCase):
    transcript = ReviewVersion.transcript

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = f'/encounters/{self.encounter.pk}/'
        self.row = vr.frozen(vr.MANIFEST_SHA256)['soap-ankle-speech']
        self.worker = tr.TranscriptionRun.__new__(tr.TranscriptionRun)
        self.worker.terms = SimpleNamespace(review=vr.MANIFEST_SHA256, patient_context=True)
        self.worker.campaign = SimpleNamespace(declaration=SimpleNamespace(transcription=self.worker.terms))
        self.worker.world = SimpleNamespace(client=self.client)
        self.temporary = tempfile.TemporaryDirectory(prefix='prospective-voice-review-')
        self.addCleanup(self.temporary.cleanup)
        self.evidence = pc.private_directory(Path(self.temporary.name) / 'evidence')

    def test_explicit_edits_are_saved_with_raw_reviewed_and_source_proof_separate(self):
        job = self.transcript(self.row['raw_text'])
        original = private_path(job.result_path).read_bytes()
        record, problems = self.worker.apply_transcript(self.encounter, job, self.evidence,
                                                        st.AUDIO_BY_ID['soap-ankle-speech'])
        self.assertEqual(problems, [])
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, self.row['reviewed_text'])
        self.assertEqual(private_path(job.result_path).read_bytes(), original)
        self.assertEqual((self.evidence / 'raw-transcript.txt').read_text(), self.row['raw_text'])
        self.assertEqual((self.evidence / 'reviewed-transcript.txt').read_text(), self.row['reviewed_text'])
        edits = json.loads((self.evidence / 'transcript-edits.json').read_text())
        self.assertEqual(edits['edits'], self.row['edits'])
        self.assertFalse(edits['human_acceptance'])
        review = TranscriptReview.objects.get(job=job)
        self.assertEqual(review.raw_sha256, self.row['prior_raw_sha256'])
        self.assertEqual(review.reviewed_sha256, self.row['reviewed_sha256'])
        self.assertEqual(review.source_sha256, record['notes_sha256'])
        self.assertTrue(transcript_context.current(self.encounter))
        event = AuditEvent.objects.get(action='transcription.applied', target=str(job.pk))
        self.assertTrue(event.details['corrected'])
        self.assertEqual(event.details['corrected_sha256'], self.row['reviewed_sha256'])
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 1)
        self.assertEqual(Usage.objects.filter(job=job).count(), 1)

    def test_new_asr_is_retained_but_never_silently_corrected_or_adopted(self):
        changed = self.row['raw_text'] + ' Unexpected additional statement.'
        job = self.transcript(changed)
        self.encounter.refresh_from_db()
        before = self.encounter.notes, self.encounter.revision
        record, problems = self.worker.apply_transcript(self.encounter, job, self.evidence,
                                                        st.AUDIO_BY_ID['soap-ankle-speech'])
        self.assertIsNone(record)
        self.assertEqual([p['code'] for p in problems], ['transcript_correction_source_mismatch'])
        self.encounter.refresh_from_db()
        self.assertEqual((self.encounter.notes, self.encounter.revision), before)
        self.assertEqual((self.evidence / 'raw-transcript.txt').read_text(), changed)
        self.assertFalse((self.evidence / 'reviewed-transcript.txt').exists())
        self.assertFalse(TranscriptReview.objects.filter(job=job).exists())
        self.assertFalse(AuditEvent.objects.filter(action='transcription.applied', target=str(job.pk)).exists())
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 1)
        self.assertEqual(Usage.objects.filter(job=job).count(), 1)
