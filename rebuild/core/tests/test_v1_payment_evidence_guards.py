"""The payment evidence real data mode reads cannot be relabelled, and the launcher's check proves its guards exist.

R4-4 (round-4 refutation): 0020 was amended after an earlier version had merged into release/v1, so a database that
applied the earlier version never receives the guards (`migrate` plans nothing), and nothing checked that the triggers
exist; reversing it then failed on the trigger it expected to drop. Now `real_mode_payment_problems()`, and therefore
`manage.py real_mode_payment_check`, which the V1 launcher runs before any surface starts, reads pg_trigger (read-only)
and reports every guard real data mode relies on that is missing, disabled, conditional or not what the migrations
installed; and 0020's reverse tolerates a missing trigger, so such a database can be reversed and re-applied.

R4-1 (round-4 refutation): real data mode decides whether a paid balance holds sandbox money from Payment rows (their
existence, wallet, status, stripe_intent and livemode), Stripe event rows (their livemode) and 'payment' ledger credits.
Round 3 guarded only an UPDATE of livemode, so the refuter relabelled sandbox money as live three other ways:

A1  delete the sandbox Payment and create a live one with the same stripe_intent;
A2  mark the sandbox Payment expired with no stripe_intent, then give that intent to an unpaid live checkout;
A3  TRUNCATE core_webhookevent (row-level DELETE triggers do not fire on TRUNCATE) plus A1, so the launcher's check
    returned no problem at all.

Each ended with reserve() in real data mode holding sandbox money. Those statements must be refused for the test
database's superuser owner and for a role holding exactly the runtime role's grants (plus TRUNCATE, so that the trigger,
not a missing privilege, is what refuses), while every write the application itself makes to a Payment still works.

No provider is called: Stripe Checkout is a mock and every webhook is signed locally with a synthetic secret.
"""
import re
import uuid
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase, override_settings

from core.billing import real_mode_payment_problems, reserve, sandbox_funded
from core.models import LedgerEntry, Payment, Reservation, Wallet, WebhookEvent
from core.tests.test_security import SyntheticFixture
from core.tests import test_v1_stripe_live as stripe_live  # Modules, so their TestCases are not collected twice here.
from core.tests import test_v1_real_mode_payments as real_mode
from core.tests.test_v1_stripe_live import LIVE, SECRET, STORAGES, event

#: Every guard the sandbox-money rule relies on, written out here rather than read from the code, so that a guard dropped
#: from the code's list is caught: (table, trigger) -> the statement that recreates it exactly as the migrations install it.
GUARDS = {
    ('core_ledgerentry', 'ledger_append_only'):
        'CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE ON core_ledgerentry FOR EACH ROW EXECUTE FUNCTION quillmd_append_only()',
    ('core_webhookevent', 'webhook_evidence_immutable'):
        'CREATE TRIGGER webhook_evidence_immutable BEFORE UPDATE OR DELETE ON core_webhookevent FOR EACH ROW '
        'EXECUTE FUNCTION quillmd_webhook_evidence_guard()',
    ('core_payment', 'payment_evidence_immutable'):
        'CREATE TRIGGER payment_evidence_immutable BEFORE UPDATE OR DELETE ON core_payment FOR EACH ROW '
        'EXECUTE FUNCTION quillmd_payment_evidence_guard()',
    ('core_webhookevent', 'webhook_livemode_immutable'):
        'CREATE TRIGGER webhook_livemode_immutable BEFORE UPDATE ON core_webhookevent FOR EACH ROW EXECUTE FUNCTION quillmd_livemode_guard()',
    ('core_payment', 'payment_no_truncate'):
        'CREATE TRIGGER payment_no_truncate BEFORE TRUNCATE ON core_payment FOR EACH STATEMENT EXECUTE FUNCTION quillmd_refuse_truncate()',
    ('core_webhookevent', 'webhook_no_truncate'):
        'CREATE TRIGGER webhook_no_truncate BEFORE TRUNCATE ON core_webhookevent FOR EACH STATEMENT EXECUTE FUNCTION quillmd_refuse_truncate()',
    ('core_ledgerentry', 'ledger_no_truncate'):
        'CREATE TRIGGER ledger_no_truncate BEFORE TRUNCATE ON core_ledgerentry FOR EACH STATEMENT EXECUTE FUNCTION quillmd_refuse_truncate()',
}
#: What 0020 itself installs, and the trigger name an earlier version of it used.
INSTALLED_BY_0020 = ['payment_evidence_immutable', 'webhook_livemode_immutable', 'payment_no_truncate', 'webhook_no_truncate',
                     'ledger_no_truncate']
