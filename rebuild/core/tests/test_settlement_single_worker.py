"""Two workers, one job (blockers.txt item 3): the settlement guard, the late receipt, and the single-worker lock.

The a1 probe (logs/probe-two-workers.json) played a SECOND worker while the first was inside a live provider call:

  A  the second worker's stale sweep held the job for reconciliation; the first then settled it and its adoption's full save
     overwrote the state as 'succeeded';
  B  an administrator resolved the swept job with release_no_cost ("Resolved by administrator: no provider cost
     evidenced.", holds released, request key freed); the first worker's receipt (0.10) then committed for that job, no
     usage and no platform cost, and audit_billing still passed every check.

Now: settle() refuses a job that is not running (core.billing.SETTLEABLE_STATES); a receipt that arrives after its job left
'running' is recorded, never settled, never dropped, and held for an administrator (core.jobs.hold_late_receipt), whose
resolution absorbs its cost; audit_billing fails until it does (receipt_policy); an adoption never overwrites a job that
left 'running'; and `manage.py worker` holds a session-level advisory lock for its whole life, so a second worker process
against the same database refuses to start (core.worker_lock).

Real PostgreSQL; synthetic records; the provider is a fake (no network request). The worker-process tests start real
`manage.py worker` processes against this test database.
"""
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import billing, worker_lock
from core.jobs import LATE_RECEIPT, cancel, deliverable, ended_key, enqueue, mark_stale, run_one
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Encounter, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, Wallet
from core.tests.test_billing_boundary import LIVE, adopted_live_result
from core.tests.test_billing_policy import AUDITABLE_RATES, PolicyFixture, STORAGES
# Modules, never their TestCases by name: a TestCase imported into this module would be collected and run here again.
from core.tests import test_mapping_outcome_unknown as mapping_outcome
from core.tests import test_settlement_database_error as held
from core.tests.test_settlement_database_error import HeldSettlementFixture

SWEPT = 'Worker stopped with an unknown provider outcome. Automatic retry is disabled.'
NO_COST = 'Resolved by administrator: no provider cost evidenced.'
RECEIPT_ABSORBED = 'Resolved by administrator: the provider cost of its durable receipt absorbed by QuillMD.'
SETTLED_ABSORBED = 'Resolved by administrator: settled provider cost absorbed by QuillMD.'
RELEASE = {'outcome': 'release_no_cost', 'evidence_note': 'Synthetic: provider console shows no completed request yet'}
UNITS = {'input_tokens': 100, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0}
#: Every session timeout the worker refuses unless it is 0 (core.worker_lock.TIMEOUT_SETTINGS), spelled out here so that
#: dropping one from the module fails a test rather than shrinking every loop that reads the module.
ALL_TIMEOUTS = ('lock_timeout', 'statement_timeout', 'idle_session_timeout', 'idle_in_transaction_session_timeout')


def failing_checks(report):
    """Every failed check of an audit_billing report, by name (per-row, per-wallet, per-batch and report-level)."""
    failed = set()
    for row in report['rows'] + report['wallets'] + report['generation_batches']:
        failed |= {name for name, passed in row['checks'].items() if not passed}
    for section in ('ledger_policy', 'cancellation_policy', 'hold_policy', 'receipt_policy'):
        failed |= {name for name, passed in report[section]['checks'].items() if not passed}
    return failed


