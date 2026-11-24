"""Reset a human platform operator's lost second factor (release 1, B2 item 7 and B8; A6's
--phase manage --command reset-second-factor): the account's keys are marked removed, its unused recovery codes voided
and its sessions ended, and a new setup code is issued (as issue_enrolment issues one: --code-file, or printed once).
No console path resets an operator's own factor. The reason is read from a file and recorded as its digest; --by names
the person who runs the act. One SecurityEvent second_factor.reset. The output names ids and counts only, and the code
when this command made it.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from studio import second_factor, security_events
from studio.management.commands.grant_operator import reason_from
from studio.management.commands.issue_enrolment import code_from, human_operator, person, reason_digest


class Command(BaseCommand):
    help = 'Reset a human platform operator\'s security keys and recovery codes and issue a new setup code.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', required=True, help='The person who runs the act (never a role).')
        parser.add_argument('--code-file', default='',
                            help='A file holding the new setup code (the installer\'s); without it one is printed once.')

    def handle(self, *args, **options):
        by = person(options['by'])
        reason = reason_from(options['reason_file'])
        user = human_operator(options['username'])
        code = code_from(options['code_file']) if options['code_file'] else None
        try:
            with transaction.atomic():
                counts, token, shown = second_factor.reset(user, by, code)
                security_events.record('second_factor.reset', actor_label=by, subject=user, token=token.pk,
                                       reason_sha256=reason_digest(reason), reason_chars=len(reason), **counts)
        except IntegrityError:
            raise CommandError('That setup code was issued before; make a new one. Nothing was recorded.')
        self.stdout.write(f'Second factor of account {user.pk} reset: {counts["keys_removed"]} key(s) removed, '
                          f'{counts["recovery_codes_voided"]} recovery code(s) voided, {counts["sessions_ended"]} '
                          f'session(s) ended; setup code issued (token {token.pk}), valid until '
                          f'{token.expires_at.isoformat()}.')
        if code is None:
            self.stdout.write(f'Setup code (shown once, stored as its digest only): {shown}')
