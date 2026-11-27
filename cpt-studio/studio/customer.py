"""The customer contract (BUILD-SPEC 6; client contract customer-2026-11-26): every payload the customer page reads,
built from stored rows on each request.

- session_json: GET /api/session.
- list_page: GET /api/encounters - one page of a list (release 2, R2-19: Documents and the Review queue 50 rows a page,
  the Overview's recent 5), newest first, with the cursor of the next page and, on a first page, the list's total.
- search_page: POST /api/encounters/search - one page of the practice's documents whose row holds the words (R2-20).
- encounter_json: GET /api/encounters/<id> - the document and its in-page view, the practice's context, the progress of
  the latest coding round, its code lines (each with its line, the second check's verdict, its quotes, its current
  decision - with the id an undo names - and the decisions the member may record), its questions (each naming the
  lines it affects), every answer given, its notes (the documentation problems, then the reason of every review the
  second check wrote that could not be tied to one line), the export readiness, the exports and the activity (a
  decision named by its line and its code).
- view_content: what GET /api/encounters/<id>/original?view=1 serves - the original PDF or text, a pasted text, or for
  a Word document the PDF the coding review read (CodingRound.view_pdf_*: the converted file, so the pages the quotes
  name are the pages shown); since release 2 (R2-15) built from view_source (what is shown, read from the rows alone,
  so a re-open the page holds can be answered 304 with no stored file read) and view_bytes (its bytes, checked).

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
import uuid
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from typing import NamedTuple, Optional

from django.db import connection
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.crypto import salted_hmac

from . import decisions, jobs, models, paging, state
from .fable import CONVERT, DOCUMENT
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


def in_queue(queryset):
    """``queryset``'s documents that wait on a member - questions to answer, codes to review or to approve: a stored
    state of QUEUE_STATES and a coding round. The one rule the Review queue's pages, its total and the session's queue
    count all read, so the three agree by construction (release 2, R2-19). The round is tested per document, a one-row
    subquery by the rounds' encounter index, so no statement reads a whole rounds table: a page stops at its 51st row, a
    count probes once per waiting document. An EXISTS let PostgreSQL hash every practice's rounds for the count instead:
    faster wherever about half or more of a large practice waits (customer.session_json
    18.3 ms against 35.9 ms, customer.list_page('queue') 25.1 ms against 40.1 ms, at 18,250 such documents among
    30,000), slower on a practice shaped like live's, where each document has its round and about one in twenty waits
    (the queue's COUNT 7.4 ms against 2.1 ms on section 8's bench data; refutation round 1, avail[1]). These are times
    of the function or the statement alone; a request adds about 5-14 ms (the session, the membership, the record)."""
    first_round = Subquery(Round.objects.filter(encounter_id=OuterRef('pk')).order_by().values('pk')[:1])
    return queryset.filter(state__in=QUEUE_STATES).alias(queue_round=first_round).filter(queue_round__isnull=False)


def live(queryset):
    """``queryset`` of encounters without the tombstones a disposal leaves (release 1, D1: an Encounter row whose
    destroyed_at is set keeps no PHI and is shown nowhere - not listed, not counted, its routes answer 404)."""
    return queryset.filter(destroyed_at__isnull=True)


def session_json(user, membership) -> dict:
    """GET /api/session: who is signed in, the workspace, the role, the approval attestation and the counts (every
    document, and those waiting on a member: questions to answer, codes to review or to approve)."""
    workspace = membership.workspace
    encounters = live(workspace.encounters.all())
    queue = in_queue(encounters).count()
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


def document_kind(encounter, has_file=None) -> str:
    """What the document is: its current revision's kind (upload or paste), or for an earlier system's revision (an
    addendum, or none) an upload when it has a stored file and a paste otherwise. ``has_file``: whether it has one, when
    the caller has read it (the list reads every row's first file in one statement); otherwise asked here."""
    revision = encounter.current_revision
    if revision is not None and revision.kind in (Revision.UPLOAD, Revision.PASTE):
        return revision.kind
    if has_file is None:
        has_file = encounter.files.exists()
    return Revision.UPLOAD if has_file else Revision.PASTE


# --- the paged lists (release 2, R2-19 and R2-16) ---------------------------------------------------------------------
# GET /api/encounters?list=documents|queue|recent[&before=<cursor>] answers {"encounters": [row...], "next", "total"}:
# Documents and the Review queue 50 rows a page (51 read, to know whether more follow), the Overview's recent 5 with no
# next page; newest first - created_at descending, then id (the console's keyset, studio.paging). total is the list's
# exact number on a first page only: the rows' own number when the whole list is on it, else one COUNT; null for recent
# and for a later page. A page is three statements, whatever the practice holds - its rows (one indexed read of
# studio_enc_ws_time, or studio_enc_ws_queue for the queue), the ids among them with a coding round, and each one's first
# stored file - plus that COUNT on a first page that has more. The flags are read apart, over the page's ids: an EXISTS
# in the SELECT list made PostgreSQL hash every practice's rounds for a 51-row page. Each row goes through release 1's
# own rules (stored_state, service_date, insurance, document_kind), so it is release 1's row but for opens_pdf: true when
# the first stored file (original_file's order) is a PDF of at most OPENS_PDF_MAX_BYTES, so the page may ask for its view
# at the click (R2-16; a Word document's converted view is not hinted: release 2 stores no size for it, C6, D-R2-31).

LIST_DOCUMENTS, LIST_QUEUE, LIST_RECENT = 'documents', 'queue', 'recent'
LIST_NAMES = (LIST_DOCUMENTS, LIST_QUEUE, LIST_RECENT)
LIST_PAGE_ROWS, LIST_RECENT_ROWS = 50, 5
OPENS_PDF_MAX_BYTES = 1024 * 1024  # 1 MiB: every live GI PDF qualifies (the largest is 891 KB)
LIST_FIELDS = ('pk', 'title', 'state', 'user_values', 'created_at', 'current_revision__kind')


def list_rows_of(found) -> list:
    """The list rows of ``found`` - step 1's values (LIST_FIELDS) of a page, in order - by R2-19's steps 2 and 3: the
    page's ids that have a coding round, then each one's first stored file (one DISTINCT ON read), each row then built
    by release 1's rules, with opens_pdf."""
    ids = [row['pk'] for row in found]
    rounds = set(Round.objects.filter(encounter_id__in=ids).order_by().values_list('encounter_id', flat=True))
    files = {item['encounter_id']: item for item in models.SourceFile.objects.filter(encounter_id__in=ids)
             .order_by('encounter_id', 'uploaded_at', 'pk').distinct('encounter_id')
             .values('encounter_id', 'media_type', 'size')}
    out = []
    for row in found:
        kind = row['current_revision__kind']
        encounter = SimpleNamespace(pk=row['pk'], state=row['state'], user_values=row['user_values'],
                                    current_revision=SimpleNamespace(kind=kind) if kind is not None else None)
        first = files.get(row['pk'])
        value = stored_state(encounter, row['pk'] in rounds)
        out.append({'id': str(row['pk']), 'title': row['title'], 'state': value,
                    'state_label': STATE_LABELS.get(value, value), 'service_date': service_date(encounter),
                    'insurance': insurance(encounter), 'created_at': iso(row['created_at']),
                    'kind': document_kind(encounter, has_file=first is not None),
                    'opens_pdf': (first is not None and first['media_type'] == PDF
                                  and first['size'] <= OPENS_PDF_MAX_BYTES)})
    return out


def list_page(membership, which, before=None) -> dict:
    """One page of GET /api/encounters (see above) of ``membership``'s practice: ``which`` one of LIST_NAMES, ``before``
    the cursor the page starts after (None: the first page; never for recent) - both read by the API before this, which
    refuses anything else. {'encounters': rows, 'next': the next page's cursor or None, 'total': int or None}."""
    if which not in LIST_NAMES or (before is not None and (which == LIST_RECENT or paging.parse(before) is None)):
        raise ValueError('list_page is given a list and a cursor the API has read.')
    listed = live(models.Encounter.objects.filter(workspace_id=membership.workspace_id))
    if which == LIST_QUEUE:
        listed = in_queue(listed)
    page, _cursor = paging.older_than(listed, before)
    size = LIST_RECENT_ROWS if which == LIST_RECENT else LIST_PAGE_ROWS
    found = list(page.order_by('-created_at', '-pk').values(*LIST_FIELDS)[:size if which == LIST_RECENT else size + 1])
    shown = found[:size]
    more = len(found) > size
    total = None
    if which != LIST_RECENT and before is None:
        total = listed.count() if more else len(shown)
    return {'encounters': list_rows_of(shown),
            'next': paging.cursor_of(shown[-1]['created_at'], shown[-1]['pk']) if more else None, 'total': total}


# --- the search (release 2, R2-20) -------------------------------------------------------------------------------------
# POST /api/encounters/search pages the practice's live documents whose row, as the page draws it, holds the words: the
# page's own rule (app.js applySearch: the row's text, lower-cased, includes the words, trimmed), read in SQL. The row's
# text is documentRow's, rebuilt from the stored row: the title trimmed of JavaScript's white space, or "Untitled
# document"; the kind's label; " · " and the insurance's label when the insurance is shown; the state's label, or "Earlier
# review" for a document with no coding round; the service date as "6 Nov 2026" when it is a calendar date the page reads
# (app.js parseIsoDate: four-digit years from 0100), else "Not entered". Matching is strpos over both sides lower-cased in
# PostgreSQL's builtin pg_c_utf8 collation (PostgreSQL 17 or newer), the words a bound parameter, so nothing in them is a
# wildcard. The browser lower-cases some letters otherwise - a final sigma by its neighbours, a dotted capital I into two
# letters, and capitals newer than PostgreSQL 17's tables (Unicode 15.1), which leave them as they are (SEARCH_NEWER: 27
# of Unicode 16.0, U+1C89, U+A7CB, U+A7CC, U+A7DA, U+A7DC and Garay's U+10D50-U+10D65, and 28 of Unicode 17.0, U+A7CE,
# U+A7D2, U+A7D4 and Beria Erfe's U+16EA0-U+16EB8) - so when the words hold any of these, in either case, or the
# combining dot, both sides are also folded (translate: final sigma to sigma, each newer capital whose letter the words
# hold to the browser's small letter, the combining dot dropped; search_fold), and the search never finds fewer
# documents than the page's rule, more only there. That holds in a browser whose newer letters SEARCH_NEWER holds: one
# on a later Unicode release can lower-case a letter the search does not fold, until the table is extended (D-R2-42;
# API.md's known limits). The words are at most SEARCH_MAX_CHARS characters, not counting the combining dot above
# (U+0307): the one letter whose lower case is longer (U+0130, to i and U+0307) adds only that dot, so the count is the
# same before and after the page lower-cases the words (search_length).
# One statement returns up to 51 rows, newest first, along studio_enc_ws_time; then the list's own steps 2 and 3
# (list_rows_of). The text needs each row's revision kind and whether it has a round (and, for an earlier system's row,
# a file): each is looked up per row, as a one-row subquery, so the walk stops at the 51st match - a join made
# PostgreSQL hash every practice's revisions and sort the practice instead, and an EXISTS inside an expression may be
# planned as a hash of every practice's rounds. A document whose stored state is none of today's would match by its
# stored word, where the page draws it computed; none exists once the app phase has recomputed the states (R2-19's
# recorded risk).

JS_WHITE_SPACE = ('\t\n\x0b\x0c\r \xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f'
                  '\u205f\u3000\ufeff')  # what JavaScript's String.prototype.trim removes (measured on node 22)
# The capitals a browser lower-cases and PostgreSQL 17's tables (Unicode 15.1) do not, each to the letter the browser
# lowers it to, against PostgreSQL 17.11's pg_c_utf8: Unicode 16.0's (node 22.22.0 with ICU 77.1, and Chromium 147) and
# Unicode 17.0's (Chromium 153 with ICU 78). tests/test_lists.py checks over every code point that each engine present
# on its host, and a committed table of Chromium 153's, lower-cases no letter PostgreSQL leaves as it is that this table
# does not map the same way; a browser on a later Unicode release needs its letters added here (API.md's known limits).
SEARCH_NEWER = {'\u1c89': '\u1c8a', '\ua7cb': '\u0264', '\ua7cc': '\ua7cd', '\ua7da': '\ua7db', '\ua7dc': '\u019b',
                **{chr(cp): chr(cp + 0x20) for cp in range(0x10d50, 0x10d66)},  # and Garay's 22 capitals
                '\ua7ce': '\ua7cf', '\ua7d2': '\ua7d3', '\ua7d4': '\ua7d5',  # Unicode 17.0 (Chromium 153, ICU 78)
                **{chr(cp): chr(cp + 0x1b) for cp in range(0x16ea0, 0x16eb9)}}  # and Beria Erfe's 25 capitals
SEARCH_FOLDED = ('\u03a3\u03c3\u03c2\u0130\u0307'  # sigma (capital, small, final), dotted capital I, combining dot above
                 + ''.join(SEARCH_NEWER) + ''.join(SEARCH_NEWER.values()))  # and the newer letters, in either case
SEARCH_MAX_CHARS = 240  # not counting the combining dot above: a row's text is at most about 224 characters
# app.js's own words for the row (KIND_LABELS, INSURANCE_SHOWN, MONTHS' first three letters); tests/test_lists.py holds the
# rebuilt text to the shipped documentRow's (tests/frontend/row_text.cjs)
SEARCH_KIND_TEXT = {Revision.UPLOAD: 'Uploaded file', Revision.PASTE: 'Pasted text'}
SEARCH_INSURANCE_TEXT = {'medicare': 'Medicare', 'medicaid': 'Medicaid', 'commercial': 'Commercial or other'}
SEARCH_MONTHS = 'JanFebMarAprMayJunJulAugSepOctNovDec'


def search_words(text) -> str:
    """The words a search looks for: ``text`` trimmed as the page trims what was typed (JavaScript's trim)."""
    return text.strip(JS_WHITE_SPACE)


def search_fold(words) -> tuple:
    """translate's (FROM, TO) for folding ``words`` and the rows: final sigma to sigma, each newer capital whose letter
    the words hold (in either case) to the browser's small letter, and the combining dot last, past TO's end, so dropped.
    A newer letter the words do not hold cannot take part in a match, so leaving it out changes nothing found - and
    translate reads FROM for every character of every row: all 27, always, doubled a folding search's time at 18,000
    documents (refutation round 1)."""
    held = [capital for capital, small in SEARCH_NEWER.items() if capital in words or small in words]
    return '\u03c2' + ''.join(held) + '\u0307', '\u03c3' + ''.join(SEARCH_NEWER[capital] for capital in held)


def search_length(words) -> int:
    """How long ``words`` are against SEARCH_MAX_CHARS: their characters, not counting the combining dot above (U+0307),
    so the same as typed and as the page lower-cases them (see above)."""
    return len(words) - words.count('\u0307')


def _sql_text(value) -> str:
    """A constant of this module as an SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def search_row_text_sql() -> str:
    """The SQL expression of a row's text (documentRow's, as above) over studio_encounter e, its current revision's kind
    d.kind and its service date d.sd (search_from_sql) - the one expression the search matches and tests/test_lists.py
    compares with the page's."""
    rounds, files = models.CodingRound._meta.db_table, models.SourceFile._meta.db_table
    has_round = f'(SELECT 1 FROM {rounds} r WHERE r.encounter_id = e.id LIMIT 1) IS NOT NULL'
    has_file = f'(SELECT 1 FROM {files} s WHERE s.encounter_id = e.id LIMIT 1) IS NOT NULL'
    title = f"COALESCE(NULLIF(btrim(e.title, %(space)s), ''), {_sql_text('Untitled document')})"
    upload, paste = (_sql_text(SEARCH_KIND_TEXT[kind]) for kind in (Revision.UPLOAD, Revision.PASTE))
    kind = (f"(CASE d.kind WHEN {_sql_text(Revision.UPLOAD)} THEN {upload} WHEN {_sql_text(Revision.PASTE)} THEN "
            f"{paste} ELSE (CASE WHEN {has_file} THEN {upload} ELSE {paste} END) END)")
    shown = ' '.join(f'WHEN {_sql_text(key)} THEN {_sql_text(" · " + label)}'
                     for key, label in SEARCH_INSURANCE_TEXT.items())
    insurance = f"(CASE e.user_values ->> 'insurance' {shown} ELSE '' END)"
    labels = ' '.join(f'WHEN {_sql_text(key)} THEN {_sql_text(label)}' for key, label in state.LABELS.items())
    label = f'(CASE WHEN {has_round} THEN (CASE e.state {labels} ELSE e.state END) ELSE {_sql_text(STATE_LABELS[EARLIER])} END)'
    day, month, year = 'substr(d.sd, 9, 2)', 'substr(d.sd, 6, 2)', 'substr(d.sd, 1, 4)'
    leap = f'mod({year}::int, 4) = 0 AND (mod({year}::int, 100) <> 0 OR mod({year}::int, 400) = 0)'
    calendar = (f"{day} <= '28' OR ({month} = '02' AND {day} = '29' AND {leap}) OR ({month} <> '02' AND ({day} <= '30' "
                f"OR {month} IN ('01', '03', '05', '07', '08', '10', '12')))")
    written = (f"ltrim({day}, '0') || ' ' || substr({_sql_text(SEARCH_MONTHS)}, {month}::int * 3 - 2, 3) || ' ' || "
               f"ltrim({year}, '0')")
    date = (f"(CASE WHEN d.sd ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$' AND d.sd >= '0100' THEN "
            f"(CASE WHEN {calendar} THEN {written} ELSE 'Not entered' END) ELSE 'Not entered' END)")
    return f'({title} || {kind} || {insurance} || {label} || {date})'