class Console:
    """One administrator for the whole test: the resolve form is posted more than once."""

    def administrator(self):
        if not hasattr(self, '_administrator'):
            self._administrator = held.ResolvingASettlementHeldByADatabaseError.console(self)
        return self._administrator[1]

    def resolve(self, job, form=RELEASE):
        return self.administrator().post(f'/console/jobs/{job.pk}/resolve/', form)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class SecondWorkerDuringALiveProviderCall(Console, HeldSettlementFixture, TransactionTestCase):
    """The probe's cases A and B, as regressions. RED before this change: A ended 'succeeded' with usage settled, B ended
    'failed' reading "no provider cost evidenced" beside a 0.10 receipt, and audit_billing passed both."""

    def wallets(self):
        return {(w.pk, w.balance, w.reserved) for w in Wallet.objects.filter(pk__in=[self.promo.pk, self.paid.pk])}

    def document(self, draft):
        e = Encounter.objects.get(pk=draft.pk)
        return (e.answers, e.status, e.revision, e.notes)

    def second_worker_during_the_call(self, name, *, resolve_form=None, then=None):
        """W1 = run_one here; while it is inside the provider call a second worker's loop sweeps the job (it has run for
        more than five minutes) and, optionally, an administrator resolves what the sweep held. W1 holds no transaction or
        lock during the provider call, so this connection is equivalent to the second process's."""
        draft = self.draft()
        before, document = self.wallets(), self.document(draft)
        job = enqueue(draft, self.user)
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_two_workers_' + name)
        seen = {}

        def provider(*args, **kwargs):
            Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
            mark_stale()
            fresh = Job.objects.get(pk=job.pk)
            seen['swept'] = (fresh.state, fresh.error)
            if resolve_form is not None:
                response = self.resolve(job, resolve_form)
                fresh = Job.objects.get(pk=job.pk)
                seen['resolved'] = (response.status_code, fresh.state, fresh.error, fresh.request_key)
            if then is not None:
                then(job, draft)
            return result
        with patch('core.jobs.generation.generate', side_effect=provider) as call:
            self.assertTrue(run_one())
        self.assertEqual(call.call_count, 1)
        self.assertEqual(seen['swept'], ('reconciliation', SWEPT))
        return job, draft, before, document, seen

    def assert_late_receipt_held(self, job, draft, document, holds, previous):
        job.refresh_from_db()
        self.assertEqual((job.state, job.error, job.finished_at), ('reconciliation', LATE_RECEIPT, None))
        self.assertNotIn('no provider cost', job.error)
        # Recorded, never dropped; never settled: no usage, no ledger movement, no platform cost yet.
        self.assertEqual(ProviderReceipt.objects.get(job=job).actual_cost, Decimal('0.1'))
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertFalse(PlatformCost.objects.filter(job=job).exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {holds})
        self.assertFalse(deliverable(job))
        self.assertEqual(self.document(draft), document)
        self.assertFalse(AuditEvent.objects.filter(target=str(job.pk), action__in=['usage.settle', 'job.succeeded']).exists())
        late = AuditEvent.objects.get(action='provider.receipt_late', target=str(job.pk))
        self.assertEqual((late.details['previous_state'], late.details['previous_error'], late.details['state']),
                         (previous[0], previous[1], 'reconciliation'))
        refused = AuditEvent.objects.get(action='job.error_after_commit', target=str(job.pk))
        self.assertEqual((refused.details['state'], refused.details['error_class']), ('reconciliation', 'SettlementRefused'))
        # audit_billing flags it: unsettled, unresolved, late, and the audit FAILS on exactly that until it is resolved.
        report = audit_report()
        self.assertFalse(report['all_checks_pass'])
        self.assertEqual(failing_checks(report), {'late_provider_receipts_resolved'})
        self.assertEqual(report['receipt_policy']['late_provider_receipts'], [str(job.pk)])
        self.assertIn(job.pk, [row['id'] for row in report['unresolved_jobs']])
        self.assertIn(job.pk, [row['job_id'] for row in report['unsettled_provider_receipts']])

    def assert_resolved_as_absorbed(self, job, before):
        response = self.resolve(job)
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', RECEIPT_ABSORBED))
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Decimal('0.1'))
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'released'})
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertEqual(self.wallets(), before)  # never charged, never double-charged
        self.assertEqual(job.request_key.count(':failed:'), 1)
        self.assertTrue(job.request_key.endswith(':failed:' + job.pk.hex))
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], failing_checks(report))
        self.assertEqual(report['receipt_policy']['late_provider_receipts'], [])
        self.assertNotIn(job.pk, [row['id'] for row in report['unresolved_jobs']])

    def test_case_a_a_sweep_during_the_call_holds_the_late_receipt_and_never_succeeds(self):
        job, draft, before, document, _ = self.second_worker_during_the_call('a')
        self.assert_late_receipt_held(job, draft, document, 'held', ('reconciliation', SWEPT))
        self.assert_resolved_as_absorbed(job, before)
        self.assertEqual(self.document(draft), document)

    def test_case_b_a_release_no_cost_during_the_call_is_reopened_not_left_false(self):
        job, draft, before, document, seen = self.second_worker_during_the_call('b', resolve_form=RELEASE)
        # What the administrator recorded was true when it was recorded: nothing was evidenced yet.
        status, state, error, key = seen['resolved']
        self.assertEqual((status, state, error), (302, 'failed', NO_COST))
        self.assertTrue(key.endswith(':failed:' + job.pk.hex))
        self.assert_late_receipt_held(job, draft, document, 'released', ('failed', NO_COST))
        self.assertEqual(Job.objects.get(pk=job.pk).request_key, key)  # the freed key stays freed; it is not re-held
        self.assert_resolved_as_absorbed(job, before)

    def test_case_b_with_a_second_request_on_the_freed_key_charges_it_once_as_its_own(self):
        second = {}

        def request_again(job, draft):
            second['job'] = enqueue(draft, self.user)  # the key was freed by the resolution
        job, draft, before, document, _ = self.second_worker_during_the_call('b2', resolve_form=RELEASE, then=request_again)
        again = second['job']
        self.assertFalse(getattr(again, 'reused', True))
        self.assertEqual(Job.objects.get(pk=again.pk).state, 'queued')
        self.assert_late_receipt_held(job, draft, document, 'released', ('failed', NO_COST))
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_two_workers_b2_again')
        with patch('core.jobs.generation.generate', return_value=result):
            self.assertTrue(run_one())
        again.refresh_from_db()
        self.assertEqual(again.state, 'succeeded')
        self.assertEqual(Usage.objects.get(job=again).charged_cost, Decimal('0.15'))
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.resolve(job)
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Decimal('0.1'))
        # One charge in all: the second request's 0.15. The first request's 0.10 is the platform's.
        charged = -sum(LedgerEntry.objects.filter(kind='usage').values_list('amount', flat=True))
        self.assertEqual(charged, Decimal('0.15'))
        self.assertEqual(sum(b for _, b, _ in before) - sum(b for _, b, _ in self.wallets()), Decimal('0.15'))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_late_receipt_meeting_an_earlier_typed_amount_records_the_receipt_and_frees_the_encounter(self):
        """L1:R1-1. The first resolution typed a platform cost before the receipt existed; the receipt (0.10) then reopened
        the job. The second resolution, whatever outcome and amount its form carries, records the receipt's amount on that
        same platform-cost row (audited with both amounts), charges nobody, ends the job and frees the encounter: the audit
        passes and a new request is accepted. RED before: every resolution answered 400 and rolled back, so the job stayed
        held, the audit failed and the encounter refused every new request ('already has a pending job') for good."""
        runs = (  # (name, the first resolution's typed amount, the second resolution's form)
            ('below_release', '0.05', RELEASE),
            ('below_same', '0.05', {'outcome': 'absorb_platform_failure', 'actual_cost': '0.05',
                                    'evidence_note': 'Synthetic: the same typed estimate again'}),
            ('above_other', '0.5', {'outcome': 'absorb_platform_failure', 'actual_cost': '0.07',
                                    'evidence_note': 'Synthetic: a second, different estimate'}),
        )
        for name, first_amount, second in runs:
            with self.subTest(run=name):
                typed = {'outcome': 'absorb_platform_failure', 'actual_cost': first_amount,
                         'evidence_note': 'Synthetic typed estimate'}
                job, draft, before, document, seen = self.second_worker_during_the_call('typed_' + name, resolve_form=typed)
                self.assertEqual(seen['resolved'][:3], (302, 'failed', 'Resolved by administrator: provider cost absorbed by QuillMD.'))
                job.refresh_from_db()
                self.assertEqual((job.state, job.error), ('reconciliation', LATE_RECEIPT))
                receipt = ProviderReceipt.objects.get(job=job)
                self.assertEqual(receipt.actual_cost, Decimal('0.1'))
                typed_row = PlatformCost.objects.get(job=job, kind='absorbed_failure')
                self.assertEqual(typed_row.amount, Decimal(first_amount))
                self.assertEqual(failing_checks(audit_report()), {'late_provider_receipts_resolved'})
                with self.assertRaisesMessage(ValidationError, 'already has a pending job'):
                    enqueue(Encounter.objects.get(pk=draft.pk), self.user)

                response = self.resolve(job, second)
                self.assertEqual(response.status_code, 302)
                job.refresh_from_db()
                self.assertEqual((job.state, job.error), ('failed', RECEIPT_ABSORBED))
                self.assertEqual(job.request_key.count(':failed:'), 1)
                # The same row, now at the receipt's amount and naming the receipt; never a second row.
                row = PlatformCost.objects.get(job=job, kind='absorbed_failure')
                self.assertEqual((row.pk, row.amount), (typed_row.pk, receipt.actual_cost))
                self.assertTrue(row.evidence_reference.startswith(f'receipt:{receipt.pk} '))
                self.assertEqual(PlatformCost.objects.filter(job=job).count(), 1)
                adjusted = AuditEvent.objects.get(action='platform_cost.adjusted_to_receipt', target=str(job.pk))
                self.assertEqual((Decimal(adjusted.details['previous_amount']), Decimal(adjusted.details['amount'])),
                                 (Decimal(first_amount), receipt.actual_cost))
                self.assertEqual((adjusted.details['platform_cost'], adjusted.details['receipt']), (str(row.pk), str(receipt.pk)))
                self.assertEqual(adjusted.details['previous_evidence_reference'], 'Synthetic typed estimate')
                resolved = AuditEvent.objects.filter(action='job.resolved', target=str(job.pk)).order_by('-created_at').first()
                self.assertEqual(Decimal(resolved.details['actual_cost']), receipt.actual_cost)
                # Never charged, never double-charged: no usage, no ledger movement, every hold released.
                self.assertFalse(Usage.objects.filter(job=job).exists())
                self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
                self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'released'})
                self.assertEqual(self.wallets(), before)
                self.assertEqual(self.document(draft), document)
                report = audit_report()
                self.assertTrue(report['all_checks_pass'], failing_checks(report))
                self.assertEqual(report['receipt_policy']['late_provider_receipts'], [])
                # The encounter takes new work again.
                again = enqueue(Encounter.objects.get(pk=draft.pk), self.user)
                self.assertFalse(getattr(again, 'reused', True))
                self.assertEqual(Job.objects.get(pk=again.pk).state, 'queued')
                self.assertEqual(self.resolve(job, second).status_code, 409)  # resolved once; never again
                cancel(again, self.user)

    def settle_then(self, name, *, resolve):
        """The sweep (and, optionally, a resolution) lands AFTER settlement committed and BEFORE the adoption."""
        draft = self.draft()
        before, document = self.wallets(), self.document(draft)
        job = enqueue(draft, self.user)
        real = billing.settle

        def settle(*args, **kwargs):
            usage = real(*args, **kwargs)
            Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
            mark_stale()
            if resolve:
                self.assertEqual(self.resolve(job).status_code, 302)
            return usage
        result = adopted_live_result(draft.notes, draft.template_version.fields, 'req_after_settle_' + name)
        with patch('core.jobs.generation.generate', return_value=result), patch('core.jobs.settle', side_effect=settle):
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(self.document(draft), document)  # nothing adopted
        self.assertFalse(AuditEvent.objects.filter(target=str(job.pk), action='job.succeeded').exists())
        refused = AuditEvent.objects.get(action='job.error_after_commit', target=str(job.pk))
        self.assertEqual(refused.details['error_class'], 'JobNoLongerRunning')
        return job, before

    def test_a_sweep_after_settlement_is_never_overwritten_as_succeeded(self):
        """Case A's other interleaving: the probe's adoption full save turned the swept job into 'succeeded'."""
        job, before = self.settle_then('sweep', resolve=False)
        self.assertEqual((job.state, job.error), ('reconciliation', SWEPT))
        self.assertTrue(Usage.objects.filter(job=job).exists())
        self.assertTrue(audit_report()['all_checks_pass'])
        self.assertEqual(self.resolve(job).status_code, 302)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', SETTLED_ABSORBED))
        self.assertEqual(self.wallets(), before)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_resolution_after_settlement_is_never_overwritten_as_succeeded(self):
        job, before = self.settle_then('resolve', resolve=True)
        self.assertEqual((job.state, job.error), ('failed', SETTLED_ABSORBED))
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Decimal('0.1'))
        self.assertEqual(self.wallets(), before)
        self.assertTrue(audit_report()['all_checks_pass'])


