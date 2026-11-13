"""The "A few details needed" flow (owner directive 2026-11-03, section 4; P5 FLOW): the details a document still needs,
the answers a member saves, and the date of service as the document and the member state it.

- ``details_needed(encounter, assessment, view)``: one row per open material question - one per fact of a documented
  service (the profiles' required facts: how far an endoscope was advanced, what was examined, a duct cannulated, a
  visit's setting, status or basis), whichever of its codes hold on it, and one per question about one code otherwise -
  each with its control: ``date`` (the date of service), ``choice`` (place of service, new or established patient,
  professional or facility claim) or ``confirm`` (a clinical fact, which a member never supplies: only "Not documented"
  or "Cannot confirm", or the physician's addendum). DESIGN section 7's keys, every one and nothing else.
- The date row also stands while a member's date of service is in effect where the document gives no single date of
  its own: as the member's saved answer, attributed, which the same row corrects or removes (refutation r2, L7-05); and
  it asks again - the document's own dates beside the one entered - where a date typed outside the details panel chose
  one of the document's conflicting dates before they were in view (L7-02).
- ``save_details(encounter, user, answers)``: one save for every row. Context values go through ONE jobs.change_context
  call (the existing path: a new context, then a re-assessment exactly as a context save makes it); "Not documented" and
  "Cannot confirm" are MemberAnswer rows - one for each code the row's question holds - each bound to the question it
  answered, and the save queues ONE recompute of the assessment (jobs.recompute_after_answers: the AGAIN path with the
  recorded runs, the bounded assess child, nothing sent), which reads the answers as an input (engine._MemberAnswers).
  Until it has run, the review overlay applies them at read time. A repeated identical save makes nothing.
- ``revoke_answer(encounter, user, answer_id)``: withdraws one answer - with it, the same question's answer for the
  row's other codes - and queues the recompute the same way. An answer the assessment itself read stays in effect on
  every surface until that recompute has run (refutation cycle 2, answers W1: one source of truth); the recompute is
  a visible job, with Stop and Resume.
- ``saved_answers(assessment)``: the standing answers of the assessment's revision.
- ``earlier_answers(encounter, assessment)``: the standing answers no question asked now takes, each with why.
- ``service_date_block(encounter)``: the date of service as the document and the member state it, side by side.

An answer binds to the question it answered (completion repair 2026-11-06, U11): the code, family and fact it was asked
of, its revision, and the fingerprint of that question as the row showed it - CPT Studio's question and reason and the
passages it concerns (studio.validation.questions) - never to a clarification row or a proposal key, which every
re-assessment makes anew. A later assessment applies it only where it asks the same question; an answer to a question
no longer asked, or asked differently, is kept and listed as an earlier answer, never applied. An answer given before
rows showed their passages (MemberAnswer.question '') was given to the installed release's fixed prompt for its code,
family and fact, and binds by them, as that release bound it (refutation cycle 2, answers W2 and W4). Every sentence a
member reads here is from the fixed tables below: no stored question, reason or
note text (engine prose, which may quote anything) is passed through; the document's own words are quoted only as
exact slices of its text.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.db import transaction

from . import audit, jobs, models, review
from .code_shapes import act_label  # the act labels, re-homed (ADJUDICATION R-2): reconcile's own object
from .gi import context as gi_context
from .gi.profiles import PROFILES
from .interpretation import readers, sentinel
from .interpretation.wording import MISSING as EVENT_FACTS_MISSING
from .validation import questions
from .validation.engine import COMPETING_FACT

NOT_DOCUMENTED, CANNOT_CONFIRM = models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM
USE_DOCUMENT = 'use_document'
# Refutation r2, L7-03 and L7-05: remove the member's date of service (the existing clear path, change_context with
# service_date '') where "Use document date" would name a date the document does not give as its single own one.
CLEAR = 'clear'
CLEAR_LABEL = 'Remove the entered date'
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
# Refutation r2, L7-08: the facts a documented service has (each profile's required facts), asked once for the service
# whichever of its codes hold on them - "How far was the instrument advanced?" is one question about one colonoscopy,
# never one per code. A question about one code (its units, its base, whether its act was done) stays that code's.
SERVICE_FACTS = frozenset(fact for profile in PROFILES.values() for fact in profile.required_facts)
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
    # harness repair 3 (HARNESS.md, P-ADMIT2): answered by the review decision, never by a detail answer
    COMPETING_FACT: 'More than one code is proposed for the same documented act. Reject the code the documentation '
                    'does not support; the code left is then ready for review.',
    # the Gemini migration's facts (design/FINAL.md 7.4, 8.3; contract 9.4): the question each code is asked names the
    # act and quotes its passage; the row's prompt is CPT Studio's general wording of the fact, and the answers allowed
    # stay "Not documented" and "Cannot confirm"
    'event_time': 'Was this act done at this encounter, on the date of service?',
    'event_performer': 'Who performed this act?',
    'act_target': 'Which lesion or site was this act done on?',
    'technique': 'Which technique was used for this act?',
    'statement_scope': 'Does the statement quoted apply to this act?',
    'act_method': 'By which method was the lesion removed?',
    'procedure': 'In which procedure was this act done?',
    # design v2's five new facts (FINAL-V2 4.8; DECISIONS D181), worded as the seven above
    'event_entry': 'In whose entry is this act documented?',
    'exam_stations': 'Which parts of the upper tract were examined?',
    'act_yield': 'What did this extraction retrieve?',
    'act_cause': 'What caused the bleeding this act treated?',
    'act_part': 'Was this act part of another act?',
}
CONFLICT_PROMPT = 'The record has conflicting statements about the {act}. Which is right for this date?'
DEFAULT_PROMPT = 'CPT Studio could not confirm a detail this code depends on.'  # U9: CPT Studio's reading
DATE_PROMPTS = {'member': 'The date of service entered for this document differs from the date in the document.',
                'document': 'The document states more than one date of service.',
                'asked': 'Confirm the date of service for this document.',
                # refutation r2: the date row's other states, each said as it is
                'third': 'The date of service entered for this document is not one of the dates the document states.',
                'unconfirmed': 'The date of service entered cannot be confirmed from the document.',
                'disagree': 'The date of service entered for this document does not agree with the document.',
                'confirm': ('The document states more than one date of service. Confirm which one is right for this '
                            'visit.'),
                'chosen': 'The document states more than one date of service. The date chosen is in use.',
                'entered': 'The date of service entered for this document is in use.'}
USE_DOCUMENT_LABELS = {DATE: 'Use document date', CHOICE: 'Use what the document states'}
# Completion repair (2026-11-06, U10): what a clinical question's row says, beside its passages - what CPT Studio could
# not confirm, never that the document does not state it (only a passage says that; a conflict's row says the record
# states it both ways, which its passages show)
STATEMENT = 'From the document, CPT Studio could not confirm {missing}.'
CONFLICT_STATEMENT = ('The document states the {act} in more than one way, and CPT Studio could not confirm which '
                      'statement is right for this date.')
COMPETING_STATEMENT = ('More than one code is proposed for the same documented act, and CPT Studio does not choose '
                       'between them.')
# a coding question, not a documentation one: what the code depends on is the reviewer's call, never the document's
CODING_STATEMENTS = {
    'base_included': ('This diagnostic examination is normally included in the other procedures documented with it; '
                      'CPT Studio does not decide whether it is reported separately.'),
}
MAX_ROW_PASSAGES = 4  # a row asked for several codes shows each code's passages, a short list in all
# Why a standing answer is listed as an earlier answer (questions.bind's reasons), as a member reads it
EARLIER_WHY = {
    questions.NO_LONGER_ASKED: 'This question is no longer asked, so this answer is not applied.',
    questions.ASKED_DIFFERENTLY: ('This question is now asked differently, so this answer is not applied; answer the '
                                  'question as it is asked now.'),
    'not_applied': 'This answer is not applied to the current results.',
}
STATED_IN_DOCUMENT = '{value} (stated in the document)'
# The activity rows this flow writes, as a customer reads them (the customer activity allowlist reads these).
ACTIVITY_SUMMARIES = {'detail.answered': 'A detail was answered', 'detail.revoked': 'A saved detail was withdrawn',
                      'assessment.refreshed': 'Results were refreshed with updated software'}

MAX_ANSWERS = 50
_ID = re.compile(r'd[0-9a-f]{15}')
_TOKEN = re.compile(r'[a-z][a-z0-9_:.-]{0,39}')
# The one date form API.md documents (api._PIPE_DATE): YYYY-MM-DD, a calendar date.
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
# The newest audit rows read for who entered the date of service in effect (bounded: a document's own trail).
DATE_ENTRY_EVENTS = 200

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
    """A detail's stable id: the same question about the same code is the same detail across re-assessments (a service
    fact's question, asked once for the service, has the code '')."""
    return 'd' + hashlib.sha256('\x1f'.join((fact, family, code)).encode()).hexdigest()[:15]


