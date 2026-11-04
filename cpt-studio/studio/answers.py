"""The "A few details needed" flow (owner directive 2026-11-03, section 4; P5 FLOW): the details a document still needs,
the answers a member saves, and the date of service as the document and the member state it.

- ``details_needed(encounter, assessment, view)``: one row per open material question, de-duplicated by (fact, family,
  code), each with its control - ``date`` (the date of service), ``choice`` (place of service, new or established
  patient, professional or facility claim) or ``confirm`` (a clinical fact, which a member never supplies: only "Not
  documented" or "Cannot confirm", or the physician's addendum). DESIGN section 7's keys, every one and nothing else.
- ``save_details(encounter, user, answers)``: one save for every row. Context values go through ONE jobs.change_context
  call (the existing path: a new context, then a re-assessment exactly as a context save makes it); "Not documented" and
  "Cannot confirm" are MemberAnswer rows, read by the review overlay at read time (no re-assessment, nothing sent). A
  repeated identical save makes nothing.
- ``revoke_answer(encounter, user, answer_id)``: withdraws one answer.
- ``saved_answers(assessment)``: the standing answers of the assessment's revision, which the overlay applies.
- ``service_date_block(encounter)``: the date of service as the document and the member state it, side by side.

An answer binds to (code, family, fact) and its revision - never to a clarification row or a proposal key, which every
re-assessment makes anew - so it stands through a re-assessment of the same revision. Every sentence a member reads here
is from the fixed tables below: no stored question, reason or note text (engine prose, which may quote anything) is
passed through.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.db import transaction

from . import audit, jobs, models, review
from .gi import context as gi_context
from .gi.profiles import PROFILES
from .validation.reconcile import act_label

NOT_DOCUMENTED, CANNOT_CONFIRM = models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM
USE_DOCUMENT = 'use_document'
DATE, CHOICE, CONFIRM = 'date', 'choice', 'confirm'
DATE_FACT = 'service_date'
CHOICES = {'setting': gi_context.SETTINGS, 'patient_status': gi_context.PATIENT_STATUSES,
           'billing_context': gi_context.BILLING_CONTEXTS}
CHOICE_LABELS = {
    'setting': {'office': 'Office', 'hospital_outpatient': 'Hospital outpatient department',
                'asc': 'Ambulatory surgery center', 'inpatient': 'Inpatient', 'emergency': 'Emergency department',
                'telehealth': 'Telehealth'},
    'patient_status': {'new': 'New patient', 'established': 'Established patient'},
    'billing_context': {'professional': 'Professional claim', 'facility': 'Facility claim'},
}
ANSWER_LABELS = {NOT_DOCUMENTED: 'Not documented', CANNOT_CONFIRM: 'Cannot confirm'}
PROMPTS = {
    'setting': 'Where was this service provided?',
    'patient_status': 'Is the patient new or established to this clinician and group?',
    'billing_context': 'Is this billed as a professional claim or a facility claim?',
    'em_basis': 'What supports the visit level: total time on the date of service, or medical decision making?',
    'extent': 'How far was the instrument advanced?',
    'completion': 'Was the examination completed as intended?',
    'target': 'What was examined, and what was sampled?',
    'cannulation': 'Was the intended duct cannulated?',
    'interpretation': 'Who interpreted the study?',
    'method': 'Which testing method was used, and for how long?',
    'route': 'How was the tube placed or replaced?',
    'performed_status': 'Was this procedure performed on the date of service, as documented?',
    'base_included': 'Is this diagnostic examination reported separately from the other procedures on this date?',
    'separate_em': 'Is a significant, separately identifiable visit documented beside the procedure?',
    'units': 'How many units were performed?',
}
CONFLICT_PROMPT = 'The record has conflicting statements about the {act}. Which is right for this date?'
DEFAULT_PROMPT = 'A detail this code depends on is not clear in the document.'
DATE_PROMPTS = {'member': 'The date of service entered for this document differs from the date in the document.',
                'document': 'The document states more than one date of service.',
                'asked': 'Confirm the date of service for this document.'}
USE_DOCUMENT_LABELS = {DATE: 'Use document date', CHOICE: 'Use what the document states'}
STATED_IN_DOCUMENT = '{value} (stated in the document)'
# The activity rows this flow writes, as a customer reads them (the customer activity allowlist reads these).
ACTIVITY_SUMMARIES = {'detail.answered': 'A detail was answered', 'detail.revoked': 'A saved detail was withdrawn',
                      'assessment.refreshed': 'Results were refreshed with updated software'}

MAX_ANSWERS = 50
_ID = re.compile(r'd[0-9a-f]{15}')
_TOKEN = re.compile(r'[a-z][a-z0-9_:.-]{0,39}')
# The one date form API.md documents (api._PIPE_DATE): YYYY-MM-DD, a calendar date.
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')

BUSY = 'Wait for processing to finish (or stop it) before saving details.'
STALE = 'That detail is no longer needed. Reload the page to see the details this document needs now.'
SHAPE = 'Send the details as a list of answers, each with its id, fact and value.'
TOO_MANY = f'Send at most {MAX_ANSWERS} answers at a time.'
TWICE = 'Each detail can be answered once in a save.'
NOT_OFFERED = 'Choose one of the answers offered for this detail.'
CLINICAL = ('Only "Not documented" or "Cannot confirm" can be recorded for this detail. A clinical detail is added '
            'to the documentation by the physician.')
BAD_DATE = 'Enter the date of service as a date in YYYY-MM-DD form.'
TWO_VALUES = 'Two answers in this save give different values for the same detail; choose one.'
ALREADY_WITHDRAWN = 'That answer was already withdrawn.'


class InvalidAnswer(ValueError):
    """An answer the detail does not allow (the API answers 400 with the message, which is from the fixed table)."""


def detail_id(fact: str, family: str, code: str) -> str:
    """A detail's stable id: the same question about the same code is the same detail across re-assessments."""
    return 'd' + hashlib.sha256('\x1f'.join((fact, family, code)).encode()).hexdigest()[:15]