class MappingLateReceipt(Console, mapping_outcome.MappingOutcomeFixture):
    """Case B on the mapping worker (core.mapping_jobs.run_one), which the stale sweep and the resolution also reach."""

    def test_a_mapping_receipt_after_release_no_cost_is_reopened_and_absorbed(self):
        before = mapping_outcome.wallets(self.user)
        job = self.enqueue()
        response = self.response()
        seen = {}

        def create(*args, **kwargs):
            Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
            mark_stale()
            answer = self.resolve(job)
            fresh = Job.objects.get(pk=job.pk)
            seen['resolved'] = (answer.status_code, fresh.state, fresh.error)
            return response
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = create
            self.assertTrue(run_one())
        self.assertEqual(seen['resolved'], (302, 'failed', NO_COST))
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', LATE_RECEIPT))
        receipt = ProviderReceipt.objects.get(job=job)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertEqual(self.template.versions.count(), 1)  # nothing adopted
        self.assertEqual(failing_checks(audit_report()), {'late_provider_receipts_resolved'})
        self.assertEqual(self.resolve(job).status_code, 302)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', RECEIPT_ABSORBED))
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, receipt.actual_cost)
        self.assertEqual(mapping_outcome.wallets(self.user), before)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_mapping_swept_after_settlement_adopts_no_version_and_is_never_succeeded(self):
        before = mapping_outcome.wallets(self.user)
        job = self.enqueue()
        real = billing.settle

        def settle(*args, **kwargs):
            usage = real(*args, **kwargs)
            Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
            mark_stale()
            return usage
        with patch('core.mapping_jobs.settle', side_effect=settle):
            self.run_mapping()
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('reconciliation', SWEPT))
        self.assertEqual(self.template.versions.count(), 1)
        self.assertTrue(Usage.objects.filter(job=job).exists())
        refused = AuditEvent.objects.get(action='job.error_after_commit', target=str(job.pk))
        self.assertEqual(refused.details['error_class'], 'JobNoLongerRunning')
        self.assertFalse(AuditEvent.objects.filter(action='mapping.review_ready', target=str(job.pk)).exists())
        self.assertEqual(self.resolve(job).status_code, 302)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', SETTLED_ABSORBED))
        self.assertEqual(mapping_outcome.wallets(self.user), before)
        self.assertTrue(audit_report()['all_checks_pass'])


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class SettleRefusesAJobThatIsNoLongerRunning(PolicyFixture, TestCase):
    def held_job(self, key, state):
        job = Job.objects.create(encounter=self.encounter, user=self.user, request_key=key)
        billing.reserve(job, Decimal('0.2'))
        Job.objects.filter(pk=job.pk).update(state=state)
        return job

    def money(self, job):
        return (sorted((str(w.pk), w.balance, w.reserved) for w in Wallet.objects.all()),
                sorted((str(r.pk), r.state, r.amount) for r in Reservation.objects.filter(job=job)),
                LedgerEntry.objects.count(), Usage.objects.count(), PlatformCost.objects.count())

    def test_every_state_but_queued_and_running_is_refused_before_any_write(self):
        for state in ('reconciliation', 'failed', 'cancelled', 'succeeded', 'staged', 'a-state-added-later'):
            with self.subTest(state=state):
                job = self.held_job(f'guard-{state}', state)
                before = self.money(job)
                with self.assertRaisesMessage(billing.SettlementRefused, f'this request is {state}, not running'):
                    billing.settle(job, Decimal('0.1'), UNITS, AUDITABLE_RATES, 'anthropic:synthetic-model', f'req_guard_{state}',
                                   provider_resource_id=f'msg_guard_{state}')
                self.assertEqual(self.money(job), before)
                self.assertFalse(AuditEvent.objects.filter(action='usage.settle', target=str(job.pk)).exists())

    def test_queued_and_running_jobs_settle(self):
        for state in ('queued', 'running'):
            with self.subTest(state=state):
                job = self.held_job(f'settles-{state}', state)
                usage = billing.settle(job, Decimal('0.1'), UNITS, AUDITABLE_RATES, 'anthropic:synthetic-model',
                                       f'req_settles_{state}', provider_resource_id=f'msg_settles_{state}')
                self.assertEqual(usage.charged_cost, Decimal('0.15'))

    def test_an_administrator_path_settles_only_the_states_it_names(self):
        job = self.held_job('named-reconciliation', 'reconciliation')
        usage = billing.settle(job, Decimal('0.1'), UNITS, AUDITABLE_RATES, 'anthropic:synthetic-model', 'req_named',
                               provider_resource_id='msg_named', allowed_states=('reconciliation',))
        self.assertEqual(usage.charged_cost, Decimal('0.15'))
        other = self.held_job('named-failed', 'failed')
        with self.assertRaises(billing.SettlementRefused):
            billing.settle(other, Decimal('0.1'), UNITS, AUDITABLE_RATES, 'anthropic:synthetic-model', 'req_named_2',
                           provider_resource_id='msg_named_2', allowed_states=('reconciliation',))

    def test_no_code_returns_a_job_to_queued(self):
        """SETTLEABLE_STATES accepts 'queued' ONLY because no code moves a job back to it: a job that ran can never be
        'queued' again, so a late settlement can never meet that state. This pins the premise."""
        core = Path(settings.BASE_DIR) / 'core'
        pattern = re.compile(r"""(?:\.state\s*=|update\([^)]*\bstate\s*=)\s*['"]queued['"]""")
        offenders = [f'{path.relative_to(core)}:{number}' for path in sorted(core.rglob('*.py')) if 'tests' not in path.parts
                     for number, line in enumerate(path.read_text().splitlines(), 1) if pattern.search(line)]
        self.assertEqual(offenders, [])
        self.assertTrue(pattern.search("job.state='queued'"))  # the pattern can match (control)

    def test_the_audit_fails_on_a_receipt_nothing_accounts_for(self):
        """The probe's case B end state, built directly: a failed job, a 0.10 receipt, no usage, no platform cost."""
        job = self.held_job('unaccounted', 'failed')
        billing.release(job)
        ProviderReceipt.objects.create(job=job, provider='anthropic:synthetic-model', provider_request_id='req_unaccounted',
                                       actual_cost=Decimal('0.1'), units=UNITS, rates=AUDITABLE_RATES)
        report = audit_report()
        self.assertEqual(failing_checks(report), {'provider_receipts_settled_absorbed_or_held'})
        self.assertEqual(report['receipt_policy']['unaccounted_provider_receipts'], [str(job.pk)])
        cost = PlatformCost.objects.create(job=job, kind='absorbed_failure', amount=Decimal('0.05'), description='typed')
        self.assertEqual(failing_checks(audit_report()), {'provider_receipts_settled_absorbed_or_held'})
        PlatformCost.objects.filter(pk=cost.pk).delete()
        PlatformCost.objects.create(job=job, kind='absorbed_failure', amount=Decimal('0.1'), description='the receipt')
        self.assertTrue(audit_report()['all_checks_pass'])
        # A held job's receipt is not a failure: it is listed as unresolved, as every held job is.
        held_job = self.held_job('held-receipt', 'reconciliation')
        ProviderReceipt.objects.create(job=held_job, provider='anthropic:synthetic-model', provider_request_id='req_held',
                                       actual_cost=Decimal('0.1'), units=UNITS, rates=AUDITABLE_RATES)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_an_ended_key_is_suffixed_once(self):
        job = Job.objects.create(encounter=self.encounter, user=self.user, request_key='transcription:' + 'x' * 101)
        once = ended_key(job, 'failed')
        self.assertEqual(len(once), 115 + 8 + 32)
        job.request_key = once
        self.assertEqual(ended_key(job, 'failed'), once)
        self.assertEqual(ended_key(job, 'cancelled'), once)
        Job.objects.filter(pk=job.pk).update(request_key=once)  # fits the 160-character column


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class LateReceiptAgainstATypedAmount(Console, PolicyFixture, TestCase):
    """The resolution's two answers to a platform cost of another amount than the job's receipt (views.admin_resolve_job).
    The whole two-worker sequence is SecondWorkerDuringALiveProviderCall's typed-amount test; these build the end state."""

    def held(self, key, *, late):
        job = Job.objects.create(encounter=self.encounter, user=self.user, request_key=key)
        billing.reserve(job, Decimal('0.2'))
        billing.release(job)
        Job.objects.filter(pk=job.pk).update(state='reconciliation', error=LATE_RECEIPT)
        typed = PlatformCost.objects.create(job=job, kind='absorbed_failure', amount=Decimal('0.05'),
                                            description='Provider cost absorbed: uncertain outcome resolved by administrator',
                                            evidence_reference='Synthetic typed estimate')
        receipt = ProviderReceipt.objects.create(job=job, provider='anthropic:synthetic-model', provider_request_id=f'req_{key}',
                                                 actual_cost=Decimal('0.1'), units=UNITS, rates=AUDITABLE_RATES)
        if late:
            AuditEvent.objects.create(action='provider.receipt_late', target=str(job.pk),
                                      details={'previous_state': 'failed', 'state': 'reconciliation'})
        return job, typed, receipt

    def money(self):
        return (sorted((str(w.pk), w.balance, w.reserved) for w in Wallet.objects.all()), LedgerEntry.objects.count(),
                Usage.objects.count())

    def test_a_late_receipt_sets_the_typed_row_to_its_amount(self):
        job, typed, receipt = self.held('late-receipt-typed', late=True)
        before = self.money()
        self.assertEqual(self.resolve(job).status_code, 302)
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('failed', RECEIPT_ABSORBED))
        row = PlatformCost.objects.get(job=job, kind='absorbed_failure')
        self.assertEqual((row.pk, row.amount), (typed.pk, receipt.actual_cost))
        self.assertEqual(self.money(), before)
        adjusted = AuditEvent.objects.get(action='platform_cost.adjusted_to_receipt', target=str(job.pk))
        self.assertEqual((Decimal(adjusted.details['previous_amount']), Decimal(adjusted.details['amount'])),
                         (Decimal('0.05'), Decimal('0.1')))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_different_amount_with_no_late_receipt_is_still_refused(self):
        """Every product path records an absorbed amount on a receipt-backed job from that receipt; only a receipt that
        arrived after a typed resolution (provider.receipt_late) meets a different one. Any other disagreement has an
        origin this view cannot see, so it is refused and nothing of the resolution stands."""
        job, typed, receipt = self.held('not-late-typed', late=False)
        before = self.money()
        refused = self.resolve(job)
        self.assertEqual(refused.status_code, 400)
        self.assertIn(b'conflicts with the previously recorded platform cost', refused.content)
        job.refresh_from_db()
        self.assertEqual(job.state, 'reconciliation')
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Decimal('0.05'))
        self.assertFalse(AuditEvent.objects.filter(action__in=['platform_cost.adjusted_to_receipt', 'job.resolved'],
                                                   target=str(job.pk)).exists())
        self.assertEqual(self.money(), before)

    def test_another_jobs_late_receipt_does_not_license_this_one(self):
        """The late-receipt licence is per job (RF-B): a provider.receipt_late event for a different job leaves this job's
        conflicting amount refused."""
        other, _, _ = self.held('other-job-late', late=True)
        self.assertTrue(AuditEvent.objects.filter(action='provider.receipt_late', target=str(other.pk)).exists())
        job, typed, receipt = self.held('this-job-not-late', late=False)
        before = self.money()
        self.assertEqual(self.resolve(job).status_code, 400)
        job.refresh_from_db()
        self.assertEqual(job.state, 'reconciliation')
        self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, Decimal('0.05'))
        self.assertEqual(self.money(), before)


