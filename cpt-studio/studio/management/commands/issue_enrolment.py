"""Issue a single-use setup code to a human platform operator (release 1, B2 item 3 and B8; A6's
--phase manage --command issue-enrolment).

The operator enters the code at admin.quillmd.com/login/enrol, chooses a new password there and registers the first
security key; the code works once, for ENROLMENT_CODE_SECONDS, and only its sha256 is stored (OneTimeToken
operator_setup). Issuing a code revokes the account's earlier unused ones. --code-file names a file holding a code made
by the caller (the installer writes it root-only and keeps it; this command reads it and prints nothing of it); without
it a new code is made and printed once, here, and never stored or logged in plain text. The reason is read from a file
(never argv) and recorded as its digest; --by names the person who runs the act, never a role. One SecurityEvent
second_factor.setup_issued. The output names ids, counts and times only - the one exception is the code this command
exists to hand over.
"""
import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from studio import request_meta, second_factor, security_events
from studio.management.commands.grant_operator import reason_from
from studio.models import User

# What --by never is: a role, an account kind or a stand-in for nobody (C3: --by names a person, never a role).
ROLE_WORDS = frozenset({
    'admin', 'administrator', 'agent', 'automated', 'automation', 'claude', 'cron', 'engineering lead', 'install',
    'installer', 'me', 'n/a', 'na', 'nobody', 'none', 'operator', 'operators', 'ops', 'ops-agent', 'owner',
    'platform operator', 'platform-operator', 'reviewer', 'root', 'security officer', 'security-officer', 'self',
    'someone', 'system', 'tbd', 'unknown', 'user', 'viewer',
})


def person(value):
    """--by as recorded: the named person who runs the act - never empty, a role, an account kind or a uid."""
    label = ' '.join(str(value or '').split())
    if len(label) < 2:
        raise CommandError('--by names the person who runs this act; nothing was recorded.')
    if len(label) > 120:
        raise CommandError('--by is at most 120 characters; nothing was recorded.')
    if request_meta.UNSTORABLE.search(label) or any(ord(char) < 32 for char in label):
        raise CommandError('--by holds a character that cannot be stored; nothing was recorded.')
    plain = label.casefold().strip('[]() ')
    if plain in ROLE_WORDS or plain.startswith('uid '):
        raise CommandError('--by names a person, never a role or an account; nothing was recorded.')
    return label


def reason_digest(reason):
    """A reason as a security event records it: its sha256 (the text stays in the ruled act's declaration)."""
    return hashlib.sha256(reason.encode('utf-8')).hexdigest()


def account_of(username):
    """The account named exactly ``username``, or CommandError (the output never repeats a typed name)."""
    user = User.objects.filter(username=username).first()
    if user is None:
        raise CommandError('No account has that username; nothing was recorded.')
    return user


def human_operator(username):
    user = account_of(username)
    if not user.is_active:
        raise CommandError(f'Account {user.pk} is not active; nothing was recorded.')
    if not second_factor.is_human_operator(user):
        raise CommandError(f'Account {user.pk} is not a human platform operator; nothing was recorded.')
    return user


def code_from(path):
    """The setup code in the file ``path`` (the caller's own; never printed)."""
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise CommandError(f'The code file cannot be read ({type(exc).__name__}); nothing was recorded.')
    if second_factor.plain_code(text, second_factor.SETUP_CODE_GROUPS) is None:
        raise CommandError('The code file holds no setup code; nothing was recorded.')
    return text.strip()


class Command(BaseCommand):
    help = 'Issue a single-use setup code to a human platform operator; the reason is read from a file.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--by', required=True, help='The person who runs the act (never a role).')
        parser.add_argument('--code-file', default='',
                            help='A file holding the code to issue (the installer\'s); without it a new code is printed '
                                 'once.')

    def handle(self, *args, **options):
        by = person(options['by'])
        reason = reason_from(options['reason_file'])
        user = human_operator(options['username'])
        code = code_from(options['code_file']) if options['code_file'] else None
        try:
            with transaction.atomic():
                token, shown = second_factor.issue_setup_code(user, by, code)
                security_events.record('second_factor.setup_issued', actor_label=by, subject=user, token=token.pk,
                                       expires_at=token.expires_at, reason_sha256=reason_digest(reason),
                                       reason_chars=len(reason))
        except IntegrityError:
            raise CommandError('That setup code was issued before; make a new one. Nothing was recorded.')
        self.stdout.write(f'Setup code issued for account {user.pk} (token {token.pk}), valid until '
                          f'{token.expires_at.isoformat()}; earlier unused codes revoked.')
        if code is None:
            self.stdout.write(f'Setup code (shown once, stored as its digest only): {shown}')
