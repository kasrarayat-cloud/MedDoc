"""Grant platform-operator access to one existing account (CORE-UX-DESIGN.md 5; release 1, C3).

The grant is the only thing that opens the operator console at /ops/; no workspace role confers it, and nothing over HTTP
records one. Operator power is for people only: an automated account is refused (studio.operator.grant), and is never an
operator whatever grant row it has (studio.operator.is_operator). Every grant rests on an approval and is reviewed:

    --username U            an existing, active account of a person
    --reason-file F         the reason, read from a file (never argv)
    --authorization-ref R   the approval the grant rests on, for example a committed ruling's path or a declaration and
                            its commit (the installer's manage phase passes "<declaration>@<commit>"; ADM-13)
    --review-by YYYY-MM-DD  the date the grant must be reviewed by: not past, at most 12 months away (ADM-8)
    --by NAME               the named person who records the grant - never a role (named_person)

All five are required. An account that already holds a grant keeps it: nothing is written and the command says so. A
username that does not exist, an inactive or automated account, an empty or unreadable reason file, a missing or
malformed approval or review date, or a role given as --by is refused and nothing is recorded. Each grant writes a
SecurityEvent operator.granted (studio.security_events).
"""
import os
import re
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
    """Who records an act whose --by is optional: ``value`` (--by), else the login the environment names, else the
    process's uid. Never a passwd lookup (refutation r2, L6-2): the installer's operators phase runs this command in a
    one-shot as its own uid, which the image has no passwd entry for, and getpass.getuser() raised KeyError there - for
    both accounts, after they and their credentials files were created, on every rerun. A grant and a revocation take
    named_person instead (release 1, C3: --by is required and names a person)."""
    label = (value or '').strip()
    for name in LOGIN_VARIABLES:
        label = label or (os.environ.get(name) or '').strip()
    return (label or f'uid {os.getuid()}')[:120]


# What --by never is (release 1, C3: "--by names a person, never a role"): a role or a function, compared with case,
# spacing and punctuation aside (normalized_label); and the uid label by_label falls back to, which names no one.
ROLE_LABELS = frozenset({
    'admin', 'administrator', 'agent', 'automation', 'bot', 'ci', 'console', 'engineering lead', 'installer', 'lead',
    'nobody', 'operator', 'operators', 'ops', 'ops agent', 'owner', 'platform operator', 'reviewer', 'root',
    'security officer', 'service', 'staff', 'superuser', 'support', 'system', 'team', 'the operator', 'user', 'viewer',
})
UID_LABEL_RE = re.compile(r'uid \d+')
BY_REQUIRED = '--by names the person who records this (a name, never a role); nothing was recorded.'


def normalized_label(value) -> str:
    """``value`` as ROLE_LABELS compares it: case folded, every run of characters that are not letters or digits one
    space, ends stripped ('Platform-Operator', '[SECURITY OFFICER]' and 'ops_agent' read 'platform operator',
    'security officer' and 'ops agent')."""
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in str(value or '').casefold()).split())


def named_person(value) -> str:
    """--by as recorded: a person's name (at most 120 characters, as the grant and revocation rows hold), refused when it
    is empty, a role (ROLE_LABELS) or a uid label, or holds a control character."""
    label = str(value or '').strip()
    reading = normalized_label(label)
    if not reading:
        raise CommandError(BY_REQUIRED)
    if reading in ROLE_LABELS or UID_LABEL_RE.fullmatch(reading):
        raise CommandError(f'--by {label!r} names a role, not a person: give the name of the person who records this; '
                           f'nothing was recorded.')
    if len(label) > 120 or any(ord(ch) < 32 or ch == '\x7f' for ch in label) or operator.UNSTORABLE.search(label):
        raise CommandError('--by is a name of at most 120 characters, with no control character; nothing was recorded.')
    return label


class Command(BaseCommand):
    help = ('Grant platform-operator access (the /ops/ console) to an existing person\'s account; the reason is read from '
            'a file, and the approval, the review date and the person who records it are required.')

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reason-file', required=True)
        parser.add_argument('--authorization-ref', required=True,
                            help='the approval the grant rests on (a committed ruling\'s path, or a declaration and its '
                                 'commit)')
        parser.add_argument('--review-by', required=True, help='the date the grant must be reviewed by, YYYY-MM-DD, at '
                                                               'most 12 months away')
        parser.add_argument('--by', required=True, help='the named person who records the grant (never a role)')

    @transaction.atomic
    def handle(self, *args, **options):
        user = account(options['username'])
        if not user.is_active:
            raise CommandError(f'The account {user.username!r} is not active; nothing was recorded.')
        if user.actor_kind != models.User.HUMAN:
            raise CommandError(operator.AGENT_GRANT_REFUSED)
        by = named_person(options['by'])
        reason = reason_from(options['reason_file'])
        try:
            reference = operator.clean_authorization_ref(options['authorization_ref'])
            review_by = operator.clean_review_by(options['review_by'])
            record, created = operator.grant(user, reason, by, authorization_ref=reference, review_by=review_by)
        except ValueError as exc:
            raise CommandError(f'{exc} Nothing was recorded.' if not str(exc).endswith('recorded.') else str(exc))
        if created:
            self.stdout.write(f'Granted operator access to {user.username} (grant {record.pk}; review by '
                              f'{record.review_by.isoformat()}).')
        else:
            self.stdout.write(f'{user.username} already holds operator access (grant {record.pk}); nothing was recorded.')
