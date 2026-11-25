"""The customer contract (BUILD-SPEC 6; client contract customer-2026-11-24): every payload the customer page reads,
built from stored rows on each request.

- session_json: GET /api/session.
- list_rows: GET /api/encounters.
- encounter_json: GET /api/encounters/<id> - the document and its in-page view, the practice's context, the progress of
  the latest coding round, its code lines (each with its line, the second check's verdict, its quotes, its current
  decision - with the id an undo names - and the decisions the member may record), its questions (each naming the
  lines it affects), every answer given, its notes (the documentation problems, then the reason of every review the
  second check wrote that could not be tied to one line), the export readiness, the exports and the activity (a
  decision named by its line and its code).
- view_content: what GET /api/encounters/<id>/original?view=1 serves - the original PDF or text, a pasted text, or for
  a Word document the PDF the coding review read (CodingRound.view_pdf_*: the converted file, so the pages the quotes
  name are the pages shown).

Only the latest round is shown: while it is queued or running, failed or stopped, it has no codes. Every code row is a
line of its own (FIX-SPEC 1: L1.. the reader's, M1.. the second check's additions), and its decision, quotes and
allowed actions are that line's - two lines with one code are decided apart. Quotes are the round's citations - the
passages the API itself verified against the document (fable.result.citations), filed under each line by the line's
marker section - and only for a line with none, the quotes the answer's JSON gave as its evidence. A question names the
lines it affects, and the codes it shows are those lines' codes. An encounter with no coding round (a record of the
earlier system) reads as an earlier review, with nothing of the earlier tables shown: Review again (POST retry) codes it
with the current version.

The second check as the customer reads it (FIX-SPEC-2 section 3): its verdict and reason as written; "The second check
did not give a clear verdict." where its verdict is neither exactly agree nor exactly disagree (never "disagrees"); CPT
Studio's own sentence where it gave none, where a review could not be placed on the line, or - on a line it added - with
the status it gave that line.

Display hygiene (BUILD-SPEC 7.4): the text the coding review wrote - reasons, the second check's reasons, questions,
documentation notes, the reasons of reviews no line could hold, and the evidence quotes its JSON gave - passes through
shown(), which replaces vendor and model names (the shared denylist's name rules, ops/verification/customer-denylist.json;
a test pins them) with "the system" and changes nothing else. Codes, modifiers, statuses and the passages the API cited
from the document are never touched (a modifier is part of the code line Fable returned; a blank modifier item carries
nothing and is never shown).
No payload carries a provider, model, usage, cost, hash, run or request id, and a platform operator's act reads as CPT
Studio's: the activity names members of the workspace only.
"""
from __future__ import annotations

import re
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from typing import NamedTuple, Optional

from django.db.models import Exists, OuterRef
from django.utils import timezone

from . import decisions, jobs, models, state
from .fable import result as fable_result
from .storage import ALLOWED_SUFFIXES, read_own_original

Round, Revision, Export = models.CodingRound, models.SourceRevision, models.ExportArtifact
PDF, DOCX, TEXT = ALLOWED_SUFFIXES['.pdf'], ALLOWED_SUFFIXES['.docx'], ALLOWED_SUFFIXES['.txt']
TEXT_SERVED = 'text/plain; charset=utf-8'

EARLIER = 'earlier'  # an encounter with no coding round: a record of the earlier system
STATE_LABELS = {**state.LABELS, EARLIER: 'Earlier review'}
QUEUE_STATES = (state.AWAITING_ANSWER, state.NEEDS_REVIEW, state.READY)  # what waits on a member (the queue count)
EARLIER_MESSAGE = ('This document was reviewed by an earlier version of CPT Studio. Review it again to code it with the '
                   'current version.')
CODE_STATUS_LABELS = {'ready': 'Ready for approval', 'needs_answer': 'Needs your answer',
                      'needs_review': 'Needs your review', 'not_supported': 'Not supported'}
QUEUED, READING, CHECKING, DONE, FAILED, STOPPED = 'queued', 'reading', 'checking', 'done', 'failed', 'stopped'
BUSY_PHASES = (QUEUED, READING, CHECKING)
# The second check's reason where it gave no verdict on a line, gave no clear one, or where a review could not be placed
# on it: CPT Studio's own sentences (fable.result.combine counts the reviews behind each).
ADDED_BY_CHECK = 'The second check found this code; it needs your review.'
ADDED_WITH_STATUS = 'The second check found this code and listed it as {status}; it needs your review.'
CHECK_STATUS_WORDS = {'ready': 'ready for approval', 'needs_answer': 'needing an answer'}  # a missed code's statuses
NOT_CHECKED = 'The second check did not review this code.'
UNCLEAR_VERDICT = 'The second check did not give a clear verdict.'
UNMATCHED_CHECK = ('A review by the second check names this line or this code but not both, so this code needs your '
                   'review.')
ALSO_UNMATCHED = ('Another review by the second check names this line or this code but not both, so this code needs '
                  'your review.')
