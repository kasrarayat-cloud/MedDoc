"""An unknown outcome waits for the operator's reconcile before anyone is offered to send again (FIX-SPEC 4, MONEY-2;
the integration of fix lane F2 with the customer API, the operator console and their refusals).

studio.jobs refuses a Resume or a retry of a round while a send of it may have reached the vendor with no outcome known
and no operator's reconcile yet (jobs.awaiting_reconcile; jobs.Refused(RECONCILE_FIRST)). What offers those acts must
agree with what refuses them: the customer's progress offers neither Resume nor Retry, the member reads the refusal's own
sentence (not "could not be saved"), and the operator console offers no retry - until the run is reconciled, when every
offer comes back. Synthetic data only; nothing is sent.
"""
import json

from django.test import TestCase

from studio import jobs, models
from tests.support import operator as ops
from tests.support import rounds as r

Run, Round = models.ProviderRun, models.CodingRound


class ReconcileFirstTests(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.done(title='Synthetic note with an unknown check')
        self.round = Round.objects.get(encounter=self.enc)
        self.checker = Run.objects.get(encounter=self.enc, purpose=jobs.CHECKER)
        self.member = self.client_for(self.reviewer)

    def unknown_check(self, round_state, **round_fields):
        """The round ended ``round_state`` while its checker's send has an unknown outcome no one reconciled."""
        Run.objects.filter(pk=self.checker.pk).update(state=Run.UNKNOWN, reconciled_at=None)
        Round.objects.filter(pk=self.round.pk).update(state=round_state, **round_fields)
        self.assertTrue(jobs.awaiting_reconcile(self.round))

    def progress(self):
        response = self.member.get(f'/api/encounters/{self.enc.pk}')
        self.assertEqual(response.status_code, 200)
        return response.json()['progress']

    def post(self, act):
        return self.member.post(f'/api/encounters/{self.enc.pk}/{act}', data=json.dumps({}),
                                content_type='application/json')

    def reconcile(self):
        operator_user = r.f.user('platform-operator')
        self.assertTrue(jobs.reconcile(self.enc, self.checker, operator_user, 'The vendor console shows one bill.'))
        self.assertFalse(jobs.awaiting_reconcile(self.round))

    def failed_unknown(self):
        self.unknown_check(Round.FAILED, failure_kind=jobs.UNKNOWN, error=jobs.FAILURE_TEXT[jobs.UNKNOWN])

    def test_a_failed_round_awaiting_its_reconcile_offers_no_retry_until_reconciled(self):
        self.failed_unknown()
        progress = self.progress()
        self.assertEqual((progress['phase'], progress['can_retry'], progress['can_resume']), ('failed', False, False))
        self.reconcile()
        self.assertTrue(self.progress()['can_retry'])
        retried = self.post('retry')
        self.assertEqual((retried.status_code, retried.json()['round']['trigger']), (201, Round.RETRY))

    def test_a_retry_refused_for_the_reconcile_says_why(self):
        self.failed_unknown()
        refused = self.post('retry')
        self.assertEqual((refused.status_code, refused.json()['error']), (409, jobs.RECONCILE_FIRST))
        self.assertEqual(Round.objects.filter(encounter=self.enc).count(), 1)  # nothing was started

    def test_a_stopped_round_awaiting_its_reconcile_offers_no_resume_until_reconciled(self):
        self.unknown_check(Round.CANCELLED)
        progress = self.progress()
        self.assertEqual((progress['phase'], progress['can_resume'], progress['can_retry']), ('stopped', False, False))
        self.reconcile()
        self.assertTrue(self.progress()['can_resume'])
        self.assertEqual(self.post('resume').status_code, 201)

    def test_a_resume_refused_for_the_reconcile_says_why(self):
        self.unknown_check(Round.CANCELLED)
        refused = self.post('resume')
        self.assertEqual((refused.status_code, refused.json()['error']), (409, jobs.RECONCILE_FIRST))
        self.assertFalse(models.Job.objects.filter(encounter=self.enc, state=models.Job.QUEUED).exists())

    def test_the_refusal_sentence_passes_the_customer_denylist(self):
        scanner = r.scan_customer()
        self.assertEqual(scanner.scan_text(jobs.RECONCILE_FIRST, scanner.scan_context(), 'json'), [])

    def test_the_operator_console_offers_no_retry_until_the_run_is_reconciled(self):
        self.failed_unknown()
        console = ops.admin_client(r.f.user('console-operator'))  # release 1, B3: the admin host, 2FA
        page = console.get(f'/ops/encounters/{self.enc.pk}').content.decode('utf-8')
        self.assertNotIn('Retry the failed round', page)
        self.assertIn('Record the reconciliation', page)
        self.assertIn('Retry waits for the reconciliation', page)
        self.reconcile()
        page = console.get(f'/ops/encounters/{self.enc.pk}').content.decode('utf-8')
        self.assertIn('Retry the failed round', page)
        self.assertNotIn('Retry waits for the reconciliation', page)
