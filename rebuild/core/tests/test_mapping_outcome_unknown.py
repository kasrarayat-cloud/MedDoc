"""RR2-M1: the mapping worker's failure handler, where a COMMIT's answer is lost.

The second refutation of the residuals (docs/rebuild/v1/residuals-assessment-20260929.md) found the RS-1 class in
core.mapping_jobs.run_one: its handler read Usage.exists() without the job's row lock and wrote the job afterwards. When
the ADOPTION's COMMIT answer is lost after the adoption committed (the new mapping version exists, the job says
'succeeded', the charge stands), the handler decided 'known and not declined' and overwrote the committed success as a
platform failure, reversing the charge of a mapping version the template now carries. RED on d5367521.

The repair is core.jobs.end_failed_job's guard: decide and write under the job's row lock; never overwrite an outcome a
committed transaction recorded; an in-doubt settlement COMMIT asserts nothing and holds the job with its request key.

The lost answer is simulated as in test_settlement_outcome_unknown (CommitAnswerLost): the COMMIT goes out, its answer
never arrives, and the transaction stays open on its own server connection, holding its row locks, until a finisher
commits it or rolls it back after another backend waits for one of them. Live mapping mode with a mocked provider
client (no network request); synthetic blank form; real PostgreSQL.
"""
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from core import billing, generation, jobs, mapping_assistance as mapping
from core.jobs import deliverable
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, LedgerEntry, PlatformCost, Reservation, Usage, Wallet
# The module, never its TestCase by name: a TestCase imported into this module would be collected and run here again.
from core.tests import test_mapping_assistance as offline
from core.tests.test_settlement_outcome_unknown import CommitAnswerLost

UNKNOWN = 'The settlement outcome of this request is unknown; an administrator must reconcile it.'
UNRECORDED = 'The outcome of this request could not be recorded; an administrator must reconcile it.'


def wallets(user):
    return {(w.pk, w.balance, w.reserved) for w in Wallet.objects.filter(user=user)}


@override_settings(**{**offline.SETTINGS, 'AI_MODE': 'live', 'QUILLMD_MAPPING_ASSISTANCE_LIVE': True})
class MappingOutcomeFixture(TransactionTestCase):
    # The synthetic blank form, template, first mapping version and funded clinician of the offline mapping suite.
    body = offline.MappingAssistance.body
    enqueue = offline.MappingAssistance.enqueue
    response = offline.MappingAssistance.response

    def setUp(self):
        offline.MappingAssistance.setUp(self)
        self.addCleanup(connection.close)
        self.config = generation.configuration()
        self.compiled = mapping.compile_request(self.version, self.config)

    def run_mapping(self, **patches):
        """One live mapping request through jobs.run_one, the provider client mocked to answer once."""
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value = self.response()
            self.assertTrue(jobs.run_one())
        self.assertEqual(client.return_value.messages.create.call_count, 1)


class AdoptionCommitAnswerLost(MappingOutcomeFixture):

    def adopt_with_lost_answer(self, landed):
        job = self.enqueue()
        harness = CommitAnswerLost(landed)
        real = mapping.validate_proposal

        def validate_proposal(*args, **kwargs):
            harness.arm()  # the next outermost COMMIT is the adoption's
            return real(*args, **kwargs)
        with harness.patched(), patch('core.mapping_assistance.validate_proposal', side_effect=validate_proposal):
            self.run_mapping()
            harness.join(self)
        self.assertTrue(harness.waiter_seen)
        job.refresh_from_db()
        return job

    def test_an_adoption_that_committed_before_its_answer_was_lost_stays_succeeded_and_charged(self):
        """RED on d5367521: 'failed' with 'platform_failure: Mapping output could not be adopted.', the charge reversed
        (an 'absorbed' ledger entry and platform cost) while the adopted mapping version stayed on the template."""
        job = self.adopt_with_lost_answer(landed=True)
        self.assertEqual((job.state, job.error), ('succeeded', ''))
        self.assertTrue(deliverable(job))
        latest = self.template.versions.latest('number')
        self.assertEqual((self.template.versions.count(), latest.assistance['job_id']), (2, str(job.pk)))
        usage = Usage.objects.get(job=job)
        self.assertEqual(-sum(e.amount for e in LedgerEntry.objects.filter(job=job, kind='usage')), usage.charged_cost)
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        self.assertFalse(PlatformCost.objects.filter(job=job, kind='absorbed_failure').exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'settled'})
        self.assertTrue(AuditEvent.objects.filter(action='mapping.review_ready', target=str(job.pk)).exists())
        self.assertFalse(AuditEvent.objects.filter(target=str(job.pk), action__in=['mapping.failed', 'usage.absorbed']).exists())
        event = AuditEvent.objects.get(action='job.error_after_commit', target=str(job.pk))
        self.assertEqual((event.details['state'], event.details['error_class']), ('succeeded', 'OperationalError'))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_an_adoption_that_did_not_commit_is_a_platform_failure_absorbed(self):
        before = wallets(self.user)
        job = self.adopt_with_lost_answer(landed=False)
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('platform_failure: '), job.error)
        self.assertIn(':failed:', job.request_key)
        self.assertFalse(deliverable(job))
        self.assertEqual(self.template.versions.count(), 1)
        self.assertEqual(wallets(self.user), before)
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Usage.objects.get(job=job).actual_cost)
        self.assertTrue(audit_report()['all_checks_pass'])