def search_from_sql() -> str:
    """What the row text is read over: studio_encounter e, with d.kind - its current revision's kind, looked up per
    document by its primary key (a join let PostgreSQL hash every practice's revisions instead of walking
    studio_enc_ws_time) - and d.sd, the service date when it is a JSON string (service_date's rule), else NULL."""
    encounters, revisions = models.Encounter._meta.db_table, Revision._meta.db_table
    service_date = ("CASE WHEN jsonb_typeof(e.user_values -> 'service_date') = 'string' THEN "
                    "e.user_values ->> 'service_date' END")
    kind = f'(SELECT v.kind FROM {revisions} v WHERE v.id = e.current_revision_id)'
    return f'{encounters} e CROSS JOIN LATERAL (SELECT {kind} AS kind, {service_date} AS sd) d'


def _search_sql(fold, later) -> str:
    """The search's one statement: the practice's live documents, newest first along studio_enc_ws_time, from the
    cursor's position when ``later``, whose row text holds the words; folded both sides when ``fold``."""
    hay = f'lower({search_row_text_sql()} COLLATE "pg_c_utf8")'
    needle = 'lower(CAST(%(words)s AS text) COLLATE "pg_c_utf8")'
    if fold:
        hay, needle = (f'translate({side}, %(fold_from)s, %(fold_to)s)' for side in (hay, needle))
    keyset = (' AND e.created_at <= %(moment)s AND (e.created_at < %(moment)s OR (e.created_at = %(moment)s AND '
              'e.id < %(key)s))') if later else ''
    return (f'SELECT e.id, e.title, e.state, e.user_values, e.created_at, d.kind FROM {search_from_sql()} '
            f'WHERE e.workspace_id = %(workspace)s AND e.destroyed_at IS NULL{keyset} AND strpos({hay}, {needle}) > 0 '
            f'ORDER BY e.created_at DESC, e.id DESC LIMIT %(limit)s')


