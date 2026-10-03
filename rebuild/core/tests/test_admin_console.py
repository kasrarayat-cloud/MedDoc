"""Administration console: money rendering, overview arithmetic, operational honesty, access.

Each test states the defect it prevents, because several of these were found by measurement and
would read as arbitrary assertions otherwise.
"""
from datetime import timedelta
from decimal import Decimal
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.template import Context, Template
from django.template.loader import render_to_string
from django.template.defaultfilters import floatformat
from django.test import Client, SimpleTestCase, TestCase, override_settings
from core.tests.surfaces import SurfaceClient
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import admin_console
from core.billing import reconcile_usage, reserve, settle
from core.models import (AuditEvent, Department, Invitation, Job, LedgerEntry, Membership,
                         Payment, PlatformCost, ProviderReceipt, Refund, Reservation,
                         ServiceHealth, Usage, User, Wallet, WebhookEvent)
from core.templatetags.console import cents_usd, exact_amount, net_cents, usd, usd_signed
from core.tests.test_security import SyntheticFixture

ISOLATED = dict(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False,
                STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                          'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})


class ExactMoneyRendering(TestCase):
    """Money is DecimalField(max_digits=24, decimal_places=12). Two renderings misreported it."""

    def test_floatformat_six_hides_a_real_balance_and_inflates_another(self):
        """The defect, asserted so the fix cannot be quietly reverted.

        These are the two directions that matter for money: a balance that exists shown as
        nothing, and a balance shown as MORE than the account holds.
        """
        self.assertEqual(floatformat(Decimal('0.000000499999'), 6), '0.000000')
        self.assertEqual(floatformat(Decimal('0.000000999999'), 6), '0.000001')
        self.assertGreater(Decimal(floatformat(Decimal('0.000000999999'), 6)), Decimal('0.000000999999'))

    def test_exact_amount_never_rounds_and_round_trips(self):
        for stored in ['0.000000499999', '0.000000999999', '0.000123456789', '10.000000000000',
                       '0E-12', '0', '1234.5', '-3.5', '0.0000005']:
            with self.subTest(stored=stored):
                rendered = exact_amount(Decimal(stored))
                self.assertEqual(Decimal(rendered), Decimal(stored))
                self.assertNotIn('E', rendered.upper())
                self.assertGreaterEqual(len(rendered.split('.')[1]), 2)

    def test_currency_sign_placement_and_absent_values(self):
        self.assertEqual(usd(Decimal('-3.5')), '-$3.50')
        self.assertEqual(usd(Decimal('0E-12')), '$0.00')
        self.assertEqual(usd_signed(Decimal('0.25')), '+$0.25')
        self.assertEqual(usd_signed(Decimal('-0.25')), '-$0.25')
        self.assertEqual(cents_usd(2500), '$25.00')
        # An absent figure reads as an em dash, never as $0 — a sum over an empty match set is
        # not the number zero.
        for empty in (None, '', 'not a number'):
            self.assertEqual(usd(empty), '—')

    def test_net_cents_subtracts_succeeded_refunds(self):
        payment = type('P', (), {'amount_cents': 2500, 'pk': 'x'})()
        self.assertEqual(net_cents(payment, {'x': 500}), 2000)
        self.assertEqual(net_cents(payment, {}), 2500)
        self.assertEqual(net_cents(payment, None), 2500)


@override_settings(**ISOLATED)
class ConsoleFixture(SyntheticFixture, TestCase):
    client_class = SurfaceClient
    def setUp(self):
        self.scope = self.make_scope('console')
        self.user, self.org, self.department, self.patient, self.template, self.encounter, _ = self.scope
        self.admin = User.objects.create_user(username='console-admin', email='console-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        self.device = TOTPDevice.objects.create(user=self.admin, name='Synthetic authenticator', confirmed=True)
        self.job = Job.objects.create(encounter=self.encounter, user=self.user, request_key='console:settled',
                                      config={'pricing_version': 'console-v1'})
        reserve(self.job, Decimal('1'))
        self.usage = settle(self.job, Decimal('0.2'), {'input_tokens': 100}, {'input_per_million': '2000'},
                            'anthropic:console-fixture', 'req_console_fixture', False)
        self.job.state = 'succeeded'
        self.job.started_at = timezone.now() - timedelta(minutes=1)
        self.job.finished_at = timezone.now()
        self.job.save(update_fields=['state', 'started_at', 'finished_at'])
        # ⚠️ EVERY DASHBOARD LIST NEEDS AT LEAST ONE ROW, or a test that asserts a filter emptied
        # a list passes on a list that was empty to begin with. Five of the eleven had nothing in
        # this fixture, and the narrowing test's positive control is what surfaced it.
        ProviderReceipt.objects.create(job=self.job, provider=self.usage.provider,
                                       provider_request_id=self.usage.provider_request_id,
                                       actual_cost=self.usage.actual_cost, units=self.usage.units,
                                       rates=self.usage.rates, simulated=False)
        PlatformCost.objects.create(kind='fixed_overhead', amount=Decimal('12'),
                                    description='Fixture overhead', recorded_by=self.admin)
        self.payment = Payment.objects.create(user=self.user, wallet=Wallet.objects.get(user=self.user, kind='paid'),
                                              amount_cents=2500, status='paid',
                                              stripe_session='cs_test_fixture', stripe_intent='pi_test_fixture')
        Refund.objects.create(payment=self.payment, stripe_refund='re_test_fixture',
                              amount_cents=500, status='succeeded')
        WebhookEvent.objects.create(event_id='evt_test_fixture', kind='checkout.session.completed',
                                    payload_hash='0' * 64, status='processed')

    def sign_in(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['otp_device_id'] = self.device.persistent_id
        session.save()

    def window(self, **params):
        request = type('R', (), {'GET': params})()
        return admin_console.date_window(request)


class ReconciliationEvidenceChoices(ConsoleFixture):
    """The evidence-type control offered only one of its two real options."""

    def test_every_form_choice_is_reachable_in_the_rendered_select(self):
        """A malformed closing tag ate the 'provider_report' option.

        The template hand-wrote `</option value="provider_report">` — a CLOSING tag with an
        attribute — so an HTML parser emitted only '' and 'invoice'. The form accepted
        'provider_report', the screen could not offer it, and an administrator recording a
        provider COST REPORT had one selectable value: 'Provider invoice'. The distinction the
        surrounding prose insists on ("an open-period report is not an invoice") was destroyed by
        a typo, and it is the distinction `invoice_reconciled` is computed from.
        """
        self.sign_in()
        body = self.client.get('/console/').content.decode()
        self.assertIn('value="provider_report"', body)
        self.assertNotIn('</option value=', body)
        from core.forms import ReconciliationForm
        for value, _ in ReconciliationForm().fields['evidence_kind'].choices:
            self.assertIn(f'value="{value}"', body)

    def test_recording_a_provider_report_keeps_it_out_of_invoice_reconciled(self):
        self.sign_in()
        response = self.client.post(f'/console/usage/{self.usage.pk}/reconcile/', {
            'evidence_kind': 'provider_report', 'reconciled_cost': '0.15',
            'evidence_reference': 'monthly-export-2026-09'})
        self.assertEqual(response.status_code, 302)
        row = Usage.objects.get(pk=self.usage.pk).reconciliation
        self.assertEqual(row.evidence_kind, 'provider_report')
        self.assertFalse(row.invoice_reconciled)
        self.assertTrue(row.provider_evidence_reconciled)


class AccountAndPermissionAccuracy(ConsoleFixture):
    def test_an_unverified_account_is_not_shown_as_active(self):
        """An unverified account cannot sign in at all and was badged green 'Active'."""
        pending = User.objects.create_user(username='pending', email='pending@synthetic.invalid')
        self.assertIsNone(pending.verified_at)
        self.sign_in()
        body = self.client.get('/console/', {'q': 'pending@synthetic.invalid'}).content.decode()
        self.assertIn('Unverified', body)
        self.assertIn('cannot sign in', body)

    def test_permissions_effective_access_follows_the_account_not_the_membership_flag(self):
        """The Status column read 'Active' for a membership the console itself had just revoked."""
        self.sign_in()
        self.client.post(f'/console/accounts/{self.user.pk}/', {})  # unchecked box = suspend
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(Membership.objects.get(user=self.user).active)
        body = self.client.get('/console/', {'q': self.user.email}).content.decode()
        self.assertIn('No access &mdash; account suspended', body)

    def test_a_refunded_payment_does_not_keep_reading_as_paid_for_its_full_amount(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        payment = Payment.objects.create(user=self.user, wallet=wallet, amount_cents=2500,
                                         stripe_session='cs_test_console', status='paid',
                                         stripe_intent='pi_test_console')
        Refund.objects.create(payment=payment, stripe_refund='re_test_console', amount_cents=500,
                              status='succeeded')
        self.sign_in()
        body = self.client.get('/console/', {'q': 'cs_test_console'}).content.decode()
        self.assertIn('refunded', body)
        self.assertIn('$25.00', body)   # gross, in dollars, not '2500 ¢'
        self.assertIn('$5.00', body)    # refunded
        self.assertIn('$20.00', body)   # net


class BusinessOverviewArithmetic(ConsoleFixture):
    def test_each_tile_equals_an_independently_computed_sum(self):
        overview = admin_console.business_overview(self.window())
        flow = {tile['label']: tile['amount'] for tile in overview['flow']}
        charged = -(LedgerEntry.objects.filter(kind__in=admin_console.WORK_KINDS, wallet__kind='promo')
                    .aggregate(t=admin_console.models.Sum('amount'))['t'] or Decimal('0'))
        self.assertEqual(flow['Charged — promotional credit'], charged)
        self.assertEqual(flow['Provider cost (configured estimate)'],
                         Usage.objects.aggregate(t=admin_console.models.Sum('actual_cost'))['t'])
        self.assertEqual(overview['difference']['amount'],
                         flow['Charged — paid balances'] + flow['Charged — promotional credit']
                         - flow['Provider cost (configured estimate)'])

    def test_the_overview_counts_a_reconciliation_the_old_charge_total_could_not(self):
        """`Sum(charged_cost)` is the charge at SETTLEMENT. Later movements live in the ledger."""
        before = admin_console.business_overview(self.window())
        charged_before = sum(t['amount'] for t in before['flow'] if t['label'].startswith('Charged'))
        reconcile_usage(self.usage, Decimal('0.05'), 'console-invoice', self.admin, evidence_kind='invoice')
        after = admin_console.business_overview(self.window())
        charged_after = sum(t['amount'] for t in after['flow'] if t['label'].startswith('Charged'))
        self.assertLess(charged_after, charged_before)
        # The settlement-time column is unmoved, which is exactly why it cannot stand alone.
        self.assertEqual(Usage.objects.get(pk=self.usage.pk).charged_cost,
                         self.usage.charged_cost)

    def test_a_date_window_narrows_flow_and_never_narrows_a_balance(self):
        future = (timezone.now() + timedelta(days=2)).date().isoformat()
        narrowed = admin_console.business_overview(self.window(**{'from': future}))
        self.assertEqual(narrowed['flow'][0]['amount'], Decimal('0'))
        # A balance is a fact about this instant; a date range cannot bound it without lying.
        wide = admin_console.business_overview(self.window())
        self.assertEqual([t['amount'] for t in narrowed['position']],
                         [t['amount'] for t in wide['position']])

    def test_an_unreadable_date_is_reported_and_narrows_nothing(self):
        """Including when only ONE bound is unreadable — the case that used to narrow anyway.

        The first version abandoned only the bad bound, so `?from=2026-09-21&to=21/09/2026`
        narrowed every figure to 2026-09-21 onwards AND printed 'these figures cover every
        record' beneath a heading naming that window. Both halves were rendered together.
        """
        for params in [{'from': 'last-tuesday'},
                       {'to': '21/09/2026'},
                       {'from': timezone.now().date().isoformat(), 'to': '21/09/2026'},
                       {'from': 'nonsense', 'to': timezone.now().date().isoformat()}]:
            with self.subTest(**params):
                window = self.window(**params)
                self.assertFalse(window['filters'], f'{params} narrowed despite an unreadable bound')
                self.assertFalse(window['active'])
                self.assertIn('YYYY-MM-DD', window['problem'])
                self.assertIn('cover every record', window['problem'])
                self.assertEqual(window['label'], 'every record (no date window)')

    def test_an_inverted_range_is_refused_rather_than_silently_returning_nothing(self):
        window = self.window(**{'from': '2026-09-10', 'to': '2026-09-01'})
        self.assertFalse(window['filters'])
        self.assertIn('before the start date', window['problem'])

    def test_the_window_is_inclusive_of_both_named_days(self):
        today = timezone.now().date().isoformat()
        window = self.window(**{'from': today, 'to': today})
        self.assertTrue(window['filters'])
        overview = admin_console.business_overview(window)
        self.assertEqual(overview['flow'][1]['amount'],
                         -(LedgerEntry.objects.filter(kind__in=admin_console.WORK_KINDS, wallet__kind='promo')
                           .aggregate(t=admin_console.models.Sum('amount'))['t'] or Decimal('0')))


class DatedRequestsReachEveryList(ConsoleFixture):
    """The window is applied to eleven querysets. Not all of them have the same date column.

    ⚠️ THIS EXISTS BECAUSE THE FIRST VERSION 500ed AND NOTHING CAUGHT IT. The window was exercised
    through `business_overview()` and through the audit view, and neither touches `User` — which
    extends `AbstractUser` and carries `date_joined`, not `created_at`. `User.objects.filter(
    created_at__gte=...)` raises FieldError, so every dated dashboard request was a 500. The code
    even carried a comment asserting that all these models inherit `Entity`. They do not.
    """

    LISTS = ['users', 'memberships', 'jobs', 'usage', 'platform_costs', 'payments',
             'refunds', 'stripe_events', 'wallets', 'ledger', 'receipts']

    def test_a_dated_dashboard_request_succeeds_and_narrows_every_list(self):
        """⚠️ THIS TEST COUNTS ROWS. Its first version asserted only status 200, that the window
        was active, and that each context key existed — and a mutation making the narrowing a
        no-op for ten of the eleven lists left all three assertions passing while every list went
        back to showing every row under a heading announcing a date window. A test that cannot
        observe the behaviour it is named after is a false green of its own.
        """
        self.sign_in()
        future = (timezone.now() + timedelta(days=400)).date().isoformat()
        narrowed = self.client.get('/console/', {'from': future})
        self.assertEqual(narrowed.status_code, 200)
        self.assertTrue(narrowed.context['window']['active'])
        wide = self.client.get('/console/')
        for key in self.LISTS:
            with self.subTest(list=key):
                # Positive control first: without the window the list HAS rows, so the zero below
                # is the filter working rather than an empty fixture.
                self.assertGreater(len(wide.context[key]), 0, f'{key} is empty even unfiltered')
                self.assertEqual(len(narrowed.context[key]), 0,
                                 f'{key} still shows rows created before a window that starts in 400 days')

    def test_the_accounts_list_narrows_on_its_own_date_column(self):
        old_account = User.objects.create_user(username='old', email='old@synthetic.invalid',
                                               verified_at=timezone.now())
        User.objects.filter(pk=old_account.pk).update(date_joined=timezone.now() - timedelta(days=400))
        self.sign_in()
        today = timezone.now().date().isoformat()
        emails = {a.email for a in self.client.get('/console/', {'from': today}).context['users']}
        self.assertNotIn('old@synthetic.invalid', emails)
        self.assertIn(self.admin.email, emails)
        # Positive control: without the window the same account IS listed, so the absence above
        # is the filter working and not an empty page.
        self.assertIn('old@synthetic.invalid', {a.email for a in self.client.get('/console/').context['users']})

    def test_a_dated_request_to_every_console_route_succeeds(self):
        self.sign_in()
        today = timezone.now().date().isoformat()
        for path in ['/console/', '/console/audit/', '/console/usage.csv']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, {'from': today, 'to': today}).status_code, 200)


class ProcessingHealthHonesty(ConsoleFixture):
    def test_a_job_past_the_staleness_bound_reports_that_no_worker_has_run(self):
        """`mark_stale` runs only inside the worker loop, so an overdue job proves it has not run."""
        stuck = Job.objects.create(encounter=self.encounter, user=self.user, request_key='console:stuck',
                                   state='running', started_at=timezone.now() - admin_console.STALENESS_BOUND
                                   - timedelta(minutes=1))
        health = admin_console.processing_health()
        self.assertEqual(health['severity'], 'error')
        self.assertIn('No worker has run recently', health['verdict'])
        self.assertEqual(health['overdue'], 1)
        # Positive control: inside the bound the same row is NOT an error, so the signal is not
        # simply "any running job is a failure".
        stuck.started_at = timezone.now()
        stuck.save(update_fields=['started_at'])
        self.assertNotEqual(admin_console.processing_health()['severity'], 'error')

    def test_an_empty_queue_is_never_presented_as_evidence_that_a_worker_exists(self):
        Job.objects.filter(state__in=['queued', 'running']).delete()
        health = admin_console.processing_health()
        self.assertEqual(health['severity'], 'success')
        self.assertIn('not evidence that a worker exists', health['detail'])

    def test_a_queue_that_is_not_draining_is_an_error_even_with_nothing_running(self):
        Job.objects.create(encounter=self.encounter, user=self.user, request_key='console:queued',
                           state='queued')
        Job.objects.filter(state='queued').update(
            created_at=timezone.now() - admin_console.STALENESS_BOUND - timedelta(minutes=1))
        health = admin_console.processing_health()
        self.assertEqual(health['severity'], 'error')
        self.assertIn('not draining', health['verdict'])

    def test_funds_held_on_open_jobs_counts_only_held_reservations(self):
        """With a NEGATIVE control, so the `state='held'` predicate is observable.

        Without the released row below, deleting `state='held'` from the filter left this
        assertion passing: the fixture's only other reservation sits on a SUCCEEDED job, which
        the `job__state__in=UNRESOLVED_STATES` half already excludes. The predicate was inert.
        """
        held = Job.objects.create(encounter=self.encounter, user=self.user, request_key='console:held',
                                  state='reconciliation')
        reserve(held, Decimal('0.2'))
        released_job = Job.objects.create(encounter=self.encounter, user=self.user,
                                          request_key='console:released', state='queued')
        Reservation.objects.create(job=released_job, wallet=Wallet.objects.get(user=self.user, kind='promo'),
                                   amount=Decimal('99'), state='released')
        self.assertEqual(admin_console.processing_health()['funds_held_on_open_jobs'],
                         Decimal('0.2') * Decimal('1.5'))


class FindingsFromTheAdversarialPass(ConsoleFixture):
    """Each of these pins a defect the refutation pass demonstrated in this branch's own work."""

    def test_a_window_with_no_matching_platform_cost_states_the_scope_of_the_totals(self):
        """M1 — the totals and the table beside them have different scopes, and it must say so.

        The three platform-cost totals are deliberately unwindowed, classified with the balances
        rather than the flow figures. The table beneath them IS windowed. Filtering to a day with
        no platform costs therefore put $156.498 of total immediately above 'No platform costs
        match these filters', with nothing on that section explaining the difference.
        """
        from core.models import PlatformCost
        PlatformCost.objects.create(kind='fixed_overhead', amount=Decimal('149'),
                                    description='hosting', recorded_by=self.admin)
        self.sign_in()
        future = (timezone.now() + timedelta(days=400)).date().isoformat()
        body = self.client.get('/console/', {'from': future}).content.decode()
        self.assertIn('the three totals cover every record, always', body)
        self.assertIn('No platform costs match these filters', body)

    def test_the_platform_totals_are_scope_independent_and_stay_that_way(self):
        """Nothing pinned this in either direction, so a refactor could silently flip it."""
        from core.models import PlatformCost
        PlatformCost.objects.create(kind='fixed_overhead', amount=Decimal('149'),
                                    description='hosting', recorded_by=self.admin)
        self.sign_in()
        future = (timezone.now() + timedelta(days=400)).date().isoformat()
        everything = (PlatformCost.objects.filter(kind='fixed_overhead')
                      .aggregate(t=admin_console.models.Sum('amount'))['t'])
        self.assertGreater(everything, 0)   # the assertion below would hold vacuously at zero
        for params in ({}, {'from': future}):
            with self.subTest(**params):
                totals = self.client.get('/console/', params).context['platform_totals']
                self.assertEqual(totals['Fixed overhead'], everything)
        # And the LIST beside them IS narrowed, which is the difference the caption now discloses.
        self.assertEqual(len(self.client.get('/console/', {'from': future}).context['platform_costs']), 0)

    def test_the_overview_does_not_also_hand_the_page_a_windowed_copy(self):
        """Two versions of the same money in one context is how the next reader picks the wrong one."""
        self.assertNotIn('platform_by_kind', admin_console.business_overview(self.window()))

    def test_a_window_where_every_recorded_send_failed_is_an_error_not_an_absence(self):
        """FG-1 — the old else-branch called five recorded failures 'No delivery recorded'."""
        for index in range(5):
            AuditEvent.objects.create(action='email.failed', target=f'probe-{index}')
        # `at` two days on, so the failures are real and recorded but outside the 24-hour probe.
        status = admin_console.email_delivery(at=timezone.now() + timedelta(days=2))
        self.assertEqual(status['severity'], 'error')
        self.assertIn('Every recorded send in this window failed', status['status'])
        self.assertNotIn('No delivery recorded', status['status'])
        # Positive control: a window that contains none of those rows IS an absence, and says so.
        # (AuditEvent is append-only at the database level, so the control cannot delete them.)
        empty = self.window(**{'from': (timezone.now() + timedelta(days=400)).date().isoformat()})
        self.assertEqual(admin_console.email_delivery(window=empty, at=timezone.now() + timedelta(days=2))['status'],
                         'No delivery recorded in this window')

    def test_a_partially_failing_window_is_neither_healthy_nor_an_outage(self):
        AuditEvent.objects.create(action='email.accepted', target='ok')
        AuditEvent.objects.create(action='email.failed', target='bad')
        status = admin_console.email_delivery(at=timezone.now() + timedelta(days=2))
        self.assertEqual(status['severity'], 'warning')
        self.assertIn('1 delivered, 1 failed', status['status'])

    def test_the_queue_is_not_called_stalled_while_something_is_running(self):
        """FR-2 — the panel asserted 'nothing is running' beside a strip reading Running = 1."""
        old_queued = Job.objects.create(encounter=self.encounter, user=self.user,
                                        request_key='console:oldq', state='queued')
        Job.objects.filter(pk=old_queued.pk).update(
            created_at=timezone.now() - admin_console.STALENESS_BOUND - timedelta(minutes=5))
        Job.objects.create(encounter=self.encounter, user=self.user, request_key='console:fresh-run',
                           state='running', started_at=timezone.now())
        health = admin_console.processing_health()
        self.assertEqual(health['running'], 1)
        self.assertNotIn('nothing is running', health['detail'])
        self.assertNotEqual(health['verdict'], 'Queue is not draining')
        # Positive control: with the running job gone, the same queue IS stalled.
        Job.objects.filter(request_key='console:fresh-run').delete()
        stalled = admin_console.processing_health()
        self.assertEqual(stalled['verdict'], 'Queue is not draining')
        self.assertEqual(stalled['severity'], 'error')

    def test_a_negative_amount_in_cents_keeps_the_sign_outside_the_symbol(self):
        """M4 — cents_usd bypassed usd() and rendered '$-5.00' where usd() gives '-$5.00'."""
        self.assertEqual(cents_usd(-500), '-$5.00')
        self.assertEqual(cents_usd(-500), usd(Decimal('-5')))

    def test_the_export_carries_the_absorbed_reversal_so_the_file_reconciles(self):
        """M3 — a wholly reversed charge exported as a charge that stands.

        `charged_cost` is the settlement-time figure; the reversal lives in the ledger. Without
        the column an accountant reading the file alone bills money QuillMD already gave back.
        """
        from core.billing import absorb_failed_job
        self.job.state = 'failed'
        self.job.error = 'Provider returned an unusable document.'
        self.job.save(update_fields=['state', 'error'])
        absorb_failed_job(self.job, actor=self.admin, note='console test absorption')
        self.sign_in()
        body = b''.join(self.client.get('/console/usage.csv').streaming_content).decode()
        rows = [line.split(',') for line in body.strip().split('\r\n')]
        self.assertEqual(rows[0][-1], 'absorbed_reversal')
        columns = dict(zip(rows[0], rows[1]))
        reversal = Decimal(columns['absorbed_reversal'])
        self.assertEqual(reversal, self.usage.charged_cost)
        # The file's own columns now give the net, and it matches the ledger.
        net = (Decimal(columns['charged_cost'])
               + (Decimal(columns['charge_delta']) if columns['charge_delta'] else Decimal('0'))
               - reversal)
        self.assertEqual(net, Decimal('0'))
        self.assertEqual(net, -(LedgerEntry.objects.filter(job=self.job, kind__in=admin_console.WORK_KINDS)
                                .aggregate(t=admin_console.models.Sum('amount'))['t']))


class PublishedOperationsStatus(ConsoleFixture):
    """Absence of a measurement is reported as absence, never as health."""

    def publish(self, **overrides):
        values = dict(key='backup', condition='healthy', severity='healthy', healthy=True,
                      action='Nothing to do.', payload={'local_capture': {'stale': False}},
                      computed_at=timezone.now(), expected_interval_seconds=300)
        values.update(overrides)
        return ServiceHealth.objects.update_or_create(key=values.pop('key'), defaults=values)[0]

    def test_never_published_is_unknown_and_not_healthy(self):
        row = admin_console.published_operations()[0]
        self.assertFalse(row['published'])
        self.assertEqual(row['severity'], 'warning')
        self.assertEqual(row['status'], 'Never published')
        self.assertIn('has not run here', row['detail'])

    def test_a_fresh_row_carries_its_own_severity(self):
        self.publish(severity='failure', condition='offsite_transfer_failed', healthy=False)
        row = admin_console.published_operations()[0]
        self.assertTrue(row['published'])
        self.assertFalse(row['stale'])
        self.assertEqual(row['severity'], 'failure')
        self.assertEqual(row['status'], 'offsite_transfer_failed')

    def test_a_stale_healthy_row_is_downgraded_rather_than_believed(self):
        """The dangerous case: the last reading said healthy and the publisher then stopped."""
        self.publish(computed_at=timezone.now() - timedelta(seconds=1200), expected_interval_seconds=300)
        row = admin_console.published_operations()[0]
        self.assertTrue(row['stale'])
        self.assertEqual(row['severity'], 'warning')
        self.assertIn('STALE', row['status'])
        self.assertIn('describes the state at the time shown, not now', row['detail'])

    def test_a_row_from_the_future_is_treated_as_stale_not_as_fresh(self):
        self.publish(computed_at=timezone.now() + timedelta(hours=1))
        self.assertTrue(admin_console.published_operations()[0]['stale'])

    def test_a_dead_publisher_escalates_past_stale_to_failure(self):
        """⚠️ THE 2026-09-22 OUTAGE, AS A TEST. The publisher raised EROFS on every tick for
        six and a half hours — seventy-seven cadences — and the panel rendered `warning`, the
        same badge as one late publication. The age was in the text; the badge could not
        escalate, and a badge that cannot escalate is one people stop reading."""
        self.publish(condition='offsite_policy_renewal_due', severity='warning', healthy=False,
                     computed_at=timezone.now() - timedelta(seconds=23000),
                     expected_interval_seconds=300)
        row = admin_console.published_operations()[0]
        self.assertTrue(row['failed'])
        self.assertTrue(row['stale'], 'a failed row is still stale; failure is the stronger claim')
        self.assertEqual(row['severity'], 'failure')
        self.assertIn('FAILED', row['status'])
        self.assertIn('the publisher is not running', row['status'])
        self.assertIn('Inspect the unit and its journal', row['detail'])

    def test_the_escalation_boundary_holds_on_both_sides(self):
        """⚠️ THE POSITIVE CONTROL. Without it, a predicate that returned True unconditionally
        passes the test above and every stale row would render as a dead publisher."""
        cadence = 300
        just_stale = cadence * admin_console.FAILED_PUBLICATION_CADENCES - 60
        just_failed = cadence * admin_console.FAILED_PUBLICATION_CADENCES + 60
        self.publish(computed_at=timezone.now() - timedelta(seconds=just_stale),
                     expected_interval_seconds=cadence)
        row = admin_console.published_operations()[0]
        self.assertTrue(row['stale'])
        self.assertFalse(row['failed'], 'a merely stale row must not be reported as a dead publisher')
        self.assertEqual(row['severity'], 'warning')
        self.publish(computed_at=timezone.now() - timedelta(seconds=just_failed),
                     expected_interval_seconds=cadence)
        self.assertTrue(admin_console.published_operations()[0]['failed'])

    def test_a_fresh_row_is_neither_stale_nor_failed(self):
        self.publish()
        row = admin_console.published_operations()[0]
        self.assertFalse(row['stale'])
        self.assertFalse(row['failed'])

    def test_a_clock_that_moved_backwards_is_stale_but_not_a_dead_publisher(self):
        """A negative age is clock movement. Calling it a dead publisher would send somebody to
        read a journal that has nothing wrong in it."""
        self.publish(computed_at=timezone.now() + timedelta(hours=1))
        row = admin_console.published_operations()[0]
        self.assertTrue(row['stale'])
        self.assertFalse(row['failed'])

    def test_every_row_carries_the_failed_key_including_never_published(self):
        """A caller that reads row['failed'] must never meet a missing key on one branch only."""
        self.assertIsNone(admin_console.published_operations()[0]['failed'])
        self.publish()
        self.assertIs(admin_console.published_operations()[0]['failed'], False)

    def test_the_rendered_badge_says_failed_and_not_stale(self):
        """⚠️ THE ESCALATION MUST BE VISIBLE, NOT JUST STYLED.

        The template read `stale` whenever the row was stale — and a failed row IS stale, so a
        dead publisher rendered the escalated COLOUR under the word *stale*. A severity a reader
        cannot read is not a distinction, and the colour alone is exactly what people stop
        noticing. The class still comes from `severity`; only the word changed.
        """
        self.publish(computed_at=timezone.now() - timedelta(seconds=23000),
                     expected_interval_seconds=300)
        # ⚠️ `sign_in()`, not `force_login`: this console requires MFA, and a bare login is
        # REDIRECTED. The first version of this test skipped it and failed as
        # "'>failed<' not found in ''" — an empty body reported as a content mismatch, which
        # sends the reader looking at the template instead of at the authentication.
        self.sign_in()
        response = self.client.get('/console/services/')
        self.assertEqual(response.status_code, 200, 'the page must render before its text means anything')
        body = response.content.decode()
        self.assertIn('badge failure', body)
        self.assertIn('>failed<', body)

    def test_a_merely_stale_row_still_renders_the_word_stale(self):
        """⚠️ THE POSITIVE CONTROL. Without it a template that always printed `failed` would
        pass the test above and destroy the distinction it exists to make."""
        self.publish(computed_at=timezone.now() - timedelta(seconds=1200),
                     expected_interval_seconds=300)
        self.sign_in()
        response = self.client.get('/console/services/')
        self.assertEqual(response.status_code, 200, 'the page must render before its text means anything')
        body = response.content.decode()
        self.assertIn('>stale<', body)
        self.assertNotIn('>failed<', body)
        self.assertIn('badge warning', body)

    def test_the_publisher_copies_the_aggregator_and_refuses_an_unasserted_report(self):
        from core.management.commands import publish_operations_status as command
        report = {'condition': 'healthy', 'severity': 'healthy', 'healthy': True, 'action': 'Nothing to do.',
                  'clinical_content_included': False, 'local_capture': {'stale': False},
                  'secret_we_do_not_recognise': 'must not be copied'}
        with patch.object(command, 'collect', return_value=(report, 0)):
            command.Command().handle(dry_run=False, interval_seconds=300)
        row = ServiceHealth.objects.get(key='backup')
        self.assertEqual(row.condition, 'healthy')
        self.assertIn('local_capture', row.payload)
        # The payload is an ALLOWLIST: an unrecognised key is dropped, not published blind.
        self.assertNotIn('secret_we_do_not_recognise', row.payload)
        from django.core.management.base import CommandError
        with patch.object(command, 'collect', return_value=({**report, 'clinical_content_included': None}, 0)):
            with self.assertRaises(CommandError):
                command.Command().handle(dry_run=False, interval_seconds=300)

    def test_the_publisher_signals_an_unhealthy_state_through_its_exit_code(self):
        from core.management.commands import publish_operations_status as command
        report = {'condition': 'offsite_stale', 'severity': 'failure', 'healthy': False,
                  'action': 'Investigate.', 'clinical_content_included': False}
        with patch.object(command, 'collect', return_value=(report, 1)):
            with self.assertRaises(SystemExit):
                command.Command().handle(dry_run=False, interval_seconds=300)
        self.assertEqual(ServiceHealth.objects.get(key='backup').severity, 'failure')


class PublishedOperationsCarryTheirStaleness(SimpleTestCase):
    """⚠️ R3-2, round 3. The monitor's status() marks a report made while a check was running
    (`check_running`: it shows the last completed check) and one made from a state it could not read
    (`state_unreadable`, with the backup condition computed anyway). The publisher's allowlist dropped
    both, so the console never learned it was looking at a stale or unreadable state. No database:
    the publisher runs with --dry-run, which writes nothing, and the page is rendered directly."""

    MARKED = {'check_running': True, 'state_unreadable': 'state_invalid', 'backup_condition': 'backup_failed',
              'backup_severity': 'failure', 'next_state_notice_at': '2026-09-21T12:00:00+00:00',
              'last_state_notice_condition': 'healthy'}

    def test_the_publisher_carries_the_monitors_own_staleness(self):
        from core.management.commands import publish_operations_status as command
        report = {'condition': 'monitoring_state_unavailable', 'severity': 'failure', 'healthy': False,
                  'action': 'Inspect.', 'clinical_content_included': False, 'local_capture': {'stale': False},
                  'monitor_age_seconds': 60, **self.MARKED}
        output = io.StringIO()
        with patch.object(command, 'collect', return_value=(report, 1)):
            command.Command(stdout=output).publish(300, dry_run=True)
        payload = json.loads(output.getvalue())['payload']
        self.assertEqual({key: payload.get(key) for key in self.MARKED}, self.MARKED,
                         'the publisher dropped what says the report is stale or unreadable')
        # The existing keys keep their meaning.
        self.assertEqual((payload['local_capture'], payload['monitor_age_seconds']), ({'stale': False}, 60))

    def test_the_console_says_when_it_shows_a_stale_or_unreadable_monitor_state(self):
        def page(payload):
            row = {'key': 'backup', 'name': 'Backup and recovery', 'published': True, 'severity': 'failure',
                   'status': 'monitoring_state_unavailable', 'detail': 'Inspect.', 'computed_at': None,
                   'age_seconds': 30, 'stale': False, 'failed': False, 'payload': payload}
            with override_settings(STORAGES=ISOLATED['STORAGES']):
                return render_to_string('admin_services.html', {
                    'published': [row], 'processing': {}, 'email': {}, 'configuration': {}, 'is_admin_site': True,
                    'user': SimpleNamespace(email='operator@synthetic.invalid', username='operator')})
        body = page(self.MARKED)
        for text in ('A monitor check was running', 'the last completed check',
                     'could not read its own state', 'state_invalid', 'Backup condition now: backup_failed (failure)',
                     'Next restart notice no earlier than 2026-09-21T12:00:00+00:00'):
            self.assertTrue(text in body, f'the page does not say: {text}')
        quiet = page({'check_running': False})
        for text in ('A monitor check was running', 'could not read its own state'):
            self.assertFalse(text in quiet, f'the positive control: an ordinary row says neither ({text})')


class SecondRoundFindings(ConsoleFixture):
    """The refutation pass ran twice. These pin what the second round demonstrated."""

    def test_an_unverified_owner_does_not_satisfy_the_last_owner_guard(self):
        """F2 — the guard counted an account that cannot exercise the role.

        `core.security.membership` requires an active membership AND an enabled AND verified
        account, so a department whose only remaining owner is unverified has no usable owner at
        all — and the guard let the demotion through.
        """
        owner = Membership.objects.get(user=self.user)
        owner.role = 'owner'
        owner.save(update_fields=['role'])
        unverified = User.objects.create_user(username='unverified-owner',
                                              email='unverified-owner@synthetic.invalid')
        self.assertIsNone(unverified.verified_at)
        Membership.objects.create(user=unverified, department=self.department, role='owner')
        self.sign_in()
        response = self.client.post(f'/console/memberships/{owner.pk}/', {'role': 'employee', 'active': 'on'})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'last active owner', response.content)
        owner.refresh_from_db()
        self.assertEqual(owner.role, 'owner')
        # Positive control: once that owner IS verified, the demotion is allowed.
        unverified.verified_at = timezone.now()
        unverified.save(update_fields=['verified_at'])
        self.assertEqual(self.client.post(f'/console/memberships/{owner.pk}/',
                                          {'role': 'employee', 'active': 'on'}).status_code, 302)

    def test_suspending_the_last_owner_is_allowed_and_announced(self):
        """L2 — the invariant is about the membership SCREEN, not about the product.

        A security suspension must never be refused because of organization structure, so this
        is deliberately permitted. What was wrong was claiming it could not happen; the console
        now says plainly what the suspension did.
        """
        owner = Membership.objects.get(user=self.user)
        owner.role = 'owner'
        owner.save(update_fields=['role'])
        self.sign_in()
        response = self.client.post(f'/console/accounts/{self.user.pk}/', {}, follow=True)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIn('now has no active, verified owner',
                      ' '.join(str(m) for m in response.context['messages']))

    def test_the_invitation_revoke_record_carries_no_recipient_address(self):
        """F3 — the house rule is that audit records hold no recipient."""
        from core.security import digest, token
        invitation = Invitation.objects.create(email='someone@synthetic.invalid', department=self.department,
                                               role='clinician', token_hash=digest(token()),
                                               expires_at=timezone.now() + timedelta(days=7),
                                               invited_by=self.user)
        self.sign_in()
        self.client.post(f'/console/invitations/{invitation.pk}/revoke/', {})
        event = AuditEvent.objects.get(action='admin.invitation_revoked')
        self.assertNotIn('someone@synthetic.invalid', str(event.details))
        self.assertEqual(event.target, str(invitation.pk))

    def test_an_over_long_date_is_unreadable_rather_than_silently_truncated(self):
        """L3 — '2026-09-2199' became a valid '2026-09-21' and narrowed everything, silently."""
        for raw in ['2026-09-2199', '2026-09-21T00:00:00Z', '2026-09-21 and more']:
            with self.subTest(raw=raw):
                window = self.window(**{'from': raw})
                self.assertFalse(window['filters'], f'{raw!r} narrowed the page')
                self.assertIn('YYYY-MM-DD', window['problem'])

    def test_a_nul_byte_in_a_console_parameter_is_refused_not_a_500(self):
        """F4 — psycopg raises DataError out of the view for a NUL in a text column."""
        self.sign_in()
        for path, params in [('/console/audit/', {'action': '\x00'}),
                             ('/console/usage.csv', {'q': '\x00'}),
                             ('/console/', {'q': '\x00', 'from': '\x00'})]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, params).status_code, 200)

    def test_the_organizations_page_query_count_does_not_grow_with_the_tree(self):
        """L1 — the first version issued 3 + 2·organizations + 2·departments queries."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from core.models import Organization
        self.sign_in()
        with CaptureQueriesContext(connection) as small:
            self.client.get('/console/organizations/')
        for index in range(12):
            organization = Organization.objects.create(name=f'Synthetic scale {index:02d}')
            for sub in range(4):
                Department.objects.create(organization=organization, name=f'Dept {sub}')
        with CaptureQueriesContext(connection) as large:
            response = self.client.get('/console/organizations/')
        self.assertEqual(response.status_code, 200)
        # Positive control: the fixture really did grow.
        self.assertGreater(Organization.objects.count(), 12)
        self.assertLessEqual(len(large), len(small) + 2,
                             f'query count grew from {len(small)} to {len(large)} with the tree')


class StuckJobRecoverySemantics(ConsoleFixture):
    """What actually recovers a stuck job, measured — instead of adding a force-complete control.

    The deferred gap was "no retry or requeue". The question underneath it is whether automatic
    recovery is demonstrated, because a control that force-completes a job whose provider outcome
    is unknown can release or absorb money for a request that is still in flight. These tests
    establish the real semantics so the console can describe them accurately.
    """

    def stale(self, minutes):
        job = Job.objects.create(encounter=self.encounter, user=self.user,
                                 request_key=f'stale:{minutes}', state='running',
                                 started_at=timezone.now() - timedelta(minutes=minutes))
        reserve(job, Decimal('0.2'))
        return job

    def test_the_reaper_moves_a_stale_job_to_reconciliation_and_keeps_the_money_held(self):
        """`mark_stale` is the only automatic recovery, and it deliberately does NOT free funds."""
        from core.jobs import mark_stale
        job = self.stale(minutes=10)
        held_before = Reservation.objects.filter(job=job, state='held').count()
        self.assertEqual(held_before, 1)
        mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, 'reconciliation')
        self.assertIn('unknown provider outcome', job.error)
        self.assertIn('Automatic retry is disabled', job.error)
        # ⚠️ THE RESERVATION SURVIVES. An unknown outcome is not a refund and not a charge; the
        # money stays held until a human resolves it with evidence. That is why there is no
        # force-complete button.
        self.assertEqual(Reservation.objects.filter(job=job, state='held').count(), 1)
        self.assertFalse(Usage.objects.filter(job=job).exists())

    def test_the_reaper_leaves_a_job_inside_the_bound_alone(self):
        """The positive control: a reaper that fired on everything would pass the test above."""
        from core.jobs import mark_stale
        job = self.stale(minutes=1)
        mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, 'running')

    def test_nothing_outside_the_worker_loop_calls_the_reaper(self):
        """Which is exactly why a dead worker leaves jobs running and the console must say so."""
        import subprocess
        hits = subprocess.run(['grep', '-rn', 'mark_stale', '--include=*.py', '.'],
                              capture_output=True, text=True, cwd='.').stdout
        callers = [line for line in hits.splitlines()
                   if 'mark_stale()' in line and '/tests/' not in line and 'def mark_stale' not in line]
        self.assertEqual(len(callers), 1, f'expected exactly one production caller, got: {callers}')
        self.assertIn('management/commands/worker.py', callers[0])

    def test_the_console_reports_the_escalation_rather_than_offering_a_force_control(self):
        self.stale(minutes=10)
        health = admin_console.processing_health()
        self.assertEqual(health['severity'], 'error')
        self.assertIn('reaper', health['detail'])
        self.assertIn('funds stay reserved', health['detail'].lower())
        self.sign_in()
        body = self.client.get('/console/services/').content.decode()
        self.assertNotIn('Force complete', body)
        self.assertNotIn('Retry job', body)


class LanguageModelOnTheServicesPage(ConsoleFixture):
    """S5-R3. The browser is read as the full configuration status, so the model, its rates, the request profile —
    including INVALID, which refuses every generation — and the pricing_version must be ON the page, not only in the
    terminal. Rendered through the real view, signed in with MFA."""

    def test_the_page_names_the_model_profile_and_pricing_version_including_invalid(self):
        import os
        from core import generation
        from core.tests.test_sonnet5_profile import PRICE_ENV, SONNET_5
        self.sign_in()
        for label, overrides, expected in (
                ('valid', SONNET_5, 'explicit {'),
                ('invalid', dict(SONNET_5, AI_EFFORT='max'),
                 'INVALID — every generation is refused before any request: QUILLMD_AI_EFFORT must be one of: '
                 'low, medium, high.')):
            with self.subTest(profile=label), override_settings(**overrides), patch.dict(os.environ, PRICE_ENV):
                response = self.client.get('/console/services/')
                self.assertEqual(response.status_code, 200, 'the page must render before its text means anything')
                body = response.content.decode()
                version = generation.configuration()['pricing_version']
                self.assertIn('id="language-model"', body)
                self.assertIn('>QUILLMD_AI_MODEL<', body)
                self.assertIn('claude-sonnet-5', body)
                self.assertIn('>QUILLMD_AI_OUTPUT_RATE<', body)
                self.assertIn(expected, body)
                self.assertIn(version, body)


    def test_the_profile_row_renders_its_severity_badge(self):
        """R2-4. The template's badge was never asserted: removing it survived the suite."""
        import os
        from core.tests.test_sonnet5_profile import PRICE_ENV, SONNET_46, SONNET_5
        self.sign_in()
        for overrides, severity, text in ((SONNET_46, 'success', 'legacy (the pre-profile request, unchanged)'),
                                          (dict(SONNET_46, AI_INFERENCE_GEO='us'), 'warning', 'NOT the pre-profile request'),
                                          (dict(SONNET_5, AI_EFFORT='max'), 'error', 'INVALID — every generation')):
            with self.subTest(severity=severity), override_settings(**overrides), patch.dict(os.environ, PRICE_ENV):
                response = self.client.get('/console/services/')
                self.assertEqual(response.status_code, 200, 'the page must render before its text means anything')
                self.assertIn(f'<span class="badge {severity}">{severity}</span> {text}', response.content.decode())


