"""One synthetic test run's own message, read from the application's private outbox without widening access.

⚠️ THE PROBLEM THIS SOLVES, AND THE ONE IT MUST NOT CREATE. The private-beta account checks — invitation
acceptance, the welcome grant, password recovery — need the links the application emails. In `file` email
mode those land in `/var/lib/quillmd/mail`, owned by the service account and unreadable by the operator
account the harness runs as. The earlier helper failed there with `PermissionError`, which is **the OS
isolation working**: an operator who could read that directory could read every message the application
has ever written, including any real one it might write later.

So the isolation is preserved exactly as it is. Nothing here changes a mode, a group, an ACL, or the unit
files; nothing here needs sudo; nothing here opens an endpoint. This module reuses `ops.private_storage`,
which already runs a small inlined reader inside a container as the SERVICE identity, with no network, a
read-only bind of one approved root, all capabilities dropped and no-new-privileges. The operator never
gains the ability to read that directory — a confined helper reads it and hands back one verified file.
This is a NARROWING of the docker-socket privilege the operator account already holds, not a new boundary
around it: `docker run -u 0:0` could already read the whole host. It is not a containment control and must
not be cited as one.

⚠️ **THE FIRST DESIGN OF THIS MODULE SELECTED MESSAGES BY FILENAME TIMESTAMP AND REGEXED THE WHOLE FILE.
BOTH WERE WRONG, AND A REFUTATION PASS DEMONSTRATED IT RETURNING ANOTHER ACCOUNT'S TOKEN.** The two facts
that break it are in the libraries, not in this application's intent:

  · `django/core/mail/backends/filebased.py` names each file `%Y%m%d-%H%M%S-<abs(id(self))>.log`, and
    `abs(id(self))` is a recycled CPython object address — measured CONSTANT across 4000 sequential backend
    instances. The only real entropy in that name is one second.
  · `core/email_backend.py` opens it `O_WRONLY|O_APPEND|O_CREAT`, so a name collision APPENDS. Three sends
    in the same second produced ONE file holding THREE records for THREE recipients, and a first-match
    `/invite/([^/]+)/` over those bytes returned a DIFFERENT account's raw token.

Multi-record files are the designed shape — `write_message` writes each message followed by a 79-dash
separator line. So selection happens at RECORD level, never at file level, and the run is identified by a
before/after `inventory()` diff rather than by a clock:

  1 · BY CHANGE, NOT BY TIME. The caller snapshots `inventory()` before the action. Candidates are paths
      that are new OR whose sha256 moved — and the second is what catches the append-collision, which a
      timestamp window cannot see at all. `inventory()` exposes no mtime, and the filename's stamp is naive
      LOCAL time from `datetime.datetime.now()`, so there was never a trusted clock to filter on.
  2 · BY EXACT ADDRESSEE, AT RECORD LEVEL. Each candidate is split on the separator, each record is parsed
      for its `To:` header, and only the record addressed to this run's unique
      `@synthetic.quillmd.invalid` address is MATCHED against a route pattern.
  3 · EXACTLY ONE, OR NOTHING. Two matching records is a refusal, not a first-match.

⚠️ **THE NARROWING IS AT MATCHING LEVEL. READING IS NARROWED ONLY TO THE FILES THIS RUN CHANGED, AND
SAYING OTHERWISE WOULD BE A LIE THE NEXT READER WOULD BELIEVE.** `private_storage.read_file` is
all-or-nothing by construction — there is no predicate and no partial read — so a changed file arrives in
this process COMPLETE, and every record in it is parsed for its `To:` header. Under the append-collision
this module exists for, that file can hold somebody else's message, and that message's raw token is in
this process's memory whether or not anything looks at it. A refutation pass demonstrated exactly that: a
real-shaped verification token for a non-synthetic address crossed the boundary inside a 1079-byte blob
while the counts reported, truthfully but misleadingly, `records_for_others: 1`.

What is done about it is a DETECTION, not a prevention, and it is named as one: a changed file holding a
record addressed OUTSIDE `@synthetic.quillmd.invalid` makes `route()` refuse. The read has already
happened by then — nothing here can undo it — but the run stops instead of continuing quietly, and a
human is told. On this synthetic-only staging host no real address exists; the guard is for the day one
does.

⚠️ **AND THE RECORD FRAMING IS IN-BAND.** The separator is a line of 79 dashes, which is also legal body
text. A body containing one splits into two chunks, and `email.message_from_bytes` will read the second
chunk's first lines as headers — so a forged `To:` inside a body can claim a record. The same refutation
pass built that file and made `route()` return a stranger's token. It is NOT reachable from this
application: every outbox write goes through `deliver_account_email`, whose three bodies are fixed and
carry no caller-controlled substring. It is recorded because the day a body becomes variable, this stops
being structural and becomes live.

**AND THE MESSAGE IS BOUND TO A RECORD, NOT ONLY TO AN ADDRESS.** Matching the addressee proves the
message was written TO this run; it does not prove the message is the one this run CAUSED. A stale
invitation to the same address, a superseded record, or a message this run did not ask for all pass an
address match. So `route(..., verify=...)` takes a predicate the CALLER supplies — run in this same
process, over the extracted token, before the route is returned — and the caller binds it to the record
it created:

  · an invitation token is bound by `sha256(token) == Invitation.token_hash` (`core/security.py` hashes
    the raw token into the row, so the comparison is exact and leaks nothing);
  · a recovery token is bound by `default_token_generator.check_token(user, …)` plus the `uidb64` segment
    decoding to that user's own primary key.

A token that does not bind is a REFUSAL, never a fallback to the next candidate. `verify` stays a callable
rather than a value so this module keeps no knowledge of the application's models.

**THE ROUTE IS THE TOKEN — they are the same string.** `core/email_delivery.py` builds
`{origin}/{route}/{raw_token}/`, so "log the extracted route" means "log the secret". `route()` returns it
because visiting it is the test. It is never logged, never written to a report, never passed as a process
argument (argv is world-readable in `ps`), and never an operand of an assertion — `unittest` prints both
operands on failure, which is a demonstrated way to put a raw token in a test log. `describe()` exists so a
caller can record THAT a route was found, of what kind and what length, without recording what it was.

**A REFUSAL HERE IS NEVER "NO MESSAGE WAS SENT".** `private_storage` collapses every failure — a stray
0644 file, a closed encrypted volume, a missing docker, a changed root inode — into one generic string. So
a caller must positive-control the instrument (snapshot non-empty) BEFORE the action, or it cannot tell an
application that sent nothing from a reader that cannot see.
"""
import email
from email.utils import getaddresses
from pathlib import Path
import re

