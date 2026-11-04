"""Grant platform-operator access to one existing account (CORE-UX-DESIGN.md 5).

The grant is the only thing that opens the operator diagnostics at /ops/; no workspace role confers it, and nothing
over HTTP records one. The reason is read from a file (never argv) and recorded with the grant, beside who ran the
command (--by, default the operating-system login). An account that already holds a grant keeps it: nothing is written
and the command says so. A username that does not exist, or an inactive account, is refused.
"""
import getpass
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


def by_label(value):
    label = (value or '').strip() or getpass.getuser()
    return label[:120]


class Command(BaseCommand):
    help = 'Grant platform-operator access (the /ops/ diagnostics) to an existing account; the reason is read from a file.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', default='', help='Who records the grant (default: the operating-system login).')

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