def search_page(membership, words, before=None) -> dict:
    """One page of POST /api/encounters/search (see above) of ``membership``'s practice: the documents whose row holds
    ``words`` (search_words', at most SEARCH_MAX_CHARS by search_length, storable - the API reads them first), 50 a page
    from the cursor ``before`` (None: the first page). {'encounters': rows, 'next': the next page's cursor or None,
    'total': None}."""
    position = paging.parse(before) if before is not None else None
    if not isinstance(words, str) or not words or search_length(words) > SEARCH_MAX_CHARS or '\x00' in words or (
            before is not None and position is None):
        raise ValueError('search_page is given words and a cursor the API has read.')
    fold_from, fold_to = search_fold(words)
    params = {'workspace': membership.workspace_id, 'words': words, 'space': JS_WHITE_SPACE,
              'fold_from': fold_from, 'fold_to': fold_to, 'limit': LIST_PAGE_ROWS + 1}
    if position is not None:
        params['moment'], params['key'] = position
    with connection.cursor() as cursor:
        cursor.execute(_search_sql(any(ch in words for ch in SEARCH_FOLDED), position is not None), params)
        found = [dict(zip(LIST_FIELDS, row)) for row in cursor.fetchall()]
    values = models.Encounter._meta.get_field('user_values')
    for row in found:  # jsonb comes back as its text, as for any JSONField read: decoded by the field itself
        if isinstance(row['user_values'], str):
            row['user_values'] = values.from_db_value(row['user_values'], None, connection)
    shown = found[:LIST_PAGE_ROWS]
    more = len(found) > LIST_PAGE_ROWS
    return {'encounters': list_rows_of(shown),
            'next': paging.cursor_of(shown[-1]['created_at'], shown[-1]['pk']) if more else None, 'total': None}


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
    """The newest round of the encounter that stored the PDF its Word document was converted to, or None: the record of
    what a round read, which the record bundle and the operator's console keep. The doctor's page reads shown_view."""
    return (Round.objects.filter(encounter_id=encounter.pk, view_pdf_storage_name__isnull=False)
            .exclude(view_pdf_storage_name='').order_by('-number').first())


