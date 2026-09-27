"""Round-5 payment evidence counterexamples. Synthetic database and mocked transports only."""
from decimal import Decimal
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase, override_settings

from core import billing
from core.models import AuditEvent, LedgerEntry, Payment, ProviderReceipt, Reservation, Usage, Wallet
from core.tests import test_v1_payment_evidence_guards as guards
from core.tests import test_v1_real_mode_payments as real
from core.tests.test_security import SyntheticFixture
from core.tests.test_v1_stripe_live import SECRET, STORAGES, event


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False,
                   STORAGES=STORAGES, QUILLMD_WELCOME_CREDIT=Decimal('0'))
class PaymentBehaviorPins(SyntheticFixture, TestCase):
    setUp = real.RealModeWorkerNeverSpendsAHoldOnSandboxMoney.setUp
    job = real.RealModeNeverSpendsSandboxMoney.job
    checkout = real.RealModeNeverSpendsSandboxMoney.checkout
    signed = real.RealModeNeverSpendsSandboxMoney.signed
    sandbox_top_up = real.RealModeNeverSpendsSandboxMoney.sandbox_top_up
    checkout_for = real.RealModeFundsOnlyWhatItCanSpend.checkout_for
    live_top_up = real.RealModeFundsOnlyWhatItCanSpend.live_top_up
    owner_of_organization = real.RealModeFundsOnlyWhatItCanSpend.owner_of_organization
    run_worker = real.RealModeWorkerNeverSpendsAHoldOnSandboxMoney.run_worker
    ANSWERS = real.RealModeWorkerNeverSpendsAHoldOnSandboxMoney.ANSWERS

    def test_live_funded_real_mode_reconciliation_collects_the_supported_difference(self):
        self.live_top_up('r5-live')
        wallet = Wallet.objects.get(user=self.user, kind='paid')
        with override_settings(**real.REAL_PAYMENTS_OFF):
            job = self.job('r5-live-charge')
            billing.reserve(job, Decimal('2'))
            usage = billing.settle(job, Decimal('1'), {'input_tokens': 1}, {'rate': '1'}, 'anthropic:synthetic')
            row = billing.reconcile_usage(usage, Decimal('1.8'), 'synthetic-r5-invoice', self.user)
        wallet.refresh_from_db()
        self.assertEqual((usage.charged_cost, row.ledger_status, row.charge_delta, wallet.balance, wallet.reserved),
                         (Decimal('1.5'), 'applied', Decimal('1.2'), Decimal('7.3'), Decimal('0')))
        self.assertEqual(LedgerEntry.objects.get(job=job, kind='reconciliation').amount, Decimal('-1.2'))
        self.assertFalse(AuditEvent.objects.filter(action='usage.reconciliation_sandbox_refused').exists())

    def test_an_organization_payers_sandbox_money_refuses_a_promotional_hold_before_the_worker_sends(self):
        department = self.owner_of_organization()
        department.organization_pays = True
        department.save(update_fields=['organization_pays'])
        with override_settings(QUILLMD_WELCOME_CREDIT=Decimal('10')):
            billing.welcome_credit(self.user)
        with override_settings(STRIPE_SECRET_KEY='rk_test_synthetic_adapter'):
            response, checkout = self.checkout_for('r5-org', f'organization:{department.organization_id}')
        self.assertEqual(response.status_code, 302)
        checkout.assert_called_once()
        payment = Payment.objects.get(stripe_session='cs_r5-org')
        self.assertEqual(self.signed(event(False, real.paid_session(payment, False, 'pi_r5_org'), 'evt_r5_org')).status_code, 200)
        wallet = Wallet.objects.get(organization=department.organization, kind='paid')
        job = self.job('r5-org-worker')
        billing.reserve(job, Decimal('2'))
        job.refresh_from_db()
        self.assertEqual(job.payer, f'organization:{department.organization_id}')
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('wallet__kind', 'amount')),
                         [('promo', Decimal('3'))])
        generate, transcribe = self.run_worker(**real.RealModeWorkerNeverSpendsAHoldOnSandboxMoney.REAL_LIVE_AI)
        generate.assert_not_called()
        transcribe.assert_not_called()
        job.refresh_from_db()
        wallet.refresh_from_db()
        self.assertEqual((job.state, wallet.balance, wallet.reserved), ('failed', Decimal('10'), Decimal('0')))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['released'])
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertTrue(AuditEvent.objects.filter(action='usage.sandbox_hold_refused', target=str(job.pk)).exists())

    def test_each_sandbox_reconciliation_refusal_is_audited_even_when_available_balance_is_short(self):
        with override_settings(QUILLMD_WELCOME_CREDIT=Decimal('10')):
            billing.welcome_credit(self.user)
        _, wallet = self.sandbox_top_up('r5-short')
        job = self.job('r5-short-reconciliation')
        billing.reserve(job, Decimal('2'))
        usage = billing.settle(job, Decimal('1'), {'input_tokens': 1}, {'rate': '1'}, 'anthropic:synthetic')
        blocker = self.job('r5-paid-wallet-held')
        billing.reserve(blocker, charge_limit=Decimal('18.5'))  # remaining promotional 8.5 and all paid 10
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance-wallet.reserved, Decimal('0'))
        with override_settings(**real.REAL_PAYMENTS_OFF):
            row = billing.reconcile_usage(usage, Decimal('1.8'), 'synthetic-r5-short-invoice', self.user)
            self.assertEqual(row.ledger_status, 'pending_funds')
            self.assertEqual(billing.apply_pending_reconciliations(actor=self.user), [])
        refusals = AuditEvent.objects.filter(action='usage.reconciliation_sandbox_refused', target=str(job.pk))
        self.assertEqual(refusals.count(), 2, 'both attempts must record the sandbox refusal before checking funds')
        self.assertFalse(LedgerEntry.objects.filter(job=job, kind='reconciliation').exists())
        wallet.refresh_from_db()
        self.assertEqual((wallet.balance, wallet.reserved), (Decimal('10'), Decimal('10')))