class TheLockKey(TestCase):
    databases = set()

    def test_the_key_is_fixed_and_no_other_advisory_key(self):
        self.assertEqual(worker_lock.WORKER_LOCK_KEY, int.from_bytes(b'QUILLWK1', 'big'))
        self.assertEqual(worker_lock.WORKER_LOCK_KEY, 5860671082139700017)
        self.assertLess(worker_lock.WORKER_LOCK_KEY, 2 ** 63)
        others = set()
        rebuild = Path(settings.BASE_DIR)
        for path in list((rebuild / 'core').rglob('*.py')) + list((rebuild / 'ops').rglob('*.py')):
            if 'tests' in path.parts or path.name.startswith('test_'):
                continue
            for line in path.read_text().splitlines():
                if 'advisory' in line or 'LOCK_KEY' in line:
                    others |= {int(n) for n in re.findall(r'(?<![\w.])(\d{9,})(?![\w.])', line)}
        self.assertTrue({716849203517, 748413910342, 748413910341, 913020260917} <= others, others)  # control
        others.discard(worker_lock.WORKER_LOCK_KEY)
        self.assertNotIn(worker_lock.WORKER_LOCK_KEY, others)
        from core import retention
        self.assertNotEqual(worker_lock.WORKER_LOCK_KEY, retention.LOCK_KEY)