def shown_view(encounter):
    """The converted PDF the doctor's page shows and downloads (document_json, view_source, download_content): the newest
    round that stored one, unless that round, or a round after it, ended failed on the Word file itself, when there is
    none: CONVERT (the file refused - R2-28 step 7, C8, at a later round - or not converted), or DOCUMENT with no view of
    its own (its own fresh conversion refused before it was stored: past the store's limit, jobs._keep_view, or past the
    send limit, fable.document._pdf_document - integrated refutation round 1, I1-18). A refused file then reads as one
    refused at its first round: no view (?view=1 404, a kept tag included; view_conversion null), the PDF download 409
    OriginalOnly, the Word file by name only (integrated refutation round 1, bypass-0 and failclosed-0). A failure of
    any other kind is not the Word file's and masks nothing (STORAGE included: a retry codes the file again), nor does a
    DOCUMENT beside a view the round stored (that view is the conversion the round itself read), and a later round that
    stores a view of its own shows it again. One statement, as converted_view."""
    newest = (Round.objects.filter(encounter_id=encounter.pk)
              .filter((Q(view_pdf_storage_name__isnull=False) & ~Q(view_pdf_storage_name=''))
                      | Q(state=Round.FAILED, failure_kind__in=(CONVERT, DOCUMENT)))
              .order_by('-number').first())
    if newest is None or (newest.state == Round.FAILED and (
            newest.failure_kind == CONVERT or (newest.failure_kind == DOCUMENT and not newest.view_pdf_storage_name))):
        # CONVERT hides even a view the round recorded (a resumed round refused at its check fails CONVERT beside it);
        # DOCUMENT only where the round stored none
        return None
    return newest


