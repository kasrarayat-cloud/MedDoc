"""Refutation F5 (dc33e094): the doctor's status sentence must be true of the ledger. A job settled by the worker and then
swept into reconciliation is charged (a usage row and a negative ledger entry); the status said "The held amount is not
charged until then". Every sentence that says "not charged" is now said only when the ledger shows no net charge.

Synthetic only; the provider call is patched (no network), as in core.tests.test_settlement_single_worker.
"""
import html
from decimal import Decimal

from django.test import TestCase, TransactionTestCase, override_settings

from core.doctor_status import doctor_status
from core.models import Encounter, Job, LedgerEntry, Usage, Wallet
from core.tests import test_settlement_single_worker as ssw
from core.tests.test_billing_boundary import LIVE
from core.tests.test_billing_policy import STORAGES
from core.tests.test_settlement_database_error import HeldSettlementFixture
from core.tests.test_security import SyntheticFixture

NOT_CHARGED = ('not charged', 'nothing was charged', 'is not charged to you')


def claims_not_charged(text):
    return any(phrase in text.lower() for phrase in NOT_CHARGED)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class StatusFollowsTheLedger(ssw.Console, HeldSettlementFixture, TransactionTestCase):
    settle_then = ssw.SecondWorkerDuringALiveProviderCall.settle_then
    wallets = ssw.SecondWorkerDuringALiveProviderCall.wallets
    document = ssw.SecondWorkerDuringALiveProviderCall.document

    def test_a_settled_job_held_for_review_says_it_was_charged_and_a_reversed_one_says_it_was_not(self):
        job, _before = self.settle_then('f5', resolve=False)
        self.assertEqual(job.state, 'reconciliation')
        charged = -sum(LedgerEntry.objects.filter(job=job).values_list('amount', flat=True))
        self.assertGreater(charged, 0)                                    # the refuter's P12: 0.15 charged
        self.assertTrue(Usage.objects.filter(job=job).exists())
        status = doctor_status(job)
        self.assertEqual(status.key, 'held')
        self.assertTrue(status.charged)                                   # dc33e094: False
        self.assertFalse(claims_not_charged(status.explanation), status.explanation)  # dc33e094: "not charged until then"
        self.assertIn('was charged', status.explanation)
        self.client.force_login(self.user)
        page = html.unescape(self.client.get(f'/encounters/{job.encounter_id}/').content.decode())
        self.assertIn(status.explanation, page)
        # The administrator resolves it: the settled charge is reversed (absorbed), so "not charged" is now true.
        self.assertEqual(self.resolve(job).status_code, 302)
        job.refresh_from_db()
        self.assertEqual(-sum(LedgerEntry.objects.filter(job=job).values_list('amount', flat=True)), 0)
        status = doctor_status(job)
        self.assertFalse(status.charged)
        self.assertTrue(claims_not_charged(status.explanation), status.explanation)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class EverySentenceIsCheckedAgainstTheLedger(SyntheticFixture, TestCase):
    """No state's sentence claims "not charged" while the ledger shows a net charge for the request."""

    def test_no_state_claims_not_charged_beside_a_charge(self):
        from core.jobs import CANCELLED_ERROR, NOT_ADOPTED, PLATFORM_FAILURE
        user, _org, _dept, _patient, _template, encounter, _blob = self.make_scope('ledger-status')
        wallet = Wallet.objects.get(user=user, kind='promo')
        cases = [('queued', ''), ('running', ''), ('reconciliation', ''), ('failed', PLATFORM_FAILURE + 'Error.'),
                 ('failed', 'Access was revoked before processing.'), ('failed', NOT_ADOPTED + 'Changed.'),
                 ('cancelled', CANCELLED_ERROR), ('succeeded', '')]
        for number, (state, error) in enumerate(cases):
            with self.subTest(state=state, error=error):
                job = Job.objects.create(encounter=encounter, user=user, request_key=f'ledger:{number}', state=state, error=error)
                self.assertFalse(doctor_status(job).charged)              # nothing on the ledger yet
                LedgerEntry.objects.create(wallet=wallet, amount=Decimal('-0.15'), kind='usage', key=f'usage:{job.pk}',
                                           description='Synthetic', job=job, balance_after=wallet.balance)
                status = doctor_status(job)
                self.assertTrue(status.charged, state)
                self.assertFalse(claims_not_charged(status.explanation), (state, status.explanation))
