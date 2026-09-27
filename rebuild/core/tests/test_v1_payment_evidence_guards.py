"""The payment evidence real data mode reads cannot be relabelled, and the launcher's check proves its guards exist.

R4-4 (round-4 refutation): 0020 was amended after an earlier version had merged into release/v1, so a database that
applied the earlier version never receives the guards (`migrate` plans nothing), and nothing checked that the triggers
exist; reversing it then failed on the trigger it expected to drop. Now `real_mode_payment_problems()`, and therefore
`manage.py real_mode_payment_check`, which the V1 launcher runs before any surface starts, reads pg_trigger (read-only)
and reports every guard real data mode relies on that is missing, disabled, conditional or not what the migrations
installed; and 0020's reverse tolerates a missing trigger, so such a database can be reversed and re-applied.
"""
import re
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase

from core.billing import real_mode_payment_problems

#: Every guard the sandbox-money rule relies on, written out here rather than read from the code, so that a guard dropped
#: from the code's list is caught: (table, trigger) -> the statement that recreates it exactly as the migrations install it.
GUARDS = {
    ('core_ledgerentry', 'ledger_append_only'):
        'CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE ON core_ledgerentry FOR EACH ROW EXECUTE FUNCTION quillmd_append_only()',
    ('core_webhookevent', 'webhook_evidence_immutable'):
        'CREATE TRIGGER webhook_evidence_immutable BEFORE UPDATE OR DELETE ON core_webhookevent FOR EACH ROW '
        'EXECUTE FUNCTION quillmd_webhook_evidence_guard()',
    ('core_payment', 'payment_livemode_immutable'):
        'CREATE TRIGGER payment_livemode_immutable BEFORE UPDATE ON core_payment FOR EACH ROW EXECUTE FUNCTION quillmd_livemode_guard()',
    ('core_webhookevent', 'webhook_livemode_immutable'):
        'CREATE TRIGGER webhook_livemode_immutable BEFORE UPDATE ON core_webhookevent FOR EACH ROW EXECUTE FUNCTION quillmd_livemode_guard()',
}
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
            narrower = create.replace('BEFORE UPDATE OR DELETE', 'BEFORE DELETE').replace('BEFORE UPDATE ON', 'BEFORE INSERT ON')
            conditional = create.replace('FOR EACH ROW', 'FOR EACH ROW WHEN (false)')
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
    """The refuter's R4-4 upgrade path: a database that applied the earlier 0020, which installed no trigger. With no live
    rows its reverse must run, and re-applying installs every guard."""

    def tearDown(self):
        # Whatever happened above, leave every guard installed for the tests that follow.
        to_leaf()
        if reported(real_mode_payment_problems()):
            MigrationExecutor(connection).migrate(BEFORE_0020)
            to_leaf()
        super().tearDown()

    def test_a_database_that_applied_the_trigger_less_0020_is_refused_then_reverses_and_reapplies(self):
        execute('DROP TRIGGER payment_livemode_immutable ON core_payment',
                'DROP TRIGGER webhook_livemode_immutable ON core_webhookevent',
                'DROP FUNCTION quillmd_livemode_guard()')
        self.assertIn(('core', '0020_payment_livemode'), MigrationRecorder(connection).applied_migrations())
        self.assertEqual(reported(real_mode_payment_problems()), {'payment_livemode_immutable', 'webhook_livemode_immutable'})
        MigrationExecutor(connection).migrate(BEFORE_0020)
        self.assertNotIn(('core', '0020_payment_livemode'), MigrationRecorder(connection).applied_migrations())
        to_leaf()
        self.assertEqual(real_mode_payment_problems(), [])

    def test_one_missing_trigger_does_not_stop_the_reverse(self):
        execute('DROP TRIGGER webhook_livemode_immutable ON core_webhookevent')
        MigrationExecutor(connection).migrate(BEFORE_0020)  # Before: 'trigger "webhook_livemode_immutable" ... does not exist'.
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname LIKE '%livemode%'")
            self.assertEqual(cursor.fetchone()[0], 0)
            cursor.execute("SELECT count(*) FROM pg_proc WHERE proname = 'quillmd_livemode_guard'")
            self.assertEqual(cursor.fetchone()[0], 0)
        to_leaf()
        self.assertEqual(real_mode_payment_problems(), [])