UNPLACED_CHECK = 'A review by the second check names none of these lines, so this code needs your review.'
ALSO_UNPLACED = 'Another review by the second check names none of these lines, so this code needs your review.'
# A note on the encounter for each review that belongs to no line (FIX-SPEC-2 section 3), with its reason as written
UNPLACED_NOTE = 'The second check made a comment that could not be tied to one line'
OPERATOR = 'CPT Studio'  # who an act of anyone but a member of the workspace reads as (a platform operator's)
STOPPING_MESSAGE = 'Stopping. A step that is already running finishes; nothing after it starts.'
STOPPED_MESSAGE = 'Stopped by a workspace member. Resume to continue the coding review.'
INTERRUPTED_MESSAGE = 'The coding review was interrupted before it finished. Resume to continue it.'
PAUSED_MESSAGE = 'Waiting for the coding service. The coding review continues when it is back; nothing is lost.'
BLOCKERS = {EARLIER: 'Review this document again to code it with the current version.',
            'busy': 'The coding review has not finished.',
            STOPPED: 'The coding review was stopped before it finished.',
            FAILED: 'The coding review could not finish.',
            'none_approved': 'No code has been approved.'}


def iso(value) -> Optional[str]:
    """A timestamp as the contract carries it: UTC, to the second, with Z."""
    if value is None:
        return None
    return value.astimezone(dt_timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


# --- display hygiene (BUILD-SPEC 7.4) --------------------------------------------------------------------------------------
# The shared denylist's name rules (ops/verification/customer-denylist.json: provider_name, provider_name_joined,
# model_id, interpreter_model), read here as replacements. The ops directory is not in the image, so the names are
# repeated; tests/test_api_customer.py pins them to the file's patterns and vectors. A model family's name (Opus, Sonnet,
# Haiku) is a name only where it continues a vendor's ("Claude 3 Opus" and "Claude Sonnet 4.5" read "the system"):
# alone it is an ordinary or a clinical word (the OPUS trial, a MED-EL SONNET 2 processor, a haiku), as another
# company's product named in a note is ("the patient asked ChatGPT"). A bare "GPT" or "GPT 45" is not a name either,
# because GPT is also the liver enzyme ALT ("GPT 45 U/L", "SGPT"): only "gpt-<x>" is a model id.

NAMES = 'corti|astra|fable|openai|anthropic|claude|gemini|google'
JOINED_NAMES = 'Corti|Astra|Fable|Openai|OpenAI|Anthropic|Claude|Gemini|Google'
ANTHROPIC = 'anthropic|claude'  # the names a model family continues
FAMILIES = 'opus|sonnet|haiku'
# a model's version: numbers of one or two digits joined by dots, dashes or underscores ("3.5", "3-5", "3_5", "2"),
# never a longer number, which in a note is a CPT code or a date ("45385-59", "2026-11-02"); a range of small numbers
# after a word taken for a name is read as a version (a recorded limit, as on main for one number)
VERSION = r'v?\d{1,2}(?:[._-]\d{1,2})*'
# What stands between the parts of one name run: anything a reader sees as a gap or as nothing - white space of any kind,
# control and invisible format characters (Unicode's default-ignorables, those above the BMP too), the blank Braille
# cell, every dash (Unicode category Pd) and the underscore - so "Claude" and "Opus" on either side of a line break, a
# non-breaking space or a zero-width space are one run (refutation rounds 3 and 4); never other punctuation.
GAP = r'[\s_\-\x00-\x1f\x7f-\x9f\u00a0\u00ad\u034f\u058a\u05be\u061c\u115f-\u1160\u1400\u1680\u17b4-\u17b5\u1806\u180b-\u180f\u2000-\u200f\u2010\u2011\u2012\u2013\u2014\u2015\u2028-\u202f\u205f-\u206f\u2212\u2800\u2e17\u2e1a\u2e3a\u2e3b\u2e40\u2e5d\u3000\u301c\u3030\u30a0\u3164\ufe00-\ufe0f\ufe31\ufe32\ufe58\ufe63\ufeff\uff0d\uffa0\ufff9-\ufffc\U00010ead\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]+'
_MODEL_ID = re.compile(r'\b(?:gpt|claude|gemini)-[a-z0-9]+(?:[.-][a-z0-9]+)*', re.ASCII | re.IGNORECASE)
# a Claude model id with the model family that continues it ("claude-3.5 Sonnet 4"): families continue Anthropic's names
# only, so a device after another vendor's id stays ("gpt-4o - OPUS 2 processor")
# (the id is an atomic group: a whole id such as claude-3-5-sonnet-20241022 never gives back its own family to this
# pattern, so _MODEL_ID replaces it whole)
_CLAUDE_ID_FAMILY = re.compile(rf'\bclaude-(?>[a-z0-9]+(?:[.-][a-z0-9]+)*){GAP}(?:{FAMILIES})(?:{GAP}{VERSION})?(?![a-z0-9])',
                               re.ASCII | re.IGNORECASE)
# One part of a name run: one of Anthropic's names with its version and the model families that follow it, each with its
# own version ("Claude 3 Opus", "Claude Sonnet 4.5"), or another name with its version ("Gemini 2.5"). A run is parts
# joined by gaps ("Gemini Claude Opus 4.5", "Claude Fable 5.2"), bounded by letters and digits only, as the denylist
# bounds a name: "fable_unknown" is replaced, and "affable", "corticosteroid", "corti2", a family's name alone and one
# after another name ("organ of Corti - OPUS 2", "Dr. Claude Corti - OPUS 2") are not.
_RUN_VERSION = rf'(?:{GAP}{VERSION})?'
_ANTHROPIC_PART = rf'(?:{ANTHROPIC}){_RUN_VERSION}(?:{GAP}(?:{FAMILIES}){_RUN_VERSION})*'
_OTHER_PART = rf'(?:{NAMES}){_RUN_VERSION}'
_NAME_RUN = re.compile(rf'(?<![a-z0-9])(?:{_ANTHROPIC_PART}|{_OTHER_PART})(?:{GAP}(?:{_ANTHROPIC_PART}|{_OTHER_PART}))*'
                       rf'(?![a-z0-9])', re.ASCII | re.IGNORECASE)
# a capitalized name joined to a word by its case alone ("GeminiTimeout", "readingGemini"), as written
_JOINED = re.compile(rf'(?:{JOINED_NAMES})(?=[A-Z])|(?<=[a-z])(?:{JOINED_NAMES})', re.ASCII)
_SENTENCE_START = re.compile(r'(?:^|[.!?]\s+|\n\s*)$')
_ARTICLE = re.compile(r'(?:^|\s)the\s+$', re.IGNORECASE)


def _the_system(match) -> str:
    before = match.string[:match.start()]
    if _ARTICLE.search(before):
        return 'system'
    return 'The system' if _SENTENCE_START.search(before) else 'the system'


def shown(text):
    """``text`` (written by the coding review) as a customer reads it: every vendor or model name replaced by "the
    system", nothing else changed. Anything that is not a string is returned as it is."""
    if not isinstance(text, str) or not text:
        return text
    for pattern in (_CLAUDE_ID_FAMILY, _MODEL_ID, _NAME_RUN, _JOINED):
        text = pattern.sub(_the_system, text)
    return text


def _shown_or(text, default=None):
    value = shown(text)
    return value if isinstance(value, str) and value.strip() else default


def _shown_question(text):
    """A code row's question as the customer reads it (shown), or None when it is no text or a blank one (the one test
    of a blank question, fable.result.blank_question, under which every text the page drops is blank)."""
    value = shown(text)
    return value if isinstance(value, str) and not fable_result.blank_question(value) else None


# --- the session and the list ----------------------------------------------------------------------------------------------

def initials(user) -> str:
    name = (user.display_name or user.get_username() or '?').replace('-', ' ').replace('_', ' ')
    parts = [part for part in name.split() if part]
    return (''.join(part[0] for part in parts[:2]) or name[:2]).upper()


def _with_rounds(queryset):
    return queryset.annotate(has_round=Exists(Round.objects.filter(encounter_id=OuterRef('pk'))))


def live(queryset):
    """``queryset`` of encounters without the tombstones a disposal leaves (release 1, D1: an Encounter row whose
    destroyed_at is set keeps no PHI and is shown nowhere - not listed, not counted, its routes answer 404)."""
    return queryset.filter(destroyed_at__isnull=True)


def session_json(user, membership) -> dict:
    """GET /api/session: who is signed in, the workspace, the role, the approval attestation and the counts (every
    document, and those waiting on a member: questions to answer, codes to review or to approve)."""
    workspace = membership.workspace
    encounters = live(workspace.encounters.all())
    queue = _with_rounds(encounters).filter(has_round=True, state__in=QUEUE_STATES).count()
    return {'user': {'id': str(user.pk), 'label': user.label(), 'initials': initials(user),
                     'actor_kind': user.actor_kind},
            'workspace': {'id': str(workspace.pk), 'name': workspace.name, 'specialty': workspace.category.name},
            'role': membership.role, 'can_review': bool(membership.can_review),
            # release 1, C4 (D15): an owner sees the team and turns a person's access to this practice off or on
            'can_manage_team': membership.role == models.Membership.OWNER and bool(membership.active),
            'acknowledgement': decisions.acknowledgement_for(user),
            'counts': {'documents': encounters.count(), 'queue': queue}}


# --- the team (release 1, C4) -----------------------------------------------------------------------------------------
# GET api/members, for a practice's owners (D15): everyone with a membership in the practice - automated and
# operator-added accounts included - by label and username, their role, whether their access here is on (the
# membership's: the switch an owner turns), their kind, their last sign-in and whether their password must still be
# changed: the shape Lane 2's Team panel reads (the lead's contract of 2026-11-24). Never a password, a hash or another
# practice's person. The owner's own row and the last active owner are refused by the act itself (api.member_access).

def member_json(row, last_sign_in) -> dict:
    """One membership as the Team panel shows it (the contract's member type)."""
    person = row.user
    return {'id': str(person.pk), 'label': person.label(), 'username': person.username, 'role': row.role,
            'active': bool(row.active), 'actor_kind': person.actor_kind, 'last_sign_in': iso(last_sign_in),
            'password_change_required': person.password_change_required_at is not None}


def last_sign_ins(usernames) -> dict:
    """{username: the time of its latest successful sign-in} (a LoginAttempt that signed in: B1's signed_in, and the
    rows an older release wrote with succeeded true)."""
    # each name's newest row (refutation round 1, avail-5), every name in one statement (refutation round 2, phi-0)
    return models.LoginAttempt.objects.latest_sign_ins(usernames)


def members_json(membership) -> list:
    """GET api/members: the practice's memberships, by the name each signs in with."""
    rows = list(models.Membership.objects.filter(workspace_id=membership.workspace_id).select_related('user')
                .order_by('user__username', 'pk'))
    last = last_sign_ins(row.user.username for row in rows)
    return [member_json(row, last.get(row.user.username)) for row in rows]


def _values(encounter) -> dict:
    return encounter.user_values if isinstance(encounter.user_values, dict) else {}


def service_date(encounter) -> Optional[str]:
    value = _values(encounter).get('service_date')
    return value if isinstance(value, str) and value else None


def insurance(encounter) -> str:
    value = _values(encounter).get('insurance')
    return value if value in jobs.INSURANCE else 'unknown'


def stored_state(encounter, has_round: bool) -> str:
    """The state a list row shows: the stored derived state of an encounter with a round (computed again when the
    stored value is not one of today's), 'earlier' for one with none."""
    if not has_round:
        return EARLIER
    if encounter.state in state.LABELS:
        return encounter.state
    return state.compute(encounter) or EARLIER


def document_kind(encounter) -> str:
    revision = encounter.current_revision
    if revision is not None and revision.kind in (Revision.UPLOAD, Revision.PASTE):
        return revision.kind
    return Revision.UPLOAD if encounter.files.exists() else Revision.PASTE


def list_rows(membership) -> list:
    """GET /api/encounters: the workspace's encounters, newest first."""
    rows = _with_rounds(live(membership.workspace.encounters.select_related('current_revision'))).order_by('-created_at')
    out = []
    for encounter in rows:
        value = stored_state(encounter, encounter.has_round)
        out.append({'id': str(encounter.pk), 'title': encounter.title, 'state': value,
                    'state_label': STATE_LABELS.get(value, value), 'service_date': service_date(encounter),
                    'insurance': insurance(encounter), 'created_at': iso(encounter.created_at),
                    'kind': document_kind(encounter)})
    return out


# --- the document and its view ----------------------------------------------------------------------------------------------

def original_file(encounter):
    """The encounter's uploaded original (its first file), or None for pasted text."""
    return encounter.files.order_by('uploaded_at', 'pk').first()


def _root_revision(encounter):
    """The revision the document is (an earlier system's addendum revision stands on its parent's document)."""
    revision, steps = encounter.current_revision, 0
    while revision is not None and revision.kind == Revision.ADDENDUM and revision.parent_id and steps < 1000:
        revision, steps = revision.parent, steps + 1
    return revision


def converted_view(encounter):
    """The newest round of the encounter that stored the PDF its Word document was converted to, or None."""
    return (Round.objects.filter(encounter_id=encounter.pk, view_pdf_storage_name__isnull=False)
            .exclude(view_pdf_storage_name='').order_by('-number').first())


def safe_name(name, fallback='original') -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name or '')[:120] or fallback