DETAIL_ID = re.compile(r'd[0-9a-f]{15}')


def is_detail_id(value) -> bool:
    return isinstance(value, str) and DETAIL_ID.fullmatch(value) is not None


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
    and no document date VALUE is shown or used (it is never read back from a note's prose - the document's own wording
    of it is quoted as it stands: _date_passage)."""
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


def _date_in_use(context) -> bool:
    """Whether a member's date of service is in effect where the document gives no single date of its own - none, one
    it does not read as this visit's, or more than one: the date row then stays, as the member's saved answer, so the
    member can correct or remove it (refutation r2, L7-05: a date saved from the panel closed its question and could
    never be corrected or withdrawn there)."""
    if context is None:
        return False
    fact = (context.facts or {}).get(DATE_FACT) or {}
    return (fact.get('origin') == 'user' and bool((context.user_values or {}).get(DATE_FACT))
            and not (_document_date(context) or {}).get('single'))


def _date_passage(context, document):
    """The document's own wording of its date of service, where no date of it is shown: the first evidence span of the
    document's date fact (recorded with the context, or - for a context recorded before that - the stored fact's) that
    is an exact slice of the text. Quoted as the document writes it, never read back as a date (refutation r2, L7-07:
    the row said "Not stated" beside a document that states one)."""
    if context is None:
        return None
    spans = (document or {}).get('evidence') or ((context.facts or {}).get(DATE_FACT) or {}).get('evidence') or []
    text = context.revision.text
    return next((found for found in (_exact(span, text) for span in spans) if found), None)


def _date_entry(encounter, entered) -> dict:
    """{'by', 'at', 'confirmed'} for the member's date of service in effect: who entered it and when - the details save
    that chose it (a detail.answered row naming the date), else the context change that set it, else the upload that
    carried it - and whether it was chosen or confirmed in the details panel on the current revision, where the
    document's own dates are in view (refutation r2, L7-02)."""
    revision = str(encounter.current_revision_id)
    events = (models.AuditEvent.objects.filter(encounter=encounter, event__in=('detail.answered', 'context.changed'))
              .select_related('actor').order_by('-created_at', '-pk')[:DATE_ENTRY_EVENTS])
    for event in events:
        data = event.data if isinstance(event.data, dict) else {}
        if event.event == 'detail.answered':
            if data.get('fact') != DATE_FACT or data.get('value') != entered:
                continue
            confirmed = data.get('revision') == revision
        else:
            if DATE_FACT not in (data.get('fields') or ()):
                continue
            made = models.EncounterContext.objects.filter(pk=data['context'], encounter=encounter).first() \
                if isinstance(data.get('context'), str) and _UUID.fullmatch(data['context']) else None
            if made is None or (made.user_values or {}).get(DATE_FACT) != entered:
                continue
            confirmed = False
        return {'by': event.actor.label() if event.actor is not None else '', 'at': _iso(event.created_at),
                'confirmed': confirmed}
    creator = encounter.created_by
    return {'by': creator.label() if creator is not None else '', 'at': _iso(encounter.created_at), 'confirmed': False}