def safe_name(name, fallback='original') -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name or '')[:120] or fallback


def converted_name(source) -> str:
    """The file name a Word document's converted PDF is served under: the Word file's name with .pdf."""
    stem = (source.original_name or 'document').rsplit('.', 1)[0]
    return safe_name(f'{stem}.pdf', 'document.pdf')


def _converted_file(view):
    """The stored converted PDF of ``view`` (a round with view_pdf_*), as storage.read_original reads a file."""
    return SimpleNamespace(storage_name=view.view_pdf_storage_name, sha256=view.view_pdf_sha256)


class Shown(NamedTuple):
    """What the in-page viewer shows (release 2, R2-15), read from the rows alone: the stored file it serves (a
    SourceFile, or a Word document's converted view: anything with storage_name and sha256) - or None for a paste, whose
    ``text`` it is - the content type it is served as and its file name."""
    stored: object
    text: Optional[str]
    content_type: str
    filename: str


def view_source(encounter) -> Optional[Shown]:
    """What GET /api/encounters/<id>/original?view=1 shows, by view_content's own branches, or None when there is
    nothing to show - reading no stored file: the original PDF or text file, the pasted text, or for a Word document the
    PDF the coding review read (shown_view: none once a later round refused the file)."""
    source = original_file(encounter)
    if source is None:
        revision = _root_revision(encounter)
        if revision is None or revision.kind != Revision.PASTE:
            return None
        return Shown(None, revision.pasted_text or '', TEXT_SERVED, 'pasted-text.txt')
    if source.media_type == PDF:
        return Shown(source, None, PDF, safe_name(source.original_name))
    if source.media_type == TEXT:
        return Shown(source, None, TEXT_SERVED, safe_name(source.original_name))
    if source.media_type == DOCX:
        view = shown_view(encounter)
        if view is None:
            return None
        return Shown(_converted_file(view), None, PDF, converted_name(source))
    return None