def converted_name(source) -> str:
    """The file name a Word document's converted PDF is served under: the Word file's name with .pdf."""
    stem = (source.original_name or 'document').rsplit('.', 1)[0]
    return safe_name(f'{stem}.pdf', 'document.pdf')


def _converted_file(view):
    """The stored converted PDF of ``view`` (a round with view_pdf_*), as storage.read_original reads a file."""
    return SimpleNamespace(storage_name=view.view_pdf_storage_name, sha256=view.view_pdf_sha256)


def view_content(encounter):
    """(bytes, content type, file name) the in-page viewer shows, or None when there is nothing to show: the original
    PDF or text file, the pasted text, or for a Word document the PDF the coding review read. A stored file that no
    longer matches its sha256 raises storage.OriginalCorrupted."""
    source = original_file(encounter)
    if source is None:
        revision = _root_revision(encounter)
        if revision is None or revision.kind != Revision.PASTE:
            return None
        return (revision.pasted_text or '').encode('utf-8'), TEXT_SERVED, 'pasted-text.txt'
    if source.media_type == PDF:
        return read_own_original(encounter.workspace_id, source), PDF, safe_name(source.original_name)
    if source.media_type == TEXT:
        return read_own_original(encounter.workspace_id, source), TEXT_SERVED, safe_name(source.original_name)
    if source.media_type == DOCX:
        view = converted_view(encounter)
        if view is None:
            return None
        return read_own_original(encounter.workspace_id, _converted_file(view)), PDF, converted_name(source)
    return None


