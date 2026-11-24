"""Clear the sign-in delay of one account (release 1, B1 item 8 and B8; A6's
--phase manage --command clear-signin-failures): the RateWindow rows of its username - its failures, its refusals and
the pairs it was tried from (studio.throttle.clear_failures) - are deleted, so its next sign-in meets no delay. Its
LoginAttempt rows are never deleted. A delay never locks anyone out (it never grows past SIGNIN_DELAY_MAX_SECONDS) and a
known device skips it; this is the recorded way back for the rest. The reason is read from a file and recorded as its
digest; --by names the person who runs the act. One SecurityEvent signin.delay_cleared. The output names ids and counts.
"""
from django.core.management.base import BaseCommand

from studio import security_events, throttle
from studio.management.commands.grant_operator import reason_from
from studio.management.commands.issue_enrolment import account_of, person, reason_digest


class Command(BaseCommand):
    help = 'Clear the sign-in delay of one account; the reason is read from a file.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', required=True, help='The person who runs the act (never a role).')

    def handle(self, *args, **options):
        by = person(options['by'])
        reason = reason_from(options['reason_file'])
        user = account_of(options['username'])
        deleted = throttle.clear_failures(user.get_username())
        security_events.record('signin.delay_cleared', actor_label=by, subject=user, rows_deleted=deleted,
                               reason_sha256=reason_digest(reason), reason_chars=len(reason))
        self.stdout.write(f'Sign-in delay of account {user.pk} cleared: {deleted} counter row(s) deleted.')