def control_for(fact: str) -> str:
    return DATE if fact == DATE_FACT else CHOICE if fact in CHOICES else CONFIRM


def _iso(value):
    return value.isoformat() if value else None


def _date_label(value: str) -> str:
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        return str(value)
    return f'{day.day} {day:%B %Y}'


def _iso_date(value) -> Optional[str]:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _exact(span, text):
    """A stored evidence span as {text, start, end} when it is an exact slice of ``text``, else None."""
    if not isinstance(span, dict):
        return None
    start, end, quoted = span.get('start'), span.get('end'), span.get('text')
    if type(start) is int and type(end) is int and 0 <= start < end <= len(text) and text[start:end] == quoted:
        return {'text': quoted, 'start': start, 'end': end}
    return None


# --- the date of service, as the document and the member state it -----------------------------------------------------

def _document_date(context):
    """The context's pre-merge document date (EncounterContext.document_date). A context recorded before the field
    existed has none: then only where no member value was merged is the stored fact the document's own; otherwise None,
    and no document date is shown or used (it is never read back from a note's prose)."""
    if context is None:
        return None
    if context.document_date is not None:
        return context.document_date
    if (context.user_values or {}).get(DATE_FACT):
        return None
    fact = (context.facts or {}).get(DATE_FACT) or {}
    if fact.get('origin') != 'document' or not fact.get('value'):
        return None
    text = context.revision.text
    quotes = [found for found in (_exact(span, text) for span in fact.get('evidence') or []) if found]
    return {'origin': 'document', 'value': fact['value'], 'single': True, 'values': [fact['value']], 'asked': False,
            'quote': quotes[0] if quotes else None, 'evidence': list(fact.get('evidence') or [])}


def _context_of(encounter):
    context = encounter.current_context
    return context if context is not None and context.revision_id == encounter.current_revision_id else None