# --- the rows ----------------------------------------------------------------------------------------------------------

@dataclass
class _Row:
    fact: str
    family: str
    code: str
    scope: str
    position: tuple
    codes: list = field(default_factory=list)
    # the questions the row answers, each (fact, family, code), and each one's standing answer (None: unanswered)
    members: list = field(default_factory=list)
    answers: dict = field(default_factory=dict)
    choices: list = field(default_factory=list)
    allow: list = field(default_factory=list)
    document_value: Optional[str] = None
    entered_value: Optional[str] = None
    quote: Optional[dict] = None
    prompt: str = ''
    # the date row: the member's date in effect as a saved answer (L7-05); a date typed outside the panel that chose
    # one of the document's own dates, asked again (L7-02); the physician's addendum as the way that settles it (L7-03)
    saved_date: Optional[dict] = None
    confirm: bool = False
    addendum: bool = False
    # completion repair (2026-11-06, U10): the passages the row's questions concern, the fact they name, and what CPT
    # Studio could not confirm
    passages: list = field(default_factory=list)
    missing: str = ''
    statement: str = ''

    @property
    def id(self):
        return detail_id(self.fact, self.family, self.code)

    @property
    def control(self):
        return control_for(self.fact)

    @property
    def answer(self) -> Optional[models.MemberAnswer]:
        """The answer standing for every question the row answers - the same value for each - else None: a row one of
        whose codes has no answer yet is asked, and the answer then saved stands for each of them (refutation r2, L7-08;
        never an answer given for one code read as given for another)."""
        found = [self.answers.get(member) for member in self.members]
        if not found or any(item is None for item in found) or len({item.value for item in found}) != 1:
            return None
        return max(found, key=lambda item: (item.answered_at, str(item.pk)))

    @property
    def addendum_allowed(self) -> bool:
        # refutation round 1 of harness repair 3 (L4-6): a competition is settled by a reviewer's rejection of the code
        # the documentation does not support, never by documentation added to the record
        return (self.control == CONFIRM and self.fact != COMPETING_FACT) or self.addendum

    def public(self):
        answer = self.answer
        if self.control == DATE:
            saved = dict(self.saved_date) if self.saved_date is not None else None
        else:
            saved = None if answer is None else {
                'value': answer.value, 'label': ANSWER_LABELS[answer.value], 'by': answer.answered_by.label(),
                'at': _iso(answer.answered_at), 'answer_id': str(answer.pk)}
        return {
            'id': self.id, 'fact': self.fact,
            'family_label': PROFILES[self.family].label if self.family in PROFILES else '',
            'prompt': self.prompt, 'control': self.control, 'choices': list(self.choices), 'allow': list(self.allow),
            'document_value': self.document_value, 'entered_value': self.entered_value, 'quote': self.quote,
            'affects': list(self.codes), 'saved': saved, 'addendum_allowed': self.addendum_allowed,
            'missing': self.missing, 'statement': self.statement, 'passages': [dict(item) for item in self.passages],
        }


def standing_answers(revision_id):
    """The revision's answers that stand (none withdrawn), oldest first."""
    return list(models.MemberAnswer.objects.filter(revision_id=revision_id, revocation__isnull=True)
                .select_related('answered_by').order_by('answered_at', 'pk'))


def saved_answers(assessment) -> list[dict]:
    """[{code, family, fact, value, answer_id, by, at, question}]: the standing member answers of ``assessment``'s
    revision, oldest first: a later answer to the same detail withdraws the earlier one. Each is applied only to the
    question it answered (``question``, its fingerprint; review.answer_states): by the assessment that read it as an
    input, or by the review overlay until that assessment is made; one no question asked now takes is an earlier
    answer (earlier_answers)."""
    if assessment is None:
        return []
    return [{'code': answer.code, 'family': answer.family, 'fact': answer.fact, 'value': answer.value,
             'answer_id': str(answer.pk), 'by': answer.answered_by.label(), 'at': _iso(answer.answered_at),
             'question': answer.question}
            for answer in standing_answers(assessment.revision_id)]


def effective_view(assessment):
    """The review overlay's view of ``assessment`` (review.effective_view, DESIGN section 4) when the review layer has
    one; None until it does, and then the stored questions are read as they are."""
    view_of = getattr(review, 'effective_view', None)
    return view_of(assessment) if callable(view_of) and assessment is not None else None