DROP_EVERYTHING_0020_INSTALLS = ['DROP TRIGGER payment_evidence_immutable ON core_payment',
                                 'DROP TRIGGER webhook_livemode_immutable ON core_webhookevent',
                                 'DROP TRIGGER payment_no_truncate ON core_payment',
                                 'DROP TRIGGER webhook_no_truncate ON core_webhookevent',
                                 'DROP TRIGGER ledger_no_truncate ON core_ledgerentry',
                                 'DROP FUNCTION quillmd_payment_evidence_guard()', 'DROP FUNCTION quillmd_livemode_guard()',
                                 'DROP FUNCTION quillmd_refuse_truncate()']
BEFORE_0020 = [('core', '0019_clinicinvitation')]


def execute(*statements):
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def reported(problems):
    """The guard names the check's guard line names; empty when there is no such line."""
    for problem in problems:
        found = re.search(r'guard trigger\(s\) missing, disabled or altered \(([^)]*)\)', problem)
        if found:
            return set(found.group(1).split(', '))
    return set()


def to_leaf():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


class TheLaunchersCheckRequiresEveryGuard(TestCase):
    def changed(self, *statements):
        """Apply DDL in a savepoint, read the check inside it, and roll the DDL back."""
        with transaction.atomic():
            execute(*statements)
            problems = real_mode_payment_problems()
            transaction.set_rollback(True)
        return problems

    def test_a_complete_database_reports_no_guard_problem(self):
        self.assertEqual(real_mode_payment_problems(), [])

    def test_each_guard_missing_disabled_or_replica_only_is_reported(self):
        """The refuter's R4-4: a trigger that is not there (or does not fire) and the check still said the database may
        run real data mode."""
        for (table, name), _ in GUARDS.items():
            for change, statement in (('dropped', f'DROP TRIGGER {name} ON {table}'),
                                      ('disabled', f'ALTER TABLE {table} DISABLE TRIGGER {name}'),
                                      ('replica only', f'ALTER TABLE {table} ENABLE REPLICA TRIGGER {name}')):
                with self.subTest(guard=name, change=change):
                    problems = self.changed(statement)
                    self.assertEqual(reported(problems), {name}, problems)
                    self.assertEqual(len(problems), 1, problems)
            with self.subTest(guard=name, change='enabled always: it still fires'):
                self.assertEqual(self.changed(f'ALTER TABLE {table} ENABLE ALWAYS TRIGGER {name}'), [])
        self.assertEqual(real_mode_payment_problems(), [])

    def test_a_guard_recreated_narrower_conditional_or_on_another_function_is_reported(self):
        for (table, name), create in GUARDS.items():
            narrower = (create.replace('BEFORE UPDATE OR DELETE', 'BEFORE DELETE').replace('BEFORE UPDATE ON', 'BEFORE INSERT ON')
                        .replace('BEFORE TRUNCATE', 'AFTER TRUNCATE'))
            conditional = create.replace('FOR EACH ROW', 'FOR EACH ROW WHEN (false)').replace(
                'FOR EACH STATEMENT', 'FOR EACH STATEMENT WHEN (false)')
            other_function = create.rsplit('EXECUTE FUNCTION', 1)[0] + 'EXECUTE FUNCTION quillmd_job_financial_guard()'
            for change, replacement in (('narrower', narrower), ('conditional', conditional), ('another function', other_function)):
                with self.subTest(guard=name, change=change):
                    self.assertNotEqual(replacement, create)
                    problems = self.changed(f'DROP TRIGGER {name} ON {table}', replacement)
                    self.assertEqual(reported(problems), {name}, problems)
            with self.subTest(guard=name, change='recreated exactly'):
                self.assertEqual(self.changed(f'DROP TRIGGER {name} ON {table}', create), [])

    def test_the_command_refuses_and_names_the_missing_guards(self):
        with transaction.atomic():
            execute('DROP TRIGGER webhook_livemode_immutable ON core_webhookevent',
                    'ALTER TABLE core_ledgerentry DISABLE TRIGGER ledger_append_only')
            with self.assertRaises(CommandError) as refused:
                call_command('real_mode_payment_check', stdout=StringIO())
            transaction.set_rollback(True)
        message = str(refused.exception)
        self.assertIn('2 payment evidence guard trigger(s) missing, disabled or altered', message)
        self.assertEqual(reported([message]), {'ledger_append_only', 'webhook_livemode_immutable'})
        self.assertEqual(real_mode_payment_problems(), [])


