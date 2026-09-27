"""Read-only: may this database serve QUILLMD_DATA_MODE=real? Run it before starting real mode.

Real data mode runs on a database that has never held sandbox payments. This command refuses (exit status 1)
when the database holds any payment or Stripe event row not recorded as live, or any paid wallet holding money
that live payments do not wholly explain. It prints counts only, never identifiers, addresses or amounts, and
it runs inside a READ ONLY transaction, so it cannot write even by mistake. It never calls Stripe.

A startup check inside every process is not used instead: settings and AppConfig.ready() also run for
migrate, makemigrations, the test runner and collectstatic, often before the database exists or is migrated,
and Django advises against queries there. The launcher runs this command; reserve() enforces the same rule
on every request in real mode (core.billing.sandbox_funded).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.billing import real_mode_payment_problems


class Command(BaseCommand):
    help = 'Read-only: refuse (exit 1) when this database holds sandbox payment evidence that real data mode must never spend.'

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
