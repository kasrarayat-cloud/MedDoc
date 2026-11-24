"""The platform-operator console (BUILD-SPEC 9): server-rendered pages under /ops/.

An operator is a person's account (actor_kind human: release 1, C3) holding an OperatorGrant that no OperatorRevocation
ended - nothing else. An automated account is never one, whatever grant row it has, and is refused a grant. No workspace
role confers it (a practice owner is not an operator) and nothing here reads a Membership to decide it. Grants are
recorded by the ``grant_operator`` management command only, never over HTTP, each tied to an approval
(authorization_ref) and a review date; a revocation also ends every session of the account; both write a SecurityEvent.

The console answers only on admin.quillmd.com, and only to a session that passed the second factor at the admin door
(release 1, B3 and B2: may_use_console). Every URL under /ops/ answers anyone else - signed out, a member of any role,
the owner of any workspace, a revoked operator, an operator with a password alone or with a session from cpt.quillmd.com,
any request on any other host - exactly what an unknown URL answers (Django's 404), before the method, the body, the CSRF
token or any record is read, so the surface's existence is not disclosed. On the console's own host, admin.quillmd.com
(D396; studio.hosts), a signed-out request goes to the operator sign-in first - a GET or HEAD back to the page asked for
(302), any other method to the console's front page (303) - and the 404 holds for every signed-in request that may not
use the console. An operator's read of an encounter page
or its original is audited as ``operator.viewed`` (never shown to customers: their activity is a fixed set of sentences,
studio.customer). Vendor and model names, usage, costs, hashes and request ids are shown here; this is the record.

    GET  /ops/                               every encounter of every workspace (title, workspace, state, rounds,
                                             latest round's cost, updated) and the standing holds, with their release
    GET  /ops/encounters/<id>                its rounds (trigger, state, failure, cost, context), each run (models, served
                                             by a fallback, tokens, cost, latency, state, ids), the reader's and the
                                             checker's whole answers, the final codes, every review of the checker that
                                             belongs to no line (in full, with the lines it reaches), every question id
                                             a line, review or missed code gave that names no question (D370), the
                                             question ids both answers defined, decisions, answers, audit events, and
                                             the original with its sha256
    GET  /ops/encounters/<id>/original       the original exactly as stored, with its sha256
    POST /ops/encounters/<id>/reconcile      the reconciliation of an unknown run: run, note (at least 12 characters)
    POST /ops/encounters/<id>/retry          a new round of a failed latest round (jobs.retry)
    POST /ops/holds/release                  every standing hold released: note (jobs.release_holds)

Every POST carries the CSRF token (checked after the gate, for operators only) and answers with a redirect to the page
it came from, or that page again with the refusal and a 4xx status.
"""
from __future__ import annotations

import functools
import json
import re
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from . import (customer, hosts, jobs, models, read_audit, request_meta, second_factor, security_events, sessions, spend,
               state)
from .fable import pricing
from .fable import result as fable_result
from .storage import OriginalCorrupted

MAX_REASON_CHARS = 2000
MAX_NOTE_CHARS = 2000
LIST_LIMIT = 200
ANSWER_TEXT_CHARS = 400_000  # a run's stored answer shown at most this long
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')
DONE = {'reconciled': 'The reconciliation was recorded.', 'retried': 'A new coding round was queued.',
        'released': 'The standing holds were released.'}


# --- who is an operator -------------------------------------------------------------------------------------------

def active_grant(user):
    """The user's operator grant that no revocation ended (the oldest), or None. Reads no Membership."""
    if user is None or not getattr(user, 'pk', None):
        return None
    return (models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True)
            .order_by('created_at', 'pk').first())


def is_operator(user) -> bool:
    """Whether ``user`` is a platform operator now: signed in, active, a person's account (release 1, C3: an automated
    account never holds operator power, whatever grant row it has), and holding a grant no revocation ended. A workspace
    role never makes one, and no Membership is read: the account is already loaded, so this is one query."""
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return False
    if getattr(user, 'actor_kind', None) != models.User.HUMAN:
        return False
    return models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True).exists()