def view_bytes(encounter, shown) -> bytes:
    """The bytes of ``shown`` (view_source's): its stored file read and checked against its recorded sha256
    (read_own_original: storage.OriginalCorrupted when it no longer matches, OSError when it cannot be read), or the
    pasted text as UTF-8."""
    if shown.stored is None:
        return shown.text.encode('utf-8')
    return read_own_original(encounter.workspace_id, shown.stored)


def view_content(encounter):
    """(bytes, content type, file name) the in-page viewer shows, or None when there is nothing to show: the original
    PDF or text file, the pasted text, or for a Word document the PDF the coding review read. A stored file that no
    longer matches its sha256 raises storage.OriginalCorrupted. Built from view_source and view_bytes (release 2,
    R2-15); the record bundle reads it."""
    shown = view_source(encounter)
    if shown is None:
        return None
    return view_bytes(encounter, shown), shown.content_type, shown.filename


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


def download_content(encounter, *, original=False, recorded=False) -> Optional[Download]:
    """The document's download (see above), or None for a paste, which has none. A stored file that no longer matches
    its sha256 raises storage.OriginalCorrupted; a Word document with no converted PDF yet raises OriginalOnly unless
    ``original`` asks for the Word file - the doctor's, by shown_view (none once a later round refused the file); with
    ``recorded`` (the operator's console), the record's, by converted_view."""
    source = original_file(encounter)
    if source is None:
        return None
    if source.media_type == DOCX and not original:
        view = converted_view(encounter) if recorded else shown_view(encounter)
        if view is None:
            raise OriginalOnly(ORIGINAL_ONLY)
        return Download(read_own_original(encounter.workspace_id, _converted_file(view)), PDF, converted_name(source),
                        CONVERTED,
                        view.view_pdf_sha256, 'pdf')
    return Download(read_own_original(encounter.workspace_id, source), source.media_type, safe_name(source.original_name),
                    ORIGINAL, source.sha256,
                    EXTENSIONS.get(source.media_type, 'bin'))


