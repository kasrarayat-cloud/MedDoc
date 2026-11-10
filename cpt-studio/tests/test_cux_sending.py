"""Core repair (2026-11-03), decision (k): a provider run left 'sending' after its stage failed blocks every further send
like an unknown outcome (R6 4.6, recorded and not verified there; reproduced here on the base rule first). The source
is closed - an answer whose outcome cannot be recorded is recorded unknown, never left 'sending' - and the backstop is
one rule every send door and the derived state read (review._unreconciled_unknown), which the stale sweep settles.

The Gemini migration (design/FINAL.md 14.6; slice S15): these are send-discipline mechanics, so they run the production
chain, Gemini reading OFFICE_NOTE from its recorded synthetic interpretation (tests.test_pipeline_api.
RecordedInterpretation); the run they assert about is Corti's primary run, which the interpretation's own run now stands
beside."""
from __future__ import annotations

import json
from datetime import timedelta
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, RecordedInterpretation, drain

NOTE = 'Checked the vendor console (synthetic): the answer was received and billed once.'


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class SendingEdgeTests(RecordedInterpretation, OperatorReads, TestCase):
    def setUp(self):
        super().setUp()
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def encounter(self, pk):
        return models.Encounter.objects.get(pk=pk)

    def unrecorded_first_answer(self):
        """The first answer arrives and its outcome cannot be written (the first _finish_run of Corti's primary request
        raises once; the interpretation's run, which the production chain finishes first through the same function, is
        recorded as usual)."""
        real = jobs._finish_run
        calls = []

        def finish(run, exchange):
            if run.purpose == models.ProviderRun.PRIMARY:
                calls.append(run.pk)
                if len(calls) == 1:
                    raise RuntimeError('synthetic: the outcome write failed')
            return real(run, exchange)
        return mock.patch('studio.jobs._finish_run', side_effect=finish)

    def test_an_answer_whose_outcome_cannot_be_recorded_is_unknown_and_blocks_the_next_send(self):
        with self.unrecorded_first_answer():
            encounter_id = self.create()
            drain()
        run = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose=models.ProviderRun.PRIMARY)
        self.assertEqual((run.state, run.sent, run.error), (models.ProviderRun.UNKNOWN, True,
                                                           jobs.UNRECORDED_OUTCOME_MESSAGE))
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.PREDICT).state,
                         models.Job.FAILED)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        # a member's context save sends nothing while it is unreconciled
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        # its reconciliation releases exactly one new attempt
        reply = self.post(f'/ops/api/encounters/{encounter_id}/reconcile', {'provider_run_id': str(run.pk), 'note': NOTE})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(len(self.provider.sent), 2)

    def test_a_run_left_sending_by_a_failed_stage_blocks_every_send_door_until_swept_and_reconciled(self):
        # the backstop: the source's own settling failed too, so the run is still 'sending' and its stage failed
        with self.unrecorded_first_answer(), mock.patch('studio.jobs._settle_unrecorded'):
            encounter_id = self.create()
            drain()
        run = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose=models.ProviderRun.PRIMARY)
        self.assertEqual(run.state, models.ProviderRun.SENDING)
        encounter = self.encounter(encounter_id)
        self.assertTrue(review._orphaned_sending(encounter))
        self.assertTrue(jobs._unreconciled_unknown(encounter))
        self.assertEqual(encounter.state, 'provider_unknown')
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)  # the predict's send door read the orphan, while it ran itself
        # the stale sweep settles it unknown once it is older than the cutoff, so it can be reconciled
        models.ProviderRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(hours=1))
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.error), (models.ProviderRun.UNKNOWN, jobs.ORPHANED_SENDING_MESSAGE))
        reply = self.post(f'/ops/api/encounters/{encounter_id}/reconcile', {'provider_run_id': str(run.pk), 'note': NOTE})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(len(self.provider.sent), 2)

    def test_control_a_running_stage_s_own_run_is_never_an_orphan(self):
        encounter_id = self.create()
        drain()
        encounter = self.encounter(encounter_id)
        job = models.Job.objects.filter(encounter=encounter).order_by('-created_at').first()
        started = timezone.now() - timedelta(seconds=5)
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.RUNNING, started_at=started)
        mine = models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider='corti', adapter_version='test',
            request_sha256='e' * 64, request_body={}, contexts=[], state=models.ProviderRun.SENDING,
            requested_by=self.reviewer)
        self.assertGreaterEqual(mine.created_at, started)
        self.assertFalse(review._orphaned_sending(encounter))  # the stage running now sent it: in flight
        jobs.mark_stale()  # nor does the sweep touch it (its stage is running and not stale)
        mine.refresh_from_db()
        self.assertEqual(mine.state, models.ProviderRun.SENDING)
        # once that stage has ended without recording it, it is one
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.FAILED)
        self.assertTrue(review._orphaned_sending(encounter))