def clean_reason(text) -> str:
    """A grant's or revocation's reason as recorded: the file's text, stripped; refused when empty, too long or not
    storable (PostgreSQL text holds no NUL)."""
    reason = str(text or '').strip()
    if not reason:
        raise ValueError('The reason file is empty.')
    if len(reason) > MAX_REASON_CHARS:
        raise ValueError(f'The reason can be at most {MAX_REASON_CHARS} characters.')
    if UNSTORABLE.search(reason):
        raise ValueError('The reason contains a NUL character or an invalid Unicode code point.')
    return reason


AGENT_GRANT_REFUSED = ('An automated account cannot be an operator: operator power is for people only (release 1, '
                       'C3); nothing was recorded.')
AUTHORIZATION_REF_CHARS = 200  # OperatorGrant.authorization_ref
REVIEW_MONTHS = 12  # a grant's review date is at most this far away (ADM-8, ADM-13)


def clean_authorization_ref(text) -> str:
    """The approval a grant rests on (for example a committed ruling's path, or a declaration and its commit): stripped;
    refused when empty, too long, or holding a character that cannot be stored or seen."""
    value = str(text or '').strip()
    if not value:
        raise ValueError('The authorization reference is required: the approval the grant rests on.')
    if len(value) > AUTHORIZATION_REF_CHARS:
        raise ValueError(f'The authorization reference can be at most {AUTHORIZATION_REF_CHARS} characters.')
    if UNSTORABLE.search(value) or any(ord(ch) < 32 for ch in value):
        raise ValueError('The authorization reference contains a control character or an invalid Unicode code point.')
    return value


def review_limit(today):
    """The latest review date a grant made ``today`` may carry: the same day REVIEW_MONTHS months later (the 28th for a
    29 February that year has none)."""
    month = today.month - 1 + REVIEW_MONTHS
    year, month = today.year + month // 12, month % 12 + 1
    for day in (today.day, 30, 29, 28):
        try:
            return today.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    raise ValueError('No review date could be computed.')  # unreachable: every month has a 28th


def clean_review_by(value, today=None):
    """A grant's review date (a date, or YYYY-MM-DD): refused when it is not a date, already past, or more than
    REVIEW_MONTHS months away."""
    today = today or timezone.localdate()
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value.strip()) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.strip()) else None
        except ValueError:
            value = None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError('The review date is a date, YYYY-MM-DD.')
    if value < today:
        raise ValueError('The review date has already passed.')
    if value > review_limit(today):
        raise ValueError(f'The review date can be at most {REVIEW_MONTHS} months away (by {review_limit(today)}).')
    return value


def grant(user, reason, granted_by, *, authorization_ref=None, review_by=None):
    """Record a grant for ``user`` (the management command's one write) with the approval it rests on and the date it
    must be reviewed by, and a SecurityEvent operator.granted. (grant, created): an operator who already holds a grant
    keeps it and nothing is written. An automated account is refused (ValueError) - operator power is for people only.

    grant_operator requires the approval, the review date and the named person who runs it (release 1, C3) and is the
    only path that records a grant outside the tests; here both are checked when given (tests.support.operator, Lane 1's
    shared helper, grants a test operator with the reason and the label alone)."""
    if getattr(user, 'actor_kind', None) != models.User.HUMAN:
        raise ValueError(AGENT_GRANT_REFUSED)
    existing = active_grant(user)
    if existing is not None:
        return existing, False
    reason = clean_reason(reason)
    reference = clean_authorization_ref(authorization_ref) if authorization_ref is not None else None
    review = clean_review_by(review_by) if review_by is not None else None
    label = str(granted_by or '')[:120]
    record = models.OperatorGrant.objects.create(user=user, reason=reason, granted_by=label,
                                                 authorization_ref=reference, review_by=review)
    security_events.record('operator.granted', actor_label=label, subject=user, grant=record.pk, review_by=review)
    return record, True


def revoke(user, reason, revoked_by):
    """End every grant of ``user`` that no revocation ended, end every session of the account at once (release 1, C3:
    studio.sessions.end_sessions) and write a SecurityEvent operator.revoked; the revocations recorded (none, and
    nothing ended or written, when there was none)."""
    reason = clean_reason(reason)
    label = str(revoked_by or '')[:120]
    out = []
    for item in models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True).order_by('created_at'):
        out.append(models.OperatorRevocation.objects.create(grant=item, reason=reason, revoked_by=label))
    if out:
        ended = sessions.end_sessions(user)
        security_events.record('operator.revoked', actor_label=label, subject=user,
                               grants=[item.grant_id for item in out], sessions_ended=ended)
    return out


