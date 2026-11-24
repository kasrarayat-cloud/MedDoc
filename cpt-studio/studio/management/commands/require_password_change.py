"""Make accounts choose a new password at their next sign-in (release 1, B4 item 3, OWNER DECISION D22; B8; A6's
--phase manage --command require-password-change): --username one account, or --all every active human account. An
automated account is never flagged (agent accounts exist only for the release walk). The flag
(User.password_change_required_at) starts STAFF_PASSWORD_UNUSED_SECONDS' clock: until the owner of the account chooses a
new password, a sign-in opens only the account page, and after the clock the password is refused like a wrong one (the
way back is a console reset, or a new setup code for the operator). An account already flagged keeps its own clock -
it is never restarted or extended. The reason is read from a file and recorded as its digest; --by names the person
who runs the act. One SecurityEvent password.change_required per flagged account. The output names ids and counts.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from studio import security_events
from studio.management.commands.grant_operator import reason_from
from studio.management.commands.issue_enrolment import account_of, person, reason_digest
from studio.models import User


class Command(BaseCommand):
    help = 'Make one account, or every active human account, choose a new password at the next sign-in.'

    def add_arguments(self, parser):
        which = parser.add_mutually_exclusive_group(required=True)
        which.add_argument('--username')
        which.add_argument('--all', action='store_true', help='Every active human account.')
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', required=True, help='The person who runs the act (never a role).')

    def handle(self, *args, **options):
        by = person(options['by'])
        reason = reason_from(options['reason_file'])
        if options['username'] is not None:
            user = account_of(options['username'])
            if user.actor_kind != User.HUMAN:
                raise CommandError(f'Account {user.pk} is an automated account, which is never flagged; nothing was '
                                   'recorded.')
            if not user.is_active:
                raise CommandError(f'Account {user.pk} is not active; nothing was recorded.')
            accounts = [user]
            automated = 0
        else:
            accounts = list(User.objects.filter(is_active=True, actor_kind=User.HUMAN).order_by('date_joined', 'pk'))
            automated = User.objects.filter(is_active=True).exclude(actor_kind=User.HUMAN).count()
        now = timezone.now()
        flagged, kept = [], 0
        with transaction.atomic():
            for user in accounts:
                if User.objects.filter(pk=user.pk, password_change_required_at__isnull=True).update(
                        password_change_required_at=now):
                    flagged.append(user)
                    security_events.record('password.change_required', actor_label=by, subject=user,
                                           reason_sha256=reason_digest(reason), reason_chars=len(reason))
                else:
                    kept += 1
        self.stdout.write(f'{len(flagged)} account(s) must choose a new password at their next sign-in'
                          f'{": " + ", ".join(str(user.pk) for user in flagged) if flagged else ""}; {kept} already '
                          f'had to (their clocks kept); {automated} automated account(s) never flagged.')