# --- the document's download (release 1, C6) --------------------------------------------------------------------------
# A Word document someone else uploaded can carry links, embedded objects and field codes that Word on the reader's
# computer acts on (UP-6), so its download is the PDF the coding review read - the file the in-page view shows. The Word
# file itself is served only when asked for by name (?format=original), after the page's warning (Lane 2, app.js); a
# Word document with no converted PDF yet is refused until then (OriginalOnly). Every download is recorded with the
# format it served (C1: member.download; ops.original).

ORIGINAL, CONVERTED = 'original', 'converted_pdf'  # the formats a download is recorded with
EXTENSIONS = {media_type: suffix.lstrip('.') for suffix, media_type in ALLOWED_SUFFIXES.items()}
ORIGINAL_ONLY = ('This Word document has no PDF copy yet. Download the original Word file instead: it can contain links '
                 'and embedded content.')


class OriginalOnly(Exception):
    """A Word document with no converted PDF yet: its download is the Word file, asked for by name (format=original)."""


class Download(NamedTuple):
    data: bytes
    content_type: str
    filename: str  # the member's file name (the operator's is encounter-<reference>.<extension>: studio.operator)
    fmt: str  # ORIGINAL or CONVERTED
    sha256: str
    extension: str


def download_content(encounter, *, original=False) -> Optional[Download]:
    """The document's download (see above), or None for a paste, which has none. A stored file that no longer matches
    its sha256 raises storage.OriginalCorrupted; a Word document with no converted PDF yet raises OriginalOnly unless
    ``original`` asks for the Word file."""
    source = original_file(encounter)
    if source is None:
        return None
    if source.media_type == DOCX and not original:
        view = converted_view(encounter)
        if view is None:
            raise OriginalOnly(ORIGINAL_ONLY)
        return Download(read_own_original(encounter.workspace_id, _converted_file(view)), PDF, converted_name(source),
                        CONVERTED,
                        view.view_pdf_sha256, 'pdf')
    return Download(read_own_original(encounter.workspace_id, source), source.media_type, safe_name(source.original_name),
                    ORIGINAL, source.sha256,
                    EXTENSIONS.get(source.media_type, 'bin'))