# --- the gate -----------------------------------------------------------------------------------------------------

def _as_an_unknown_url(request):
    """Leave ``request``'s session exactly as an unknown URL leaves it - never read: the gate had to read it to know the
    user, and SessionMiddleware answers a request whose session was read with "Vary: Cookie" (and deletes a stale
    session cookie it loaded), which an unknown URL's 404 never carries."""
    if hasattr(request, 'session'):
        store = import_module(settings.SESSION_ENGINE).SessionStore
        request.session = store(request.COOKIES.get(settings.SESSION_COOKIE_NAME))


def may_use_console(request) -> bool:
    """Whether ``request`` reaches the console (release 1, B3 and B2 step 4): all three must hold - the request is on the
    admin host (studio.hosts.is_admin_host: admin.quillmd.com, read from the Host header Django checked; never
    X-Forwarded-Host), its session passed the second factor at the admin door (studio.second_factor.satisfied: a password
    alone, a session opened at cpt.quillmd.com or one from before release 1 never does), and its account is a person
    holding an operator grant (is_operator). The host is read first, so on any other host the session is not read."""
    return hosts.is_admin_host(request) and second_factor.satisfied(request) and is_operator(request.user)


def operator_view(view):
    """Any request that may not use the console (may_use_console) gets exactly what an unknown URL gets - Django's 404 -
    before the method, the body, the CSRF token or the record is read; an operator who passed the second factor on the
    admin host gets the view. Django resolves a URL before CsrfViewMiddleware runs and an unknown URL stops there, so the
    global CSRF check is skipped here (csrf_exempt) and the same check (csrf_protect) runs after the gate, for operators
    only; no operator URL is reached by appending a slash. On the admin host (admin.quillmd.com, D396)
    studio.hosts.signed_out_to_sign_in first sends any signed-out request to the operator sign-in (a GET or HEAD back to
    the page, any other method to the front page with a 303); this gate answers every signed-in request that may not use
    the console, there as on cpt.quillmd.com, where the console answers nobody (release 1, B3)."""
    protected = csrf_protect(_fail_closed(view))

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not may_use_console(request):
            _as_an_unknown_url(request)
            raise Http404()
        return protected(request, *args, **kwargs)
    wrapper.csrf_exempt = True  # the CSRF check is the operator's, after the gate (csrf_protect above)
    wrapper.should_append_slash = False  # /ops answers what /opsx answers (CommonMiddleware's APPEND_SLASH)
    return wrapper