def service_date_block(encounter) -> dict:
    """DESIGN section 7 ``service_date``: the date in effect (``value``) and where it comes from; the document's own
    date and its quote, only when the document gives one date of its own; the date a member entered; whether the two
    conflict; and whether "Use document date" - clearing the member's date - settles it. Never a date the document
    does not give as its own, and never one of two conflicting dates chosen for the member."""
    context = _context_of(encounter)
    fact = ((context.facts or {}).get(DATE_FACT) if context is not None else None) or {}
    entered = ((context.user_values if context is not None else encounter.user_values) or {}).get(DATE_FACT) or None
    document = _document_date(context) or {}
    origin = fact.get('origin') or 'missing'
    single = bool(document.get('single'))
    member_conflict = gi_context.is_member_conflict(fact) if fact else False
    return {
        'value': fact.get('value') if origin in ('document', 'user') else None,
        'source': {'document': 'document', 'user': 'member', 'conflict': 'conflict'}.get(origin, 'missing'),
        'document_value': document.get('value') if single else None,
        'document_quote': document.get('quote') if single else None,
        'entered_value': entered,
        'conflict': origin == 'conflict' and not gi_context.charge_date_problem(fact),
        'can_use_document_date': single and bool(entered) and member_conflict,
    }


# --- the rows ----------------------------------------------------------------------------------------------------------

@dataclass
class _Row:
    fact: str
    family: str
    code: str
    scope: str
    position: tuple
    codes: list = field(default_factory=list)
    answer: Optional[models.MemberAnswer] = None
    choices: list = field(default_factory=list)
    allow: list = field(default_factory=list)
    document_value: Optional[str] = None
    entered_value: Optional[str] = None
    quote: Optional[dict] = None
    prompt: str = ''

    @property
    def id(self):
        return detail_id(self.fact, self.family, self.code)

    @property
    def control(self):
        return control_for(self.fact)

    def public(self):
        answer = self.answer
        return {
            'id': self.id, 'fact': self.fact,
            'family_label': PROFILES[self.family].label if self.family in PROFILES else '',
            'prompt': self.prompt, 'control': self.control, 'choices': list(self.choices), 'allow': list(self.allow),
            'document_value': self.document_value, 'entered_value': self.entered_value, 'quote': self.quote,
            'affects': list(self.codes),
            'saved': None if answer is None else {
                'value': answer.value, 'label': ANSWER_LABELS[answer.value], 'by': answer.answered_by.label(),
                'at': _iso(answer.answered_at), 'answer_id': str(answer.pk)},
            'addendum_allowed': self.control == CONFIRM,
        }


def standing_answers(revision_id):
    """The revision's answers that stand (none withdrawn), oldest first."""
    return list(models.MemberAnswer.objects.filter(revision_id=revision_id, revocation__isnull=True)
                .select_related('answered_by').order_by('answered_at', 'pk'))


def saved_answers(assessment) -> list[dict]:
    """[{code, family, fact, value, answer_id, by, at}]: the standing member answers of ``assessment``'s revision, which
    the review overlay applies to the questions they answer (a proposal's question answered 'not documented' or 'cannot
    confirm' leaves that proposal excluded until the answer is withdrawn; a service's question is closed). One per
    detail: a later answer to the same detail withdraws the earlier one."""
    if assessment is None:
        return []
    return [{'code': answer.code, 'family': answer.family, 'fact': answer.fact, 'value': answer.value,
             'answer_id': str(answer.pk), 'by': answer.answered_by.label(), 'at': _iso(answer.answered_at)}
            for answer in standing_answers(assessment.revision_id)]


def effective_view(assessment):
    """The review overlay's view of ``assessment`` (review.effective_view, DESIGN section 4) when the review layer has
    one; None until it does, and then the stored questions are read as they are."""
    view_of = getattr(review, 'effective_view', None)
    return view_of(assessment) if callable(view_of) and assessment is not None else None