def _questions(encounter, assessment, view, states=((), (), ())):
    """(scope, fact, family, code, position) of every open question of ``assessment`` - the stored ones, or with the
    overlay's ``view`` the proposals' questions it holds (plus any stored one an answer the overlay applies answers, so
    the member can see and withdraw it) - and every question the assessment closed with a member's answer it read, so
    the member sees that answer in effect and can withdraw it; when ``assessment`` is the live one on the current
    context; none otherwise.

    ``view``: review.effective_view's {proposal key: review_view.View}, whose ``questions`` are the dicts the overlay
    builds ({id, scope, family, fact, question, reason}; review_view._question). Only a view in the effective set asks
    (``active``): a rejected code's stored question decides nothing, as readiness reads it (review._assessment_blockers),
    and it is asked again once a revocation brings the code back. ``states``: review.answer_states(assessment) - the
    answers the assessment read, those the overlay applies, and the earlier ones (which ask nothing)."""
    if assessment is None or assessment.pk != getattr(review.live_assessment(encounter), 'pk', None) \
            or assessment.context_id != encounter.current_context_id:
        return []
    applied, bound = list(states[0]), list(states[1])
    out = []
    stored = assessment.clarifications.filter(state=models.Clarification.OPEN).select_related('proposal')
    for item in stored.order_by('created_at', 'pk'):
        proposal = item.proposal
        if proposal is not None:
            out.append(('proposal', item.fact, item.family or proposal.family, proposal.code, (2, proposal.position)))
        else:
            out.append((item.scope, item.fact, item.family, '', (0 if item.scope == 'encounter' else 1, 0)))
    # completion repair (2026-11-06, U11): a question the assessment closed with a member's answer it read
    read = {answer.pk for answer in applied}
    # refutation cycle 3 (answers C3-3): and a closed question a standing answer now supersedes (bound to it by
    # review._closed_pairs) keeps its row - the member's saved answer is shown on it, never on no surface at all
    superseding = {(answer.fact, answer.family, answer.code) for answer in bound}
    closed = []
    for item in (assessment.clarifications.filter(state=models.Clarification.ANSWERED, answer__isnull=False)
                 .select_related('proposal').order_by('created_at', 'pk')):
        proposal = item.proposal
        key = (item.fact, item.family or (proposal.family if proposal is not None else ''),
               proposal.code if proposal is not None else '')
        if item.answer_id not in read and key not in superseding:
            continue
        if proposal is not None:
            closed.append(('proposal', item.fact, item.family or proposal.family, proposal.code,
                           (2, proposal.position)))
        else:
            closed.append((item.scope, item.fact, item.family, '', (0 if item.scope == 'encounter' else 1, 0)))
    if view is None:
        return out + closed
    proposals = {proposal.key: proposal for proposal in assessment.proposals.all()}
    answered = {(answer.fact, answer.family, answer.code) for answer in bound}
    held = [entry for entry in out if entry[0] != 'proposal']
    held += [entry for entry in out if entry[0] == 'proposal' and entry[1:4] in answered]
    for key, item in view.items():
        proposal = proposals.get(key)
        if proposal is None or not getattr(item, 'active', True):
            continue
        for spec in getattr(item, 'questions', ()) or ():
            fact, family = spec.get('fact') or '', spec.get('family') or ''
            held.append(('proposal', fact, family or proposal.family, proposal.code, (2, proposal.position)))
    # A code an answer the overlay applies excluded (review.DETAIL_UNAVAILABLE) holds no open question in its view - the
    # answer closed it - and the question may be the overlay's own, with no stored row: its answered rows stay, so the
    # member still sees the answer in effect and can withdraw it.
    excluded = {proposal.code: proposal for key, proposal in proposals.items()
                if getattr(view.get(key), 'reason', '') == review.DETAIL_UNAVAILABLE}
    for answer in bound:
        proposal = excluded.get(answer.code) if answer.code else None
        if proposal is not None:
            held.append(('proposal', answer.fact, answer.family or proposal.family, answer.code,
                         (2, proposal.position)))
    return held + closed


def _row_key(fact, family, code):
    """The row a question is asked in: the date of service once for the document; a service fact once for its service
    (refutation r2, L7-08), whichever of its codes asks it; any other question once for its code."""
    if fact == DATE_FACT:
        return (DATE_FACT, '', '')
    if code and fact in SERVICE_FACTS:
        return (fact, family, '')
    return (fact, family, code)


def _states(encounter, assessment):
    """review.answer_states of the live assessment (([], [], []) for any other, or none)."""
    if assessment is None or assessment.pk != getattr(review.live_assessment(encounter), 'pk', None):
        return [], [], []
    return review.answer_states(assessment)


def _passages_of(assessment, members, by_code) -> list:
    """The passages the questions ``members`` ((fact, family, code) each) concern, as their row shows them: each
    code's (questions.passages of its proposals: its matched acts' passages, its own, CPT Studio's located ones), a
    documented service's (questions.service_passages), in member order, each once, at most MAX_ROW_PASSAGES, exact
    slices of the revision's text with their page. ``by_code``: the assessment's proposals by code, in stored order."""
    if assessment is None:
        return []
    revision = assessment.revision
    text, pages = revision.text, revision.pages
    acts = questions.acts_of(assessment.services)
    found = []
    for fact, family, code in members:
        if code:
            for proposal in by_code.get(code, ()):
                found += questions.question_passages(assessment.services, family, fact, proposal.evidence,
                                                     proposal.support, text, acts)
        else:
            found += questions.service_passages(assessment.services, family, fact, text)
    out, seen = [], []
    for start, end, quoted in found:
        if len(out) >= MAX_ROW_PASSAGES:
            break
        if any(start < b and a < end for a, b in seen):
            continue  # it overlaps a passage the row shows already (another code's question's)
        seen.append((start, end))
        out.append({'text': quoted, 'start': start, 'end': end, 'page': review._page_of(pages, start)})
    return out


