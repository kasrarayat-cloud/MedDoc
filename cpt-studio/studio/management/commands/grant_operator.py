"""Grant platform-operator access to one existing account (CORE-UX-DESIGN.md 5).

The grant is the only thing that opens the operator diagnostics at /ops/; no workspace role confers it, and nothing
over HTTP records one. The reason is read from a file (never argv) and recorded with the grant, beside who ran the
command (--by, default the operating-system login the environment names, else the process's uid - never a passwd
lookup: the installer runs this in a one-shot as a uid the image has no passwd entry for). An account that already
holds a grant keeps it: nothing is written and the command says so. A username that does not exist, or an inactive
account, is refused.
"""
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studio import models, operator


def reason_from(path):
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise CommandError(f'The reason file cannot be read: {path} ({type(exc).__name__}).')
    try:
        return operator.clean_reason(text)
    except ValueError as exc:
        raise CommandError(str(exc))


def account(username):
    user = models.User.objects.filter(username=username).first()
    if user is None:
        raise CommandError(f'No account is named {username!r}; nothing was recorded.')
    return user


# The variables getpass.getuser() reads before it falls back to the passwd database, in its order.
LOGIN_VARIABLES = ('LOGNAME', 'USER', 'LNAME', 'USERNAME')


def by_label(value):
    """Who records a grant or revocation: ``value`` (--by), else the login the environment names, else the process's
    uid. Never a passwd lookup (refutation r2, L6-2): the installer's operators phase runs this command in a one-shot as
    its own uid, which the image has no passwd entry for, and getpass.getuser() raised KeyError there - for both
    accounts, after they and their credentials files were created, on every rerun."""
    label = (value or '').strip()
    for name in LOGIN_VARIABLES:
        label = label or (os.environ.get(name) or '').strip()
    return (label or f'uid {os.getuid()}')[:120]


class Command(BaseCommand):
    help = 'Grant platform-operator access (the /ops/ diagnostics) to an existing account; the reason is read from a file.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', default='', help='Who records the grant (default: the login the environment '
                                                     'names, else the uid).')

    @transaction.atomic
    def handle(self, *args, **options):
        user = account(options['username'])
        if not user.is_active:
            raise CommandError(f'The account {user.username!r} is not active; nothing was recorded.')
        reason = reason_from(options['reason_file'])
        record, created = operator.grant(user, reason, by_label(options['by']))
        if created:
            self.stdout.write(f'Granted operator access to {user.username} (grant {record.pk}).')
        else:
            self.stdout.write(f'{user.username} already holds operator access (grant {record.pk}); nothing was recorded.')
