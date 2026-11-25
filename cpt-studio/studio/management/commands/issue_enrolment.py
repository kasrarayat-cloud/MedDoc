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
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from studio import request_meta, second_factor, security_events
from studio.management.commands.grant_operator import reason_from
from studio.models import User

# What --by never is, in any spelling (C3: --by names a person, never a role; refutation r2, finding 7): a role, an
# account kind, a system or an agent, or a stand-in for nobody. Compared as plain words (plain_words): case, width,
# accents' composition, punctuation and spacing aside.
ROLE_WORDS = frozenset({
    'admin', 'admins', 'administrator', 'administrators', 'agent', 'agents', 'ai', 'anon', 'anonymous', 'assistant',
    'automated', 'automation', 'bot', 'bots', 'claude', 'cron', 'daemon', 'gid', 'guest', 'install', 'installer', 'me',
    'myself', 'na', 'nobody', 'none', 'null', 'officer', 'operator', 'operators', 'ops', 'owner', 'owners', 'reviewer',
    'root', 'script', 'security', 'self', 'server', 'service', 'someone', 'somebody', 'staff', 'superuser', 'support',
    'sysadmin', 'sysadmins', 'system', 'systems', 'tbd', 'team', 'test', 'tester', 'uid', 'unknown', 'user', 'users',
    'viewer',
})
# phrases that are roles though one of their words is not (compared with their spaces, and without them)
ROLE_PHRASES = frozenset({'claude code', 'engineering lead', 'not applicable', 'n a', 'ops agent', 'platform operator',
                          'security officer', 'on call'})
FILLER_WORDS = frozenset({'a', 'account', 'an', 'and', 'behalf', 'by', 'for', 'my', 'of', 'on', 'our', 'the', 'this',
                          'your'})
NAME_CHARS = 120  # SecurityEvent.actor_label and OneTimeToken.created_by


def name_as_recorded(value) -> str:
    """--by as it is recorded and compared: Unicode NFKC (a composed and a decomposed accent, a full-width and an
    ordinary letter, a no-break and an ordinary space are one spelling), every character no one can see or type removed
    (studio.console.hidden), NFKC again, and runs of white space made one space - the normalisation of the two-person
    rule's names (studio.disposal.name_as_recorded), so one person's name is one spelling in every ruled act."""
    from studio.console import hidden  # here: the console is loaded only by an act that names a person
    text = unicodedata.normalize('NFKC', str(value or ''))
    text = ''.join(char for char in text if char.isspace() or not hidden(char))
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def plain_words(name) -> list:
    """A recorded name's words as ROLE_WORDS compares them: casefolded, every character that is not a letter or a digit
    a space between words."""
    return ''.join(char if unicodedata.category(char)[0] in 'LN' else ' ' for char in name.casefold()).split()


def names_no_person(name) -> bool:
    """Whether a recorded --by names no person: fewer than two letters (empty, punctuation, digits only); a role phrase
    with or without its spaces, its plural or its article; or only role words, fillers and numbers ('the operator',
    'Admins', 'Security_Officer', 'n/a.', 'uid 1000', 'system administrator')."""
    if sum(1 for char in name if unicodedata.category(char).startswith('L')) < 2:
        return True
    words = plain_words(name)
    stripped = list(words)
    while stripped and stripped[0] in FILLER_WORDS:
        stripped = stripped[1:]
    if not stripped:
        return True
    roles = ROLE_WORDS | ROLE_PHRASES | {phrase.replace(' ', '') for phrase in ROLE_PHRASES}
    for each in (words, stripped):
        phrase = ' '.join(each)
        if {phrase, phrase.replace(' ', ''), phrase[:-1] if phrase.endswith('s') else phrase} & roles:
            return True
    return all(word in ROLE_WORDS or word in FILLER_WORDS or word.isdigit() for word in words)


def person(value):
    """--by as recorded (name_as_recorded): the named person who runs the act - never empty, a role, an account kind,
    a system, an agent or a uid, in any spelling (names_no_person). CommandError otherwise; nothing is recorded."""
    if request_meta.UNSTORABLE.search(str(value or '')):
        raise CommandError('--by holds a character that cannot be stored; nothing was recorded.')
    label = name_as_recorded(value)
    if len(label) > NAME_CHARS:
        raise CommandError(f'--by is at most {NAME_CHARS} characters; nothing was recorded.')
    if names_no_person(label):
        raise CommandError('--by names the person who runs this act, never a role, an account or nobody; nothing was '
                           'recorded.')
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