def _rows(encounter, assessment, view=None, states=None):
    context = _context_of(encounter)
    states = _states(encounter, assessment) if states is None else states
    # the answers that stand for a question asked now: those the assessment read, and those the overlay applies until
    # the recompute that reads them has run (review.answer_states); an earlier answer stands for none (earlier_answers)
    answers = list(states[0]) + list(states[1])
    by_key = {(answer.fact, answer.family, answer.code): answer for answer in answers}
    rows: dict = {}
    hold = context is not None and gi_context.is_member_conflict((context.facts or {}).get(DATE_FACT))
    selected = [proposal.code for proposal in assessment.proposals.filter(bucket=models.Proposal.SELECTED)] \
        if assessment is not None else []
    if hold or _date_in_use(context):  # the date of service, which every selected code depends on
        rows[(DATE_FACT, '', '')] = _Row(DATE_FACT, '', '', 'encounter', (0, -1), codes=list(selected))
    for scope, fact, family, code, position in _questions(encounter, assessment, view, states):
        if hold and fact != DATE_FACT:
            # While a member's date conflicts with the document nothing is sent: the date is the one detail asked.
            # Every other question belongs to a reading made without a settled date, and the assessment that follows
            # the member's choice asks again what it still needs (an answer saved before stays bound to its detail).
            continue
        key = _row_key(fact, family, code)
        row = rows.get(key)
        if row is None:
            row = rows[key] = _Row(key[0], key[1], key[2], 'encounter' if fact == DATE_FACT else scope, position)
        elif position < row.position:
            row.position = position
        if fact == DATE_FACT:
            row.codes = list(dict.fromkeys(row.codes + selected))
            continue
        if (fact, family, code) not in row.members:
            row.members.append((fact, family, code))
        if code and code not in row.codes:
            row.codes.append(code)
    values = dict((context.user_values if context is not None else encounter.user_values) or {})
    by_code: dict = {}
    for proposal in (assessment.proposals.order_by('position') if assessment is not None else ()):
        by_code.setdefault(proposal.code, []).append(proposal)
    out = []
    for row in sorted(rows.values(), key=lambda item: item.position):
        row.answers = {member: by_key.get(member) for member in row.members}
        if row.control == DATE:
            _date_row(row, encounter, context)
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
            row.missing = questions.missing(row.fact)
        else:
            # codes competing for one act are settled by rejecting one (P-ADMIT2): no detail answer fits the question
            row.allow = [] if row.scope == 'encounter' or row.fact == COMPETING_FACT \
                else [NOT_DOCUMENTED, CANNOT_CONFIRM]
            subject = row.fact.split(':', 1)[1] if row.fact.startswith('conflict:') else ''
            row.prompt = CONFLICT_PROMPT.format(act=act_label(subject)) if subject else PROMPTS.get(row.fact,
                                                                                                   DEFAULT_PROMPT)
            # completion repair (2026-11-06, U10): the question shows the passages it concerns and names the fact
            # CPT Studio could not confirm - never that the document leaves it out (the new path's facts in their own
            # words: interpretation.wording.MISSING)
            row.missing = (EVENT_FACTS_MISSING.get(row.fact)
                           or questions.missing(row.fact, act_label(subject) if subject else ''))
            row.statement = (CONFLICT_STATEMENT.format(act=act_label(subject)) if subject
                             else COMPETING_STATEMENT if row.fact == COMPETING_FACT
                             else CODING_STATEMENTS.get(row.fact) or STATEMENT.format(missing=row.missing))
            row.passages = _passages_of(assessment, row.members, by_code)
        out.append(row)
    return out


def _date_row(row, encounter, context):
    """The date row: the document's date and the member's side by side, and the ways the server takes.

    - A member's date that conflicts with the document (the hold): "Use document date" where the document gives one
      date of its own; the document's own dates as choices where it states more than one (or where its closing charge
      block's question takes one); otherwise the document's own wording of its date and the removal of the entered date
      - with the physician's addendum where the document has date text but no date of service this service reads, so
      that no member date can be shown to agree with it (interpretation 35: "an addendum settles it"; refutation r2,
      L7-03: no way out had been offered).
    - A member's date in effect where the document gives no single date of its own: the member's saved answer, with
      who entered it and when, which the row corrects or removes (L7-05) - unless it was typed outside the panel and
      chose one of the document's own dates, when it is asked again with them in view (L7-02).
    - Otherwise the date asked: the document's own dates as choices where it states more than one; else its wording
      of the date, if any, with the physician's addendum where that date text is not one this service reads.

    Never a date the document does not state as its own offered as the document's, and never prefilled."""
    block = service_date_block(encounter)
    fact = ((context.facts or {}).get(DATE_FACT) if context is not None else None) or {}
    document = _document_date(context) or {}
    single = bool(document.get('single'))
    stated = [] if single else [value for value in document.get('values') or [] if _iso_date(value)]
    documented = [{'value': value, 'label': STATED_IN_DOCUMENT.format(value=_date_label(value))} for value in stated]
    clear = {'value': CLEAR, 'label': CLEAR_LABEL}
    # The document has date text of its own, recorded with this context, but no date of service this service takes as
    # an answer: another occasion's date, a date it cannot read.
    unusable = (context is not None and context.document_date is not None and not single and not stated
                and bool(document.get('evidence')))
    entered = block['entered_value']
    row.document_value, row.quote, row.entered_value, row.allow = (block['document_value'], block['document_quote'],
                                                                   entered, [])
    if gi_context.is_member_conflict(fact):
        if block['can_use_document_date']:
            row.choices, row.prompt = [{'value': USE_DOCUMENT, 'label': USE_DOCUMENT_LABELS[DATE]}], \
                DATE_PROMPTS['member']
        elif documented:
            row.choices, row.prompt = documented, DATE_PROMPTS['third' if len(stated) > 1 else 'member']
        else:
            row.choices, row.addendum = [clear], unusable
            row.quote = row.quote or _date_passage(context, document)
            row.prompt = DATE_PROMPTS['unconfirmed' if unusable else 'disagree']
        return
    if _date_in_use(context):
        entry = _date_entry(encounter, entered)
        if len(stated) > 1 and entered in stated and not entry['confirmed']:
            row.choices, row.prompt, row.confirm = documented, DATE_PROMPTS['confirm'], True
            return
        row.choices = documented + [clear]
        row.prompt = DATE_PROMPTS['chosen' if len(stated) > 1 else 'entered']
        if not documented:
            row.quote = row.quote or _date_passage(context, document)
        row.saved_date = {'value': entered, 'label': _date_label(entered), 'by': entry['by'], 'at': entry['at'],
                          'answer_id': ''}
        return
    if documented:
        row.choices = documented
        row.prompt = DATE_PROMPTS['document' if len(stated) > 1 else 'asked']
        return
    row.prompt = DATE_PROMPTS['asked']
    row.quote = row.quote or _date_passage(context, document)
    row.addendum = unusable


