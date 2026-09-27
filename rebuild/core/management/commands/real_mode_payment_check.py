"""Read-only: may this database serve QUILLMD_DATA_MODE=real? Run it before starting real mode.

Real data mode runs on a database that has never held sandbox payments. This command refuses (exit status 1)
when the database holds any payment or Stripe event row not recorded as live, or any paid wallet holding money
that live payments do not wholly explain, or when any database trigger that keeps that evidence from being relabelled
is missing, disabled or altered (full definition, function schema and installed body hash), an unexpected row or statement trigger
exists, or the current/effective persistent runtime session_replication_role is not origin. See
core.billing.missing_payment_evidence_guards for the exact checks. Connect as the target runtime role/database.
It prints counts and fixed labels only, never a payment's identifier, address or amount, and it runs inside a READ
ONLY transaction, so it cannot write even by mistake. It never calls Stripe. This is point-in-time evidence, not a
lock against an owner who can alter the database and this checker.

A startup check inside every process is not used instead: settings and AppConfig.ready() also run for
migrate, makemigrations, the test runner and collectstatic, often before the database exists or is migrated,
and Django advises against queries there. The launcher runs this command. In real mode the running application
then enforces the narrower per-balance rule, core.billing.real_mode_refuses (a paid balance any non-live payment
funded): reserve() refuses to hold it, checkout refuses to add live money to it, and the worker refuses to send a
job whose hold, taken before the switch to real mode, sits on it. This command is stricter: it refuses a database
holding ANY sandbox payment or event row, funded or not.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.billing import real_mode_payment_problems


class Command(BaseCommand):
    help = ('Read-only: refuse (exit 1) when this database holds sandbox payment evidence that real data mode must never spend, '
            'or lacks a trigger guarding that evidence.')

    def handle(self, *args, **options):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            problems = real_mode_payment_problems()
            # Nothing to keep: roll back, which inside an enclosing transaction also ends the read-only setting.
            transaction.set_rollback(True)
        if problems:
            raise CommandError('This database may not run in real data mode: ' + '; '.join(problems)
                               + '. Real mode runs on a database that has never held sandbox payments.')
        self.stdout.write('Payment records: no sandbox payment evidence; this database may run in real data mode.')