def document_json(encounter) -> dict:
    """The document block: what was uploaded or pasted, its download (an upload's) and its in-page view."""
    base = f'/api/encounters/{encounter.pk}/original'
    source = original_file(encounter)
    if source is None:
        revision = _root_revision(encounter)
        text = revision.pasted_text if revision is not None and revision.kind == Revision.PASTE else None
        return {'name': None, 'media_type': TEXT, 'size': len(text.encode('utf-8')) if text is not None else None,
                'kind': Revision.PASTE, 'original_url': None, 'view_url': f'{base}?view=1' if text is not None else None,
                'view_media_type': TEXT if text is not None else None, 'converted': False}
    view_type, converted = None, False
    if source.media_type in (PDF, TEXT):
        view_type = source.media_type
    elif source.media_type == DOCX and converted_view(encounter) is not None:
        view_type, converted = PDF, True
    return {'name': source.original_name, 'media_type': source.media_type, 'size': source.size,
            'kind': Revision.UPLOAD, 'original_url': base, 'view_url': f'{base}?view=1' if view_type else None,
            'view_media_type': view_type, 'converted': converted}


# --- the round: progress, codes, questions -------------------------------------------------------------------------------------

def phase(round_) -> str:
    if round_ is None:
        return EARLIER
    if round_.state in (Round.QUEUED, Round.RUNNING):
        if round_.reader_result is not None:
            return CHECKING  # the reader's answer is in: the checker is next (or waiting for a slot)
        return READING if round_.state == Round.RUNNING else QUEUED
    return {Round.DONE: DONE, Round.FAILED: FAILED, Round.CANCELLED: STOPPED}.get(round_.state, FAILED)


def progress_json(encounter, round_, can_review: bool, now) -> dict:
    current = phase(round_)
    busy = current in BUSY_PHASES
    stopping = busy and encounter.stopped_at is not None
    message, error = '', None
    if round_ is None:
        message = EARLIER_MESSAGE
    elif stopping:
        message = STOPPING_MESSAGE
    elif busy and jobs.worker_responding(now=now) is False:
        message = PAUSED_MESSAGE
    elif current == STOPPED:
        message = STOPPED_MESSAGE if encounter.stopped_at is not None else INTERRUPTED_MESSAGE
    if current == FAILED:
        error = {'text': round_.error or jobs.FAILURE_TEXT[jobs.FAILED]}
    running = jobs.busy(encounter) if round_ is not None else False
    return {'phase': current, 'busy': busy,
            'started_at': iso(round_.started_at) if round_ is not None else None,
            'finished_at': iso(round_.finished_at) if round_ is not None else None,
            'server_time': iso(now), 'message': message,
            'can_stop': can_review and busy and not stopping,
            # a send of the round that awaits an operator's reconcile is never offered again (jobs.resume refuses it)
            'can_resume': can_review and current == STOPPED and not running and not jobs.awaiting_reconcile(round_),
            'can_retry': can_review and decisions.retry_offered(encounter, round_),
            'error': error}


