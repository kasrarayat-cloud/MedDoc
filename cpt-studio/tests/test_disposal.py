"""Release 1, D1: destroying one document or a whole practice's data (studio.disposal and the dispose command), and the
closed practice it starts from. Synthetic practices only, on a test database and an originals folder of the tests' own;
nothing here can reach another database or folder."""
from __future__ import annotations

import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from studio import intake, jobs, models
from tests.support import coding as f
from tests.support import rounds

Round, Job = models.CodingRound, models.Job


def close(workspace):
    models.Workspace.objects.filter(pk=workspace.pk).update(closed_at=timezone.now())


class ClosedPracticeTests(rounds.CustomerCase, TestCase):
    """D1 step 1: a closed practice takes no new upload and starts no coding; reading stays on."""

    def files(self):
        return sorted(path for path in Path(self._originals.name).rglob('*') if path.is_file())

    def test_an_upload_to_a_closed_practice_is_refused_and_stores_nothing(self):
        close(self.ws)
        client, before = self.client_for(self.reviewer), self.files()
        for fields in ({'text': f.NOTE}, {'file': SimpleUploadedFile('synthetic.pdf', f.PDF_BYTES)}):
            with self.subTest(fields=sorted(fields)):
                answer = client.post('/api/encounters', {**fields, 'synthetic_attestation': 'yes'})
                self.assertEqual((answer.status_code, answer.json()['error']), (400, intake.CLOSED_TEXT))
        self.assertFalse(models.Encounter.objects.exists())
        self.assertEqual(self.files(), before)

    def test_reading_stays_on_in_a_closed_practice(self):
        enc = self.done()
        close(self.ws)
        client = self.client_for(self.reviewer)
        self.assertEqual(client.get(f'/api/encounters/{enc.pk}').status_code, 200)
        self.assertEqual(client.get(f'/api/encounters/{enc.pk}/original').content, f.PDF_BYTES)
        self.assertIn(str(enc.pk), json.dumps(client.get('/api/encounters').json()))

    def test_no_coding_starts_in_a_closed_practice(self):
        failed = self.encounter()
        rounds.write_round(failed, state_=Round.FAILED, failure_kind='failed', error='Coding did not finish.')
        stopped = self.started(title='Synthetic stopped note')
        jobs.stop_encounter(stopped, self.reviewer)
        close(self.ws)
        for label, act in (('a new round', lambda: jobs.start_round(failed, failed.current_revision, Round.ANSWERS,
                                                                    self.reviewer)),
                           ('a retry', lambda: jobs.retry(failed, self.reviewer)),
                           ('a resume', lambda: jobs.resume(stopped, self.reviewer))):
            with self.subTest(act=label):
                with self.assertRaisesMessage(jobs.Refused, jobs.CLOSED_MESSAGE):
                    act()
        self.assertFalse(Job.objects.filter(state=Job.QUEUED).exists())

    def test_a_job_queued_before_the_close_never_starts_and_nothing_is_sent(self):
        enc = self.started()
        close(self.ws)
        fake = self.use(f.FakeCoder())  # any send would fail the test: no answer is expected
        job = jobs.claim_next()
        self.assertEqual((job.state, job.error), (Job.CANCELLED, jobs.CLOSED_JOB_ERROR))
        self.assertEqual(models.CodingRound.objects.get(encounter=enc).state, Round.CANCELLED)
        self.assertEqual((fake.calls, fake.counts), ([], []))
        self.assertFalse(models.ProviderRun.objects.exists())
        self.assertIsNone(jobs.claim_next())

    def test_an_open_practice_uploads_and_codes_as_before(self):
        client = self.client_for(self.reviewer)
        answer = client.post('/api/encounters', {'text': f.NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(answer.status_code, 201)
        enc = models.Encounter.objects.get(pk=answer.json()['id'])
        self.code_round(enc)
        self.assertEqual(models.CodingRound.objects.get(encounter=enc).state, Round.DONE)