def holders():
    with connection.cursor() as cursor:
        return worker_lock.lock_holders(cursor)


def wait_for(condition, seconds, label):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(f'timed out waiting for {label}')


class SingleWorkerLock(TestCase):
    """In-process: the lock, its loss, the worker command and the timeouts."""

    def test_a_second_acquire_is_refused_until_the_first_releases(self):
        first = worker_lock.acquire()
        try:
            self.assertEqual(holders(), [first.pid])
            with self.assertRaises(worker_lock.WorkerLockHeld) as refused:
                worker_lock.acquire()
            self.assertIn(f'held by database session {first.pid}', str(refused.exception))
            self.assertIn(str(worker_lock.WORKER_LOCK_KEY), str(refused.exception))
            first.verify()
        finally:
            first.release()
        self.assertEqual(holders(), [])
        second = worker_lock.acquire()
        second.release()

    def test_a_lock_whose_session_ended_is_lost_and_free(self):
        lock = worker_lock.acquire()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_terminate_backend(%s)', [lock.pid])
            wait_for(lambda: holders() == [], 30, 'the terminated session to release the lock')
            with self.assertRaisesMessage(worker_lock.WorkerLockLost, 'no longer holds the single-worker lock'):
                lock.verify()
        finally:
            lock.release()
        worker_lock.acquire().release()

    def test_the_worker_command_refuses_while_another_worker_holds_the_lock(self):
        other = worker_lock.acquire()
        try:
            with patch('core.management.commands.worker.run_one') as work, patch('core.management.commands.worker.mark_stale') as sweep:
                with self.assertRaisesMessage(CommandError, 'Another QuillMD worker holds the single-worker lock'):
                    call_command('worker', once=True)
            self.assertFalse(work.called or sweep.called)  # nothing swept, nothing sent
        finally:
            other.release()
        with patch('core.management.commands.worker.run_one', return_value=False) as work:
            call_command('worker', once=True)
        self.assertTrue(work.called)
        self.assertEqual(holders(), [])  # --once releases its lock

    def test_a_lost_lock_stops_the_worker_before_its_next_pass(self):
        passes = []

        def one_pass():
            passes.append(1)
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_terminate_backend(%s)', [holders()[0]])
            wait_for(lambda: holders() == [], 30, 'the lock to be released')
            return False
        with patch('core.management.commands.worker.run_one', side_effect=one_pass), \
                patch('core.management.commands.worker.time.sleep'):
            with self.assertRaisesMessage(CommandError, 'no longer holds the single-worker lock'):
                call_command('worker')
        self.assertEqual(len(passes), 1)

    def report(self):
        out = StringIO()
        call_command('configuration_status', stdout=out)
        return out.getvalue()

    def test_configuration_status_reports_the_lock_and_zero_timeouts(self):
        report = self.report()
        # L2:R2-5: an absent lock shows that no worker HOLDS it, never that no worker process runs (one whose lock session
        # ended is still inside its request until its next pass; a build from before the lock never takes it).
        self.assertIn(f'single-worker lock (advisory key {worker_lock.WORKER_LOCK_KEY}): not held: no lock-holding worker\n',
                      report)
        self.assertNotIn('no worker is running', report)
        self.assertEqual(worker_lock.TIMEOUT_SETTINGS, ALL_TIMEOUTS)
        for name in ALL_TIMEOUTS:
            self.assertRegex(report, rf'  {name}: 0 for this session; no login default \(role \w+\)')
        lock = worker_lock.acquire()
        try:
            self.assertIn(f'held by database session {lock.pid}', self.report())
        finally:
            lock.release()

    def test_the_services_page_mirror_carries_the_worker_lines(self):
        from core import admin_console
        lines = self.report().splitlines()
        start = lines.index('Worker (one per database; it refuses to start unless every timeout below is 0):')
        mirror = [f"{row['name']}: {row['value']}" for row in admin_console.configuration_rows()['worker']]
        self.assertEqual(len(mirror), 1 + len(ALL_TIMEOUTS))
        section = [line.strip() for line in lines[start + 1:start + 1 + len(mirror)]]
        self.assertEqual(mirror, section)

    def assert_refused(self, found):
        out = StringIO()
        with self.assertRaisesMessage(CommandError, found):
            call_command('configuration_status', stdout=out)
        self.assertIn('NON-ZERO, the worker refuses to start', out.getvalue())
        with patch('core.management.commands.worker.run_one') as work:
            with self.assertRaisesMessage(CommandError, found):
                call_command('worker', once=True)
        self.assertFalse(work.called)
        self.assertEqual(holders(), [])  # refused before the lock

    def test_a_non_zero_timeout_in_this_session_is_refused(self):
        # Seven minutes, not seconds: this test's own session sits idle in its transaction between statements.
        for name in ALL_TIMEOUTS:
            with self.subTest(name=name):
                with connection.cursor() as cursor:
                    cursor.execute(f"SET {name} = '7min'")
                try:
                    self.assert_refused(f'{name}=420000 (this session)')
                finally:
                    with connection.cursor() as cursor:
                        cursor.execute(f'RESET {name}')
        self.assertEqual(worker_lock.session_timeout_problems(), [])

    def test_a_non_zero_login_default_is_refused(self):
        """ALTER DATABASE ... SET reaches only NEW sessions; the refusal reads the login default too. Inside this test's
        transaction, which rolls it back."""
        database = connection.settings_dict['NAME']
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER DATABASE {connection.ops.quote_name(database)} SET lock_timeout = '5s'")
        self.assertEqual(worker_lock.session_timeouts()['lock_timeout']['current'], '0')
        self.assert_refused('lock_timeout=5s (login default for this role or database)')

    def test_a_non_zero_idle_in_transaction_timeout_is_refused(self):
        """L2:R2-3. The worker's adoption holds its transaction, and the encounter's row lock, open while Python adopts the
        output, so its session sits 'idle in transaction': idle_in_transaction_session_timeout ends it mid-adoption and the
        paid-for generation is lost. RED before: a 1s login default passed every check and the worker started."""
        database = connection.settings_dict['NAME']
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER DATABASE {connection.ops.quote_name(database)} SET idle_in_transaction_session_timeout = '1s'")
        self.assertEqual(worker_lock.session_timeout_problems(),
                         ['idle_in_transaction_session_timeout=1s (login default for this role or database)'])
        self.assert_refused('idle_in_transaction_session_timeout=1s (login default for this role or database)')

    def test_configuration_status_degrades_when_the_database_cannot_be_read(self):
        """L2:R2-2. Every worker row reads UNKNOWN and the command exits 0, as the rest of the report degrades. RED before:
        the timeout refusal opened its own cursor with no guard and ended the command in an OperationalError traceback."""
        class Unreachable:
            def cursor(self):
                raise OperationalError('synthetic: connection refused')
        out = StringIO()
        with patch('core.worker_lock.connection', Unreachable()):
            call_command('configuration_status', stdout=out)
        lines = out.getvalue().splitlines()
        start = lines.index('Worker (one per database; it refuses to start unless every timeout below is 0):')
        unknown = 'UNKNOWN: the database could not be read (OperationalError)'
        self.assertEqual([line.strip() for line in lines[start + 1:]],
                         [f'single-worker lock: {unknown}'] + [f'{name}: {unknown}' for name in ALL_TIMEOUTS])
        from core import admin_console
        with patch('core.worker_lock.connection', Unreachable()):
            rows = admin_console.configuration_rows()['worker']
        self.assertEqual([(row['value'], row['severity']) for row in rows], [(unknown, 'error')] * (1 + len(ALL_TIMEOUTS)))


