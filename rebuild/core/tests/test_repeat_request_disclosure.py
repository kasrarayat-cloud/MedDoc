"""A repeated request must not be announced as a new one.

`enqueue` is deliberately idempotent: the same (kind, encounter, revision) — or the same
audio bytes — returns the job that already holds that request key, so nothing is charged
twice. That behaviour is correct and is NOT changed here.

What was wrong is what the doctor is TOLD. A successful generation does not bump
`Encounter.revision` (only a notes save, an answer save or a transcript append does), so the
succeeded job keeps holding `generation:<pk>:<revision>`. A re-POST from a stale page
therefore returns that old job while the view reports "Generation queued. Refresh this page
to view the result." Nothing was queued, nothing new will appear, and where the page also
says "charged separately at provider usage x 1.5" the billing disclosure is false too.

⚠️ WHICH STALE PAGE, MEASURED RATHER THAN ASSUMED. An earlier description of this defect said
"browser Back, or a second tab". Only the second tab is right. Every response carries
`Cache-Control: no-store, private`, which disables the back/forward cache, so Back RE-FETCHES
and the generate form is absent once answers exist (verified in Chromium against the
candidate: button count 0 after the job succeeds). The reachable route is a SECOND TAB opened
before generating, which still holds a live form — exercised end to end in
`.runtime/word-forms-doctor-20260921/candidate-walk.mjs`, step "repeat generation from a
second tab". The server-side behaviour proven below is what makes either route safe.

Isolated synthetic DB. No provider request is made by these tests.
"""
import os
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.jobs import enqueue, run_one
from core.models import Job, Usage
from core.tests.test_billing_boundary import BoundaryFixture
from core.tests.test_billing_policy import STORAGES


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, STORAGES=STORAGES)
class RepeatedGenerationDisclosure(BoundaryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.encounter.answers = {}
        self.encounter.notes = 'Fictional software test only. Estimated blood loss was less than one millilitre.'
        self.encounter.save(update_fields=['answers', 'notes'])
        self.url = f'/encounters/{self.encounter.pk}/'

    def post_generate(self):
        """POST and FOLLOW the redirect, exactly as a browser does.

        Following matters for correctness of the assertion, not just realism: a message
        survives an unfollowed redirect in the session, so a later post would be judged
        against its own message concatenated with the previous one's. Rendering the
        redirect target consumes the storage, so each post is judged on ITS OWN message.
        """
        revision = self.encounter.revision
        response = self.client.post(self.url + 'generate/', {'revision': str(revision)}, follow=True)
        response.produced_messages = [str(m) for m in response.context['messages']]
        return response

    def test_generation_does_not_bump_revision_so_the_key_stays_held(self):
        """The precondition that makes the stale re-POST reachable at all."""
        before = self.encounter.revision
        self.post_generate()
        self.assertTrue(run_one())
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.revision, before,
                         'A successful generation must not silently renumber the source revision.')
        job = Job.objects.get(encounter=self.encounter, kind='generation')
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.request_key, f'generation:{self.encounter.pk}:{before}')

    def test_repeat_generate_reuses_the_job_and_charges_nothing_extra(self):
        """Idempotency itself — this must KEEP working after the disclosure repair."""
        self.post_generate()
        self.assertTrue(run_one())
        first = Job.objects.get(encounter=self.encounter, kind='generation')
        usage_before = Usage.objects.filter(job=first).count()

        self.post_generate()          # the stale re-POST
        self.assertFalse(run_one())   # nothing new to run

        self.assertEqual(Job.objects.filter(encounter=self.encounter, kind='generation').count(), 1)
        self.assertEqual(Usage.objects.filter(job=first).count(), usage_before)

    def test_repeat_generate_is_not_announced_as_queued(self):
        """THE DEFECT: the doctor is told a new request was queued when none was."""
        first_said = ' '.join(self.post_generate().produced_messages)
        self.assertIn('queued', first_said.lower(),
                      'Positive control: a genuinely new request IS still announced as queued.')
        self.assertTrue(run_one())

        response = self.post_generate()   # the stale re-POST
        said = ' '.join(response.produced_messages)

        self.assertNotIn('queued', said.lower(),
                         f'A reused request must not be reported as queued. Got: {said!r}')
        self.assertTrue(
            'nothing was charged' in said.lower() or 'no new request' in said.lower(),
            f'The doctor must be told the earlier draft was reused and nothing was charged. Got: {said!r}')

    def test_enqueue_reports_whether_it_reused_a_job(self):
        """The signal the views need, at its source."""
        first = enqueue(self.encounter, self.user, expected_revision=self.encounter.revision)
        self.assertFalse(getattr(first, 'reused', None), 'A newly created job is not reused.')
        self.assertTrue(run_one())

        again = enqueue(self.encounter, self.user, expected_revision=self.encounter.revision)
        self.assertEqual(again.pk, first.pk)
        self.assertTrue(getattr(again, 'reused', None),
                        'enqueue must tell the caller it returned an existing job.')


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, STORAGES=STORAGES)
class RepeatedTranscriptionDisclosure(BoundaryFixture, TestCase):
    """The same disclosure defect on the voice path, where identical audio bytes dedupe."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.encounter.answers = {}
        self.encounter.save(update_fields=['answers'])
        self.url = f'/encounters/{self.encounter.pk}/'

    def test_identical_recording_is_not_announced_as_queued_again(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.tests.audio_fixtures import wav_bytes
        from core.tests.test_billing_boundary import deepgram

        payload = wav_bytes(seconds=1, tag='repeat-disclosure')
        with patch.dict(os.environ, self.VOICE_ENV):
            quote = self.client.get(self.url).context['usage_quote']
            self.client.post(self.url + 'voice/', {
                'audio': SimpleUploadedFile('synthetic.wav', payload), 'consent': 'on', 'usage_quote': quote})
            with patch('core.jobs.httpx.post', return_value=deepgram('Fictional.', 'syn-1', duration=1)):
                self.assertTrue(run_one())

            quote = self.client.get(self.url).context['usage_quote']
            response = self.client.post(self.url + 'voice/', {
                'audio': SimpleUploadedFile('synthetic.wav', payload), 'consent': 'on', 'usage_quote': quote})

        self.assertEqual(Job.objects.filter(encounter=self.encounter, kind='transcription').count(), 1)
        # Drain: the first post's message survives an unfollowed redirect, so reading without
        # consuming would judge this assertion against both messages concatenated.
        said = ' '.join(str(m) for m in list(response.wsgi_request._messages))
        self.assertNotIn('queued', said.lower(),
                         f'A reused transcription must not be reported as queued. Got: {said!r}')