try:                                    # the house idiom: `discover -s ops` makes this a top-level module
    from . import private_storage
except ImportError:                     # pragma: no cover - import shape, not behaviour
    import private_storage

OUTBOX = Path('/var/lib/quillmd/mail')
# ⚠️ THE RECORD SEPARATOR AND THE SYNTHETIC DOMAIN NOW LIVE IN `private_storage`, WITH THE MATCHER THAT
# USES THEM, AND ARE RE-EXPORTED HERE RATHER THAN RESTATED. A second copy of a matcher is what produced
# the defect this module exists for; a second copy of the constants it matches on is the same mistake one
# size smaller.
SEPARATOR = private_storage.RECORD_SEPARATOR
SYNTHETIC_DOMAIN = private_storage.SYNTHETIC_DOMAIN
# Routes a test may extract, each anchored to the shape the application actually emits. Anything else is
# refused rather than pattern-matched loosely.
#
# ⚠️ THE TWO KINDS DO NOT HAVE THE SAME SHAPE, AND THE FIRST VERSION OF THIS FILE ASSUMED THEY DID. An
# invitation token is one `secrets.token_urlsafe(32)` segment. A recovery token is TWO segments —
# `core/recovery.py` builds `f'{urlsafe_base64_encode(pk)}/{default_token_generator.make_token(user)}'`, and
# `urls.py` routes it as `recovery/confirm/<uidb64>/<token>/`. A single-segment pattern matches the
# invitation and silently never matches the recovery link at all.
KINDS = {'invite': r'/invite/(?P<token>[A-Za-z0-9_-]{16,512})/',
         'recovery/confirm': r'/recovery/confirm/(?P<token>[A-Za-z0-9_-]{2,512}/[0-9a-z]{4,12}-[0-9a-z]{16,128})/'}