def citation_index(round_) -> dict:
    """{line: [(text, page)]} of the round's citations, each line's reader citations then its checker's."""
    index: dict = {}
    citations = round_.citations if isinstance(round_.citations, dict) else {}
    for key, items in citations.items():
        if not isinstance(key, str) or not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
                index.setdefault(key, []).append((item['text'], item.get('page')))
    return index


def _page(value) -> Optional[int]:
    return value if type(value) is int and value > 0 else None


def quotes(row, index) -> list:
    """A line's quotes: its citations (the document's own words, verified by the API, shown exactly), or only when it
    has none, the evidence quotes its JSON gave (written by the coding review, so shown through shown()); each passage
    once."""
    line = row.get('line') if isinstance(row.get('line'), str) else None
    found = (index.get(line) if line is not None else None) or [
        (shown(item.get('quote')), item.get('page')) for item in row.get('evidence') or ()
        if isinstance(item, dict) and isinstance(item.get('quote'), str) and item['quote'].strip()]
    out, seen = [], set()
    for text, page in found:
        key = (' '.join(text.split()), _page(page))
        if key not in seen:
            seen.add(key)
            out.append({'text': text, 'page': _page(page)})
    return out


def decision_json(decision) -> Optional[dict]:
    """A line's current decision as the page shows it; ``id`` is what an undo names (FIX-SPEC-2 section 5)."""
    if decision is None:
        return None
    return {'id': str(decision.pk), 'action': decision.action, 'by': decision.reviewer.label(),
            'at': iso(decision.created_at), 'note': decision.note}


def _count(value) -> int:
    return value if type(value) is int and value > 0 else 0


def check_json(row) -> dict:
    """The second check as the customer reads it (module docstring): its verdict on a reader line and its reason as
    written; for a verdict neither exactly agree nor exactly disagree, no verdict and the sentence that says it gave no
    clear one; CPT Studio's sentence where it gave none, or for a line it added, with the status it gave it - and where a
    review could not be placed on a line (fable.result.combine), the sentence that says so, never that the line was not
    reviewed."""
    if row.get('listed_by') == 'checker':
        words = CHECK_STATUS_WORDS.get(row.get('listed_status'))
        return {'agrees': None, 'reason': ADDED_WITH_STATUS.format(status=words) if words else ADDED_BY_CHECK}
    check = row.get('second_check') if isinstance(row.get('second_check'), dict) else {}
    agrees = check.get('agrees') if isinstance(check.get('agrees'), bool) else None
    unmatched, unplaced = _count(check.get('unmatched')), _count(check.get('unplaced'))
    if agrees is None:
        reason = UNMATCHED_CHECK if unmatched else UNPLACED_CHECK if unplaced else NOT_CHECKED
        return {'agrees': None, 'reason': reason}
    words = [_shown_or(check.get('reason'))]
    if agrees is False and check.get('verdict') != fable_result.DISAGREE:  # neither agree nor disagree, as written
        agrees, words = None, [UNCLEAR_VERDICT, *words]
    words += [ALSO_UNMATCHED] * bool(unmatched) + [ALSO_UNPLACED] * bool(unplaced)
    return {'agrees': agrees, 'reason': ' '.join(word for word in words if word) or None}