class ReversingAnEarlierPaymentModeMigration(TransactionTestCase):
    """The refuter's R4-4 upgrade path: a database that applied an earlier 0020 (the first installed no trigger, the
    second only payment_livemode_immutable and webhook_livemode_immutable). With no live rows its reverse must run, and
    re-applying installs every guard."""

    def setUp(self):
        # Every guard is in place and enabled when each test starts, including after the previous test's flush, which
        # lifts the TRUNCATE guards for itself alone (core/tests/__init__.py).
        self.assertEqual(real_mode_payment_problems(), [])

    def tearDown(self):
        # Whatever happened above, leave every guard installed for the tests that follow.
        to_leaf()
        if reported(real_mode_payment_problems()):
            MigrationExecutor(connection).migrate(BEFORE_0020)
            to_leaf()
        super().tearDown()

    def test_a_database_that_applied_the_trigger_less_0020_is_refused_then_reverses_and_reapplies(self):
        execute(*DROP_EVERYTHING_0020_INSTALLS)
        self.assertIn(('core', '0020_payment_livemode'), MigrationRecorder(connection).applied_migrations())
        self.assertEqual(reported(real_mode_payment_problems()), set(INSTALLED_BY_0020))
        MigrationExecutor(connection).migrate(BEFORE_0020)
        self.assertNotIn(('core', '0020_payment_livemode'), MigrationRecorder(connection).applied_migrations())
        to_leaf()
        self.assertEqual(real_mode_payment_problems(), [])

    def test_one_missing_trigger_does_not_stop_the_reverse(self):
        for name, table in (('webhook_livemode_immutable', 'core_webhookevent'), ('payment_evidence_immutable', 'core_payment'),
                            ('ledger_no_truncate', 'core_ledgerentry')):
            with self.subTest(missing=name):
                execute(f'DROP TRIGGER {name} ON {table}')
                MigrationExecutor(connection).migrate(BEFORE_0020)  # Before: 'trigger "..." ... does not exist'.
                self.assertEqual(self.installed(), (0, 0))
                to_leaf()
                self.assertEqual(real_mode_payment_problems(), [])
                self.assertEqual(self.installed(), (5, 3))

    def test_the_round_3_version_with_its_earlier_trigger_name_reverses_and_reapplies(self):
        """The second earlier 0020 guarded core_payment with payment_livemode_immutable (livemode only) and installed no
        TRUNCATE guard: the check names what is missing, and reverse plus re-apply replaces the old trigger."""
        execute(*DROP_EVERYTHING_0020_INSTALLS)
        execute("CREATE FUNCTION quillmd_livemode_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                "IF NEW.livemode IS DISTINCT FROM OLD.livemode THEN RAISE EXCEPTION 'A recorded payment mode is immutable'; "
                "END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER payment_livemode_immutable BEFORE UPDATE ON core_payment FOR EACH ROW EXECUTE FUNCTION quillmd_livemode_guard()',
                GUARDS[('core_webhookevent', 'webhook_livemode_immutable')])
        self.assertEqual(reported(real_mode_payment_problems()),
                         {'payment_evidence_immutable', 'payment_no_truncate', 'webhook_no_truncate', 'ledger_no_truncate'})
        MigrationExecutor(connection).migrate(BEFORE_0020)
        self.assertEqual(self.installed(), (0, 0))
        to_leaf()
        self.assertEqual(real_mode_payment_problems(), [])
        self.assertEqual(self.installed(), (5, 3))

    @staticmethod
    def installed():
        """(triggers 0020 or an earlier version of it installs, their functions) present now."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM pg_trigger WHERE tgname = ANY(%s)', [INSTALLED_BY_0020 + ['payment_livemode_immutable']])
            triggers = cursor.fetchone()[0]
            cursor.execute('SELECT count(*) FROM pg_proc WHERE proname = ANY(%s)',
                           [['quillmd_payment_evidence_guard', 'quillmd_livemode_guard', 'quillmd_refuse_truncate']])
            return triggers, cursor.fetchone()[0]


SETTINGS = dict(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES,
                QUILLMD_WELCOME_CREDIT=Decimal('0'))


def attempt(statement):
    """Run one statement in its own savepoint: 'done', or 'refused: <the database's first line>'."""
    try:
        with transaction.atomic():
            statement()
        return 'done'
    except DatabaseError as exc:
        return 'refused: ' + str(exc).splitlines()[0]