MAX_CHANGED_PATHS = private_storage.MAX_SELECT_NAMES
# What the helper's refusal codes mean to a caller. The helper returns a fixed code and never a quotation,
# so these strings are the only prose either side produces about a failed selection.
REASONS = {'outside_synthetic': 'a changed outbox file also holds a message addressed outside the '
                                'synthetic test domain; stopping rather than continuing',
           'no_record_for_this_run': 'no message for this run was found among the changed files',
           'more_than_one_record': 'more than one message is addressed to this run',
           'no_link_of_this_purpose': "the run's message carries no link of the requested purpose",
           'token_not_bound': 'the located token does not belong to the record this run created'}


class MailUnavailable(Exception):
    """The run's message could not be located. Carries no message content and no token, ever."""


def snapshot(root=OUTBOX):
    """`{relative path: sha256}` for the outbox, as the confined reader sees it. Never any content.

    This is also the instrument's positive control: it raises if the reader cannot answer at all, so a
    caller can distinguish "the application sent nothing" from "I could not look".
    """
    return {name: info['sha256'] for name, info in private_storage.inventory(Path(root)).items()}


def _changed(root, before):
    """Paths that are new since `before`, or whose content moved. Metadata only — nothing is read here."""
    after = snapshot(root)
    names = sorted(name for name, digest in after.items() if before.get(name) != digest)
    if len(names) > MAX_CHANGED_PATHS:
        raise MailUnavailable('more outbox files changed than a single test run can explain')
    return names


def route(kind, address, before, root=OUTBOX, notes=None, expect_sha256='', expect_prefix='', verify=None):
    """The `/<kind>/<token>/` path for THIS run, selected and bound INSIDE the confined helper.

    `before` is a `snapshot()` taken before the action that sends the message. `expect_sha256` and
    `expect_prefix` are the record binding, applied by the helper before anything is returned.
    `verify` is an optional FINAL host-side check for a binding the container cannot compute — Django's
    `check_token` needs the secret key and the user's password hash, and the helper has neither a database
    nor a network. `notes`, if given, receives counts and booleans a report MAY publish.

    ⚠️ THE RETURNED STRING IS THE SECRET ITSELF. Navigate to it. Do not log it, store it, assert on it,
    put it in a report, or pass it to a subprocess.
    """
    if kind not in KINDS:
        raise MailUnavailable('unknown route kind')
    address = address.lower()
    if not address.endswith(SYNTHETIC_DOMAIN):
        raise MailUnavailable('only a synthetic test address may be located')
    changed = _changed(root, before)
    if notes is not None:
        notes.update({'changed_paths': len(changed), 'records_for_this_run': 0, 'records_for_others': 0,
                      'records_outside_synthetic': 0, 'token_bound': None})
    if not changed:
        raise MailUnavailable('no outbox file changed during this run')
    result = private_storage.select_message(Path(root), changed, address, kind, KINDS[kind],
                                            expect_sha256=expect_sha256, expect_prefix=expect_prefix)
    if notes is not None:
        notes.update({k: result[k] for k in
                      ('records_for_this_run', 'records_for_others', 'records_outside_synthetic')})
        notes['token_bound'] = bool(result['found']) if (expect_sha256 or expect_prefix) else None
    if not result['found']:
        raise MailUnavailable(REASONS.get(result['reason'], 'the run\'s message could not be located'))
    found = result['route']
    if verify is not None:
        try:
            bound = bool(verify(found[len('/%s/' % kind):].rstrip('/')))
        except Exception:
            # A predicate that raises has not said yes. Never quoted: it was handed the token.
            bound = False
        if notes is not None:
            notes['token_bound'] = bound
        if not bound:
            del found
            raise MailUnavailable('the located %s token does not belong to the record this run created' % kind)
    return found


def describe(found):
    """What a report may record about a route: that one was found, its kind, its length. Never the token.

    The kind is matched against KINDS rather than counted off by slashes, because `recovery/confirm` has two
    segments in both its name and its token and positional splitting gets both of them wrong.
    """
    for kind in KINDS:
        prefix = '/%s/' % kind
        if found.startswith(prefix):
            return {'found': True, 'kind': kind, 'token_characters': len(found[len(prefix):].rstrip('/'))}
    return {'found': False, 'kind': '', 'token_characters': 0}
