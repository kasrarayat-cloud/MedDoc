"""The customer contract (BUILD-SPEC 6; client contract customer-2026-11-20): every payload the customer page reads, built
from stored rows on each request.

- session_json: GET /api/session.
- list_rows: GET /api/encounters.
- encounter_json: GET /api/encounters/<id> - the document and its in-page view, the practice's context, the progress of
  the latest coding round, its codes (each with the second check's verdict, its quotes, its current decision and the
  decisions the member may record), its questions, every answer given, its documentation notes, the export readiness,
  the exports and the activity.
- view_content: what GET /api/encounters/<id>/original?view=1 serves - the original PDF or text, a pasted text, or for
  a Word document the PDF the coding review read (CodingRound.view_pdf_*: the converted file, so the pages the quotes
  name are the pages shown).

Only the latest round is shown: while it is queued or running, failed or stopped, it has no codes. Quotes are the
round's citations - the passages the API itself verified against the document (fable.result.citations), filed under
each code by the reader's CODE and the checker's REVIEW sections - and only for a code with none, the quotes the answer's
JSON gave as its evidence. An encounter with no coding round (a record of the earlier system) reads as an earlier
review, with nothing of the earlier tables shown: Review again (POST retry) codes it with the current version.

Display hygiene (BUILD-SPEC 7.4): the text the coding review wrote - reasons, the second check's reasons, questions and
documentation notes - passes through shown(), which replaces vendor and model names (the shared denylist's name rules,
ops/verification/customer-denylist.json; a test pins them) with "the system" and changes nothing else. Codes, statuses
and quotes of the document are never touched. No payload carries a provider, model, usage, cost, hash, run or request id.
"""
from __future__ import annotations

import re
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from typing import Optional

from django.db.models import Exists, OuterRef
from django.utils import timezone

from . import decisions, jobs, models, state
from .storage import ALLOWED_SUFFIXES, read_original

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
# The second check's reason where it gave no verdict on a code: CPT Studio's own sentence.
ADDED_BY_CHECK = 'The second check found this code; it needs your review.'
NOT_CHECKED = 'The second check did not review this code.'
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
# repeated; tests/test_api_customer.py pins them to the file's patterns and vectors.

NAMES = 'corti|astra|fable|openai|anthropic|claude|gemini|google'
JOINED_NAMES = 'Corti|Astra|Fable|Openai|OpenAI|Anthropic|Claude|Gemini|Google'
_MODEL_ID = re.compile(r'\b(?:gpt|claude|gemini)-[a-z0-9]+(?:[.-][a-z0-9]+)*', re.ASCII | re.IGNORECASE)
# a name, any names joined to it ("Claude Fable"), and a version after them ("5.2"); bounded by letters and digits only,
# so "fable_unknown" is a hit and "affable" or "corticosteroid" is not
_NAME_RUN = re.compile(rf'(?<![a-z0-9])(?:{NAMES})(?:[ _-]+(?:{NAMES}))*(?:[ _-]+v?\d+(?:\.\d+)*)?(?![a-z0-9])',
                       re.ASCII | re.IGNORECASE)
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
    for pattern in (_MODEL_ID, _NAME_RUN, _JOINED):
        text = pattern.sub(_the_system, text)
    return text


def _shown_or(text, default=None):
    value = shown(text)
    return value if isinstance(value, str) and value.strip() else default


# --- the session and the list ----------------------------------------------------------------------------------------------

def initials(user) -> str:
    name = (user.display_name or user.get_username() or '?').replace('-', ' ').replace('_', ' ')
    parts = [part for part in name.split() if part]
    return (''.join(part[0] for part in parts[:2]) or name[:2]).upper()


def _with_rounds(queryset):
    return queryset.annotate(has_round=Exists(Round.objects.filter(encounter_id=OuterRef('pk'))))


