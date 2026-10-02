"""Refutation F5 (dc33e094): the doctor's status sentence must be true of the ledger. A job settled by the worker and then
swept into reconciliation is charged (a usage row and a negative ledger entry); the status said "The held amount is not
charged until then". Every sentence that says "not charged" is now said only when the ledger shows no net charge.

Synthetic only; the provider call is patched (no network), as in core.tests.test_settlement_single_worker.
"""
import html
from decimal import Decimal

from django.test import TestCase, TransactionTestCase, override_settings

from core.doctor_status import doctor_status
from django.utils import timezone

from core.models import Encounter, Job, LedgerEntry, Reservation, Usage, Wallet
from core.tests import test_workflow
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


from core.models import GenerationBatch  # noqa: E402
from core.tests.test_generation_batch import BatchFixture, SETTINGS as BATCH_SETTINGS  # noqa: E402


@override_settings(**BATCH_SETTINGS)
class BatchStatusFollowsTheLedger(BatchFixture, TestCase):
    """Refutation FG-1 and FG-5 (4cfa4301): the complete-form branch of doctor_status read the ledger over all its parts, and
    no test pinned it (a mutant reading 0, or the viewed part only, survived every suite). Read through part 1, as the held
    list and the charge page do."""

    def charge(self, part, amount='-0.15'):
        wallet = Reservation.objects.filter(job=part.job).first().wallet
        LedgerEntry.objects.create(wallet=wallet, amount=Decimal(amount), kind='usage', key=f'usage:{part.job.pk}',
                                   description='Synthetic', job=part.job, balance_after=wallet.balance)

    def read(self, part):
        return doctor_status(Job.objects.get(pk=part.job_id))

    def test_FG1_a_held_batch_whose_other_part_is_charged_says_it_was_charged(self):
        batch = self.admit()
        first, second = batch.parts.select_related('job').order_by('ordinal')
        GenerationBatch.objects.filter(pk=batch.pk).update(state='reconciliation')
        status = self.read(first)
        self.assertEqual((status.key, status.charged), ('held', False))
        self.assertTrue(claims_not_charged(status.explanation))           # the control: nothing on the ledger yet
        self.charge(second)
        status = self.read(first)
        self.assertTrue(status.charged)
        self.assertFalse(claims_not_charged(status.explanation), status.explanation)
        self.assertIn('was charged', status.explanation)

    def test_FG5_a_batch_not_applied_says_it_remains_charged_only_with_a_charge(self):
        batch = self.admit()
        first, second = batch.parts.select_related('job').order_by('ordinal')
        GenerationBatch.objects.filter(pk=batch.pk).update(state='not_adopted')
        status = self.read(first)
        self.assertEqual((status.key, status.charged), ('completed_not_applied', False))
        self.assertIn('No charge is recorded for it.', status.explanation)
        self.assertNotIn('remains charged', status.explanation)
        self.charge(second)
        status = self.read(first)
        self.assertTrue(status.charged)
        self.assertIn('remains charged', status.explanation)


@override_settings(**test_workflow.TEST_SETTINGS)
class OnePageOneAnswer(TestCase):
    """Refutation M3 (4cfa4301): the encounter page said "Earlier generations remain charged" (job state) beside "No charge
    is recorded for it." (ledger) for one request whose settled charge a reconciliation credited back in full. Both now
    read the ledger."""
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload, create_encounter = workflow.setUp, workflow.make_docx, workflow.upload, workflow.create_encounter

    def test_a_request_credited_back_in_full_is_not_called_charged(self):
        from core.billing import reconcile_usage, reserve, settle
        from core.jobs import NOT_ADOPTED
        from core.models import User
        _t, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, 'Symptoms: no chest pain.\nExamination: Normal gait.')
        job = Job.objects.create(encounter=encounter, user=self.user, request_key='m3:job', state='queued', kind='generation')
        reserve(job, charge_limit=Decimal('0.30'))
        Job.objects.filter(pk=job.pk).update(state='running')
        usage = settle(job, Decimal('0.10'), {}, {}, 'synthetic-live', simulated=False)
        Job.objects.filter(pk=job.pk).update(state='failed', error=NOT_ADOPTED + 'The notes changed while it ran.')
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertEqual(page.context['prior_generations'], 1)               # the control: charged, so disclosed
        self.assertContains(page, 'Earlier generations remain charged')
        admin = User.objects.create_user(username='m3-admin', email='m3-admin@synthetic.invalid', is_staff=True,
                                         verified_at=timezone.now())
        reconcile_usage(usage, Decimal('0'), 'SYNTHETIC-INVOICE-0', admin)
        self.assertEqual(-sum(LedgerEntry.objects.filter(job=job).values_list('amount', flat=True)), 0)
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertContains(page, 'No charge is recorded for it.')
        self.assertNotContains(page, 'Earlier generations remain charged')    # 4cfa4301: both sentences
        self.assertEqual(page.context['prior_generations'], 0)