def sql(text, params=()):
    def run():
        with connection.cursor() as cursor:
            cursor.execute(text, params)
    return run


@override_settings(**SETTINGS)
class SandboxEvidenceCannotBeRelabelledLive(SyntheticFixture, TestCase):
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed
    sandbox_top_up = real_mode.RealModeNeverSpendsSandboxMoney.sandbox_top_up
    job = real_mode.RealModeNeverSpendsSandboxMoney.job

    def paid_sandbox_top_up(self):
        """sandbox_top_up() returns the Payment as read before its webhook: re-read it, so its stripe_intent is set."""
        payment, wallet = self.sandbox_top_up()
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.livemode, payment.stripe_intent), ('paid', False, 'pi_sandbox-top-up'))
        return payment, wallet

    def live_unpaid_checkout(self, nonce):
        """An unpaid checkout created in live mode on the user's personal paid balance (synthetic data, live Stripe)."""
        with override_settings(STRIPE_SECRET_KEY='rk_live_synthetic_adapter', **LIVE):
            self.assertTrue(self.checkout(nonce)[1].called)
        live = Payment.objects.get(stripe_session=f'cs_{nonce}')
        self.assertEqual((live.status, live.livemode, live.stripe_intent), ('pending', True, None))
        return live

    def forge_live(self, wallet, intent, session):
        return lambda: Payment.objects.create(user=self.user, wallet=wallet, amount_cents=1000, stripe_session=session,
                                              stripe_intent=intent, status='paid', livemode=True)

    def assert_real_mode_never_spends(self, wallet, label, steps):
        """The harm itself: reserve() in real data mode must refuse the balance sandbox money funded."""
        with override_settings(**real_mode.REAL_PAYMENTS_OFF):
            job = self.job(label)
            try:
                reserve(job, Decimal('2'))
                refusal = ''
            except ValidationError as exc:
                refusal = ' '.join(exc.messages)
        held = list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount'))
        self.assertEqual(held, [], f'{label}: real data mode reserve() held sandbox money after {steps}')
        self.assertIn('sandbox', refusal)
        self.assertTrue(sandbox_funded(wallet), f'{label}: the sandbox-funded balance reads as live-funded after {steps}')

    def test_A1_a_sandbox_payment_cannot_be_deleted_and_recreated_live(self):
        """The refuter's A1: delete the sandbox Payment, create a live one with the same stripe_intent."""
        payment, wallet = self.paid_sandbox_top_up()
        steps = [('delete the sandbox payment', attempt(lambda: Payment.objects.filter(pk=payment.pk).delete())),
                 ('create a live payment with its intent', attempt(self.forge_live(wallet, payment.stripe_intent, 'cs_forged_a1')))]
        self.assert_real_mode_never_spends(wallet, 'after-A1', steps)
        self.assertTrue(steps[0][1].startswith('refused: Payment evidence cannot be deleted'), steps)
        self.assertTrue(steps[1][1].startswith('refused: duplicate key'), steps)  # The sandbox row still holds its intent.
        self.assertIs(Payment.objects.get(pk=payment.pk).livemode, False)
        self.assertTrue(attempt(sql('DELETE FROM core_payment WHERE id = %s', [payment.pk])).startswith(
            'refused: Payment evidence cannot be deleted'))
        # An unpaid row is evidence too (the launcher's check counts it): it cannot be deleted either.
        live = self.live_unpaid_checkout('live-unpaid-delete')
        self.assertTrue(attempt(lambda: Payment.objects.filter(pk=live.pk).delete()).startswith(
            'refused: Payment evidence cannot be deleted'))

    def test_A2_a_sandbox_payment_cannot_hand_its_intent_to_a_live_checkout(self):
        """The refuter's A2: mark the sandbox payment expired with no stripe_intent, then give that intent to an unpaid
        live checkout on the same wallet."""
        payment, wallet = self.paid_sandbox_top_up()
        live = self.live_unpaid_checkout('live-unpaid')
        intent = payment.stripe_intent
        steps = [('sandbox row: expired, no intent', attempt(
                     lambda: Payment.objects.filter(pk=payment.pk).update(status='expired', stripe_intent=None))),
                 ('live checkout takes the intent', attempt(
                     lambda: Payment.objects.filter(pk=live.pk).update(stripe_intent=intent)))]
        self.assert_real_mode_never_spends(wallet, 'after-A2', steps)
        self.assertTrue(steps[0][1].startswith('refused: Recorded payment evidence is immutable'), steps)
        self.assertTrue(steps[1][1].startswith('refused: duplicate key'), steps)
        # Each half of the first step is refused on its own.
        self.assertTrue(attempt(lambda: Payment.objects.filter(pk=payment.pk).update(status='expired')).startswith(
            'refused: A paid payment is final'))
        for value in (None, 'pi_other', ''):
            with self.subTest(stripe_intent=value):
                self.assertTrue(attempt(lambda: Payment.objects.filter(pk=payment.pk).update(stripe_intent=value)).startswith(
                    'refused: Recorded payment evidence is immutable'))
        self.assertEqual(Payment.objects.filter(pk=payment.pk).values_list('status', 'stripe_intent').get(), ('paid', intent))

    def test_A3_truncating_the_evidence_cannot_blind_the_launchers_check(self):
        """The refuter's A3: TRUNCATE core_webhookevent, plus A1, and real_mode_payment_problems() returned []."""
        payment, wallet = self.paid_sandbox_top_up()
        steps = [('truncate Stripe events', attempt(sql('TRUNCATE core_webhookevent'))),
                 ('delete the sandbox payment', attempt(lambda: Payment.objects.filter(pk=payment.pk).delete())),
                 ('create a live payment with its intent', attempt(self.forge_live(wallet, payment.stripe_intent, 'cs_forged_a3')))]
        problems = real_mode_payment_problems()
        self.assertEqual(len(problems), 3, (problems, steps))
        for text in ('1 payment row(s)', '1 Stripe event row(s)', '1 paid wallet(s)'):
            self.assertTrue(any(text in problem for problem in problems), (text, problems))
        self.assert_real_mode_never_spends(wallet, 'after-A3', steps)
        self.assertTrue(steps[0][1].startswith('refused: QuillMD payment evidence cannot be truncated (core_webhookevent)'), steps)
        # Every table the check reads refuses TRUNCATE, however it is named. (A plain TRUNCATE core_payment is refused
        # before any trigger, by core_refund's foreign key; naming core_refund too reaches the trigger.) Inside this test's
        # transaction the deferred foreign-key checks of the rows written above are still pending, and PostgreSQL refuses to
        # TRUNCATE a table with pending trigger events before any trigger runs; a real session has committed its writes.
        # Run those checks now, so that each refusal below is the guard's own.
        execute('SET CONSTRAINTS ALL IMMEDIATE')
        for table, statements in (('core_payment', ['TRUNCATE core_payment, core_refund', 'TRUNCATE core_payment CASCADE',
                                                    'TRUNCATE core_payment RESTART IDENTITY CASCADE']),
                                  ('core_webhookevent', ['TRUNCATE core_webhookevent', 'TRUNCATE core_webhookevent CASCADE']),
                                  ('core_ledgerentry', ['TRUNCATE core_ledgerentry', 'TRUNCATE core_ledgerentry CASCADE'])):
            for statement in statements:
                with self.subTest(statement=statement):
                    outcome = attempt(sql(statement))
                    self.assertTrue(outcome.startswith(f'refused: QuillMD payment evidence cannot be truncated ({table})'), outcome)
        outcome = attempt(sql('TRUNCATE core_payment'))
        self.assertTrue(outcome.startswith('refused: '), outcome)
        # A TRUNCATE of another table that CASCADEs into these is refused too.
        outcome = attempt(sql('TRUNCATE core_wallet CASCADE'))
        self.assertTrue(outcome.startswith('refused: QuillMD payment evidence cannot be truncated'), outcome)
        self.assertEqual((Payment.objects.count(), WebhookEvent.objects.count(), LedgerEntry.objects.filter(kind='payment').count()),
                         (1, 1, 1))

    def test_a_payments_wallet_amount_and_mode_never_change_and_paid_is_final(self):
        payment, wallet = self.paid_sandbox_top_up()
        other = Wallet.objects.get(user=self.make_scope('other-wallet')[0], kind='paid')
        for field, value, reason in (('wallet_id', other.pk, 'Recorded payment evidence is immutable'),
                                     ('amount_cents', 500, 'Recorded payment evidence is immutable'),
                                     ('livemode', True, 'A recorded payment mode is immutable')):
            with self.subTest(field=field):
                self.assertTrue(attempt(lambda: Payment.objects.filter(pk=payment.pk).update(**{field: value})).startswith(
                    'refused: ' + reason))
        for status in ('creating', 'pending', 'processing', 'uncertain', 'failed', 'expired', 'refunded', ''):
            with self.subTest(status=status):
                self.assertTrue(attempt(lambda: Payment.objects.filter(pk=payment.pk).update(status=status)).startswith(
                    'refused: A paid payment is final'))
        # An unpaid row's wallet and amount are fixed too: checkout binds them to what the payer authorized.
        live = self.live_unpaid_checkout('live-unpaid-fields')
        for field, value in (('wallet_id', other.pk), ('amount_cents', 500)):
            with self.subTest(unpaid_field=field):
                self.assertTrue(attempt(lambda: Payment.objects.filter(pk=live.pk).update(**{field: value})).startswith(
                    'refused: Recorded payment evidence is immutable'))
        self.assertTrue(sandbox_funded(wallet))
        self.assertFalse(sandbox_funded(other))

    def test_a_role_with_the_runtime_grants_can_neither_relabel_the_evidence_nor_unguard_it(self):
        """The runtime role (ops/database_roles.py) holds SELECT, INSERT, UPDATE and DELETE and owns nothing. This probe
        role is also granted TRUNCATE, so each refusal below is the trigger's, not a missing privilege's. It cannot drop
        or disable a trigger: only the owner can."""
        payment, wallet = self.paid_sandbox_top_up()
        live = self.live_unpaid_checkout('live-unpaid-runtime')
        other = Wallet.objects.get(user=self.make_scope('runtime-other')[0], kind='paid')
        intent = payment.stripe_intent
        role = 'quillmd_runtime_probe_' + uuid.uuid4().hex[:12]
        execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOINHERIT',  # Rolled back with the test.
                f'GRANT USAGE ON SCHEMA public TO {role}',
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}',
                f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}',
                f'GRANT TRUNCATE ON core_payment, core_refund, core_webhookevent, core_ledgerentry TO {role}',
                'SET CONSTRAINTS ALL IMMEDIATE',  # See test_A3: no pending foreign-key events, so each TRUNCATE meets the guard.
                f'SET ROLE {role}')
        try:
            # (what the probe role runs, its outcome, the refusal it must meet)
            steps = [
                ('A2: sandbox row expired, intent cleared', attempt(sql(
                    "UPDATE core_payment SET status = 'expired', stripe_intent = NULL WHERE id = %s", [payment.pk])),
                 'Recorded payment evidence is immutable'),
                ('A2: live checkout takes the intent', attempt(sql(
                    'UPDATE core_payment SET stripe_intent = %s WHERE id = %s', [intent, live.pk])),
                 'duplicate key value violates unique constraint'),
                ('A3: truncate Stripe events', attempt(sql('TRUNCATE core_webhookevent')),
                 'QuillMD payment evidence cannot be truncated (core_webhookevent)'),
                ('A1: delete the sandbox payment', attempt(sql('DELETE FROM core_payment WHERE id = %s', [payment.pk])),
                 'Payment evidence cannot be deleted'),
                ('A1: insert a live payment with its intent', attempt(self.forge_live(wallet, intent, 'cs_forged_runtime')),
                 'duplicate key value violates unique constraint'),
                ('truncate payments', attempt(sql('TRUNCATE core_payment, core_refund')),
                 'QuillMD payment evidence cannot be truncated (core_payment)'),
                ('truncate the ledger', attempt(sql('TRUNCATE core_ledgerentry')),
                 'QuillMD payment evidence cannot be truncated (core_ledgerentry)'),
                ('relabel the mode', attempt(sql('UPDATE core_payment SET livemode = true WHERE id = %s', [payment.pk])),
                 'A recorded payment mode is immutable'),
                ('move the payment to another wallet', attempt(sql(
                    'UPDATE core_payment SET wallet_id = %s WHERE id = %s', [other.pk, payment.pk])),
                 'Recorded payment evidence is immutable'),
                ('delete a Stripe event', attempt(sql('DELETE FROM core_webhookevent')), 'Signed payment evidence cannot be deleted'),
                ('drop a guard', attempt(sql('DROP TRIGGER webhook_livemode_immutable ON core_webhookevent')),
                 'must be owner of relation core_webhookevent'),
                ('disable the guards', attempt(sql('ALTER TABLE core_payment DISABLE TRIGGER USER')),
                 'must be owner of table core_payment'),
                ('switch triggers off for the session', attempt(sql('SET session_replication_role = replica')),
                 'permission denied to set parameter "session_replication_role"'),
            ]
            # Positive control: the probe role writes what the application writes.
            control = attempt(sql("UPDATE core_payment SET checkout_url = 'https://checkout.stripe.com/c/pay/probe' WHERE id = %s",
                                  [live.pk]))
        finally:
            execute('RESET ROLE')
        self.assertEqual(control, 'done')
        self.assert_real_mode_never_spends(wallet, 'after-runtime-role', steps)
        self.assertEqual(len(real_mode_payment_problems()), 3, real_mode_payment_problems())
        for name, outcome, reason in steps:
            with self.subTest(statement=name):
                self.assertTrue(outcome.startswith('refused: ' + reason), outcome)