def addendum_detail(encounter, detail):
    """(found, clarification) for an addendum sent from details row ``detail``: ``found`` when it is an open row that a
    physician may answer with documentation (details_needed's ``addendum_allowed``: a confirmation row, or the date row
    where documentation is what settles the date), and the stored open clarification that row shows, if it shows one -
    None for a question only the review overlay asks, or the date held before anything was asked, which the reading
    that follows the addendum answers or asks again."""
    assessment = review.live_assessment(encounter)
    view = review.effective_view(assessment) if assessment is not None else None
    for row in _rows(encounter, assessment, view):
        if row.id != detail or not row.addendum_allowed:
            continue
        if assessment is None:
            return True, None
        keys = set(row.members) or {(row.fact, row.family, row.code)}
        stored = assessment.clarifications.filter(state=models.Clarification.OPEN).select_related('proposal')
        for item in stored.order_by('created_at', 'pk'):
            proposal = item.proposal
            key = ((item.fact, item.family or proposal.family, proposal.code) if proposal is not None
                   else (item.fact, item.family, ''))
            if key in keys:
                return True, item
        return True, None
    return False, None


def date_confirmation_open(encounter) -> bool:
    """Whether the date row asks the member to confirm a date entered outside the details panel that chose one of the
    document's own conflicting dates (refutation r2, L7-02): for a reader that holds the approved export until the member
    has settled it with those dates in view. Reads the context only (no assessment), as the date row does."""
    return any(row.confirm for row in _rows(encounter, None) if row.control == DATE)


def details_needed(encounter, assessment, view=None) -> list[dict]:
    """DESIGN section 7 ``details_needed``: one row per open material question of the live assessment on the current
    context - a service fact's once for its service, any other once for its code - and the date of service at once
    while a member's date conflicts with the document, before any assessment (or stands as the member's own saved date
    where the document gives no single date of its own); dates first, then the document's, the services' and the codes'
    questions."""
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
        given = '' if value in (USE_DOCUMENT, CLEAR) else (_iso_date(value) or value) if fact == DATE_FACT else value
        return current == given
    return any(answer.fact == fact and answer.value == value for answer in answers)


ANSWER_GATE = 'answers.save_details'  # the sentinel write gates of a member answer on a new-path revision (FINAL 10.3)
REVOKE_GATE = 'answers.revoke_answer'


def _new_path(encounter) -> bool:
    """Whether ``encounter``'s current revision is read on the new path (its current assessment the events engine's, or
    its context derived from an event inventory): a member answer saved or withdrawn there is a gated write."""
    return readers.label_of(encounter) == sentinel.NEW_PATH


def save_details(encounter, user, items) -> dict:
    """_save_details (below), and the Gemini migration's write gate (design/FINAL.md 10.3): on a new-path revision the
    save runs in a new_path sentinel scope of its own, asked again as the last thing before its transaction commits -
    when it counted an execution of the legacy reader, or this process cannot vouch for its count, nothing of it is
    written, the trip is audited ('sentinel.tripped') and sentinel.Tripped is raised. A context save this save makes
    and that its own gate refuses (jobs.change_context) rolled its audit row back with this save's work, so the row
    is recorded again here, after the rollback (jobs.Refused.trip). The scope is opened from ``encounter`` as the request
    read it and decided again from the locked row, first: when a reading that finished in between moved the row to the
    other path, nothing is saved (jobs.Refused, readers.MOVED: 409). A legacy revision's save is made exactly as before."""
    parsed = _parse(items)
    with readers.write_scope(ANSWER_GATE, _new_path(encounter)) as gate:
        try:
            return _save_details(encounter, user, parsed, gate)
        except readers.GateClosed as closed:
            readers.refuse(ANSWER_GATE, closed, encounter=encounter, actor=user)
        except jobs.Refused as exc:
            readers.record_trip(encounter, user, getattr(exc, 'trip', None))
            raise