class GuardDefinitionPins(TestCase):
    changed = guards.TheLaunchersCheckRequiresEveryGuard.changed

    def test_replacing_each_guard_function_body_with_a_noop_is_reported(self):
        for function, names in (
                ('quillmd_append_only', {'ledger_append_only'}),
                ('quillmd_webhook_evidence_guard', {'webhook_evidence_immutable'}),
                ('quillmd_payment_evidence_guard', {'payment_evidence_immutable'}),
                ('quillmd_livemode_guard', {'webhook_livemode_immutable'}),
                ('quillmd_refuse_truncate', {'payment_no_truncate', 'webhook_no_truncate', 'ledger_no_truncate'})):
            with self.subTest(function=function):
                problems = self.changed(f'CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql '
                                        'AS $$ BEGIN RETURN NEW; END; $$')
                self.assertTrue(names.issubset(guards.reported(problems)), problems)
        self.assertEqual(billing.real_mode_payment_problems(), [])

    def test_an_update_column_list_cannot_narrow_the_payment_guard(self):
        problems = self.changed('DROP TRIGGER payment_evidence_immutable ON core_payment',
                                'CREATE TRIGGER payment_evidence_immutable BEFORE UPDATE OF request_key OR DELETE '
                                'ON core_payment FOR EACH ROW EXECUTE FUNCTION quillmd_payment_evidence_guard()')
        self.assertEqual(guards.reported(problems), {'payment_evidence_immutable'}, problems)

    def test_the_same_function_name_and_body_in_another_schema_is_not_the_installed_function(self):
        from psycopg import sql
        with transaction.atomic():
            guards.execute('CREATE SCHEMA r5_other')
            with connection.cursor() as cursor:
                cursor.execute("SELECT prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                               "WHERE n.nspname=current_schema() AND proname='quillmd_payment_evidence_guard'")
                body = cursor.fetchone()[0]
                cursor.execute(sql.SQL('CREATE FUNCTION r5_other.quillmd_payment_evidence_guard() RETURNS trigger '
                                       'LANGUAGE plpgsql AS {}').format(sql.Literal(body)))
            guards.execute('DROP TRIGGER payment_evidence_immutable ON core_payment',
                           'CREATE TRIGGER payment_evidence_immutable BEFORE UPDATE OR DELETE ON core_payment '
                           'FOR EACH ROW EXECUTE FUNCTION r5_other.quillmd_payment_evidence_guard()')
            self.assertEqual(guards.reported(billing.real_mode_payment_problems()), {'payment_evidence_immutable'})
            transaction.set_rollback(True)

    def test_extra_before_and_after_row_triggers_are_reported_without_printing_their_names(self):
        for table in ('core_payment', 'core_webhookevent', 'core_ledgerentry'):
            for timing in ('BEFORE', 'AFTER'):
                with self.subTest(table=table, timing=timing):
                    body = 'BEGIN NEW.livemode := true; RETURN NEW; END;' if table != 'core_ledgerentry' else 'BEGIN RETURN NEW; END;'
                    problems = self.changed('CREATE FUNCTION r5_relabel() RETURNS trigger LANGUAGE plpgsql AS $$ '+body+' $$',
                                            f'CREATE TRIGGER zz_private_canary {timing} INSERT OR UPDATE ON {table} '
                                            'FOR EACH ROW EXECUTE FUNCTION r5_relabel()')
                    self.assertTrue(problems, 'an extra row trigger escaped the payment evidence check')
                    self.assertNotIn('private_canary', ' '.join(problems))
        self.assertEqual(billing.real_mode_payment_problems(), [], 'the installed PostgreSQL FK triggers are allowed')

    def test_extra_before_and_after_statement_triggers_are_reported_without_printing_their_names(self):
        for table in ('core_payment', 'core_webhookevent', 'core_ledgerentry'):
            for timing in ('BEFORE', 'AFTER'):
                with self.subTest(table=table, timing=timing):
                    # Statement hooks can modify evidence while temporarily suppressing the required row guards.
                    body = ("BEGIN PERFORM set_config('session_replication_role','replica',true); "
                            "UPDATE core_payment SET livemode=true; "
                            "PERFORM set_config('session_replication_role','origin',true); RETURN NULL; END;")
                    problems = self.changed('CREATE FUNCTION r5_statement_relabel() RETURNS trigger LANGUAGE plpgsql '
                                            'SECURITY DEFINER AS $$ '+body+' $$',
                                            f'CREATE TRIGGER zz_private_statement_canary {timing} INSERT ON {table} '
                                            'FOR EACH STATEMENT EXECUTE FUNCTION r5_statement_relabel()')
                    self.assertEqual(guards.reported(problems), {f'unexpected_statement_triggers:{table}'}, problems)
                    self.assertNotIn('private_statement_canary', ' '.join(problems))
        self.assertEqual(billing.real_mode_payment_problems(), [], 'required TRUNCATE statement guards remain allowed')


class RuntimeReplicationPins(TestCase):
    changed = guards.TheLaunchersCheckRequiresEveryGuard.changed

    def test_current_replication_mode_must_be_origin(self):
        for value in ('replica', 'local'):
            with self.subTest(value=value):
                problems = self.changed(f"SET LOCAL session_replication_role = '{value}'")
                self.assertTrue(any('session_replication_role' in problem for problem in problems), problems)
        self.assertEqual(billing.real_mode_payment_problems(), [])

    def test_persistent_defaults_are_checked_for_the_database_and_runtime_role(self):
        from psycopg import sql
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user')
            database, role = cursor.fetchone()
        for statement in (
                sql.SQL('ALTER ROLE {} SET session_replication_role = replica').format(sql.Identifier(role)),
                sql.SQL('ALTER DATABASE {} SET session_replication_role = replica').format(sql.Identifier(database)),
                sql.SQL('ALTER ROLE {} IN DATABASE {} SET session_replication_role = replica').format(
                    sql.Identifier(role), sql.Identifier(database)),
                sql.SQL('ALTER ROLE ALL SET session_replication_role = replica')):
            with self.subTest(statement=statement):
                problems = self.changed(statement)
                self.assertTrue(any('session_replication_role' in problem for problem in problems), problems)
        self.assertEqual(billing.real_mode_payment_problems(), [])

    def test_effective_default_uses_role_and_database_precedence_and_ignores_other_roles(self):
        from psycopg import sql
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user')
            database, role = cursor.fetchone()
        self.assertEqual(self.changed(
            sql.SQL('ALTER DATABASE {} SET session_replication_role = replica').format(sql.Identifier(database)),
            sql.SQL('ALTER ROLE {} SET session_replication_role = origin').format(sql.Identifier(role))), [])
        self.assertEqual(self.changed(
            sql.SQL('ALTER ROLE {} SET session_replication_role = replica').format(sql.Identifier(role)),
            sql.SQL('ALTER ROLE {} IN DATABASE {} SET session_replication_role = origin').format(
                sql.Identifier(role), sql.Identifier(database))), [])
        self.assertEqual(self.changed('CREATE ROLE r5_unrelated NOLOGIN',
                                     'ALTER ROLE r5_unrelated SET session_replication_role = replica'), [])

    def test_set_role_does_not_hide_the_runtime_roles_persistent_replication_mode(self):
        # PostgreSQL does not apply login defaults at SET ROLE. Inspect the active runtime identity's catalog too.
        problems = self.changed('CREATE ROLE r5_runtime NOLOGIN', 'GRANT USAGE ON SCHEMA public TO r5_runtime',
                                'GRANT SELECT ON core_payment, core_webhookevent, core_wallet, core_ledgerentry TO r5_runtime',
                                'ALTER ROLE r5_runtime SET session_replication_role = replica',
                                'SET LOCAL ROLE r5_runtime')
        self.assertTrue(any('session_replication_role' in problem for problem in problems), problems)