class ConsoleAccessControl(ConsoleFixture):
    ROUTES = ['/console/', '/console/audit/', '/console/organizations/', '/console/services/',
              '/console/usage.csv']

    def test_held_mapping_job_without_encounter_renders_its_requester_and_preserves_money(self):
        """Mapping requests have a template scope, not an encounter or encounter author."""
        from core.models import CostReconciliation
        version = self.encounter.template_version
        mapping = Job.objects.create(mapping_version=version, user=self.user, kind='mapping',
            state='reconciliation', request_key='console:held-mapping-without-encounter',
            config={'mode': 'fixture', 'source_sha256': self.template.sha256,
                    'department_id': str(self.department.pk), 'mapping_version_id': str(version.pk)})
        reserve(mapping, charge_limit=Decimal('.13'))
        self.assertIsNone(mapping.encounter_id)
        self.assertEqual(Reservation.objects.get(job=mapping).state, 'held')
        financial = [Job, Wallet, Reservation, Usage, LedgerEntry, ProviderReceipt,
                     Payment, PlatformCost, CostReconciliation]
        before = {model.__name__: list(model.objects.order_by('pk').values()) for model in financial}
        self.sign_in()
        response = self.client.get('/console/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(mapping.pk))
        self.assertContains(response, self.user.email)
        self.assertEqual(before,
            {model.__name__: list(model.objects.order_by('pk').values()) for model in financial})

    def test_every_console_route_answers_an_mfa_administrator(self):
        """A smoke test over every route, because one of these shipped as a 500 during authoring.

        `audit()` takes `action` positionally; a detail named `action` collided with it and the
        audit page raised TypeError. Nothing but a request to each route catches that class.
        """
        self.sign_in()
        for path in self.ROUTES + [f'/console/accounts/{self.user.pk}/detail/',
                                   f'/console/jobs/{self.job.pk}/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_a_clinical_user_cannot_reach_any_of_them(self):
        self.client.force_login(self.user)
        for path in self.ROUTES + [f'/console/accounts/{self.user.pk}/detail/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_staff_without_mfa_is_redirected_and_the_view_itself_refuses(self):
        self.client.force_login(self.admin)   # no otp_device_id in the session
        for path in self.ROUTES:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, '/mfa/')
        # And independently of the middleware, so a route mounted elsewhere is still closed.
        from django.http import Http404
        from core.admin_views import gate
        unverified = User.objects.get(pk=self.admin.pk)
        unverified.is_verified = lambda: False       # what OTPMiddleware attaches, saying 'no'
        with self.assertRaises(Http404):
            gate(type('R', (), {'user': unverified})())
        clinical = User.objects.get(pk=self.user.pk)
        clinical.is_verified = lambda: True
        with self.assertRaises(Http404):
            gate(type('R', (), {'user': clinical})())

    def test_console_writes_require_csrf(self):
        client = SurfaceClient(enforce_csrf_checks=True)
        client.force_login(self.admin)
        session = client.session
        session['otp_device_id'] = self.device.persistent_id
        session.save()
        membership = Membership.objects.get(user=self.user)
        for path in [f'/console/accounts/{self.user.pk}/sessions/',
                     f'/console/memberships/{membership.pk}/',
                     f'/console/departments/{self.department.pk}/payer/']:
            with self.subTest(path=path):
                self.assertEqual(client.post(path, {}).status_code, 403)


class MembershipAndPayerInvariants(ConsoleFixture):
    def test_the_last_active_owner_of_a_department_cannot_be_removed(self):
        owner = Membership.objects.get(user=self.user)
        owner.role = 'owner'
        owner.save(update_fields=['role'])
        self.sign_in()
        response = self.client.post(f'/console/memberships/{owner.pk}/', {'role': 'employee', 'active': 'on'})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'last active owner', response.content)
        owner.refresh_from_db()
        self.assertEqual(owner.role, 'owner')

    def test_a_second_owner_makes_the_demotion_legal(self):
        owner = Membership.objects.get(user=self.user)
        owner.role = 'owner'
        owner.save(update_fields=['role'])
        second = User.objects.create_user(username='second', email='second@synthetic.invalid',
                                          verified_at=timezone.now())
        Membership.objects.create(user=second, department=self.department, role='owner')
        self.sign_in()
        self.assertEqual(self.client.post(f'/console/memberships/{owner.pk}/',
                                          {'role': 'employee', 'active': 'on'}).status_code, 302)
        owner.refresh_from_db()
        self.assertEqual(owner.role, 'employee')
        self.assertTrue(AuditEvent.objects.filter(action='admin.membership_update', target=str(owner.pk)).exists())

    def test_an_administrator_membership_is_not_editable_here(self):
        staff_membership = Membership.objects.create(user=self.admin, department=self.department, role='employee')
        self.sign_in()
        self.assertEqual(self.client.post(f'/console/memberships/{staff_membership.pk}/',
                                          {'role': 'owner', 'active': 'on'}).status_code, 403)
        staff_membership.refresh_from_db()
        self.assertEqual(staff_membership.role, 'employee')

    def test_an_ordinary_administrator_cannot_change_who_pays(self):
        """Who is billed is reserved for a platform owner / billing role this deployment has not
        established, so the control is read-only — and the refusal is enforced on the SERVER.

        A control merely absent from the template is not an authorization boundary: the route is
        what an ordinary administrator can reach. `is_superuser` confers nothing anywhere in this
        codebase and production carries zero superusers, so granting this to `is_staff` would
        hand it to exactly the population the restriction excludes.
        """
        self.sign_in()
        was = self.department.organization_pays
        response = self.client.post(f'/console/departments/{self.department.pk}/payer/',
                                    {'organization_pays': 'on', 'reason': 'trying it on anyway',
                                     'confirm': 'on'})
        self.assertEqual(response.status_code, 403)
        self.department.refresh_from_db()
        self.assertEqual(self.department.organization_pays, was)
        self.assertFalse(AuditEvent.objects.filter(action='admin.department_payer').exists())
        # And the screen says so rather than silently omitting the control.
        body = self.client.get('/console/organizations/').content.decode()
        self.assertIn('Who pays is read-only here', body)
        self.assertIn('has not established one', body)

    def test_the_payer_control_refuses_without_a_reason_or_confirmation(self):
        with self.granted():
            self.sign_in()
            for payload in [{'organization_pays': 'on', 'confirm': 'on'},
                            {'organization_pays': 'on', 'reason': 'too short', 'confirm': 'on'},
                            {'organization_pays': 'on', 'reason': 'a sufficiently long reason'}]:
                with self.subTest(payload=sorted(payload)):
                    self.assertEqual(self.client.post(
                        f'/console/departments/{self.department.pk}/payer/', payload).status_code, 400)
            self.department.refresh_from_db()
            self.assertFalse(self.department.organization_pays)

    def granted(self):
        """Grant the capability the way a deployment would: the flag AND the highest flag there is."""
        User.objects.filter(pk=self.admin.pk).update(is_superuser=True)
        self.admin.refresh_from_db()
        return override_settings(QUILLMD_PAYER_ROLE_GRANTED=True)

    def test_changing_the_payer_is_audited_and_does_not_rewrite_settled_work(self):
        """The retained implementation, exercised with the capability granted."""
        with self.granted():
            self.sign_in()
            recorded = Job.objects.get(pk=self.job.pk).payer
            response = self.client.post(f'/console/departments/{self.department.pk}/payer/',
                                        {'organization_pays': 'on', 'confirm': 'on',
                                         'reason': 'billing owner moved this department to the organization balance'})
            self.assertEqual(response.status_code, 302)
            self.department.refresh_from_db()
            self.assertTrue(self.department.organization_pays)
            self.assertTrue(Wallet.objects.filter(organization=self.org, kind='paid').exists())
            # ⚠️ THE INVARIANT THE SCREEN PROMISES: the change is prospective only. `Job.payer` is
            # stamped when funds are first held and never re-read from the department.
            self.assertEqual(Job.objects.get(pk=self.job.pk).payer, recorded)
            self.assertEqual(Usage.objects.get(pk=self.usage.pk).payer, recorded)
            self.assertEqual(
                {r.wallet_id for r in Reservation.objects.filter(job=self.job)},
                {r.wallet_id for r in Reservation.objects.filter(job=self.job)})
            event = AuditEvent.objects.get(action='admin.department_payer')
            self.assertEqual(event.details['organization_pays_to'], True)
            self.assertEqual(event.details['organization_pays_from'], False)
            self.assertIn('billing owner moved', event.details['reason'])

    def test_the_return_location_cannot_be_used_to_redirect_off_the_console(self):
        self.sign_in()
        response = self.client.post(f'/console/accounts/{self.user.pk}/sessions/',
                                    {'back': 'https://example.invalid/phish'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/console/'))

    def test_an_outstanding_invitation_can_be_revoked_from_the_console(self):
        from core.security import digest, token
        invitation = Invitation.objects.create(email='invited@synthetic.invalid', department=self.department,
                                               role='clinician', token_hash=digest(token()),
                                               expires_at=timezone.now() + timedelta(days=7),
                                               invited_by=self.user)
        self.sign_in()
        self.assertEqual(self.client.post(f'/console/invitations/{invitation.pk}/revoke/', {}).status_code, 302)
        invitation.refresh_from_db()
        self.assertLessEqual(invitation.expires_at, timezone.now())


class SessionRevocation(ConsoleFixture):
    def test_signing_out_everywhere_invalidates_sessions_without_changing_access(self):
        """Previously the ONLY way to invalidate a session was to disable the account."""
        signed_in = SurfaceClient()
        signed_in.force_login(self.user)
        self.assertEqual(signed_in.get('/patients/').status_code, 200)
        before = self.user.session_version
        self.sign_in()
        self.client.post(f'/console/accounts/{self.user.pk}/sessions/', {})
        self.user.refresh_from_db()
        self.assertEqual(self.user.session_version, before + 1)
        self.assertTrue(self.user.is_active)                       # access unchanged
        self.assertEqual(signed_in.get('/patients/').status_code, 302)   # the live session is gone
        event = AuditEvent.objects.get(action='admin.sessions_revoked')
        self.assertEqual(event.details['still_enabled'], True)

    def test_another_administrator_cannot_be_signed_out_from_this_screen(self):
        other = User.objects.create_user(username='other-admin', email='other-admin@synthetic.invalid',
                                         verified_at=timezone.now(), is_staff=True)
        self.sign_in()
        self.assertEqual(self.client.post(f'/console/accounts/{other.pk}/sessions/', {}).status_code, 403)
        other.refresh_from_db()
        self.assertEqual(other.session_version, 0)


class UsageExport(ConsoleFixture):
    def rows(self, **params):
        self.sign_in()
        response = self.client.get('/console/usage.csv', params)
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content).decode()
        return [line.split(',') for line in body.strip().split('\r\n')]

    def test_the_export_carries_the_filtered_rows_and_no_clinical_column(self):
        rows = self.rows()
        self.assertEqual(rows[0], admin_console.EXPORT_COLUMNS)
        self.assertEqual(len(rows) - 1, Usage.objects.count())
        self.assertNotIn('notes', rows[0])
        self.assertNotIn('answers', rows[0])
        body = '\n'.join(','.join(row) for row in rows)
        self.assertNotIn(self.encounter.notes.split('\n')[0], body)
        self.assertNotIn(self.patient.display_name, body)

    def test_the_export_honours_the_same_search_and_window_as_the_screen(self):
        self.assertEqual(len(self.rows(q='no-such-provider-anywhere')) - 1, 0)
        future = (timezone.now() + timedelta(days=2)).date().isoformat()
        self.assertEqual(len(self.rows(**{'from': future})) - 1, 0)
        self.assertEqual(len(self.rows(q='anthropic:console-fixture')) - 1, 1)

    def test_money_columns_are_exact_fixed_point(self):
        row = self.rows()[1]
        columns = dict(zip(admin_console.EXPORT_COLUMNS, row))
        self.assertEqual(Decimal(columns['configured_cost']), self.usage.actual_cost)
        self.assertNotIn('E', columns['configured_cost'].upper())

    def test_exporting_is_itself_audited(self):
        self.rows(q='anthropic')
        event = AuditEvent.objects.get(action='admin.usage_export')
        self.assertEqual(event.details['rows'], 1)
        self.assertEqual(event.actor, self.admin)


class AuditInvestigation(ConsoleFixture):
    def test_the_action_picker_matches_exactly_where_the_text_box_widens(self):
        AuditEvent.objects.create(action='payment.refund', target='a')
        AuditEvent.objects.create(action='payment.refund_reconciliation_required', target='b')
        self.sign_in()
        widened = self.client.get('/console/audit/', {'q': 'payment.refund'})
        self.assertEqual(len({e.action for e in widened.context['audit_events']}), 2)
        exact = self.client.get('/console/audit/', {'action': 'payment.refund'})
        self.assertEqual({e.action for e in exact.context['audit_events']}, {'payment.refund'})

    def test_the_picker_only_offers_actions_that_exist(self):
        self.sign_in()
        response = self.client.get('/console/audit/')
        self.assertIn('usage.settle', response.context['actions'])
        self.assertNotIn('an.action.that.was.never.recorded', response.context['actions'])

    def test_a_date_window_applies_to_the_audit_trail(self):
        self.sign_in()
        future = (timezone.now() + timedelta(days=2)).date().isoformat()
        self.assertEqual(len(self.client.get('/console/audit/', {'from': future}).context['audit_events']), 0)
        self.assertGreater(len(self.client.get('/console/audit/').context['audit_events']), 0)

    def test_reading_the_audit_trail_is_itself_recorded(self):
        """The one administrative read the product did not record."""
        self.sign_in()
        self.client.get('/console/audit/', {'q': 'usage'})
        event = AuditEvent.objects.get(action='admin.audit_read')
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.details['query'], 'usage')

    def test_the_dashboard_recent_panel_is_not_filled_with_its_own_reads(self):
        self.sign_in()
        for _ in range(9):
            self.client.get('/console/')
        recent = self.client.get('/console/').context['audit_events']
        self.assertTrue(all(event.action != 'admin.dashboard' for event in recent))


class AccountDetail(ConsoleFixture):
    def test_one_page_carries_verification_mfa_money_and_events_about_the_account(self):
        self.sign_in()
        response = self.client.get(f'/console/accounts/{self.user.pk}/detail/')
        context = response.context
        self.assertTrue(context['verified'])
        self.assertEqual(context['mfa_devices'], [])
        self.assertEqual(context['wallet_totals']['promo'],
                         Wallet.objects.get(user=self.user, kind='promo').balance)
        self.assertEqual(context['usage_count'], 1)
        # Events performed ON the account, which an actor-only audit search cannot find.
        self.client.post(f'/console/accounts/{self.user.pk}/sessions/', {})
        actions = {e.action for e in self.client.get(
            f'/console/accounts/{self.user.pk}/detail/').context['audit_events']}
        self.assertIn('admin.sessions_revoked', actions)

    def test_the_organization_wallet_that_pays_is_shown_beside_the_personal_ones(self):
        self.department.organization_pays = True
        self.department.save(update_fields=['organization_pays'])
        Wallet.objects.get_or_create(organization=self.org, kind='paid')
        self.sign_in()
        wallets = self.client.get(f'/console/accounts/{self.user.pk}/detail/').context['wallets']
        self.assertTrue(any(w.organization_id == self.org.pk for w in wallets))

    def test_reading_an_account_is_audited(self):
        self.sign_in()
        self.client.get(f'/console/accounts/{self.user.pk}/detail/')
        self.assertTrue(AuditEvent.objects.filter(action='admin.account_read',
                                                  target=str(self.user.pk)).exists())


class IntegrationSeverity(TestCase):
    def test_every_configured_row_carries_a_badge_variant_that_exists(self):
        """The template wrote the whole status SENTENCE into the CSS class, so every row was grey."""
        from core.context import integration_status
        for row in integration_status():
            with self.subTest(name=row['name']):
                self.assertIn(row['severity'], {'success', 'warning', 'error'})

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic', CPT_LICENSE_ID='x', CPT_LICENSE_EXPIRY='2020-01-01')
    def test_a_broken_integration_is_red_and_its_wording_is_unchanged(self):
        from core.context import integration_status
        rows = {row['name']: row for row in integration_status()}
        self.assertEqual(rows['Payments']['status'], 'Not connected')
        self.assertEqual(rows['Payments']['severity'], 'error')
        self.assertEqual(rows['CPT terminology']['status'], 'License expired')
        self.assertEqual(rows['CPT terminology']['severity'], 'error')

    def test_the_rendered_badge_class_is_the_severity_and_not_the_sentence(self):
        rendered = Template("{% include 'integrations.html' %}").render(Context(
            {'integrations': [{'name': 'X', 'status': 'Not connected', 'severity': 'error', 'detail': 'd'}]}))
        self.assertIn('class="badge error"', rendered)
        self.assertNotIn('class="badge Not connected"', rendered)