def _save_details(encounter, user, parsed, gate) -> dict:
    """Save a member's answers to the details asked, in one transaction under the encounter's row lock: every answer
    is checked against the detail's own control before anything is written (InvalidAnswer: 400), the whole save is
    refused while processing runs or when a detail is no longer asked (jobs.Refused: 409). Context values are ONE
    jobs.change_context call; 'not_documented' / 'cannot_confirm' are MemberAnswer rows, one for each question the row
    answers, each bound to that question as it is asked now (its fingerprint; a later answer withdraws the earlier one),
    and - with no context change, whose re-assessment reads them - ONE recompute of the assessment
    (jobs.recompute_after_answers: nothing sent). A date typed outside the panel that the member confirms with the
    document's own dates in view is recorded as confirmed (a detail.answered row; nothing is re-assessed or sent). An
    answer already in effect is left as it is, so a repeated identical save makes nothing. Every save ends by
    re-deriving the stored list state (review.refresh_state), after its last row is written."""
    with transaction.atomic():
        encounter = jobs._locked(encounter)
        if jobs.busy(encounter):
            raise jobs.Refused(BUSY)
        if readers.moved(gate, _new_path(encounter)):
            # the gate decided from the LOCKED row (review finding 3): a reading that finished since the request read
            # the encounter moved it to the other path; nothing is read or written under a scope that does not fit it
            raise jobs.Refused(readers.MOVED)
        assessment = review.live_assessment(encounter)
        states = _states(encounter, assessment)
        rows = {row.id: row for row in _rows(encounter, assessment, effective_view(assessment), states)}
        # the question each member of a row is asked now (review.asked_fingerprints), which its answer binds to; one a
        # standing answer the assessment read answers is that answer's question (its row shows it, closed)
        asked = review.asked_fingerprints(assessment) if assessment is not None else {}
        # refutation cycle 3 (answers C3-4): a question the assessment closed with an answer it read is asked as the
        # engine recorded it (completeness member_answers 'asked'), so a new answer to that row is bound to it, never
        # recorded in the earlier, key-only form
        if assessment is not None:
            for entry in ((assessment.completeness or {}).get('member_answers') or {}).get('applied') or ():
                if entry.get('asked'):
                    asked.setdefault(questions.member_key(entry.get('code') or '', entry.get('family') or '',
                                                          entry.get('fact') or ''), entry['asked'])
        answers = standing_answers(encounter.current_revision_id) if encounter.current_revision_id else []
        values, recorded, superseded, unchanged, confirming = {}, [], [], 0, None
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
                    # refutation round 1 of harness repair 3 (L4-6): the competing question offers no answer at all
                    raise InvalidAnswer(CLINICAL if row.control == CONFIRM and row.fact != COMPETING_FACT
                                        else NOT_OFFERED)
                if row.answer is not None and row.answer.value == value:
                    unchanged += 1
                    continue
                recorded.append((row, value))
                continue
            if row.control == CONFIRM:
                raise InvalidAnswer(CLINICAL)
            if value in (USE_DOCUMENT, CLEAR):
                if value not in offered:
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
            if row.confirm and given in offered:
                confirming = row  # one of the document's own dates, chosen with them in view
            # a value given for a detail said not to be documented replaces that answer, for each of the row's codes
            superseded.extend(answer for answer in row.answers.values() if answer is not None)
        current = dict(encounter.user_values or {})
        changed = {name: value for name, value in values.items() if (current.get(name) or '') != value}
        if DATE_FACT in changed:
            confirming = None  # chosen anew: the context change records the choice
        unchanged += len(values) - len(changed) - (1 if confirming is not None else 0)
        revision = str(encounter.current_revision_id)
        saved_ids = []
        for row, value in recorded:
            for member in row.members:
                standing = row.answers.get(member)
                if standing is not None and standing.value == value:
                    continue  # already this answer for this code
                if standing is not None:
                    models.MemberAnswerRevocation.objects.create(answer=standing, revoked_by=user,
                                                                 reason=models.MemberAnswerRevocation.SUPERSEDED)
                fact, family, code = member
                question = asked.get(questions.member_key(code, family, fact)) or (
                    standing.question if standing is not None else '')
                answer = models.MemberAnswer.objects.create(
                    encounter=encounter, revision=encounter.current_revision, assessment=assessment, fact=fact,
                    family=family, code=code, value=value, answered_by=user, question=question)
                saved_ids.append(str(answer.pk))
                audit.record(encounter.workspace, 'detail.answered', encounter=encounter, actor=user, fact=fact,
                             family=family, code=code, value=value, answer=str(answer.pk))
        for answer in superseded:
            models.MemberAnswerRevocation.objects.create(answer=answer, revoked_by=user,
                                                         reason=models.MemberAnswerRevocation.SUPERSEDED)
        if changed:
            context = jobs.change_context(encounter, user, changed)
            for name in sorted(changed):
                row = next(item for item in rows.values() if item.fact == name)
                dated = {'revision': revision, 'value': changed[name]} if name == DATE_FACT else {}
                audit.record(encounter.workspace, 'detail.answered', encounter=encounter, actor=user, fact=name,
                             family=row.family, code=row.code, kind='context', context=str(context.pk), **dated)
        if confirming is not None:
            audit.record(encounter.workspace, 'detail.answered', encounter=encounter, actor=user, fact=DATE_FACT,
                         family='', code='', kind='context', confirmed=True, context=str(encounter.current_context_id),
                         revision=revision, value=values[DATE_FACT])
        # Completion repair (2026-11-06, U11): an answer recomputes the assessment - one AGAIN assess of the recorded runs
        # with the answers as an input (jobs.recompute_after_answers; nothing sent). A context change's own
        # re-assessment reads the answers already, so it queues none of its own.
        recompute = None
        if saved_ids and not changed:
            recompute = jobs.recompute_after_answers(encounter, user)
            if recompute is not None:
                audit.record(encounter.workspace, 'assessment.recompute_queued', encounter=encounter, actor=user,
                             job=str(recompute.pk), answers=saved_ids)
        # The list state follows every save, derived once the save's last row is written: the answers the overlay
        # reads, the confirmation readiness reads (review.DATE_CONFIRMATION_BLOCKER) and a context change's
        # re-assessment (refutation round 3, B-01 and C-R3-1: a save that only confirmed the date never refreshed it, and
        # one that also recorded an answer refreshed it before the confirmation was written, so a finished review read
        # "Ready for review" and stayed on the review queue).
        review.refresh_state(encounter)
        readers.check(gate)  # the last thing before the commit (FINAL 10.3): a refusal rolls the save back whole
    withdrawn = [answer for answer in superseded if answer.fact not in changed]  # counted once with its value
    return {'saved': len(recorded) + len(changed) + len(withdrawn) + (1 if confirming is not None else 0),
            'unchanged': unchanged, 'answer_ids': saved_ids, 'reassessing': bool(changed) or recompute is not None}