def view_conversion_of(encounter, view) -> str:
    """The name the doctor's page knows the converted PDF ``view`` serves by (``view``: a round with view_pdf_*, as
    shown_view answers): a UUID derived with the site's key from the document and the stored file's name - never the
    file's bytes, a hash of them or any words - so it names the stored file served, and nothing about its content. A
    later round that reads back the same stored file (a reuse: jobs._keep_view records the file an earlier round stored)
    keeps it; one that converts the file again stores another file, and another name (integrated refutation round 2,
    viewer-1)."""
    return str(uuid.UUID(salted_hmac('studio.customer.view_conversion', f'{encounter.pk}:{view.view_pdf_storage_name}',
                                     algorithm='sha256').hexdigest()[:32]))


def document_json(encounter) -> dict:
    """The document block: what was uploaded or pasted, its download (an upload's) and its in-page view.
    ``view_conversion`` names the stored conversion a Word document's view serves (view_conversion_of shown_view), null
    for any other document and for a Word document with no view: a later round that converts the file again (R2-28 step
    7, C8) serves another PDF at the same view_url, so the page redraws its viewer whole when this changes (integrated
    refutation round 1, viewer-0) - and only then: a later round that reads back the same file names the same
    conversion, so the page keeps its viewer, its zoom and its place (integrated refutation round 2, viewer-1).
    shown_view is read once, as before: no statement is added."""
    base = f'/api/encounters/{encounter.pk}/original'
    source = original_file(encounter)
    if source is None:
        revision = _root_revision(encounter)
        text = revision.pasted_text if revision is not None and revision.kind == Revision.PASTE else None
        return {'name': None, 'media_type': TEXT, 'size': len(text.encode('utf-8')) if text is not None else None,
                'kind': Revision.PASTE, 'original_url': None, 'view_url': f'{base}?view=1' if text is not None else None,
                'view_media_type': TEXT if text is not None else None, 'converted': False, 'view_conversion': None}
    view_type, converted, conversion = None, False, None
    if source.media_type in (PDF, TEXT):
        view_type = source.media_type
    elif source.media_type == DOCX:
        shown = shown_view(encounter)
        if shown is not None:
            view_type, converted, conversion = PDF, True, view_conversion_of(encounter, shown)
    return {'name': source.original_name, 'media_type': source.media_type, 'size': source.size,
            'kind': Revision.UPLOAD, 'original_url': base, 'view_url': f'{base}?view=1' if view_type else None,
            'view_media_type': view_type, 'converted': converted, 'view_conversion': conversion}


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


