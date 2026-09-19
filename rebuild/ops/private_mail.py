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
# Django's own record separator: write_message() emits the message, then 79 dashes, then a newline.
SEPARATOR = b'\n' + b'-' * 79 + b'\n'
SYNTHETIC_DOMAIN = '@synthetic.quillmd.invalid'
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
MAX_CHANGED_PATHS = 8
MAX_RECORDS = 256


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


def _records(blob):
    """Split one outbox file into the messages it holds. A file routinely holds more than one."""
    chunks = [chunk for chunk in blob.split(SEPARATOR) if chunk.strip()]
    if len(chunks) > MAX_RECORDS:
        raise MailUnavailable('more messages in one file than a single test run can explain')
    return chunks


def _recipients(chunk):
    """This one record's To: addresses, lowercased. Never raises with content attached."""
    try:
        parsed = email.message_from_bytes(chunk)
        return [found.lower() for _, found in getaddresses(parsed.get_all('To') or []) if found]
    except Exception:
        return []


def route(kind, address, before, root=OUTBOX, notes=None, verify=None):
    """The `/<kind>/<token>/` path from THIS run's message to `address`, or raise MailUnavailable.

    `before` is a `snapshot()` taken before the action that sends the message. `verify`, if given, is a
    predicate over the extracted token that binds the message to the RECORD this run created; a token that
    does not satisfy it is refused, never swapped for another candidate. `notes`, if given, is filled with
    counts a report MAY publish: how many paths changed, how many records this run owned, how many belonged
    to somebody else, how many files could not be read, and whether the token bound. Counts and booleans
    only — never a name, never content, never the token.

    ⚠️ THE RETURNED STRING IS THE SECRET ITSELF. Navigate to it. Do not log it, store it, assert on it,
    put it in a report, or pass it to a subprocess.
    """
    if kind not in KINDS:
        raise MailUnavailable('unknown route kind')
    address = address.lower()
    if not address.endswith(SYNTHETIC_DOMAIN):
        raise MailUnavailable('only a synthetic test address may be located')
    pattern = re.compile(KINDS[kind])
    changed = _changed(root, before)
    mine, foreign, outside, unreadable = [], 0, 0, 0
    for name in changed:
        try:
            blob = private_storage.read_file(Path(root), name)
        except Exception:
            # A file that cannot be read is counted, not quoted: its content is not ours to report.
            unreadable += 1
            continue
        try:
            for chunk in _records(blob):
                recipients = _recipients(chunk)
                if address in recipients:
                    mine.append(chunk)
                    continue
                # Somebody else's message, sharing this file because the filenames collided. It is never
                # matched against a route pattern and never described beyond a count — but it HAS been
                # read, because read_file is all-or-nothing. See the module docstring.
                foreign += 1
                if any(not found.endswith(SYNTHETIC_DOMAIN) for found in recipients) or not recipients:
                    outside += 1
        finally:
            del blob
    if notes is not None:
        notes.update({'changed_paths': len(changed), 'records_for_this_run': len(mine),
                      'records_for_others': foreign, 'records_outside_synthetic': outside,
                      'files_unreadable': unreadable})
    if outside:
        # A message for an address this harness is not entitled to touch shared a file with the run's own.
        # The bytes are already here; stopping is what is left, and it is better than continuing quietly.
        mine.clear()
        raise MailUnavailable('a changed outbox file also holds %d message(s) addressed outside the '
                              'synthetic test domain; stopping rather than continuing' % outside)
    if not mine:
        raise MailUnavailable('no message for this run was found among %d changed file(s), %d of which '
                              'could not be read' % (len(changed), unreadable))
    if len(mine) > 1:
        # Two records for one unique per-run address means the run is not the only writer, or the address
        # is not unique. Either way the next line would be a guess.
        raise MailUnavailable('more than one message is addressed to this run')
    try:
        match = pattern.search(mine[0].decode('utf-8', 'replace'))
    finally:
        mine.clear()
    if not match:
        raise MailUnavailable("the run's message carries no %s link" % kind)
    token = match.group('token')
    if verify is not None:
        try:
            bound = bool(verify(token))
        except Exception:
            # A predicate that raises is a predicate that did not say yes. Never quoted: it was handed the
            # token, so its message could carry one.
            bound = False
        if notes is not None:
            notes['token_bound'] = bound
        if not bound:
            del token
            raise MailUnavailable('the located %s token does not belong to the record this run created' % kind)
    elif notes is not None:
        notes['token_bound'] = None
    return '/%s/%s/' % (kind, token)


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