def _questions(encounter, assessment, view, answers):
    """(scope, fact, family, code, position) of every open question of ``assessment`` - the stored ones, or with the
    overlay's ``view`` the proposals' questions it holds (plus any stored one a standing answer answers, so the member
    can see and withdraw it) - when ``assessment`` is the live one on the current context; none otherwise.

    ``view``: review.effective_view's {proposal key: review_view.View}, whose ``questions`` are the dicts the overlay
    builds ({id, scope, family, fact, question, reason}; review_view._question). Only a view in the effective set asks
    (``active``): a rejected code's stored question decides nothing, as readiness reads it (review._assessment_blockers),
    and it is asked again once a revocation brings the code back."""
    if assessment is None or assessment.pk != getattr(review.live_assessment(encounter), 'pk', None) \
            or assessment.context_id != encounter.current_context_id:
        return []
    out = []
    stored = assessment.clarifications.filter(state=models.Clarification.OPEN).select_related('proposal')
    for item in stored.order_by('created_at', 'pk'):
        proposal = item.proposal
        if proposal is not None:
            out.append(('proposal', item.fact, item.family or proposal.family, proposal.code, (2, proposal.position)))
        else:
            out.append((item.scope, item.fact, item.family, '', (0 if item.scope == 'encounter' else 1, 0)))
    if view is None:
        return out
    proposals = {proposal.key: proposal for proposal in assessment.proposals.all()}
    standing = {(answer.fact, answer.family, answer.code) for answer in answers}
    held = [entry for entry in out if entry[0] != 'proposal']
    held += [entry for entry in out if entry[0] == 'proposal' and entry[1:4] in standing]
    for key, item in view.items():
        proposal = proposals.get(key)
        if proposal is None or not getattr(item, 'active', True):
            continue
        for spec in getattr(item, 'questions', ()) or ():
            fact, family = spec.get('fact') or '', spec.get('family') or ''
            held.append(('proposal', fact, family or proposal.family, proposal.code, (2, proposal.position)))
    # A code a standing answer excluded (review.DETAIL_UNAVAILABLE) holds no open question in its view - the answer
    # closed it - and the question may be the overlay's own, with no stored row: its answered rows stay, so the member
    # still sees the answer in effect and can withdraw it.
    excluded = {proposal.code: proposal for key, proposal in proposals.items()
                if getattr(view.get(key), 'reason', '') == review.DETAIL_UNAVAILABLE}
    for answer in answers:
        proposal = excluded.get(answer.code) if answer.code else None
        if proposal is not None:
            held.append(('proposal', answer.fact, answer.family or proposal.family, answer.code,
                         (2, proposal.position)))
    return held


def _rows(encounter, assessment, view=None):
    context = _context_of(encounter)
    answers = standing_answers(encounter.current_revision_id) if encounter.current_revision_id else []
    by_key = {(answer.fact, answer.family, answer.code): answer for answer in answers}
    rows: dict = {}
    hold = context is not None and gi_context.is_member_conflict((context.facts or {}).get(DATE_FACT))
    if hold:
        rows[(DATE_FACT, '', '')] = _Row(DATE_FACT, '', '', 'encounter', (0, -1))
    selected = [proposal.code for proposal in assessment.proposals.filter(bucket=models.Proposal.SELECTED)] \
        if assessment is not None else []
    for scope, fact, family, code, position in _questions(encounter, assessment, view, answers):
        key = (DATE_FACT, '', '') if fact == DATE_FACT else (fact, family, code)
        row = rows.get(key)
        if row is None:
            row = rows[key] = _Row(key[0], key[1], key[2], 'encounter' if fact == DATE_FACT else scope, position)
        if fact == DATE_FACT:
            row.codes = list(dict.fromkeys(row.codes + selected))
        elif code and code not in row.codes:
            row.codes.append(code)
    values = dict((context.user_values if context is not None else encounter.user_values) or {})
    out = []
    for row in sorted(rows.values(), key=lambda item: item.position):
        row.answer = by_key.get((row.fact, row.family, row.code))
        if row.control == DATE:
            _date_row(row, encounter)
        elif row.control == CHOICE:
            fact = (context.facts or {}).get(row.fact) if context is not None else None
            conflict = gi_context.is_member_conflict(fact)
            row.choices = [{'value': value, 'label': CHOICE_LABELS[row.fact].get(value, value)}
                           for value in CHOICES[row.fact]]
            if conflict:
                row.choices.append({'value': USE_DOCUMENT, 'label': USE_DOCUMENT_LABELS[CHOICE]})
                row.quote = next((found for found in (_exact(span, context.revision.text)
                                                      for span in (fact or {}).get('evidence') or []) if found), None)
            row.allow = [] if conflict or row.scope == 'encounter' else [NOT_DOCUMENTED]
            row.entered_value = values.get(row.fact) or None
            row.prompt = PROMPTS[row.fact]
        else:
            row.allow = [] if row.scope == 'encounter' else [NOT_DOCUMENTED, CANNOT_CONFIRM]
            subject = row.fact.split(':', 1)[1] if row.fact.startswith('conflict:') else ''
            row.prompt = CONFLICT_PROMPT.format(act=act_label(subject)) if subject else PROMPTS.get(row.fact,
                                                                                                   DEFAULT_PROMPT)
        out.append(row)
    return out