def _modifiers(value) -> Optional[list]:
    """A line's modifiers as stored (a list of strings; a blank item carries nothing and is not shown), or None when
    they were not given - the page, the JSON and the exports show the same list (FIX-SPEC-2 section 2)."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [item for item in value if item.strip()]


def code_json(row, index, decision, can_review: bool) -> dict:
    status = row.get('status')
    return {'line': row.get('line'), 'code': row.get('code'),
            'units': row.get('units') if type(row.get('units')) is int and row['units'] >= 0 else None,
            'modifiers': _modifiers(row.get('modifiers')),
            'status': status, 'status_label': CODE_STATUS_LABELS.get(status, 'Not reviewable'),
            'reason': _shown_or(row.get('reason'), ''), 'second_check': check_json(row),
            'question': _shown_question(row.get('question')), 'quotes': quotes(row, index),
            'decision': decision_json(decision), 'allowed_actions': decisions.allowed_actions(row, decision, can_review)}


def line_rows(round_) -> list:
    """The code lines of a round as stored, in order: each a dict with a line, a code and a status the page shows."""
    return [row for row in round_.codes or () if isinstance(row, dict) and isinstance(row.get('line'), str)
            and isinstance(row.get('code'), str) and row.get('status') in CODE_STATUS_LABELS]


def round_rows(round_, current, can_review: bool) -> list:
    """The code lines of a done round (its stored order), each with its current decision; [] for any other round."""
    if round_ is None or round_.state != Round.DONE:
        return []
    index = citation_index(round_)
    return [code_json(row, index, current.get(row['line']), can_review) for row in line_rows(round_)]


def questions_json(round_) -> list:
    """The round's questions, each naming the lines it affects and showing those lines' codes (never a code it named
    that is no line's)."""
    if round_ is None or round_.state != Round.DONE:
        return []
    codes = {row['line']: row['code'] for row in line_rows(round_)}
    out = []
    for identifier, item in decisions.round_questions(round_):
        named = item.get('lines') if isinstance(item.get('lines'), list) else []
        lines = list(dict.fromkeys(line for line in named if isinstance(line, str) and line in codes))
        out.append({'id': identifier, 'text': shown(item['text']),
                    'codes': list(dict.fromkeys(codes[line] for line in lines)), 'lines': lines})
    return out


def answers_json(encounter) -> list:
    rows = models.CodingAnswer.objects.filter(encounter_id=encounter.pk).select_related('answered_by').order_by(
        'answered_at', 'pk')
    return [{'question': shown(row.question), 'answer': row.answer, 'by': row.answered_by.label(),
             'at': iso(row.answered_at)} for row in rows]


def notes_json(round_) -> list:
    """The notes on a done round: its documentation problems, then a note for every review of the second check that
    belongs to no line (fable.result.unmatched_reviews), with its reason as written (FIX-SPEC-2 section 3)."""
    if round_ is None or round_.state != Round.DONE:
        return []
    notes = [shown(item) for item in round_.problems or () if isinstance(item, str) and item.strip()]
    for item in fable_result.unmatched_reviews(round_.codes, round_.checker_result):
        reason = _shown_or(item['reason'])
        notes.append(f'{UNPLACED_NOTE}: {reason}' if reason else f'{UNPLACED_NOTE}.')
    return notes


def readiness(round_, current) -> dict:
    """What can be exported now (BUILD-SPEC 6, 8): a draft once the latest round is done, the approved export once a
    code of it is approved; the blockers say why not, in the member's words."""
    if round_ is None:
        return {'draft': False, 'approved': False, 'blockers': [BLOCKERS[EARLIER]]}
    if round_.state != Round.DONE:
        key = {Round.FAILED: FAILED, Round.CANCELLED: STOPPED}.get(round_.state, 'busy')
        return {'draft': False, 'approved': False, 'blockers': [BLOCKERS[key]]}
    approved = bool(approved_lines(round_, current))
    return {'draft': True, 'approved': approved, 'blockers': [] if approved else [BLOCKERS['none_approved']]}


def approved_lines(round_, current) -> list:
    """The lines of a done round the approved export lists: those whose current decision is approve and whose status
    is ready or needs_review (FIX-SPEC 1)."""
    return [row['line'] for row in line_rows(round_) if row.get('status') in decisions.DECIDABLE
            and current.get(row['line']) is not None
            and current[row['line']].action == models.CodeDecision.APPROVE]


def export_current(export, latest_round_id, last_decision_at=None) -> bool:
    """Whether ``export`` is current: made from the latest round, and no decision on that round recorded after it. The
    page's rule, and the rule a request for the same report reuses a stored copy by (release 1, C5: studio.exports)."""
    return export.round_id == latest_round_id and (last_decision_at is None or last_decision_at <= export.created_at)


def last_decision_at(round_id):
    """When the latest decision on round ``round_id`` was recorded, or None."""
    return models.CodeDecision.objects.filter(round_id=round_id).order_by('-created_at').values_list(
        'created_at', flat=True).first()


def report_json(export, latest_round_id, last_decision_at=None) -> dict:
    """One export as the page lists it; ``current`` while it was made from the latest round and no decision on that
    round was recorded after it (an earlier one is still listed and served as stored, marked earlier)."""
    current = export_current(export, latest_round_id, last_decision_at)
    return {'id': str(export.pk), 'kind': export.kind, 'fmt': export.fmt, 'filename': export.filename,
            'generated_at': iso(export.created_at), 'download_url': f'/api/reports/{export.pk}/download',
            'current': current}


def reports_json(encounter, round_) -> list:
    exports = Export.objects.filter(encounter_id=encounter.pk).order_by('-created_at', '-pk').only(
        'pk', 'kind', 'fmt', 'filename', 'created_at', 'round_id')
    decided = last_decision_at(round_.pk) if round_ is not None else None
    return [report_json(export, round_.pk if round_ is not None else None, decided) for export in exports]


# --- the activity ------------------------------------------------------------------------------------------------------------

def _plural(value, one, many) -> str:
    return f'{value} {one if value == 1 else many}'


def _activity_text(event, numbers, members) -> str:
    data = event.data if isinstance(event.data, dict) else {}
    who = event.actor.label() if event.actor_id is not None and event.actor_id in members else OPERATOR
    name = event.event
    if name == 'encounter.created':
        return f'Pasted by {who}.' if data.get('kind') == Revision.PASTE else f'Uploaded by {who}.'
    if name == 'coding.round_queued':
        return f'{who} asked for the coding review again.' if data.get('trigger') == Round.RETRY else ''
    if name == 'answers.recorded' and type(data.get('count')) is int:
        return f'{who} answered {_plural(data["count"], "question", "questions")}.'
    if name in ('coding.round_done', 'coding.round_failed'):
        number = numbers.get(data.get('round'))
        review = f'Coding review {number}' if number else 'The coding review'
        if name == 'coding.round_failed':
            return f'{review} could not finish.'
        if data.get('codes') == 0:
            return f'{review} finished with no codes.'
        if type(data.get('questions')) is int and data['questions'] > 0:
            return f'{review} finished with {_plural(data["questions"], "question", "questions")}.'
        return f'{review} finished.'
    if name == 'decision.recorded' and 'round' in data and isinstance(data.get('code'), str):
        words = {decisions.APPROVE: 'approved', decisions.REJECT: 'rejected',
                 decisions.REVOKE: 'undid the decision on'}.get(data.get('action'))
        line = data.get('line')  # two lines can hold one code: the line names which (FIX-SPEC-2 section 5)
        named = f'{line} {data["code"]}' if isinstance(line, str) and line else data['code']
        return f'{who} {words} {named}.' if words else ''
    if name == 'export.created':
        return f'{"Approved" if data.get("kind") == Export.APPROVED else "Draft"} download made by {who}.'
    if name == 'pipeline.stopped':
        return f'Stopped by {who}.'
    if name == 'pipeline.resumed':
        return f'Resumed by {who}.'
    return ''


# The events the activity shows (_activity_text's): read in SQL by name (release 1, C1 item 8; FLOW-11 (4)), so no other
# row of the document's audit trail - an operator's act, a reuse of a report, whatever a later release records - is read
# into the page. Reads of the document are AccessRecords, in their own table, and never reach it.
ACTIVITY_EVENTS = ('encounter.created', 'coding.round_queued', 'answers.recorded', 'coding.round_done',
                   'coding.round_failed', 'decision.recorded', 'export.created', 'pipeline.stopped', 'pipeline.resumed')


def activity_json(encounter) -> list:
    """What happened to the document, oldest first, each in a fixed sentence (never an event's stored data as text).
    An act names its member - anyone holding a membership of the workspace, active or not - and anyone else's act (a
    platform operator's retry) reads as CPT Studio's: who did it is the operator's record, never the practice's."""
    numbers = {str(pk): number for pk, number in Round.objects.filter(encounter_id=encounter.pk)
               .values_list('pk', 'number')}
    members = set(models.Membership.objects.filter(workspace_id=encounter.workspace_id)
                  .values_list('user_id', flat=True))
    out = []
    for event in (encounter.audit_events.filter(event__in=ACTIVITY_EVENTS).select_related('actor')
                  .order_by('created_at', 'pk')):
        text = _activity_text(event, numbers, members)
        if text:
            out.append({'at': iso(event.created_at), 'text': text})
    return out


# --- the encounter ------------------------------------------------------------------------------------------------------------

def encounter_json(encounter, membership, *, now=None) -> dict:
    """GET /api/encounters/<id> (BUILD-SPEC 6)."""
    now = now or timezone.now()
    can_review = bool(membership.can_review)
    round_ = state.latest_round(encounter)
    current = state.current_decisions(round_) if round_ is not None and round_.state == Round.DONE else {}
    value = state.compute(encounter) if round_ is not None else EARLIER
    return {
        'id': str(encounter.pk), 'title': encounter.title, 'created_at': iso(encounter.created_at),
        'updated_at': iso(encounter.updated_at), 'state': value, 'state_label': STATE_LABELS.get(value, value),
        'permissions': {'can_review': can_review},
        'document': document_json(encounter),
        'context': {'service_date': service_date(encounter), 'insurance': insurance(encounter)},
        'progress': progress_json(encounter, round_, can_review, now),
        'round': ({'number': round_.number, 'trigger': round_.trigger, 'finished_at': iso(round_.finished_at)}
                  if round_ is not None else None),
        'codes': round_rows(round_, current, can_review),
        'questions': questions_json(round_),
        'answers': answers_json(encounter),
        'notes': notes_json(round_),
        'readiness': readiness(round_, current),
        'reports': reports_json(encounter, round_),
        'activity': activity_json(encounter),
    }


def round_json(round_) -> dict:
    """A round as an act's answer gives it (the encounter's ``round`` block)."""
    return {'number': round_.number, 'trigger': round_.trigger, 'finished_at': iso(round_.finished_at)}