class ConfigurationStatusWithoutADatabase(TestCase):
    databases = set()

    def test_an_unreachable_database_degrades_to_unknown_rows_and_exit_zero(self):
        """L2:R2-2 end to end: a real `manage.py configuration_status` whose database port refuses the connection (port 1,
        a synthetic password; nothing listens there). RED before: exit 1 with an OperationalError traceback."""
        environment = dict(os.environ, QUILLMD_DB_HOST='127.0.0.1', QUILLMD_DB_PORT='1',
                           QUILLMD_DB_PASSWORD='synthetic-unreachable-port-no-credential', PYTHONUNBUFFERED='1')
        done = subprocess.run([sys.executable, '-B', str(Path(settings.BASE_DIR) / 'manage.py'), 'configuration_status'],
                              cwd=settings.BASE_DIR, env=environment, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=180)
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        self.assertNotIn('Traceback', done.stderr)
        unknown = 'UNKNOWN: the database could not be read (OperationalError)'
        self.assertIn(f'  single-worker lock: {unknown}\n', done.stdout)
        for name in ALL_TIMEOUTS:
            self.assertIn(f'  {name}: {unknown}\n', done.stdout)


class WorkerProcesses(TransactionTestCase):
    """Two real `manage.py worker` processes against this test database: the second refuses to start; the lock is released
    when the first dies; a third then starts, and a graceful stop releases it."""

    def start(self):
        environment = dict(os.environ, QUILLMD_DB_NAME=connection.settings_dict['NAME'], PYTHONUNBUFFERED='1')
        process = subprocess.Popen([sys.executable, '-B', str(Path(settings.BASE_DIR) / 'manage.py'), 'worker'],
                                   cwd=settings.BASE_DIR, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        return process

    def holding(self, process):
        def held():
            if process.poll() is not None:
                raise AssertionError(f'worker exited {process.returncode}: {process.stderr.read()[-2000:]}')
            return holders()
        return wait_for(held, 90, 'the worker to take the lock')

    def test_a_second_worker_refuses_and_the_lock_follows_the_process(self):
        self.processes = []
        try:
            first = self.start()
            [pid] = self.holding(first)
            second = self.start()
            _, errors = second.communicate(timeout=120)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn('Another QuillMD worker holds the single-worker lock', errors)
            self.assertIn(f'held by database session {pid}', errors)
            self.assertIsNone(first.poll())
            self.assertEqual(holders(), [pid])
            first.send_signal(signal.SIGKILL)  # dies without releasing anything
            first.wait(30)
            wait_for(lambda: holders() == [], 60, 'the dead worker\'s lock to be released')
            third = self.start()
            [third_pid] = self.holding(third)
            self.assertNotEqual(third_pid, pid)
            third.send_signal(signal.SIGTERM)  # graceful stop
            third.wait(60)
            self.assertEqual(third.returncode, 0)
            self.assertEqual(holders(), [])
        finally:
            for process in self.processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(30)
                for stream in (process.stdout, process.stderr):
                    stream.close()