def _siblings(encounter, answer):
    """The other standing answers of the row ``answer`` answers: one question asked once for a service, whose answer
    stands for each of its codes (refutation r2, L7-08) - withdrawn together, so the question is asked again for all."""
    if answer.revision_id != encounter.current_revision_id:
        return []
    assessment = review.live_assessment(encounter)
    key = (answer.fact, answer.family, answer.code)
    for row in _rows(encounter, assessment, effective_view(assessment)):
        # only the row whose answer it is: an earlier answer (no question asked now takes it) withdraws alone, never
        # the answers that stand for the question as it is asked now
        if key in row.members and row.answers.get(key) is not None and row.answers[key].pk == answer.pk:
            return [item for item in row.answers.values() if item is not None and item.pk != answer.pk]
    return []


def revoke_answer(encounter, user, answer_id):
    """_revoke_answer (below), gated on a new-path revision as save_details is (design/FINAL.md 10.3)."""
    with readers.write_scope(REVOKE_GATE, _new_path(encounter)) as gate:
        try:
            return _revoke_answer(encounter, user, answer_id, gate)
        except readers.GateClosed as closed:
            readers.refuse(REVOKE_GATE, closed, encounter=encounter, actor=user)


def _revoke_answer(encounter, user, answer_id, gate):
    """Withdraw one standing answer (a MemberAnswerRevocation, 'withdrawn') - and the same question's answer for the
    row's other codes: the detail is asked again. Refused while processing runs and for an answer already withdrawn
    (jobs.Refused: 409); MemberAnswer.DoesNotExist for an answer that is not this document's (404). Returns the
    revocation of ``answer_id``."""
    with transaction.atomic():
        encounter = jobs._locked(encounter)
        if jobs.busy(encounter):
            raise jobs.Refused(BUSY)
        if readers.moved(gate, _new_path(encounter)):  # the gate decided from the LOCKED row (review finding 3)
            raise jobs.Refused(readers.MOVED)
        answer = models.MemberAnswer.objects.select_for_update().get(pk=answer_id, encounter=encounter)
        if models.MemberAnswerRevocation.objects.filter(answer=answer).exists():
            raise jobs.Refused(ALREADY_WITHDRAWN)
        revocations = []
        for item in [answer] + _siblings(encounter, answer):
            revocations.append(models.MemberAnswerRevocation.objects.create(
                answer=item, revoked_by=user, reason=models.MemberAnswerRevocation.WITHDRAWN))
            audit.record(encounter.workspace, 'detail.revoked', encounter=encounter, actor=user, fact=item.fact,
                         family=item.family, code=item.code, answer=str(item.pk))
        # completion repair (2026-11-06, U11): the withdrawal recomputes the assessment, as the answer did
        if answer.revision_id == encounter.current_revision_id:
            recompute = jobs.recompute_after_answers(encounter, user)
            if recompute is not None:
                audit.record(encounter.workspace, 'assessment.recompute_queued', encounter=encounter, actor=user,
                             job=str(recompute.pk), withdrawn=[str(item.answer_id) for item in revocations])
        review.refresh_state(encounter)
        readers.check(gate)  # the last thing before the commit (FINAL 10.3)
    return revocations[0]


def earlier_answers(encounter, assessment) -> list[dict]:
    """The standing answers of the current revision that no question the live assessment asks now takes (completion
    repair 2026-11-06, U11): answered to a question no longer asked, or asked differently. Kept, never applied, each
    listed with who gave it, when, the code it was given for and why it is not applied (EARLIER_WHY), and withdrawable.
    Every sentence is from the fixed tables above."""
    out = []
    for answer, why in _states(encounter, assessment)[2]:
        subject = answer.fact.split(':', 1)[1] if answer.fact.startswith('conflict:') else ''
        out.append({
            'answer_id': str(answer.pk), 'fact': answer.fact,
            'family_label': PROFILES[answer.family].label if answer.family in PROFILES else '',
            'prompt': (CONFLICT_PROMPT.format(act=act_label(subject)) if subject
                       else PROMPTS.get(answer.fact, DEFAULT_PROMPT)),
            'affects': [answer.code] if answer.code else [],
            'value': answer.value, 'label': ANSWER_LABELS.get(answer.value, ''),
            'by': answer.answered_by.label(), 'at': _iso(answer.answered_at),
            'why': why, 'why_text': EARLIER_WHY.get(why, EARLIER_WHY['not_applied'])})
    return out