def _date_row(row, encounter):
    """The date row: the document's date and the member's side by side, "Use document date" only where the document
    gives one date of its own and the member's differs (clearing the member's date then leaves that date), and the
    document's own dates as choices where it states more than one, or where its closing charge block's question takes
    one - never a date it does not state as its own, and never prefilled."""
    block = service_date_block(encounter)
    context = _context_of(encounter)
    document = _document_date(context) or {}
    row.document_value, row.quote, row.entered_value = (block['document_value'], block['document_quote'],
                                                         block['entered_value'])
    if block['can_use_document_date']:
        row.choices = [{'value': USE_DOCUMENT, 'label': USE_DOCUMENT_LABELS[DATE]}]
        row.prompt = DATE_PROMPTS['member']
    elif not document.get('single') and document.get('values'):
        row.choices = [{'value': value, 'label': STATED_IN_DOCUMENT.format(value=_date_label(value))}
                       for value in document['values']]
        row.prompt = DATE_PROMPTS['member' if block['entered_value'] else
                                  'document' if len(document['values']) > 1 else 'asked']
    else:
        row.prompt = DATE_PROMPTS['member' if block['entered_value'] and block['conflict'] else 'asked']
    row.allow = []


def details_needed(encounter, assessment, view=None) -> list[dict]:
    """DESIGN section 7 ``details_needed``: one row per open material question of the live assessment on the current
    context (and the date of service at once while a member's date conflicts with the document, before any assessment),
    de-duplicated by (fact, family, code), dates first, then the document's, the services' and the codes' questions."""
    return [row.public() for row in _rows(encounter, assessment, view)]


# --- saving and withdrawing ----------------------------------------------------------------------------------------------

def _parse(items):
    if not isinstance(items, list) or not items:
        raise InvalidAnswer(SHAPE)
    if len(items) > MAX_ANSWERS:
        raise InvalidAnswer(TOO_MANY)
    parsed, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise InvalidAnswer(SHAPE)
        given = tuple(item.get(name) for name in ('id', 'fact', 'value'))
        if not all(isinstance(value, str) for value in given):
            raise InvalidAnswer(SHAPE)
        ident, fact, value = given
        if not _ID.fullmatch(ident) or not _TOKEN.fullmatch(fact) or not 0 < len(value) <= 40:
            raise InvalidAnswer(SHAPE)
        if ident in seen:
            raise InvalidAnswer(TWICE)
        seen.add(ident)
        parsed.append((ident, fact, value))
    return parsed


def _in_effect(encounter, answers, fact, value):
    """Whether an answer for a detail no longer asked is already what stands: a repeated save after the re-assessment it
    caused (the context value is the one saved), or an answer already recorded."""
    if fact in CHOICES or fact == DATE_FACT:
        current = (encounter.user_values or {}).get(fact) or ''
        given = '' if value == USE_DOCUMENT else (_iso_date(value) or value) if fact == DATE_FACT else value
        return current == given
    return any(answer.fact == fact and answer.value == value for answer in answers)


