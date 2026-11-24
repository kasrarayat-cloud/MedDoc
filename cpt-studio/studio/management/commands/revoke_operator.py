"""Revoke platform-operator access from one account (CORE-UX-DESIGN.md 5; release 1, C3).

Every grant of the account that no revocation ended gets one OperatorRevocation row with the reason read from the file
(never argv) and the named person who ran the command (--by, required: a person's name, never a role -
grant_operator.named_person); the grant rows stay. The account's every session ends at once, and a SecurityEvent
operator.revoked is written (studio.operator.revoke). A username that does not exist, an account that holds no grant, an
empty or unreadable reason file, or a missing --by or one that names a role is refused and nothing is recorded.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studio import operator
from studio.management.commands.grant_operator import account, named_person, reason_from


class Command(BaseCommand):
    help = ('Revoke platform-operator access from an account and end its sessions; the reason is read from a file and '
            'the person who records it is required.')

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', required=True, help='the named person who records the revocation (never a role)')

    @transaction.atomic
    def handle(self, *args, **options):
        user = account(options['username'])
        by = named_person(options['by'])
        reason = reason_from(options['reason_file'])
        try:
            revoked = operator.revoke(user, reason, by)
        except operator.sessions.Refused as exc:  # a session store the console cannot end: nothing is recorded
            raise CommandError(f'{exc} Nothing was recorded.')
        if not revoked:
            raise CommandError(f'{user.username!r} holds no operator grant; nothing was recorded.')
        self.stdout.write(f'Revoked operator access from {user.username} '
                          f'({len(revoked)} grant{"s" if len(revoked) != 1 else ""}); every session of the account '
                          f'has ended.')
