"""Revoke platform-operator access from one account (CORE-UX-DESIGN.md 5).

Every grant of the account that no revocation ended gets one OperatorRevocation row with the reason read from the file
(never argv) and who ran the command (--by, default the operating-system login); the grant rows stay. A username that
does not exist, or an account that holds no grant, is refused and nothing is recorded.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studio import operator
from studio.management.commands.grant_operator import account, by_label, reason_from


class Command(BaseCommand):
    help = 'Revoke platform-operator access from an account; the reason is read from a file.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', default='', help='Who records the revocation (default: the operating-system login).')

    @transaction.atomic
    def handle(self, *args, **options):
        user = account(options['username'])
        reason = reason_from(options['reason_file'])
        revoked = operator.revoke(user, reason, by_label(options['by']))
        if not revoked:
            raise CommandError(f'{user.username!r} holds no operator grant; nothing was recorded.')
        self.stdout.write(f'Revoked operator access from {user.username} '
                          f'({len(revoked)} grant{"s" if len(revoked) != 1 else ""}).')