def save_details(encounter, user, items) -> dict:
    """Save a member's answers to the details asked, in one transaction under the encounter's row lock: every answer
    is checked against the detail's own control before anything is written (InvalidAnswer: 400), the whole save is
    refused while processing runs or when a detail is no longer asked (jobs.Refused: 409). Context values are ONE
    jobs.change_context call; 'not_documented' / 'cannot_confirm' are MemberAnswer rows (a later answer withdraws the
    earlier one). An answer already in effect is left as it is, so a repeated identical save makes nothing."""
    parsed = _parse(items)
    with transaction.atomic():
        encounter = jobs._locked(encounter)
        if jobs.busy(encounter):
            raise jobs.Refused(BUSY)
        assessment = review.live_assessment(encounter)
        rows = {row.id: row for row in _rows(encounter, assessment, effective_view(assessment))}
        answers = standing_answers(encounter.current_revision_id) if encounter.current_revision_id else []
        values, recorded, superseded, unchanged = {}, [], [], 0
        for ident, fact, value in parsed:
            row = rows.get(ident)
            if row is None or row.fact != fact:
                if _in_effect(encounter, answers, fact, value):
                    unchanged += 1
                    continue
                raise jobs.Refused(STALE)
            offered = {choice['value'] for choice in row.choices}
            if value in (NOT_DOCUMENTED, CANNOT_CONFIRM):
                if value not in row.allow:
                    raise InvalidAnswer(CLINICAL if row.control == CONFIRM else NOT_OFFERED)
                if row.answer is not None and row.answer.value == value:
                    unchanged += 1
                    continue
                recorded.append((row, value))
                continue
            if row.control == CONFIRM:
                raise InvalidAnswer(CLINICAL)
            if value == USE_DOCUMENT:
                if USE_DOCUMENT not in offered:
                    raise InvalidAnswer(NOT_OFFERED)
                given = ''
            elif row.control == DATE:
                given = _iso_date(value)
                if given is None:
                    raise InvalidAnswer(BAD_DATE)
            elif value in CHOICES[row.fact]:
                given = value
            else:
                raise InvalidAnswer(NOT_OFFERED)
            if values.get(row.fact, given) != given:
                raise InvalidAnswer(TWO_VALUES)
            values[row.fact] = given
            if row.answer is not None:
                superseded.append(row.answer)  # a value given for a detail said not to be documented replaces that
        current = dict(encounter.user_values or {})
        changed = {name: value for name, value in values.items() if (current.get(name) or '') != value}
        unchanged += len(values) - len(changed)
        saved_ids = []
        for row, value in recorded:
            if row.answer is not None:
                models.MemberAnswerRevocation.objects.create(answer=row.answer, revoked_by=user,
                                                             reason=models.MemberAnswerRevocation.SUPERSEDED)
            answer = models.MemberAnswer.objects.create(
                encounter=encounter, revision=encounter.current_revision, assessment=assessment, fact=row.fact,
                family=row.family, code=row.code, value=value, answered_by=user)
            saved_ids.append(str(answer.pk))
            audit.record(encounter.workspace, 'detail.answered', encounter=encounter, actor=user, fact=row.fact,
                         family=row.family, code=row.code, value=value, answer=str(answer.pk))
        for answer in superseded:
            models.MemberAnswerRevocation.objects.create(answer=answer, revoked_by=user,
                                                         reason=models.MemberAnswerRevocation.SUPERSEDED)
        if changed:
            context = jobs.change_context(encounter, user, changed)
            for name in sorted(changed):
                row = next(item for item in rows.values() if item.fact == name)
                audit.record(encounter.workspace, 'detail.answered', encounter=encounter, actor=user, fact=name,
                             family=row.family, code=row.code, kind='context', context=str(context.pk))
        elif recorded or superseded:
            review.refresh_state(encounter)  # the overlay reads the answers: the list state follows them
    withdrawn = [answer for answer in superseded if answer.fact not in changed]  # counted once with its value
    return {'saved': len(recorded) + len(changed) + len(withdrawn), 'unchanged': unchanged, 'answer_ids': saved_ids,
            'reassessing': bool(changed)}


def revoke_answer(encounter, user, answer_id):
    """Withdraw one standing answer (a MemberAnswerRevocation, 'withdrawn'): the detail is asked again. Refused while
    processing runs and for an answer already withdrawn (jobs.Refused: 409); MemberAnswer.DoesNotExist for an answer
    that is not this document's (404)."""
    with transaction.atomic():
        encounter = jobs._locked(encounter)
        if jobs.busy(encounter):
            raise jobs.Refused(BUSY)
        answer = models.MemberAnswer.objects.select_for_update().get(pk=answer_id, encounter=encounter)
        if models.MemberAnswerRevocation.objects.filter(answer=answer).exists():
            raise jobs.Refused(ALREADY_WITHDRAWN)
        revocation = models.MemberAnswerRevocation.objects.create(
            answer=answer, revoked_by=user, reason=models.MemberAnswerRevocation.WITHDRAWN)
        audit.record(encounter.workspace, 'detail.revoked', encounter=encounter, actor=user, fact=answer.fact,
                     family=answer.family, code=answer.code, answer=str(answer.pk))
        review.refresh_state(encounter)
    return revocation
