"""Real data mode never spends sandbox-funded money (round-2 refutation F2).

A database that took sandbox (test-card) payments and is then started in real data mode would let that money fund
real provider calls, and real mode refuses the sandbox refund that could remove it. So: every Payment and Stripe
event records the mode it was created in; reserve() in real mode refuses a paid balance any non-live payment funded;
and `manage.py real_mode_payment_check` (read-only) refuses a database holding sandbox payment evidence.

No provider is called: Stripe Checkout is a mock and every webhook is signed locally with a synthetic secret.
"""
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from core.billing import reserve
from core.models import AuditEvent, Job, LedgerEntry, Payment, Reservation, Wallet, WebhookEvent
from core.tests.test_security import SyntheticFixture
from core.tests import test_v1_stripe_live as stripe_live  # The module, so its TestCase is not collected twice here.
from core.tests.test_v1_stripe_live import LIVE, SECRET, STORAGES, event

REAL = dict(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real')
#: The documented V1 value until live payments are approved: real data, no Stripe key.
REAL_PAYMENTS_OFF = dict(REAL, QUILLMD_STRIPE_MODE='test', STRIPE_LIVE_ENABLED=False, STRIPE_SECRET_KEY='')


def paid_session(payment, livemode, intent):
    return {'id': payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd', 'amount_total': payment.amount_cents,
            'metadata': {'payment_id': str(payment.pk)}, 'payment_intent': intent, 'mode': 'payment', 'livemode': livemode}


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                   QUILLMD_WELCOME_CREDIT=Decimal('0'))
class RealModeNeverSpendsSandboxMoney(SyntheticFixture, TestCase):
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed

    def job(self, key):
        return Job.objects.create(encounter=self.user.membership_set.first().department.encounter_set.first(),
                                  user=self.user, kind='generation', request_key=key, config={})

    def sandbox_top_up(self, nonce='sandbox-top-up'):
        """Today's deployment: synthetic data, sandbox Stripe; a test-card checkout of $10 credits the paid wallet."""
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            self.assertEqual(self.checkout(nonce)[0].status_code, 302)
        payment = Payment.objects.get(stripe_session=f'cs_{nonce}')
        self.assertEqual(self.signed(event(False, paid_session(payment, False, f'pi_{nonce}'), f'evt_{nonce}')).status_code, 200)
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        self.assertEqual(wallet.balance, 10)
        return payment, wallet

    def test_checkout_and_events_record_their_mode(self):
        payment, _ = self.sandbox_top_up()
        self.assertIs(payment.livemode, False)
        self.assertIs(WebhookEvent.objects.get(event_id='evt_sandbox-top-up').livemode, False)
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **LIVE):
            self.checkout('live-top-up')
            live = Payment.objects.get(stripe_session='cs_live-top-up')
            self.assertEqual(self.signed(event(True, paid_session(live, True, 'pi_live'), 'evt_live')).status_code, 200)
        self.assertIs(live.livemode, True)
        self.assertIs(WebhookEvent.objects.get(event_id='evt_live').livemode, True)

    def test_real_mode_refuses_to_reserve_from_a_sandbox_funded_balance(self):
        """The refuter's P2: the same database restarted in real mode, payments off, held 30 of sandbox money."""
        _, wallet = self.sandbox_top_up()
        with override_settings(**REAL_PAYMENTS_OFF):
            job = self.job('stock-probe')
            with self.assertRaisesRegex(ValidationError, 'sandbox'):
                reserve(job, Decimal('2'))
        self.assertFalse(Reservation.objects.filter(job=job).exists())
        wallet.refresh_from_db()
        self.assertEqual((wallet.balance, wallet.reserved), (10, 0))
        self.assertFalse(AuditEvent.objects.filter(action='usage.reserve').exists())

    def test_a_payment_recorded_before_the_mode_was_stored_is_sandbox(self):
        """Rows from before this change carry NULL: live mode did not exist then, so they count as sandbox."""
        payment, wallet = self.sandbox_top_up()
        Payment.objects.filter(pk=payment.pk).update(livemode=None)
        with override_settings(**REAL_PAYMENTS_OFF), self.assertRaises(ValidationError):
            reserve(self.job('legacy'), Decimal('2'))
        from core.billing import sandbox_funded
        self.assertTrue(sandbox_funded(wallet))

    def test_a_payment_credit_without_a_live_payment_counts(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal('5'))
        LedgerEntry.objects.create(wallet=wallet, amount=Decimal('5'), kind='payment', key='payment:pi_orphan',
                                   description='Explicit Stripe wallet top-up', balance_after=Decimal('5'))
        with override_settings(**REAL_PAYMENTS_OFF), self.assertRaises(ValidationError):
            reserve(self.job('orphan'), Decimal('2'))
        from core.billing import sandbox_funded
        self.assertTrue(sandbox_funded(wallet))

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE)
    def test_real_mode_spends_money_live_payments_funded(self):
        self.checkout('real-live')
        payment = Payment.objects.get(stripe_session='cs_real-live')
        self.assertEqual(self.signed(event(True, paid_session(payment, True, 'pi_real_live'), 'evt_real_live')).status_code, 200)
        job = self.job('live-spend')
        reserve(job, Decimal('2'))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount')), [('paid', Decimal('3'))])
        from core.billing import sandbox_funded
        self.assertFalse(sandbox_funded(Wallet.objects.get(user=self.user, kind='paid')))

    @override_settings(**REAL_PAYMENTS_OFF)
    def test_real_mode_without_payments_still_reserves_promotional_credit(self):
        with override_settings(QUILLMD_WELCOME_CREDIT=Decimal('10')):
            other = self.make_scope('promo-only')
        job = Job.objects.create(encounter=other[5], user=other[0], kind='generation', request_key='promo-only', config={})
        reserve(job, Decimal('2'))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount')), [('promo', Decimal('3'))])

    def test_synthetic_mode_keeps_spending_sandbox_money_as_before(self):
        self.sandbox_top_up()
        job = self.job('synthetic-spend')
        reserve(job, Decimal('2'))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount')), [('paid', Decimal('3'))])


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                   QUILLMD_WELCOME_CREDIT=Decimal('0'))
class RealModePaymentCheckCommand(SyntheticFixture, TestCase):
    """`manage.py real_mode_payment_check`: read-only; exit 1 on sandbox evidence; counts only in its output."""
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed
    sandbox_top_up = RealModeNeverSpendsSandboxMoney.sandbox_top_up

    @staticmethod
    def contents():
        """Every value the check could change, not only how many rows there are (round-3 F4: a check that rewrote
        every row as live and kept the row counts passed a count comparison)."""
        return {
            'payments': list(Payment.objects.order_by('pk').values_list(
                'pk', 'livemode', 'status', 'wallet_id', 'amount_cents', 'stripe_session', 'stripe_intent')),
            'events': list(WebhookEvent.objects.order_by('pk').values_list(
                'pk', 'livemode', 'status', 'kind', 'attempts', 'payload_hash', 'semantic_hash')),
            'wallets': list(Wallet.objects.order_by('pk').values_list('pk', 'kind', 'balance', 'reserved')),
            'ledger': list(LedgerEntry.objects.order_by('pk').values_list(
                'pk', 'wallet_id', 'amount', 'kind', 'key', 'balance_after')),
            'audit': list(AuditEvent.objects.order_by('pk').values_list('pk', 'action', 'target')),
        }

    def run_check(self):
        before = self.contents()
        out = StringIO()
        try:
            call_command('real_mode_payment_check', stdout=out)
            result = (0, out.getvalue())
        except CommandError as exc:
            result = (1, str(exc))
        self.assertEqual(self.contents(), before, 'the check changed a payment, event, wallet, ledger or audit row')
        return result

    def test_a_database_without_payments_may_run_real_mode(self):
        status, message = self.run_check()
        self.assertEqual(status, 0, message)
        self.assertIn('may run in real data mode', message)
        from core.billing import real_mode_payment_problems
        self.assertEqual(real_mode_payment_problems(), [])

    def test_sandbox_payments_events_and_balances_refuse(self):
        payment, _ = self.sandbox_top_up()
        status, message = self.run_check()
        self.assertEqual(status, 1)
        for text in ('1 payment row(s)', '1 Stripe event row(s)', '1 paid wallet(s)', 'never held sandbox payments'):
            self.assertIn(text, message)
        # Counts only: no identifier, address or amount.
        for private in (payment.stripe_session, 'pi_sandbox-top-up', 'evt_sandbox-top-up', self.user.email, str(payment.pk), '10'):
            self.assertNotIn(private, message)

    def test_a_sandbox_payment_that_never_paid_still_refuses(self):
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            self.checkout('never-paid')
        status, message = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn('1 payment row(s)', message)

    def test_a_paid_balance_the_ledger_does_not_explain_refuses(self):
        Wallet.objects.filter(user=self.user, kind='paid').update(balance=Decimal('7'))
        status, message = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn('1 paid wallet(s)', message)

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE)
    def test_live_payments_only_may_run_real_mode(self):
        self.checkout('live-only')
        payment = Payment.objects.get(stripe_session='cs_live-only')
        self.assertEqual(self.signed(event(True, paid_session(payment, True, 'pi_live_only'), 'evt_live_only')).status_code, 200)
        status, message = self.run_check()
        self.assertEqual(status, 0, message)

    def test_a_write_inside_the_checks_transaction_is_refused(self):
        """Round-3 F4 (mutant R1/R3): the command runs its reads in a READ ONLY transaction, so any write made inside it,
        by mistake or by a later edit, is refused by the database rather than rolled back afterwards."""
        payment, wallet = self.sandbox_top_up()
        attempts = []

        def problems_that_write():
            for name, write in (('wallet', lambda: Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal('999'))),
                                ('payment', lambda: Payment.objects.filter(pk=payment.pk).update(status='expired')),
                                ('audit', lambda: AuditEvent.objects.create(action='synthetic.write_probe'))):
                try:
                    with transaction.atomic():
                        write()
                    attempts.append((name, 'written'))
                except DatabaseError as exc:
                    attempts.append((name, 'refused: read-only' if 'read-only transaction' in str(exc) else f'other: {exc}'[:120]))
            return []

        with patch('core.management.commands.real_mode_payment_check.real_mode_payment_problems', problems_that_write):
            status, message = self.run_check()
        self.assertEqual(attempts, [('wallet', 'refused: read-only'), ('payment', 'refused: read-only'),
                                    ('audit', 'refused: read-only')])
        self.assertEqual(status, 0, message)
        # The test's own transaction is writable again once the command has ended.
        Wallet.objects.filter(pk=wallet.pk).update(reserved=Decimal('0'))

    def test_legacy_rows_recorded_before_the_mode_was_stored_refuse_even_when_their_wallet_is_drained(self):
        """Round-3 F4 (mutant C12): after 0020 the private-beta database's rows carry livemode NULL, and a paid wallet
        whose sandbox money was all spent holds 0, so the wallet count cannot catch it: the row counts must."""
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        Payment.objects.create(user=self.user, wallet=wallet, amount_cents=1000, stripe_session='cs_legacy_drained',
                               stripe_intent='pi_legacy_drained', status='paid', livemode=None)
        WebhookEvent.objects.create(event_id='evt_legacy_drained', kind='checkout.session.completed', payload_hash='0' * 64,
                                    object_data={}, status='processed', livemode=None)
        LedgerEntry.objects.create(wallet=wallet, amount=Decimal('10'), kind='payment', key='payment:pi_legacy_drained',
                                   description='Explicit Stripe wallet top-up', balance_after=Decimal('10'))
        LedgerEntry.objects.create(wallet=wallet, amount=Decimal('-10'), kind='usage', key='usage:legacy-drained',
                                   description='Provider cost × 1.5', balance_after=Decimal('0'))
        wallet.refresh_from_db()
        self.assertEqual((wallet.balance, wallet.reserved), (0, 0))
        status, message = self.run_check()
        self.assertEqual(status, 1, message)
        self.assertIn('1 payment row(s) not recorded as live', message)
        self.assertIn('1 Stripe event row(s) not recorded as live', message)
        self.assertNotIn('paid wallet(s)', message)