def session_json(user, membership) -> dict:
    """GET /api/session: who is signed in, the workspace, the role, the approval attestation and the counts (every
    document, and those waiting on a member: questions to answer, codes to review or to approve)."""
    workspace = membership.workspace
    encounters = workspace.encounters.all()
    queue = _with_rounds(encounters).filter(has_round=True, state__in=QUEUE_STATES).count()
    return {'user': {'id': str(user.pk), 'label': user.label(), 'initials': initials(user),
                     'actor_kind': user.actor_kind},
            'workspace': {'id': str(workspace.pk), 'name': workspace.name},
            'role': membership.role, 'can_review': bool(membership.can_review),
            'acknowledgement': decisions.acknowledgement_for(user),
            'counts': {'documents': encounters.count(), 'queue': queue}}


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
    rows = _with_rounds(membership.workspace.encounters.select_related('current_revision')).order_by('-created_at')
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
        return read_original(source), PDF, safe_name(source.original_name)
    if source.media_type == TEXT:
        return read_original(source), TEXT_SERVED, safe_name(source.original_name)
    if source.media_type == DOCX:
        view = converted_view(encounter)
        if view is None:
            return None
        data = read_original(SimpleNamespace(storage_name=view.view_pdf_storage_name, sha256=view.view_pdf_sha256))
        stem = (source.original_name or 'document').rsplit('.', 1)[0]
        return data, PDF, safe_name(f'{stem}.pdf', 'document.pdf')
    return None


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
            'can_resume': can_review and current == STOPPED and not running,
            'can_retry': can_review and decisions.retry_offered(encounter, round_),
            'error': error}


def citation_index(round_) -> dict:
    """{CODE: [(text, page)]} of the round's citations, each code's reader citations then its checker's."""
    index: dict = {}
    for key, items in (round_.citations or {}).items():
        if not isinstance(key, str) or not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
                index.setdefault(key.strip().upper(), []).append((item['text'], item.get('page')))
    return index


def _page(value) -> Optional[int]:
    return value if type(value) is int and value > 0 else None


def quotes(row, index) -> list:
    """A code's quotes: its citations (verified by the API), or only when it has none, its JSON evidence quotes; each
    passage once."""
    code = row.get('code') if isinstance(row.get('code'), str) else ''
    found = index.get(code.strip().upper()) or [
        (item.get('quote'), item.get('page')) for item in row.get('evidence') or ()
        if isinstance(item, dict) and isinstance(item.get('quote'), str) and item['quote'].strip()]
    out, seen = [], set()
    for text, page in found:
        key = (' '.join(text.split()), _page(page))
        if key not in seen:
            seen.add(key)
            out.append({'text': text, 'page': _page(page)})
    return out


def decision_json(decision) -> Optional[dict]:
    if decision is None:
        return None
    return {'action': decision.action, 'by': decision.reviewer.label(), 'at': iso(decision.created_at),
            'note': decision.note}


def code_json(row, index, decision, can_review: bool) -> dict:
    status = row.get('status')
    check = row.get('second_check') if isinstance(row.get('second_check'), dict) else {}
    agrees = check.get('agrees') if isinstance(check.get('agrees'), bool) else None
    if row.get('listed_by') == 'checker':
        check_reason = ADDED_BY_CHECK
    elif agrees is None:
        check_reason = NOT_CHECKED
    else:
        check_reason = _shown_or(check.get('reason'))
    modifiers = row.get('modifiers')
    return {'code': row.get('code'), 'units': row.get('units') if type(row.get('units')) is int else None,
            'modifiers': [item for item in modifiers if isinstance(item, str)] if isinstance(modifiers, list) else [],
            'status': status, 'status_label': CODE_STATUS_LABELS.get(status, 'Not reviewable'),
            'reason': _shown_or(row.get('reason'), ''),
            'second_check': {'agrees': agrees, 'reason': check_reason},
            'question': _shown_or(row.get('question')), 'quotes': quotes(row, index),
            'decision': decision_json(decision), 'allowed_actions': decisions.allowed_actions(row, decision, can_review)}


def round_rows(round_, current, can_review: bool) -> list:
    """The code rows of a done round (its stored order), each with its current decision; [] for any other round."""
    if round_ is None or round_.state != Round.DONE:
        return []
    index = citation_index(round_)
    rows = [row for row in round_.codes or () if isinstance(row, dict) and isinstance(row.get('code'), str)
            and row.get('status') in CODE_STATUS_LABELS]
    return [code_json(row, index, current.get(row['code']), can_review) for row in rows]


def questions_json(round_) -> list:
    if round_ is None or round_.state != Round.DONE:
        return []
    return [{'id': identifier, 'text': shown(item['text']),
             'codes': [code for code in item.get('codes') or () if isinstance(code, str)]}
            for identifier, item in decisions.round_questions(round_)]


def answers_json(encounter) -> list:
    rows = models.CodingAnswer.objects.filter(encounter_id=encounter.pk).select_related('answered_by').order_by(
        'answered_at', 'pk')
    return [{'question': shown(row.question), 'answer': row.answer, 'by': row.answered_by.label(),
             'at': iso(row.answered_at)} for row in rows]


