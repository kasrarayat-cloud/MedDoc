"""Real data mode never spends sandbox-funded money (round-2 refutation F2).

A database that took sandbox (test-card) payments and is then started in real data mode would let that money fund
real provider calls, and real mode refuses the sandbox refund that could remove it. So: every Payment and Stripe
event records the mode it was created in; reserve() in real mode refuses a paid balance any non-live payment funded;
and `manage.py real_mode_payment_check` (read-only) refuses a database holding sandbox payment evidence.

No provider is called: Stripe Checkout is a mock and every webhook is signed locally with a synthetic secret.
"""
import tempfile
import uuid
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase, override_settings

from core.billing import reserve, sandbox_funded, welcome_credit
from core.models import AuditEvent, Job, LedgerEntry, Payment, ProviderReceipt, Reservation, Usage, Wallet, WebhookEvent
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
        """Rows from before this change carry NULL: live mode did not exist then, so they count as sandbox. (Recorded as
        NULL here: a recorded mode cannot be changed afterwards, 0020's trigger.)"""
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        Payment.objects.create(user=self.user, wallet=wallet, amount_cents=1000, stripe_session='cs_legacy',
                               stripe_intent='pi_legacy', status='paid', livemode=None)
        Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal('10'))
        LedgerEntry.objects.create(wallet=wallet, amount=Decimal('10'), kind='payment', key='payment:pi_legacy',
                                   description='Explicit Stripe wallet top-up', balance_after=Decimal('10'))
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


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                   QUILLMD_WELCOME_CREDIT=Decimal('0'))
class RealModeFundsOnlyWhatItCanSpend(SyntheticFixture, TestCase):
    """Round-3 refutation F1.

    (a) Real data mode never takes live money into a paid balance reserve() will always refuse: checkout is refused
        before any Payment row or Stripe call, tells the payer to contact support, names nothing, and is audited.
    (b) Only a payment that FUNDED the wallet makes it sandbox-funded. A sandbox checkout nobody paid holds no money,
        and every way sandbox money can reach a wallet is still caught.
    """
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed
    sandbox_top_up = RealModeNeverSpendsSandboxMoney.sandbox_top_up
    job = RealModeNeverSpendsSandboxMoney.job

    def checkout_for(self, nonce, payer):
        token = signing.dumps({'user': str(self.user.pk), 'nonce': nonce}, salt='checkout-authorization')
        session = SimpleNamespace(id=f'cs_{nonce}', url='https://checkout.stripe.com/c/pay/synthetic')
        with patch('stripe.checkout.Session.create', return_value=session) as api:
            response = self.client.post('/billing/checkout/', {'amount': '10.00', 'consent': 'on', 'checkout_token': token,
                                                               'payer': payer})
        return response, api

    def owner_of_organization(self):
        membership = self.user.membership_set.first()
        membership.role = 'owner'
        membership.save(update_fields=['role'])
        return membership.department

    def live_top_up(self, nonce, payer='personal'):
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            response, api = self.checkout_for(nonce, payer)
            self.assertTrue(api.called, 'the live checkout was refused')
            payment = Payment.objects.get(stripe_session=f'cs_{nonce}')
            self.assertEqual(self.signed(event(True, paid_session(payment, True, f'pi_{nonce}'), f'evt_{nonce}')).status_code, 200)
        return payment

    def recorded(self, wallet, key, *, status, livemode, credit):
        """A Payment row as some earlier deployment left it, optionally with the 'payment' credit it produced."""
        payment = Payment.objects.create(user=self.user, wallet=wallet, amount_cents=500, stripe_session=f'cs_{key}',
                                         stripe_intent=f'pi_{key}', status=status, livemode=livemode)
        if credit:
            balance = Wallet.objects.get(pk=wallet.pk).balance + Decimal('5')
            Wallet.objects.filter(pk=wallet.pk).update(balance=balance)
            LedgerEntry.objects.create(wallet=wallet, amount=Decimal('5'), kind='payment', key=f'payment:pi_{key}',
                                       description='Explicit Stripe wallet top-up', balance_after=balance)
        return payment

    # (a) Checkout ---------------------------------------------------------------------------------------------------

    def assert_refused_before_stripe(self, response, api, nonce):
        self.assertEqual(response.status_code, 302)
        api.assert_not_called()
        self.assertFalse(Payment.objects.filter(stripe_session=f'cs_{nonce}').exists())
        message = str(list(response.wsgi_request._messages)[0])
        self.assertIn('Contact support', message)
        self.assertIn('No charge was made', message)
        return message

    def test_P1_real_mode_refuses_a_live_checkout_into_a_sandbox_funded_personal_balance(self):
        """The refuter's P1: sandbox top-up, then a live checkout in real mode took $10 of live money into a wallet
        reserve() refuses forever."""
        payment, wallet = self.sandbox_top_up()
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            response, api = self.checkout('live-into-sandbox')
        message = self.assert_refused_before_stripe(response, api, 'live-into-sandbox')
        self.assertEqual(list(Payment.objects.values_list('pk', flat=True)), [payment.pk])
        for private in (str(wallet.pk), str(payment.pk), self.user.email, 'pi_sandbox-top-up', 'cs_sandbox-top-up', '10', '$'):
            self.assertNotIn(private, message)
        refused = AuditEvent.objects.get(action='payment.checkout_refused_sandbox_balance')
        self.assertEqual((refused.actor_id, refused.target), (self.user.pk, str(wallet.pk)))
        wallet.refresh_from_db()
        self.assertEqual((wallet.balance, wallet.reserved), (10, 0))

    def test_real_mode_refuses_a_live_checkout_into_a_sandbox_funded_organization_balance_only(self):
        department = self.owner_of_organization()
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            self.assertTrue(self.checkout_for('org-sandbox', f'organization:{department.organization_id}')[1].called)
        payment = Payment.objects.get(stripe_session='cs_org-sandbox')
        self.assertEqual(self.signed(event(False, paid_session(payment, False, 'pi_org_sandbox'), 'evt_org_sandbox')).status_code, 200)
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            response, api = self.checkout_for('org-live', f'organization:{department.organization_id}')
        self.assert_refused_before_stripe(response, api, 'org-live')
        # The owner's personal paid balance holds no sandbox money: its live checkout proceeds.
        self.live_top_up('personal-live')

    def test_real_mode_checks_out_into_a_balance_a_sandbox_checkout_never_funded(self):
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            self.checkout('abandoned-before-live')
        self.live_top_up('live-after-abandoned')

    def test_synthetic_mode_checks_out_into_a_sandbox_funded_balance_as_before(self):
        self.sandbox_top_up()
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            response, api = self.checkout('second-sandbox')
        self.assertTrue(api.called)
        self.assertFalse(AuditEvent.objects.filter(action='payment.checkout_refused_sandbox_balance').exists())

    # (b) Which payments count ---------------------------------------------------------------------------------------

    def test_P7_an_unpaid_sandbox_checkout_does_not_freeze_a_balance_live_money_funded(self):
        """The refuter's P7: one abandoned sandbox checkout (pending, no money, no credit) made a live-only wallet
        unspendable in real mode."""
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            self.checkout('abandoned-sandbox')
        abandoned = Payment.objects.get(stripe_session='cs_abandoned-sandbox')
        self.assertEqual((abandoned.status, abandoned.livemode), ('pending', False))
        self.live_top_up('live-only-money')
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        self.assertEqual(list(LedgerEntry.objects.filter(wallet=wallet, kind='payment').values_list('key', 'amount')),
                         [('payment:pi_live-only-money', Decimal('10'))])
        self.assertFalse(sandbox_funded(wallet))
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            job = self.job('live-money-only')
            reserve(job, Decimal('2'))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount')), [('paid', Decimal('3'))])

    def test_no_payment_that_never_funded_the_wallet_makes_it_sandbox_funded(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        for status in ('creating', 'pending', 'processing', 'uncertain', 'failed', 'expired'):
            for livemode in (False, None):
                self.recorded(wallet, f'unfunded-{status}-{livemode}', status=status, livemode=livemode, credit=False)
        self.assertFalse(sandbox_funded(wallet))

    def test_every_way_sandbox_money_reaches_a_wallet_is_still_caught(self):
        cases = {
            # A paid sandbox or pre-mode Payment, even if its credit were somehow absent.
            'paid sandbox, no credit': dict(status='paid', livemode=False, credit=False),
            'paid legacy NULL, no credit': dict(status='paid', livemode=None, credit=False),
            'paid sandbox with its credit': dict(status='paid', livemode=False, credit=True),
            'paid legacy NULL with its credit': dict(status='paid', livemode=None, credit=True),
            # A credit whose Payment is not live, whatever that Payment's status says.
            'credit, Payment NULL and not paid': dict(status='processing', livemode=None, credit=True),
            'credit, Payment sandbox and not paid': dict(status='expired', livemode=False, credit=True),
        }
        for index, (name, case) in enumerate(cases.items()):
            with self.subTest(case=name):
                wallet = Wallet.objects.get(user=self.make_scope(f'caught{index}')[0], kind='paid')
                self.recorded(wallet, f'caught-{index}', **case)
                self.assertTrue(sandbox_funded(wallet))
        with self.subTest(case='credit whose Payment is missing'):
            wallet = Wallet.objects.get(user=self.make_scope('orphan-credit')[0], kind='paid')
            Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal('5'))
            LedgerEntry.objects.create(wallet=wallet, amount=Decimal('5'), kind='payment', key='payment:pi_orphan_credit',
                                       description='Explicit Stripe wallet top-up', balance_after=Decimal('5'))
            self.assertTrue(sandbox_funded(wallet))
        with self.subTest(case='a live payment beside a sandbox credit'):
            self.live_top_up('live-beside-sandbox')
            wallet = Wallet.objects.get(user=self.user, kind='paid')
            self.assertFalse(sandbox_funded(wallet))
            self.recorded(wallet, 'sandbox-beside-live', status='paid', livemode=False, credit=True)
            self.assertTrue(sandbox_funded(wallet))

    def test_organization_and_promotional_wallets_are_judged_by_their_own_money(self):
        department = self.owner_of_organization()
        organization_wallet, _ = Wallet.objects.get_or_create(organization_id=department.organization_id, kind='paid')
        personal = Wallet.objects.get(user=self.user, kind='paid')
        promo = Wallet.objects.get(user=self.user, kind='promo')
        self.recorded(organization_wallet, 'org-sandbox-money', status='paid', livemode=False, credit=True)
        self.assertEqual((sandbox_funded(organization_wallet), sandbox_funded(personal), sandbox_funded(promo)),
                         (True, False, False))
        self.live_top_up('personal-live-money')
        with override_settings(**REAL_PAYMENTS_OFF):
            reserve(self.job('personal-payer'), Decimal('2'))  # The department pays personally: live money only.
            department.organization_pays = True
            department.save(update_fields=['organization_pays'])
            with self.assertRaisesRegex(ValidationError, 'sandbox'):
                reserve(self.job('organization-payer'), Decimal('2'))
        # And the other way round: sandbox money in the personal wallet leaves the organization's live money spendable.
        other = self.make_scope('org-live-owner')
        other_org_wallet, _ = Wallet.objects.get_or_create(organization=other[1], kind='paid')
        self.recorded(Wallet.objects.get(user=other[0], kind='paid'), 'personal-sandbox-money', status='paid', livemode=False,
                      credit=True)
        self.assertFalse(sandbox_funded(other_org_wallet))
        self.assertFalse(sandbox_funded(Wallet.objects.get(user=other[0], kind='promo')))


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                   QUILLMD_WELCOME_CREDIT=Decimal('0'))
class RealModeWorkerNeverSpendsAHoldOnSandboxMoney(SyntheticFixture, TestCase):
    """Round-3 refutation F2: a hold taken before the switch to real data mode sits on sandbox money. The worker refuses
    the job before any provider request: not processed, nothing charged, the hold released, audited."""
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed
    sandbox_top_up = RealModeNeverSpendsSandboxMoney.sandbox_top_up
    job = RealModeNeverSpendsSandboxMoney.job
    ANSWERS = {'symptoms': {'text': 'no chest pain', 'status': 'supported', 'reviewed': False, 'evidence': []}}

    def setUp(self):
        stripe_live.LiveCheckoutAndSettlement.setUp(self)
        # A job the worker sends writes its result file under MEDIA_ROOT: a temporary directory, never the tree's .runtime.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        media = override_settings(MEDIA_ROOT=Path(directory.name))
        media.enable()
        self.addCleanup(media.disable)
    REAL_LIVE_AI = dict(REAL_PAYMENTS_OFF, AI_MODE='live')

    def run_worker(self, **now):
        from core import jobs
        provider = ({'answers': self.ANSWERS}, Decimal('1'), {'input_tokens': 1}, {'rate': '1'}, 'anthropic:probe',
                    'msg_probe_refute3', False)
        with override_settings(**now), patch('core.jobs.generation.generate', return_value=provider) as generate, \
                patch('core.jobs.generation.validated', return_value=self.ANSWERS), \
                patch('core.jobs.transcribe', side_effect=AssertionError('transcription was sent')) as transcribe:
            self.assertTrue(jobs.run_one())
        return generate, transcribe

    def assert_refused_and_released(self, job, wallet):
        job.refresh_from_db()
        wallet.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertIn('sandbox (test) payments', job.error)
        self.assertIn('Contact support', job.error)
        self.assertIn('nothing was charged and the held funds were released', job.error)
        self.assertEqual((wallet.balance, wallet.reserved), (10, 0))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['released'])
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        refused = AuditEvent.objects.get(action='usage.sandbox_hold_refused')
        self.assertEqual((refused.actor_id, refused.target), (self.user.pk, str(job.pk)))
        self.assertEqual(AuditEvent.objects.get(action='job.failed', target=str(job.pk)).details['billing'], 'not_processed')
        self.assertTrue(AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).exists())

    def test_P2_a_generation_hold_taken_in_synthetic_mode_is_never_spent_on_a_real_mode_provider_call(self):
        """The refuter's P2: synthetic mode, sandbox top-up, a generation job holds $3; restart in real data mode,
        payments off, AI_MODE live; run_one() called the provider and debited $1.50 of sandbox money."""
        _, wallet = self.sandbox_top_up()
        job = self.job('queued-before-restart')
        reserve(job, Decimal('2'))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount', 'state')),
                         [('paid', Decimal('3'), 'held')])
        generate, _ = self.run_worker(**self.REAL_LIVE_AI)
        generate.assert_not_called()
        self.assert_refused_and_released(job, wallet)

    def test_a_transcription_hold_taken_in_synthetic_mode_is_never_sent_in_real_mode(self):
        _, wallet = self.sandbox_top_up()
        job = Job.objects.create(encounter=self.user.membership_set.first().department.encounter_set.first(), user=self.user,
                                 kind='transcription', request_key='transcription-before-restart', config={})
        reserve(job, charge_limit=Decimal('3'))
        _, transcribe = self.run_worker(**self.REAL_LIVE_AI)
        transcribe.assert_not_called()
        self.assert_refused_and_released(job, wallet)

    def test_synthetic_mode_spends_the_same_hold_as_before(self):
        _, wallet = self.sandbox_top_up()
        job = self.job('synthetic-worker')
        reserve(job, Decimal('2'))
        generate, _ = self.run_worker(AI_MODE='live')
        self.assertTrue(generate.called)
        wallet.refresh_from_db()
        self.assertEqual((wallet.balance, wallet.reserved), (Decimal('8.5'), 0))
        self.assertFalse(AuditEvent.objects.filter(action='usage.sandbox_hold_refused').exists())

    def test_real_mode_spends_a_hold_on_promotional_credit(self):
        with override_settings(QUILLMD_WELCOME_CREDIT=Decimal('10')):
            other = self.make_scope('promo-worker')
        job = Job.objects.create(encounter=other[5], user=other[0], kind='generation', request_key='promo-worker', config={})
        with override_settings(**self.REAL_LIVE_AI):
            reserve(job, Decimal('2'))
        generate, _ = self.run_worker(**self.REAL_LIVE_AI)
        self.assertTrue(generate.called)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)

    def test_real_mode_spends_a_hold_on_live_money(self):
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            self.checkout('worker-live')
            payment = Payment.objects.get(stripe_session='cs_worker-live')
            self.assertEqual(self.signed(event(True, paid_session(payment, True, 'pi_worker_live'), 'evt_worker_live')).status_code, 200)
            job = self.job('worker-live')
            reserve(job, Decimal('2'))
        generate, _ = self.run_worker(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', AI_MODE='live', **REAL, **LIVE)
        self.assertTrue(generate.called)
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        self.assertEqual((wallet.balance, wallet.reserved), (Decimal('8.5'), 0))

    def split_hold(self, key, promo_first):
        """reserve() of $3 split $1 promotional / $2 sandbox-funded paid, with the order of the two holds' primary keys
        chosen: a reader that looks only at the first hold (by primary key) meets the promotional one first when
        promo_first. Returns the job."""
        job = self.job(key)
        reserve(job, Decimal('2'))
        holds = {r.wallet.kind: r for r in Reservation.objects.filter(job=job).select_related('wallet')}
        self.assertEqual({kind: (r.amount, r.state) for kind, r in holds.items()},
                         {'promo': (Decimal('1'), 'held'), 'paid': (Decimal('2'), 'held')})
        low, high = sorted([uuid.uuid4(), uuid.uuid4()])
        first, second = ('promo', 'paid') if promo_first else ('paid', 'promo')
        Reservation.objects.filter(pk=holds[first].pk).update(id=low)
        Reservation.objects.filter(pk=holds[second].pk).update(id=high)
        self.assertEqual(Reservation.objects.filter(job=job, state='held').select_related('wallet').first().wallet.kind, first)
        return job

    def test_R4_3_a_hold_split_between_promotional_credit_and_sandbox_money_is_refused_before_sending(self):
        """The refuter's R4-3: $1 promotional + $10 sandbox money, and a $3 hold split $1/$2. No test held a split hold,
        so a reader that looked only at the first hold (H2) or required every hold to be refused (H3) survived. Both
        orders of the two holds run, so the first hold is the promotional one in one of them."""
        with override_settings(QUILLMD_WELCOME_CREDIT=Decimal('1')):
            welcome_credit(self.user)
        _, wallet = self.sandbox_top_up()
        promo = Wallet.objects.get(user=self.user, kind='promo')
        self.assertEqual(promo.balance, 1)
        for order, promo_first in (('promotional hold first', True), ('paid hold first', False)):
            with self.subTest(order=order):
                job = self.split_hold(f'split-{order}', promo_first)
                generate, transcribe = self.run_worker(**self.REAL_LIVE_AI)
                generate.assert_not_called()
                transcribe.assert_not_called()
                job.refresh_from_db()
                self.assertEqual(job.state, 'failed')
                self.assertIn('sandbox (test) payments', job.error)
                self.assertIn('nothing was charged and the held funds were released', job.error)
                self.assertEqual(sorted(Reservation.objects.filter(job=job).values_list('wallet__kind', 'state')),
                                 [('paid', 'released'), ('promo', 'released')])
                self.assertFalse(Usage.objects.filter(job=job).exists())
                self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
                self.assertTrue(AuditEvent.objects.filter(action='usage.sandbox_hold_refused', target=str(job.pk)).exists())
                wallet.refresh_from_db()
                promo.refresh_from_db()
                self.assertEqual((wallet.balance, wallet.reserved, promo.balance, promo.reserved), (10, 0, 1, 0))


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                   QUILLMD_WELCOME_CREDIT=Decimal('0'))
class RecordedPaymentModeIsImmutable(SyntheticFixture, TestCase):
    """Round-3 refutation F3: once recorded, Payment.livemode and WebhookEvent.livemode never change (a database trigger,
    like 0008's signed-evidence guard). Otherwise one UPDATE turns sandbox evidence into 'live', and both the launcher's
    check and reserve() believe it."""
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed
    sandbox_top_up = RealModeNeverSpendsSandboxMoney.sandbox_top_up

    def assert_mode_refused(self, model, pk, values):
        before = model.objects.get(pk=pk).livemode
        for value in values:
            with self.subTest(model=model.__name__, before=before, after=value):
                with self.assertRaisesRegex(DatabaseError, 'payment mode is immutable'), transaction.atomic():
                    model.objects.filter(pk=pk).update(livemode=value)
        self.assertIs(model.objects.get(pk=pk).livemode, before)

    def test_P3_sandbox_evidence_cannot_be_relabelled_live(self):
        """The refuter's P3: update(livemode=True) on a recorded sandbox event and payment succeeded, and then
        real_mode_payment_problems() returned [] and sandbox_funded() False."""
        payment, wallet = self.sandbox_top_up()
        row = WebhookEvent.objects.get(event_id='evt_sandbox-top-up')
        self.assert_mode_refused(WebhookEvent, row.pk, (True, None))
        self.assert_mode_refused(Payment, payment.pk, (True, None))
        with self.assertRaisesRegex(DatabaseError, 'payment mode is immutable'), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE core_payment SET livemode = true WHERE id = %s', [payment.pk])
        with self.assertRaisesRegex(DatabaseError, 'payment mode is immutable'), transaction.atomic():
            payment.livemode = True
            payment.save()
        from core.billing import real_mode_payment_problems
        self.assertEqual(len(real_mode_payment_problems()), 3)
        self.assertTrue(sandbox_funded(wallet))

    def test_rows_recorded_before_the_mode_was_stored_cannot_be_given_one(self):
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        payment = Payment.objects.create(user=self.user, wallet=wallet, amount_cents=500, stripe_session='cs_legacy_mode',
                                         status='pending', livemode=None)
        row = WebhookEvent.objects.create(event_id='evt_legacy_mode', kind='checkout.session.completed', payload_hash='0' * 64,
                                          object_data={}, livemode=None)
        self.assert_mode_refused(Payment, payment.pk, (True, False))
        self.assert_mode_refused(WebhookEvent, row.pk, (True, False))

    @override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE)
    def test_live_evidence_cannot_be_relabelled_sandbox_or_unknown(self):
        self.checkout('live-mode-fixed')
        payment = Payment.objects.get(stripe_session='cs_live-mode-fixed')
        self.assertEqual(self.signed(event(True, paid_session(payment, True, 'pi_live_fixed'), 'evt_live_fixed')).status_code, 200)
        self.assert_mode_refused(Payment, payment.pk, (False, None))
        self.assert_mode_refused(WebhookEvent, WebhookEvent.objects.get(event_id='evt_live_fixed').pk, (False, None))

    def test_every_other_field_still_updates_and_a_same_value_save_passes(self):
        payment, _ = self.sandbox_top_up()
        row = WebhookEvent.objects.get(event_id='evt_sandbox-top-up')
        WebhookEvent.objects.filter(pk=row.pk).update(attempts=row.attempts + 1, error='synthetic', status='processed')
        Payment.objects.filter(pk=payment.pk).update(checkout_url='https://checkout.stripe.com/c/pay/synthetic-2')
        payment.refresh_from_db()
        payment.save()  # Every column, livemode unchanged.
        WebhookEvent.objects.filter(pk=row.pk).update(livemode=False)  # The same value is not a change.
        self.assertIs(Payment.objects.get(pk=payment.pk).livemode, False)
        self.assertEqual(WebhookEvent.objects.get(pk=row.pk).attempts, row.attempts + 1)


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                   QUILLMD_WELCOME_CREDIT=Decimal('0'))
class ReversingThePaymentModeMigration(SyntheticFixture, TransactionTestCase):
    """Round-3 refutation F5: reversing 0020 drops livemode, and re-applying it records every row NULL, which real mode
    treats as sandbox money it never spends. So the reverse refuses while any row is recorded as live; a database with
    no live rows still reverses."""
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed
    sandbox_top_up = RealModeNeverSpendsSandboxMoney.sandbox_top_up
    job = RealModeNeverSpendsSandboxMoney.job
    BEFORE_0020 = [('core', '0019_clinicinvitation')]

    def to_leaf(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    @staticmethod
    def schema():
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM information_schema.columns WHERE column_name = 'livemode' "
                           "AND table_name IN ('core_payment', 'core_webhookevent')")
            columns = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname IN ('payment_evidence_immutable', 'webhook_livemode_immutable', "
                           "'payment_no_truncate', 'webhook_no_truncate', 'ledger_no_truncate')")
            triggers = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM pg_proc WHERE proname IN ('quillmd_payment_evidence_guard', 'quillmd_livemode_guard', "
                           "'quillmd_refuse_truncate')")
            functions = cursor.fetchone()[0]
        return columns, triggers, functions

    def test_P4_reversing_0020_refuses_while_live_evidence_exists(self):
        """The refuter's P4: a live payment, 0020 reversed and re-applied: the payment read NULL and reserve() refused a
        wallet only live money funded, permanently."""
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            self.checkout('live-before-rollback')
            live = Payment.objects.get(stripe_session='cs_live-before-rollback')
            self.assertEqual(self.signed(event(True, paid_session(live, True, 'pi_live_rb'), 'evt_live_rb')).status_code, 200)
        try:
            with self.assertRaisesRegex(IrreversibleError, r'1 payment row\(s\) and 1 Stripe event row\(s\) are recorded as live') as refused:
                MigrationExecutor(connection).migrate(self.BEFORE_0020)
            for private in (live.stripe_session, 'pi_live_rb', 'evt_live_rb', str(live.pk), self.user.email):
                self.assertNotIn(private, str(refused.exception))
            self.assertIn(('core', '0020_payment_livemode'), MigrationRecorder(connection).applied_migrations())
            self.assertEqual(self.schema(), (2, 5, 3))
            self.assertIs(Payment.objects.get(pk=live.pk).livemode, True)
            self.assertIs(WebhookEvent.objects.get(event_id='evt_live_rb').livemode, True)
            with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
                self.assertFalse(sandbox_funded(Wallet.objects.get(user=self.user, kind='paid')))
                reserve(self.job('after-refused-rollback'), Decimal('2'))
        finally:
            self.to_leaf()

    def test_a_live_payment_alone_refuses_too(self):
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **REAL, **LIVE):
            self.checkout('live-never-paid')  # A live checkout nobody has paid yet: its row alone is live evidence.
        try:
            with self.assertRaisesRegex(IrreversibleError, r'1 payment row\(s\) and 0 Stripe event row\(s\) are recorded as live'):
                MigrationExecutor(connection).migrate(self.BEFORE_0020)
            self.assertEqual(self.schema(), (2, 5, 3))
        finally:
            self.to_leaf()

    def test_a_live_event_alone_refuses_too(self):
        # (A Payment row can no longer be deleted to leave the event alone: 0020's guard. So no payment is made here.)
        WebhookEvent.objects.create(event_id='evt_live_unmatched', kind='checkout.session.expired', payload_hash='0' * 64,
                                    object_data={}, status='reconciliation', livemode=True)
        try:
            with self.assertRaisesRegex(IrreversibleError, r'0 payment row\(s\) and 1 Stripe event row\(s\) are recorded as live'):
                MigrationExecutor(connection).migrate(self.BEFORE_0020)
            self.assertEqual(self.schema(), (2, 5, 3))
        finally:
            self.to_leaf()

    def test_a_database_without_live_rows_still_reverses_and_reapplies(self):
        payment, _ = self.sandbox_top_up()
        try:
            MigrationExecutor(connection).migrate(self.BEFORE_0020)
            self.assertNotIn(('core', '0020_payment_livemode'), MigrationRecorder(connection).applied_migrations())
            self.assertEqual(self.schema(), (0, 0, 0))
        finally:
            self.to_leaf()
        self.assertEqual(self.schema(), (2, 5, 3))
        self.assertIsNone(Payment.objects.get(pk=payment.pk).livemode)