_NOT_READ = object()  # reports_json's ``decided`` when its caller has not read the round's decisions


def reports_json(encounter, round_, decided=_NOT_READ) -> list:
    """The document's exports, newest first, each marked current or earlier against ``round_`` (the latest round) and
    ``decided`` - when the newest decision on it was recorded, revokes included (None: none was), as encounter_json reads
    it from the round's decisions (release 2, R2-25); read here (last_decision_at) when not given."""
    exports = Export.objects.filter(encounter_id=encounter.pk).order_by('-created_at', '-pk').only(
        'pk', 'kind', 'fmt', 'filename', 'created_at', 'round_id')
    if decided is _NOT_READ:
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
    """GET /api/encounters/<id> (BUILD-SPEC 6). Release 2 (R2-25): the latest round is read once, and its decisions once
    (state.decisions_of), so the state, the codes' decisions and the exports' current marks are of one reading: the state
    is state.derive's (compute's rules) over those decisions, and an export is earlier than the round's newest decision,
    revokes included."""
    now = now or timezone.now()
    can_review = bool(membership.can_review)
    round_ = state.latest_round(encounter)
    decisions = state.decisions_of(round_) if round_ is not None else []
    current_now = state.current_of(decisions)
    current = current_now if round_ is not None and round_.state == Round.DONE else {}
    value = state.derive(round_, current_now) if round_ is not None else EARLIER
    decided = max((decision.created_at for decision in decisions), default=None)
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
        'reports': reports_json(encounter, round_, decided),
        'activity': activity_json(encounter),
    }


def round_json(round_) -> dict:
    """A round as an act's answer gives it (the encounter's ``round`` block)."""
    return {'number': round_.number, 'trigger': round_.trigger, 'finished_at': iso(round_.finished_at)}