def _fail_closed(view):
    """A console view whose read cannot be recorded (studio.read_audit.NotRecorded, raised before the page or file is
    built from it) answers 503 with read_audit.NOT_RECORDED and nothing else (release 1, C1; RELEASE-1-SPEC 2.2)."""
    @functools.wraps(view)
    def answer(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except read_audit.NotRecorded:
            return HttpResponse(read_audit.NOT_RECORDED, status=503, content_type='text/plain; charset=utf-8')
    return answer


def _methods(*allowed):
    def decorate(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                return HttpResponse(status=405, headers={'Allow': ', '.join(allowed)})
            return view(request, *args, **kwargs)
        return wrapper
    return decorate


def _encounter(encounter_id):
    """The encounter a console route names; 404 for none, and for a disposal's tombstone (release 1, D1: nothing of
    it is left to show)."""
    try:
        return models.Encounter.objects.select_related('workspace', 'created_by', 'current_revision').get(
            pk=encounter_id, destroyed_at__isnull=True)
    except (models.Encounter.DoesNotExist, ValueError, TypeError, ValidationError):
        raise Http404()


def _see_other(url):
    response = HttpResponseRedirect(url)
    response.status_code = 303
    return response


def _pretty(value) -> str:
    return json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True, default=str)


# --- what the pages show --------------------------------------------------------------------------------------------

def round_runs(round_):
    return list(models.ProviderRun.objects.filter(purpose__in=jobs.PURPOSES, scope__round=str(round_.pk))
                .select_related('reconciled_by').order_by('created_at', 'pk'))


def runs_cost(runs):
    """(the known cost of ``runs`` as a string, how many have no known cost): studio.spend's reading, the Spending page's
    own (refutation r2, figures-1) - a run still being sent, of unknown outcome or not priceable counts apart, a run that
    sent nothing, was cancelled or was refused before answering costs nothing, and a run only reserved is not counted."""
    total, unpriced = Decimal(0), 0
    for run in runs:
        if run.state == models.ProviderRun.RESERVED and not run.sent:
            continue
        cost, _worst = spend.run_spend(run)
        if cost is None:
            unpriced += 1
        else:
            total += cost
    return pricing.usd(total), unpriced


def _answer_text(run) -> str:
    """The run's whole stored answer as text: the message's text blocks, or the stored bytes when they are no message."""
    if not run.response_bytes:
        return ''
    try:
        text = fable_result.message_text(jobs.stored_message(run))
    except ValueError:
        text = bytes(run.response_bytes).decode('utf-8', 'replace')
    return text[:ANSWER_TEXT_CHARS]


def _tokens(usage) -> dict:
    usage = usage if isinstance(usage, dict) else {}
    keys = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
    iterations = usage.get('iterations') if isinstance(usage.get('iterations'), list) else []
    return {**{key: usage.get(key) for key in keys}, 'iterations': len(iterations)}


def run_view(run, *, content=False) -> dict:
    """A run's card. Its cost is studio.spend's reading, its round's and the Spending page's own (refutation r3, r3-1):
    the known cost, or none yet; beside it, what its stored usage prices at whenever that differs (a run in flight or of
    unknown outcome, a replay, a run that sent nothing), and the worst case it was reserved at. Its whole answer, the
    request as stored and the vendor's error text are content (release 1, C2): read only with ``content``."""
    scope = run.scope if isinstance(run.scope, dict) else {}
    known, _worst = spend.run_spend(run)
    priced = jobs.run_cost(run)
    return {'run': run, 'role': {jobs.READER: 'reader', jobs.CHECKER: 'checker'}.get(run.purpose, run.purpose),
            'fallback': bool(scope.get('fallback')), 'tokens': _tokens(run.usage),
            'cost': pricing.usd(known) if known is not None else None,
            'usage_priced': pricing.usd(priced) if priced is not None and priced != known else None,
            # a run only reserved has sent nothing yet: its round does not count it (runs_cost), nor does its card (r4-5)
            'reserved_only': run.state == models.ProviderRun.RESERVED and not run.sent,
            'worst_usd': scope.get('worst_usd'),
            'counted_input_tokens': scope.get('input_tokens_counted'), 'stop_reason': scope.get('stop_reason'),
            'failure_kind': scope.get('failure_kind'), 'error_type': scope.get('error_type'),
            'can_reconcile': run.state == models.ProviderRun.UNKNOWN and run.reconciled_at is None,
            'answer': _answer_text(run) if content else '', 'request': _pretty(run.request_body) if content else '',
            'error': run.error if content else ''}


def round_view(round_, *, content=False) -> dict:
    """A round's card: its metadata always - trigger, state, failure kind, times, cost, revision, the converted PDF's
    sha256, the counts of its codes, questions and answers, and each run's card - and, with ``content`` (release 1, C2),
    what the coding review read and wrote: the practice's values, the answers, the codes, the questions, the reviews,
    the citations and both final answers."""
    runs = round_runs(round_)
    cost, unpriced = runs_cost(runs)
    context = round_.context if isinstance(round_.context, dict) else {}
    answers = context.get('answers') if isinstance(context.get('answers'), list) else []
    codes = [item for item in round_.codes or () if isinstance(item, dict)]
    questions = [item for item in round_.questions or () if isinstance(item, dict)]
    view = {'round': round_, 'cost': cost, 'unpriced': unpriced, 'runs': [run_view(run, content=content) for run in runs],
            'answer_count': len(answers), 'code_count': len(codes), 'question_count': len(questions)}
    if not content:
        return view
    done = round_.state == models.CodingRound.DONE
    return {**view, 'service_date': context.get('service_date'), 'insurance': context.get('insurance'),
            'answers': answers,
            # modifiers the coding review did not give stay None (shown "not given", FIX-SPEC 2), never read as none
            'codes': [{**code, 'modifiers': code.get('modifiers') if isinstance(code.get('modifiers'), list) else None}
                      for code in codes],
            'questions': questions,
            # every review of a done round that belongs to no line, in full (FIX-SPEC-2 section 3): fable.result's own
            # placement over the round's stored lines
            'unmatched': [{'number': item['number'], 'reaches': item['reaches'], 'json': _pretty(item['review'])}
                          for item in (fable_result.unmatched_reviews(round_.codes, round_.checker_result)
                                       if done else ())],
            # every reference to a question id that names no question (D370): it carried no text, so the customer saw
            # none from it - fable.result's own reading over the two answers as stored, here because this is where the
            # round's whole record is read, and the customer is never shown it (a needs_answer line no question names
            # still gets a question the member can answer)
            'dangling': [{**item, 'reference': json.dumps(item['reference'], ensure_ascii=False)}
                         for item in (fable_result.dangling_references(round_.reader_result, round_.checker_result)
                                      if done else ())],
            # every question id both the reader and the checker defined, case aside (D370 round 2, F3): a reference of
            # the checker's to it reaches every question carrying it in either answer - one question where their texts
            # are the same (round 3, G1) - and the code never chooses among them; shown, as written, beside the ids
            # that name no question, read the same way from the two stored answers
            'shared_ids': [json.dumps(ident, ensure_ascii=False)
                           for ident in (fable_result.shared_ids(round_.reader_result, round_.checker_result)
                                         if done else ())],
            'problems': [item for item in round_.problems or () if isinstance(item, str)],
            'citations': _pretty(round_.citations or {}), 'reader_result': _pretty(round_.reader_result),
            'checker_result': _pretty(round_.checker_result)}


def holds_view():
    return [{'hold': hold, 'run': hold.run} for hold in jobs.standing_holds().select_related('run')]


def encounter_view(encounter, *, open_until=None, **extra) -> dict:
    """The encounter page (release 1, C2): its metadata always - the practice, the reference, state, times, who added
    it, the original's type, size and sha256, every round's and run's metadata, the decisions by action, the number of
    answers, the audit events without their data, the standing holds and the acts that need no content (retry,
    reconcile) - and, while its content is open in this session (``open_until``, an epoch second), the content too:
    the title, the original's name and download, the practice's values, the decisions, the answers, the events' data,
    and each round's codes, questions, reviews, citations and both final answers."""
    content = open_until is not None
    rounds = list(models.CodingRound.objects.filter(encounter_id=encounter.pk).order_by('-number'))
    latest = rounds[0] if rounds else None
    source = encounter.files.order_by('uploaded_at', 'pk').first()
    revision = encounter.current_revision
    events = [{'event': event, 'data': _pretty(event.data) if content else ''}
              for event in encounter.audit_events.select_related('actor').order_by('created_at', 'pk')]
    failed = latest is not None and latest.state == models.CodingRound.FAILED
    # a send of the failed round that may have reached the vendor with no outcome known waits for the reconcile first:
    # jobs.retry refuses it until then (FIX-SPEC 4), so the retry is not offered
    waits = failed and jobs.awaiting_reconcile(latest)
    decisions = list(models.CodeDecision.objects.filter(encounter_id=encounter.pk)
                     .select_related('reviewer', 'round').order_by('sequence'))
    actions = {}
    for decision in decisions:
        actions[decision.action] = actions.get(decision.action, 0) + 1
    word = source is not None and source.media_type == customer.DOCX
    return {'error': None, 'done': None,  # the notice slots, named so the page never looks a missing one up (r2, figures-4)
            'encounter': encounter, 'reference': short_reference(encounter.pk),
            'state_label': state.label(encounter.state) if latest else 'Earlier review',
            'source': source, 'revision': revision,
            'pasted_chars': len(revision.pasted_text or '') if revision is not None and source is None else None,
            'rounds': [round_view(round_, content=content) for round_ in rounds],
            'can_retry': failed and not jobs.busy(encounter) and not waits, 'retry_waits': waits,
            'decision_counts': sorted(actions.items()), 'decision_total': len(decisions),
            'answer_total': models.CodingAnswer.objects.filter(encounter_id=encounter.pk).count(),
            'decisions': decisions if content else [],
            'answers': list(models.CodingAnswer.objects.filter(encounter_id=encounter.pk)
                            .select_related('answered_by', 'round').order_by('answered_at', 'pk')) if content else [],
            'events': events, 'holds': holds_view(), 'release': settings.RELEASE_SHA, 'section': 'encounters',
            'note_chars': jobs.RECONCILE_NOTE_CHARS,
            # release 1, C2: the content is opened with a reason and a reference, for this session only
            'content': content, 'open_until': open_until, 'reasons': list(CONTENT_REASONS.items()),
            'open_until_at': datetime.fromtimestamp(open_until, tz=dt_timezone.utc) if content else None,
            'reference_chars': REFERENCE_CHARS, 'grant_minutes': settings.CONTENT_GRANT_SECONDS // 60,
            # release 1, C6: a Word document's download is its converted PDF; the Word file is asked for by name
            'word': word, 'converted': word and customer.converted_view(encounter) is not None, **extra}


def _note(request, limit=MAX_NOTE_CHARS) -> str:
    note = request.POST.get('note', '')
    if UNSTORABLE.search(note):
        raise jobs.Refused(NOTE_UNSTORABLE)
    if len(note) > limit:
        raise jobs.Refused(f'The note can be at most {limit:,} characters.')
    return note


# --- the reads (release 1, C1) and the content an operator opens (C2) --------------------------------------------------
# Every console page that shows a document - the list, a document's page, its content, its original - and the lists
# across practices (studio.console) writes its AccessRecord before the page or file is built from it; a read that cannot
# be recorded answers 503 and nothing else (_fail_closed). A refused act answers 303 back to its GET page with an error
# code, so a page with data is never served without its row (TEC-9 (2)).
#
# The console shows less by default (ORG-19 (4)-(6)): lists name a document by its short reference, never its title or
# file name, and a document's page opens on its metadata. Its content opens for one document, in this session only, for
# CONTENT_GRANT_SECONDS, once the operator gives one of the fixed reasons and a reference (a ticket or request number),
# recorded as ops.content_open (D24). The original is served only while it is open, named by the reference.

CONTENT_SESSION_KEY = 'cpt_ops_content'  # {encounter id: the epoch second its content stays open until}
CONTENT_REASONS = {
    'support_request': "A practice's support request",
    'failed_processing': 'Failed or stuck processing',
    'security_investigation': 'A security investigation',
    'practice_check': 'A check the practice asked for',
}
REFERENCE_CHARS = 60
# a ticket or request number: letters, digits, spaces and . _ : / # -, with at least one digit - so a name alone, which
# could be a patient's, is never taken for one
REFERENCE_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._:/#-]*')
REFERENCE_RULE = (f'Give the ticket or request number this opening answers (at most {REFERENCE_CHARS} letters, digits, '
                  'spaces and . _ : / # -, with at least one digit) - never patient details.')
OPEN_FIRST = 'Open the content first, with a reason.'
NOTE_UNSTORABLE = 'The note contains a NUL character or an invalid Unicode code point.'
TEXT_PLAIN = 'text/plain; charset=utf-8'
DONE['opened'] = 'The content of this document is open in this session.'
# Why an act was refused, by code (the 303's ?error=): every sentence the acts can answer. A refusal whose sentence is
# not here (a new one of studio.jobs) reads REFUSED_ELSE, never its own text in a URL.
ERRORS = {
    'run': 'That run is not part of this document.',
    'reconcile-only': 'Only an unreconciled unknown outcome can be reconciled.',
    'note-short': f'Write a note of at least {jobs.RECONCILE_NOTE_CHARS} characters saying what was found.',
    'note-long': f'The note can be at most {MAX_NOTE_CHARS:,} characters.',
    'note-unstorable': NOTE_UNSTORABLE,
    'busy': jobs.BUSY_MESSAGE,
    'retry-nothing': jobs.RETRY_NOTHING,
    'reconcile-first': jobs.RECONCILE_FIRST,
    'release-note': 'A release needs a note saying why the hold may end.',
    'no-hold': 'No hold was standing.',
    'reason': 'Choose why the content is opened.',
    'reference': REFERENCE_RULE,
    'refused': 'That could not be done. Reload the page and try again.',
}
REFUSED_ELSE = 'refused'


def short_reference(encounter_id) -> str:
    """A document's short reference: the first 8 characters of its id - what every console list names it by."""
    return str(encounter_id)[:8]


def clean_reference(text) -> str:
    """The reference an opening of content gives (REFERENCE_RULE), stripped; ValueError otherwise."""
    value = ' '.join(str(text or '').split())
    if not value or len(value) > REFERENCE_CHARS or not REFERENCE_RE.fullmatch(value) or not any(
            ch.isdigit() for ch in value):
        raise ValueError(REFERENCE_RULE)
    return value


def _grants(request) -> dict:
    value = request.session.get(CONTENT_SESSION_KEY)
    return value if isinstance(value, dict) else {}


def _second(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def content_open_until(request, encounter_id):
    """The epoch second the content of ``encounter_id`` stays open until in this session, or None: never opened in this
    session, or its time is up."""
    until = _second(_grants(request).get(str(encounter_id)))
    return until if until is not None and until > request_meta.epoch_seconds() else None


def _open_content(request, encounter_id) -> int:
    """Open the content of ``encounter_id`` in this session for CONTENT_GRANT_SECONDS (a grant that ran out is dropped);
    the epoch second it stays open until."""
    now = request_meta.epoch_seconds()
    grants = {key: until for key, until in _grants(request).items() if (_second(until) or 0) > now}
    grants[str(encounter_id)] = now + settings.CONTENT_GRANT_SECONDS
    request.session[CONTENT_SESSION_KEY] = grants
    return grants[str(encounter_id)]


def _record(request, view, encounter, **fields):
    """The AccessRecord of a read of one document by the operator (read_audit.record), before it is served."""
    return read_audit.record(request, view=view, workspace_id=encounter.workspace_id, encounter_ids=[encounter.pk],
                             **fields)


def _error_code(message) -> str:
    return next((code for code, sentence in ERRORS.items() if sentence == message), REFUSED_ELSE)


def _refused(encounter, code):
    """A refused act on a document's page: 303 back to its page, which names the refusal by its code (ERRORS)."""
    return _see_other(f'/ops/encounters/{encounter.pk}?error={code}')


# --- the pages ------------------------------------------------------------------------------------------------------

@operator_view
@_methods('GET')
@read_audit.phi_read(read_audit.OPS_LIST)
def index(request):
    """Every open workspace's documents, most recently updated first (at most LIST_LIMIT), each by its short reference
    - recorded as ops.list with the documents shown - and the standing holds. A destroyed document's tombstone and the
    documents of a closed practice are left out (release 1, D1: a closed practice drops out of the routine lists)."""
    rows = []
    listed = models.Encounter.objects.filter(destroyed_at__isnull=True, workspace__closed_at__isnull=True)
    encounters = (listed.select_related('workspace').defer('title', 'user_values')
                  .annotate(rounds_count=Count('rounds')).order_by('-updated_at')[:LIST_LIMIT])
    for encounter in encounters:
        latest = state.latest_round(encounter)
        cost, unpriced = runs_cost(round_runs(latest)) if latest is not None else (None, 0)
        rows.append({'encounter': encounter, 'reference': short_reference(encounter.pk), 'latest': latest, 'cost': cost,
                     'unpriced': unpriced,
                     'state_label': state.label(encounter.state) if latest is not None else 'Earlier review'})
    read_audit.record(request, view=read_audit.OPS_LIST, encounter_ids=[row['encounter'].pk for row in rows],
                      count=len(rows))
    return render(request, 'studio/ops_index.html', {
        'rows': rows, 'total': listed.count(), 'limit': LIST_LIMIT, 'holds': holds_view(),
        'closed': models.Workspace.objects.filter(closed_at__isnull=False).count(),
        'error': ERRORS.get(request.GET.get('error', '')), 'done': DONE.get(request.GET.get('done', '')),
        'release': settings.RELEASE_SHA, 'mode': settings.CODING_MODE, 'section': 'encounters'})


@operator_view
@_methods('GET')
@read_audit.phi_read(read_audit.OPS_DETAIL)
def encounter_page(request, encounter_id):
    """One document's page: its metadata, and its content while it is open in this session (encounter_view), recorded
    as ops.detail on every view, with whether its content was shown."""
    encounter = _encounter(encounter_id)
    open_until = content_open_until(request, encounter.pk)
    _record(request, read_audit.OPS_DETAIL, encounter, filters={'content': open_until is not None})
    return render(request, 'studio/ops_encounter.html', encounter_view(
        encounter, open_until=open_until, done=DONE.get(request.GET.get('done', '')),
        error=ERRORS.get(request.GET.get('error', ''))))


@operator_view
@_methods('POST')
@read_audit.phi_read(read_audit.OPS_CONTENT_OPEN)
def content_open(request, encounter_id):
    """Open one document's content for CONTENT_GRANT_SECONDS in this session (release 1, C2; D24): one of the fixed
    reasons and a reference, both required, recorded as ops.content_open with both before anything opens. No second key
    touch: every opening is recorded with its reason."""
    encounter = _encounter(encounter_id)
    reason = request.POST.get('reason', '')
    if not isinstance(reason, str) or reason not in CONTENT_REASONS:
        return _refused(encounter, 'reason')
    try:
        reference = clean_reference(request.POST.get('reference', ''))
    except ValueError:
        return _refused(encounter, 'reference')
    _record(request, read_audit.OPS_CONTENT_OPEN, encounter, reason=f'{reason}: {reference}')
    _open_content(request, encounter.pk)
    return _see_other(f'/ops/encounters/{encounter.pk}?done=opened')


@operator_view
@_methods('GET')
@read_audit.phi_read(read_audit.OPS_ORIGINAL)
def original(request, encounter_id):
    """The upload, while the document's content is open in this session (403 OPEN_FIRST otherwise), named
    encounter-<reference>.<extension> and with its sha256 - a Word document's converted PDF, the Word file itself with
    format=original (release 1, C6: customer.download_content) - recorded as ops.original with its format."""
    encounter = _encounter(encounter_id)
    if content_open_until(request, encounter.pk) is None:
        return HttpResponse(OPEN_FIRST, status=403, content_type=TEXT_PLAIN)
    try:
        found = customer.download_content(encounter, original=request.GET.get('format') == customer.ORIGINAL)
    except customer.OriginalOnly:
        return HttpResponse(customer.ORIGINAL_ONLY, status=409, content_type=TEXT_PLAIN)
    except (OriginalCorrupted, OSError):
        return HttpResponse('The stored original no longer matches its recorded sha256 or cannot be read.',
                            status=409, content_type=TEXT_PLAIN)
    if found is None:
        raise Http404()
    _record(request, read_audit.OPS_ORIGINAL, encounter, filters={'format': found.fmt})
    response = HttpResponse(found.data, content_type=found.content_type)
    response['Content-Disposition'] = (f'attachment; filename="encounter-{short_reference(encounter.pk)}.'
                                       f'{found.extension}"')
    response['X-Content-SHA256'] = found.sha256
    return response


@operator_view
@_methods('POST')
def reconcile(request, encounter_id):
    """Record the reconciliation of one unknown run (jobs.reconcile): who looked, when and what they found. It queues
    nothing; a retry starts a new round."""
    encounter = _encounter(encounter_id)
    try:
        run = encounter.provider_runs.get(pk=request.POST.get('run', ''))
    except (models.ProviderRun.DoesNotExist, ValueError, ValidationError):
        return _refused(encounter, 'run')
    try:
        recorded = jobs.reconcile(encounter, run, request.user, _note(request))
    except jobs.Refused as exc:
        return _refused(encounter, _error_code(str(exc)))
    if recorded is None:
        return _refused(encounter, 'reconcile-only')
    return _see_other(f'/ops/encounters/{encounter.pk}?done=reconciled')


@operator_view
@_methods('POST')
def retry(request, encounter_id):
    """A new round of the encounter's failed latest round (jobs.retry), requested by the operator."""
    encounter = _encounter(encounter_id)
    try:
        jobs.retry(encounter, request.user)
    except jobs.Refused as exc:
        return _refused(encounter, _error_code(str(exc)))
    return _see_other(f'/ops/encounters/{encounter.pk}?done=retried')


@operator_view
@_methods('POST')
def release_holds(request):
    """Release every standing hold, each with a release naming this operator and the note (jobs.release_holds); a
    refusal answers 303 back to the console's first page with its code."""
    try:
        released = jobs.release_holds(user=request.user, note=_note(request))
    except jobs.Refused as exc:
        return _see_other(f'/ops/?error={_error_code(str(exc))}')
    if not released:
        return _see_other('/ops/?error=no-hold')
    return _see_other('/ops/?done=released')