def notes_json(round_) -> list:
    if round_ is None or round_.state != Round.DONE:
        return []
    return [shown(item) for item in round_.problems or () if isinstance(item, str) and item.strip()]


def readiness(round_, current) -> dict:
    """What can be exported now (BUILD-SPEC 6, 8): a draft once the latest round is done, the approved export once a
    code of it is approved; the blockers say why not, in the member's words."""
    if round_ is None:
        return {'draft': False, 'approved': False, 'blockers': [BLOCKERS[EARLIER]]}
    if round_.state != Round.DONE:
        key = {Round.FAILED: FAILED, Round.CANCELLED: STOPPED}.get(round_.state, 'busy')
        return {'draft': False, 'approved': False, 'blockers': [BLOCKERS[key]]}
    approved = any(decision.action == models.CodeDecision.APPROVE for decision in current.values())
    return {'draft': True, 'approved': approved, 'blockers': [] if approved else [BLOCKERS['none_approved']]}


def report_json(export, latest_round_id, last_decision_at=None) -> dict:
    """One export as the page lists it; ``current`` while it was made from the latest round and no decision on that
    round was recorded after it (an earlier one is still listed and served as stored, marked earlier)."""
    current = export.round_id == latest_round_id and (last_decision_at is None or last_decision_at <= export.created_at)
    return {'id': str(export.pk), 'kind': export.kind, 'fmt': export.fmt, 'filename': export.filename,
            'generated_at': iso(export.created_at), 'download_url': f'/api/reports/{export.pk}/download',
            'current': current}


def reports_json(encounter, round_) -> list:
    exports = Export.objects.filter(encounter_id=encounter.pk).order_by('-created_at', '-pk').only(
        'pk', 'kind', 'fmt', 'filename', 'created_at', 'round_id')
    last_decision_at = None
    if round_ is not None:
        last = models.CodeDecision.objects.filter(round_id=round_.pk).order_by('-created_at').values_list(
            'created_at', flat=True).first()
        last_decision_at = last
    return [report_json(export, round_.pk if round_ is not None else None, last_decision_at) for export in exports]


# --- the activity ------------------------------------------------------------------------------------------------------------

def _count(value, one, many) -> str:
    return f'{value} {one if value == 1 else many}'


def _activity_text(event, numbers) -> str:
    data = event.data if isinstance(event.data, dict) else {}
    who = event.actor.label() if event.actor is not None else 'CPT Studio'
    name = event.event
    if name == 'encounter.created':
        return f'Pasted by {who}.' if data.get('kind') == Revision.PASTE else f'Uploaded by {who}.'
    if name == 'coding.round_queued':
        return f'{who} asked for the coding review again.' if data.get('trigger') == Round.RETRY else ''
    if name == 'answers.recorded' and type(data.get('count')) is int:
        return f'{who} answered {_count(data["count"], "question", "questions")}.'
    if name in ('coding.round_done', 'coding.round_failed'):
        number = numbers.get(data.get('round'))
        review = f'Coding review {number}' if number else 'The coding review'
        if name == 'coding.round_failed':
            return f'{review} could not finish.'
        if data.get('codes') == 0:
            return f'{review} finished with no codes.'
        if type(data.get('questions')) is int and data['questions'] > 0:
            return f'{review} finished with {_count(data["questions"], "question", "questions")}.'
        return f'{review} finished.'
    if name == 'decision.recorded' and 'round' in data and isinstance(data.get('code'), str):
        words = {decisions.APPROVE: 'approved', decisions.REJECT: 'rejected',
                 decisions.REVOKE: 'undid the decision on'}.get(data.get('action'))
        return f'{who} {words} {data["code"]}.' if words else ''
    if name == 'export.created':
        return f'{"Approved" if data.get("kind") == Export.APPROVED else "Draft"} download made by {who}.'
    if name == 'pipeline.stopped':
        return f'Stopped by {who}.'
    if name == 'pipeline.resumed':
        return f'Resumed by {who}.'
    return ''


def activity_json(encounter) -> list:
    """What happened to the document, oldest first, each in a fixed sentence (never an event's stored data as text)."""
    numbers = {str(pk): number for pk, number in Round.objects.filter(encounter_id=encounter.pk)
               .values_list('pk', 'number')}
    out = []
    for event in encounter.audit_events.select_related('actor').order_by('created_at', 'pk'):
        text = _activity_text(event, numbers)
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
