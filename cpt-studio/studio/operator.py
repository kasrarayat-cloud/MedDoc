"""The platform-operator console (BUILD-SPEC 9): server-rendered pages under /ops/.

An operator is a user holding an OperatorGrant that no OperatorRevocation ended - nothing else. No workspace role
confers it (a practice owner is not an operator) and nothing here reads a Membership to decide it. Grants are recorded
by the ``grant_operator`` management command only, never over HTTP.

Every URL under /ops/ answers anyone who is not an operator - signed out, a member of any role, the owner of any
workspace, a revoked operator - exactly what an unknown URL answers (Django's 404), before the method, the body, the
CSRF token or any record is read, so the surface's existence is not disclosed. An operator's read of an encounter page
or its original is audited as ``operator.viewed`` (never shown to customers: their activity is a fixed set of sentences,
studio.customer). Vendor and model names, usage, costs, hashes and request ids are shown here; this is the record.

    GET  /ops/                               every encounter of every workspace (title, workspace, state, rounds,
                                             latest round's cost, updated) and the standing holds, with their release
    GET  /ops/encounters/<id>                its rounds (trigger, state, failure, cost, context), each run (models, served
                                             by a fallback, tokens, cost, latency, state, ids), the reader's and the
                                             checker's whole answers, the final codes, every review of the checker that
                                             belongs to no line (in full, with the lines it reaches), every question id
                                             a line, review or missed code gave that names no question (D370),
                                             decisions, answers, audit events, and the original with its sha256
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
from datetime import timedelta
from decimal import Decimal
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from . import audit, jobs, models, state
from .fable import pricing
from .fable import result as fable_result
from .storage import OriginalCorrupted, read_original

VIEWED = 'operator.viewed'
# One audit row per operator, encounter and view within this window: a page reloaded is not a new act of looking.
VIEW_AUDIT_WINDOW = timedelta(minutes=10)
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
    """Whether ``user`` is a platform operator now: signed in, active, and holding a grant no revocation ended. A workspace
    role never makes one, and no Membership is read."""
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
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


def grant(user, reason, granted_by):
    """Record a grant for ``user`` (the management command's one write). (grant, created): an operator who already holds
    a grant keeps it and nothing is written."""
    existing = active_grant(user)
    if existing is not None:
        return existing, False
    return models.OperatorGrant.objects.create(user=user, reason=clean_reason(reason),
                                               granted_by=str(granted_by or '')[:120]), True


def revoke(user, reason, revoked_by):
    """End every grant of ``user`` that no revocation ended; the revocations recorded (none when there was none)."""
    reason = clean_reason(reason)
    out = []
    for item in models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True).order_by('created_at'):
        out.append(models.OperatorRevocation.objects.create(grant=item, reason=reason,
                                                            revoked_by=str(revoked_by or '')[:120]))
    return out


def record_view(user, encounter, view, **data):
    """Audit an operator's read of ``encounter`` as operator.viewed - once per operator, encounter and view within
    VIEW_AUDIT_WINDOW."""
    since = timezone.now() - VIEW_AUDIT_WINDOW
    if models.AuditEvent.objects.filter(event=VIEWED, encounter=encounter, actor=user, created_at__gte=since,
                                        data__view=view).exists():
        return None
    return audit.record(encounter.workspace, VIEWED, encounter=encounter, actor=user, view=view, **data)


# --- the gate -----------------------------------------------------------------------------------------------------

def _as_an_unknown_url(request):
    """Leave ``request``'s session exactly as an unknown URL leaves it - never read: the gate had to read it to know the
    user, and SessionMiddleware answers a request whose session was read with "Vary: Cookie" (and deletes a stale
    session cookie it loaded), which an unknown URL's 404 never carries."""
    if hasattr(request, 'session'):
        store = import_module(settings.SESSION_ENGINE).SessionStore
        request.session = store(request.COOKIES.get(settings.SESSION_COOKIE_NAME))


def operator_view(view):
    """Anyone who is not an operator gets exactly what an unknown URL gets - Django's 404 - before the method, the body,
    the CSRF token or the record is read; an operator gets the view. Django resolves a URL before CsrfViewMiddleware runs
    and an unknown URL stops there, so the global CSRF check is skipped here (csrf_exempt) and the same check
    (csrf_protect) runs after the gate, for operators only; no operator URL is reached by appending a slash."""
    protected = csrf_protect(view)

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_operator(request.user):
            _as_an_unknown_url(request)
            raise Http404()
        return protected(request, *args, **kwargs)
    wrapper.csrf_exempt = True  # the CSRF check is the operator's, after the gate (csrf_protect above)
    wrapper.should_append_slash = False  # /ops answers what /opsx answers (CommonMiddleware's APPEND_SLASH)
    return wrapper


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
    try:
        return models.Encounter.objects.select_related('workspace', 'created_by', 'current_revision').get(
            pk=encounter_id)
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
    """(the priced cost of ``runs`` as a string, how many could not be priced)."""
    total, unpriced = Decimal(0), 0
    for run in runs:
        cost = jobs.run_cost(run)
        if cost is None:
            unpriced += int(bool(run.sent))
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


def run_view(run) -> dict:
    scope = run.scope if isinstance(run.scope, dict) else {}
    cost = jobs.run_cost(run)
    return {'run': run, 'role': {jobs.READER: 'reader', jobs.CHECKER: 'checker'}.get(run.purpose, run.purpose),
            'fallback': bool(scope.get('fallback')), 'tokens': _tokens(run.usage),
            'cost': pricing.usd(cost) if cost is not None else None, 'worst_usd': scope.get('worst_usd'),
            'counted_input_tokens': scope.get('input_tokens_counted'), 'stop_reason': scope.get('stop_reason'),
            'failure_kind': scope.get('failure_kind'), 'error_type': scope.get('error_type'),
            'can_reconcile': run.state == models.ProviderRun.UNKNOWN and run.reconciled_at is None,
            'answer': _answer_text(run), 'request': _pretty(run.request_body)}


def round_view(round_) -> dict:
    runs = round_runs(round_)
    cost, unpriced = runs_cost(runs)
    context = round_.context if isinstance(round_.context, dict) else {}
    return {'round': round_, 'service_date': context.get('service_date'), 'insurance': context.get('insurance'),
            'answers': context.get('answers') if isinstance(context.get('answers'), list) else [],
            'cost': cost, 'unpriced': unpriced, 'runs': [run_view(run) for run in runs],
            # modifiers the coding review did not give stay None (shown "not given", FIX-SPEC 2), never read as none
            'codes': [{**code, 'modifiers': code.get('modifiers') if isinstance(code.get('modifiers'), list) else None}
                      for code in round_.codes or () if isinstance(code, dict)],
            'questions': [item for item in round_.questions or () if isinstance(item, dict)],
            # every review of a done round that belongs to no line, in full (FIX-SPEC-2 section 3): fable.result's own
            # placement over the round's stored lines
            'unmatched': [{'number': item['number'], 'reaches': item['reaches'], 'json': _pretty(item['review'])}
                          for item in (fable_result.unmatched_reviews(round_.codes, round_.checker_result)
                                       if round_.state == models.CodingRound.DONE else ())],
            # every reference to a question id that names no question (D370): it carried no text, so the customer saw
            # none from it - fable.result's own reading over the two answers as stored, here because this is where the
            # round's whole record is read, and the customer is never shown it (a needs_answer line no question names
            # still gets a question the member can answer)
            'dangling': [{**item, 'reference': json.dumps(item['reference'], ensure_ascii=False)}
                         for item in (fable_result.dangling_references(round_.reader_result, round_.checker_result)
                                      if round_.state == models.CodingRound.DONE else ())],
            'problems': [item for item in round_.problems or () if isinstance(item, str)],
            'citations': _pretty(round_.citations or {}), 'reader_result': _pretty(round_.reader_result),
            'checker_result': _pretty(round_.checker_result)}


def holds_view():
    return [{'hold': hold, 'run': hold.run} for hold in jobs.standing_holds().select_related('run')]


def encounter_view(encounter, **extra) -> dict:
    rounds = list(models.CodingRound.objects.filter(encounter_id=encounter.pk).order_by('-number'))
    latest = rounds[0] if rounds else None
    source = encounter.files.order_by('uploaded_at', 'pk').first()
    revision = encounter.current_revision
    events = [{'event': event, 'data': _pretty(event.data)}
              for event in encounter.audit_events.select_related('actor').order_by('created_at', 'pk')]
    failed = latest is not None and latest.state == models.CodingRound.FAILED
    # a send of the failed round that may have reached the vendor with no outcome known waits for the reconcile first:
    # jobs.retry refuses it until then (FIX-SPEC 4), so the retry is not offered
    waits = failed and jobs.awaiting_reconcile(latest)
    return {'encounter': encounter, 'state_label': state.label(encounter.state) if latest else 'Earlier review',
            'source': source, 'revision': revision,
            'pasted_chars': len(revision.pasted_text or '') if revision is not None and source is None else None,
            'rounds': [round_view(round_) for round_ in rounds],
            'can_retry': failed and not jobs.busy(encounter) and not waits, 'retry_waits': waits,
            'decisions': list(models.CodeDecision.objects.filter(encounter_id=encounter.pk)
                              .select_related('reviewer', 'round').order_by('sequence')),
            'answers': list(models.CodingAnswer.objects.filter(encounter_id=encounter.pk)
                            .select_related('answered_by', 'round').order_by('answered_at', 'pk')),
            'events': events, 'holds': holds_view(), 'release': settings.RELEASE_SHA,
            'note_chars': jobs.RECONCILE_NOTE_CHARS, **extra}


def _note(request, limit=MAX_NOTE_CHARS) -> str:
    note = request.POST.get('note', '')
    if UNSTORABLE.search(note):
        raise jobs.Refused('The note contains a NUL character or an invalid Unicode code point.')
    if len(note) > limit:
        raise jobs.Refused(f'The note can be at most {limit:,} characters.')
    return note


# --- the pages ------------------------------------------------------------------------------------------------------

@operator_view
@_methods('GET')
def index(request):
    return _index_page(request, done=DONE.get(request.GET.get('done', '')))


def _index_page(request, *, error=None, done=None, status=200):
    rows = []
    encounters = (models.Encounter.objects.select_related('workspace').annotate(rounds_count=Count('rounds'))
                  .order_by('-updated_at')[:LIST_LIMIT])
    for encounter in encounters:
        latest = state.latest_round(encounter)
        cost, unpriced = runs_cost(round_runs(latest)) if latest is not None else (None, 0)
        rows.append({'encounter': encounter, 'latest': latest, 'cost': cost, 'unpriced': unpriced,
                     'state_label': state.label(encounter.state) if latest is not None else 'Earlier review'})
    return render(request, 'studio/ops_index.html', {
        'rows': rows, 'total': models.Encounter.objects.count(), 'limit': LIST_LIMIT, 'holds': holds_view(),
        'error': error, 'done': done, 'release': settings.RELEASE_SHA, 'mode': settings.CODING_MODE},
        status=status)


@operator_view
@_methods('GET')
def encounter_page(request, encounter_id):
    encounter = _encounter(encounter_id)
    response = render(request, 'studio/ops_encounter.html',
                      encounter_view(encounter, done=DONE.get(request.GET.get('done', ''))))
    record_view(request.user, encounter, 'detail')
    return response


def _refused(request, encounter, message, status):
    return render(request, 'studio/ops_encounter.html', encounter_view(encounter, error=message), status=status)


@operator_view
@_methods('GET')
def original(request, encounter_id):
    """The original upload exactly as stored, with its sha256."""
    encounter = _encounter(encounter_id)
    source = encounter.files.order_by('uploaded_at', 'pk').first()
    if source is None:
        raise Http404()
    try:
        data = read_original(source)
    except (OriginalCorrupted, OSError):
        return HttpResponse('The stored original no longer matches its recorded sha256 or cannot be read.',
                            status=409, content_type='text/plain; charset=utf-8')
    response = HttpResponse(data, content_type=source.media_type)
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', source.original_name)[:120] or 'original'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    response['X-Content-SHA256'] = source.sha256
    record_view(request.user, encounter, 'original')
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
        return _refused(request, encounter, 'That run is not part of this document.', 404)
    try:
        recorded = jobs.reconcile(encounter, run, request.user, _note(request))
    except jobs.Refused as exc:
        return _refused(request, encounter, str(exc), 400)
    if recorded is None:
        return _refused(request, encounter, 'Only an unreconciled unknown outcome can be reconciled.', 409)
    return _see_other(f'/ops/encounters/{encounter.pk}?done=reconciled')


@operator_view
@_methods('POST')
def retry(request, encounter_id):
    """A new round of the encounter's failed latest round (jobs.retry), requested by the operator."""
    encounter = _encounter(encounter_id)
    try:
        jobs.retry(encounter, request.user)
    except jobs.Refused as exc:
        return _refused(request, encounter, str(exc), 409)
    return _see_other(f'/ops/encounters/{encounter.pk}?done=retried')


@operator_view
@_methods('POST')
def release_holds(request):
    """Release every standing hold, each with a release naming this operator and the note (jobs.release_holds)."""
    try:
        released = jobs.release_holds(user=request.user, note=_note(request))
    except jobs.Refused as exc:
        return _index_page(request, error=str(exc), status=400)
    if not released:
        return _index_page(request, error='No hold was standing.', status=409)
    return _see_other('/ops/?done=released')