@override_settings(**SETTINGS)
class EveryPaymentWriteTheAppMakesStillWorks(SyntheticFixture, TestCase):
    """The guards must refuse relabelling and nothing else. These are every write the application makes to a Payment,
    found by reading every writer (core/views.py checkout; core/billing.py checkout_event and credit_payment; nothing in
    the application deletes a Payment), each driven through the application's own code:

        insert                     'creating', livemode recorded (checkout's get_or_create)
        creating   -> pending      Checkout Session created: stripe_session and checkout_url set
        creating   -> uncertain    Session.create failed
        creating                   stripe_session bound by the first checkout event when still unset
        unpaid     -> processing   a checkout event that is not paid yet
        unpaid     -> failed       checkout.session.async_payment_failed
        unpaid     -> expired      checkout.session.expired (failed -> expired and expired -> failed too)
        unpaid     -> paid         credit_payment: status and stripe_intent in one write, from every unpaid status
        paid       -> paid         a replayed paid event, and an expired or failed event after payment: no write
        paid       -> paid         the checkout view's late save (stripe_session, checkout_url, status unchanged) when
                                   the webhook settled the payment before Session.create returned
        any                        request_key and checkout_url (the private-beta backfill), a same-value save()

    Green before and after 0020's guards.
    """
    setUp = stripe_live.LiveCheckoutAndSettlement.setUp
    checkout = stripe_live.LiveCheckoutAndSettlement.checkout
    signed = stripe_live.LiveCheckoutAndSettlement.signed

    def send(self, payment, kind, nonce, session=None, **fields):
        obj = {'id': session or payment.stripe_session, 'payment_status': 'unpaid', 'currency': 'usd',
               'amount_total': payment.amount_cents, 'metadata': {'payment_id': str(payment.pk)}, 'mode': 'payment',
               'livemode': False, **fields}
        response = self.signed({**event(False, obj, f'evt_{nonce}'), 'type': kind})
        self.assertEqual(response.status_code, 200, kind)
        payment.refresh_from_db()
        return payment.status

    def created(self, nonce):
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            self.assertEqual(self.checkout(nonce)[0].status_code, 302)
        return Payment.objects.get(stripe_session=f'cs_{nonce}')

    def paid(self, payment, nonce, **kwargs):
        return self.send(payment, 'checkout.session.completed', nonce, payment_status='paid', payment_intent=f'pi_{nonce}', **kwargs)

    def test_creating_to_pending_and_to_uncertain(self):
        payment = self.created('to-pending')
        self.assertEqual((payment.status, payment.livemode, payment.checkout_url), ('pending', False, 'https://checkout.stripe.com/c/pay/synthetic'))
        token = signing.dumps({'user': str(self.user.pk), 'nonce': 'to-uncertain'}, salt='checkout-authorization')
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'), \
                patch('stripe.checkout.Session.create', side_effect=RuntimeError('synthetic outage')):
            self.client.post('/billing/checkout/', {'amount': '10.00', 'consent': 'on', 'checkout_token': token})
        self.assertEqual(Payment.objects.get(stripe_session__isnull=True).status, 'uncertain')

    def test_every_unpaid_status_moves_and_every_one_can_become_paid(self):
        payment = self.created('walk')
        path = [payment.status,
                self.send(payment, 'checkout.session.completed', 'walk-1'),             # pending -> processing
                self.send(payment, 'checkout.session.async_payment_failed', 'walk-2'),  # processing -> failed
                self.send(payment, 'checkout.session.expired', 'walk-3'),               # failed -> expired
                self.send(payment, 'checkout.session.async_payment_failed', 'walk-4')]  # expired -> failed
        self.assertEqual(path, ['pending', 'processing', 'failed', 'expired', 'failed'])
        uncertain = self.created('uncertain-processing')
        Payment.objects.filter(pk=uncertain.pk).update(status='uncertain')
        self.assertEqual(self.send(uncertain, 'checkout.session.completed', 'uncertain-processing'), 'processing')
        for start in ('pending', 'processing', 'uncertain', 'failed', 'expired'):
            with self.subTest(start=start):
                row = self.created(f'from-{start}')
                Payment.objects.filter(pk=row.pk).update(status=start)
                self.assertEqual(self.paid(row, f'from-{start}'), 'paid')
                self.assertEqual(row.stripe_intent, f'pi_from-{start}')
        # 'creating' with no session yet: the paid event binds the session, then credits.
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        creating = Payment.objects.create(user=self.user, wallet=wallet, amount_cents=1000, status='creating', livemode=False,
                                          request_key='synthetic-creating')
        self.assertEqual(self.paid(creating, 'from-creating', session='cs_from-creating'), 'paid')
        self.assertEqual((creating.stripe_session, creating.stripe_intent), ('cs_from-creating', 'pi_from-creating'))
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 60)

    def test_a_paid_payment_takes_every_later_event_and_save_without_changing(self):
        payment = self.created('settled')
        self.assertEqual(self.paid(payment, 'settled'), 'paid')
        for kind in ('checkout.session.completed', 'checkout.session.async_payment_failed', 'checkout.session.expired'):
            with self.subTest(kind=kind):
                fields = {'payment_status': 'paid', 'payment_intent': 'pi_settled'} if kind.endswith('completed') else {}
                self.assertEqual(self.send(payment, kind, 'settled-' + kind.rsplit('.', 1)[1], **fields), 'paid')
        # The checkout view's late save, exactly as it writes it.
        payment.checkout_url = 'https://checkout.stripe.com/c/pay/synthetic-late'
        payment.save(update_fields=['stripe_session', 'checkout_url', 'status'])
        Payment.objects.filter(pk=payment.pk).update(request_key='backfilled-key', checkout_url='https://checkout.stripe.com/c/pay/backfill')
        payment.refresh_from_db()
        payment.save()
        self.assertEqual((payment.status, payment.stripe_intent, payment.request_key), ('paid', 'pi_settled', 'backfilled-key'))
        self.assertEqual(Wallet.objects.get(user=self.user, kind='paid').balance, 10)