class SettlementCommitAnswerLost(MappingOutcomeFixture):
    """An in-doubt settlement asserts nothing, landed or not: the job is held with its request key; nothing is released,
    absorbed or adopted. (The code before the repair also held it, with 'Provider outcome or settlement is uncertain;
    reconcile before retrying.', because its unlocked read preceded the commit; a handler that merely took the lock would
    have read a landed settlement as known and absorbed it. This pins the RS-1 rule on the mapping path.)"""

    def settle_with_lost_answer(self, landed):
        job = self.enqueue()
        key = job.request_key
        harness = CommitAnswerLost(landed)
        real = billing.settle

        def settle(*args, **kwargs):
            harness.arm()
            return real(*args, **kwargs)
        with harness.patched(), patch('core.mapping_jobs.settle', side_effect=settle):
            self.run_mapping()
            harness.join(self)
            self.assertFalse(jobs.run_one())  # never retried automatically
        self.assertTrue(harness.waiter_seen)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error, job.request_key), ('reconciliation', UNKNOWN, key))
        self.assertFalse(deliverable(job))
        self.assertEqual(self.template.versions.count(), 1)
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        self.assertFalse(PlatformCost.objects.filter(job=job).exists())
        self.assertFalse(AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).exists())
        event = AuditEvent.objects.get(action='mapping.reconciliation', target=str(job.pk))
        self.assertEqual((event.details['billing'], event.details['error_class']), ('uncertain', 'OperationalError'))
        self.assertEqual(self.enqueue().pk, job.pk)  # the same request is not bought twice
        return job

    def test_a_settlement_that_landed_after_its_answer_was_lost_is_held_as_unknown(self):
        job = self.settle_with_lost_answer(landed=True)
        self.assertTrue(Usage.objects.filter(job=job).exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'settled'})

    def test_a_settlement_that_did_not_land_after_its_answer_was_lost_is_held_as_unknown(self):
        job = self.settle_with_lost_answer(landed=False)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'held'})


class HandlerStatementFails(MappingOutcomeFixture):

    def test_a_handler_whose_first_statement_loses_the_connection_holds_the_job(self):
        """The RS-2 shape on the mapping path: settlement committed, the output could not be used, and the server ended
        the connection at the handler's first statement. RED on d5367521: OperationalError out of run_one, the job left
        'running' with its charge until the stale sweep. Now it is held for an administrator, asserting nothing."""
        job = self.enqueue()
        armed = {}

        def unusable(*args, **kwargs):
            armed['armed'] = True
            raise ValidationError('synthetic: the proposal cannot be used')

        def wrapper(execute, sql, params, many, context):
            if armed.get('armed') and not armed.get('fired'):
                armed['fired'] = sql
                return execute('SELECT pg_terminate_backend(pg_backend_pid())', None, many, context)
            return execute(sql, params, many, context)
        with patch('core.mapping_assistance.validate_proposal', side_effect=unusable), connection.execute_wrapper(wrapper):
            self.run_mapping()
        self.assertTrue(armed.get('fired'))
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', UNRECORDED))
        self.assertNotIn(':failed:', job.request_key)
        self.assertTrue(Usage.objects.filter(job=job).exists())  # settled before the failure; an administrator resolves it
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='absorbed').exists())
        self.assertEqual(AuditEvent.objects.get(action='mapping.reconciliation', target=str(job.pk)).details['billing'], 'uncertain')
        self.assertEqual(self.template.versions.count(), 1)

    def test_an_unusable_output_is_still_a_platform_failure_absorbed(self):
        """Control: with nothing lost, the locked handler records what it always recorded."""
        before = wallets(self.user)
        job = self.enqueue()
        with patch('core.mapping_assistance.validate_proposal', side_effect=ValidationError('synthetic: unusable')):
            self.run_mapping()
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', 'platform_failure: Mapping output could not be adopted.'))
        self.assertIn(':failed:', job.request_key)
        self.assertEqual(wallets(self.user), before)
        self.assertGreater(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Decimal(0))
        self.assertTrue(AuditEvent.objects.filter(action='mapping.failed', target=str(job.pk)).exists())
        self.assertTrue(audit_report()['all_checks_pass'])
