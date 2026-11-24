"""Clear the sign-in delay of one account, or the refusal of one address (release 1, B1 item 8 and B8; A6's
--phase manage --command clear-signin-failures).

--username NAME: the RateWindow rows of the username - its failures, its refusals and the pairs it was tried from
(studio.throttle.clear_failures) - are deleted, so its next sign-in meets no delay. One SecurityEvent
signin.delay_cleared. A delay never locks anyone out (it never grows past SIGNIN_DELAY_MAX_SECONDS), and a known device
or a known address skips it; this is the recorded way back for the rest.

--address ADDRESS: an IPv4 address, or an IPv6 address or /64 prefix (counted as its /64, as the sign-in counts it):
its failures, its refusals and the pairs tried from it (studio.throttle.clear_address) are deleted, so a network that
reached the address limit (SIGNIN_CLIENT_LIMIT failures in SIGNIN_WINDOW_SECONDS) can sign in again at once instead
of waiting for its failures to leave the window (refutation r2, finding 9). One SecurityEvent signin.address_cleared,
naming the address's client key.

LoginAttempt rows are never deleted. The reason is read from a file and recorded as its digest; --by names the person
who runs the act. The output names ids and counts only.
"""
from django.core.management.base import BaseCommand, CommandError

from studio import security_events, throttle
from studio.management.commands.grant_operator import reason_from
from studio.management.commands.issue_enrolment import account_of, person, reason_digest


class Command(BaseCommand):
    help = 'Clear the sign-in delay of one account, or the refusal of one address; the reason is read from a file.'

    def add_arguments(self, parser):
        which = parser.add_mutually_exclusive_group(required=True)
        which.add_argument('--username')
        which.add_argument('--address', help='An IPv4 address, or an IPv6 address or /64 prefix.')
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', required=True, help='The person who runs the act (never a role).')

    def handle(self, *args, **options):
        by = person(options['by'])
        reason = reason_from(options['reason_file'])
        if options['address'] is not None:
            try:
                key = throttle.address_key(options['address'])
            except ValueError:
                raise CommandError('--address is an IPv4 address, or an IPv6 address or /64 prefix; nothing was '
                                   'recorded.') from None
            deleted = throttle.clear_address(key)
            security_events.record('signin.address_cleared', actor_label=by, address=key, rows_deleted=deleted,
                                   reason_sha256=reason_digest(reason), reason_chars=len(reason))
            self.stdout.write(f'Sign-in refusals of the address cleared: {deleted} counter row(s) deleted.')
            return
        user = account_of(options['username'])
        deleted = throttle.clear_failures(user.get_username())
        security_events.record('signin.delay_cleared', actor_label=by, subject=user, rows_deleted=deleted,
                               reason_sha256=reason_digest(reason), reason_chars=len(reason))
        self.stdout.write(f'Sign-in delay of account {user.pk} cleared: {deleted} counter row(s) deleted.')
