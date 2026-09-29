"""Read-only: how many stored account and invitation addresses fall outside the account email rule. Counts only.

The rule (core.forms.account_email) stores an internationalized domain as its A-label, and the lookup doors (sign-in,
recovery, verification resend) find an account by that form. A row stored BEFORE the rule with a Unicode domain (main's
RegisterForm stored the address as typed) is then found by no spelling of that domain, and a second account for the same
mailbox can be created beside it. So the rule's install precondition is that the installed database holds no non-ASCII
address. This command answers that on the database it runs against, without printing, returning or logging any address:
it reads in a READ ONLY transaction that it then rolls back, and it writes counts only.

Per table: `non_ascii` rows (the address, or an account's username, has a non-ASCII character: the precondition's
hazard) and, disjoint from them, `ascii_not_normalised` rows (ASCII, but the rule refuses the address or stores it
differently, for example an invalid "xn--" label or a quoted local part stored before the rule; their lookup key is
unchanged by the rule). Exit status 0 only when every count is 0.
"""
import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction

from core.forms import account_email
from core.models import ClinicInvitation, Invitation, User

#: Each table and the columns it stores an address in; the first is the address the rule is applied to.
TABLES = ((User, ('email', 'username')), (Invitation, ('email',)), (ClinicInvitation, ('email',)))


def outside_rule(address):
    """True when the rule refuses the stored address or would store it differently."""
    try:
        return account_email(address) != address
    except ValidationError:
        return True


def table_counts(model, columns):
    counts = {'rows': 0, 'non_ascii': 0, 'ascii_not_normalised': 0}
    for values in model.objects.order_by().values_list(*columns):
        counts['rows'] += 1
        if not all(value.isascii() for value in values):
            counts['non_ascii'] += 1
        elif outside_rule(values[0]):
            counts['ascii_not_normalised'] += 1
    return counts


def audit():
    with transaction.atomic():
        # Before the first read. Whatever this command runs, the database refuses a write in this transaction, and the
        # transaction (or, inside an outer one, its savepoint) is rolled back, not committed.
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        tables = {model._meta.db_table: table_counts(model, columns) for model, columns in TABLES}
        transaction.set_rollback(True)
    clean = all(not counts['non_ascii'] and not counts['ascii_not_normalised'] for counts in tables.values())
    return {'tables': tables, 'clean': clean}


class Command(BaseCommand):
    help = ('Read-only: count stored account and invitation email addresses outside the account email rule '
            '(non-ASCII, or not equal to the stored form the rule gives). Counts only; exit status 0 only when all are 0.')
    requires_system_checks = []
    requires_migrations_checks = False

    def handle(self, *args, **options):
        try:
            report = audit()
        except DatabaseError:
            # No SQL, no address and no database exception detail in the output.
            raise CommandError('account_email_audit_refused; nothing was written') from None
        self.stdout.write(json.dumps(report, sort_keys=True))
        if not report['clean']:
            raise CommandError('account_email_audit: stored addresses outside the account email rule (counts above)')
