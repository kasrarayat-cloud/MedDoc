"""The events engine's entry (design/FINAL.md 7.1, 7.2 R6-R9, 7.8-7.11; DECISIONS D3, D5, D10, D19, D21):
``assess(...) -> types.AssessmentResult``, the same shape persist_assessment writes today, with engine_version
``cpt-studio-events@1``. Pure apart from the reference lookup it is given; it runs in bounded.run_bounded.

What it reads. Every clinical fact comes from the event inventory (``inventory``: a store.StoredInventory, a
normalize.Inventory, or a mapping of its content). The revision ``text`` is read for integrity only: the exact evidence
of the proposers' spans (checks.exact_evidence), the participants' quotes, and the member answers' passages. ``context``
is the gemini-context@1 facts (facts.derive: the date of service, and setting, billing context and patient status from
member values only, D3).

What it does, per proposed code (events.evaluate for R1-R5, then here):
- R6 the profile's required facts, as FactStates built from the inventory - extent (the verified reach of the session's
  current examination), target (EUS), cannulation (ERCP), em_basis (the visit event's basis) - and setting and patient
  status from the context; worded by checks.required_facts_check and checks.fact_clarifications; and (DECISIONS D28) the
  EUS examination class of a code the catalogue gives one (CodeProfile.exam): its required facts gain the extent - the
  same verified reach of its session's examination - and a reach that does not fit the class (a full examination needs
  it at or beyond the duodenum, mapping.FULL_REACH; a limited one short of it, mapping.SHORT_OF_DUODENUM) holds the
  code with the extent question in another_technique's form (facts.examination_class); never an exclusion, never READY;
- R7 the date of service (checks.service_date_state over the gemini context; PROPOSAL_DATE_CHECK and the encounter's
  question);
- R8 the combination holds (combination.py): base, base-within, competing, the same-day E/M by date of service (C-3);
- R9 the reference checks (PFS, MUE, the endoscopic family), recorded and never making a code ready; a failed MUE is
  shown and does not hold.
Status: ``excluded`` when R1 or 7.5 decides (or a member's answer); ``needs_clarification`` when any hold or question
stands or the date is unknown; otherwise ``ready``. READY is never approval (P5): no input to the readiness rule names a
proposer, and a Decision is still required.

Participants (P-ADMIT, FINAL 7.10): a code a participant's frozen FIRST reading proposes, in scope, quoted verbatim with
an exact span, that no decidable proposal carries, is evaluated by exactly the per-code rule from that participant's
spans (origin 'participant'); a code a decidable proposal carries adds the participant to support.proposed_by and
nothing else (I3); a code proposed only in peer review stays an alternative. The second review (FINAL 7.10, D10): a code
it selected becomes a proposal (origin 'second_review') only when its E* intersects the events of the marked
no_proposal and not_covered items; otherwise it is listed with why. Member answers (7.10): bound through questions.bind
to the questions these inputs ask with no answer; "Not documented" or "Cannot confirm" excludes exactly the code it
answers, by the first open question of that code a member answered (review_view's one rule, ported without it).

What it writes (FINAL 7.11 and 4.3): the legacy check ids wherever the old image's overlay keys on them; the new ids
events.match, events.attributes and events.relation; Proposal.support with origin, proposed_by, state, reason,
status/supporting/unrelated/source (by offset overlap only, contract 9.3), acts, session, lesions, competes,
reinstatement_waits, summary and event_reading; the fingerprint over the engine, the code and the events the decision
read; ``services`` the empty stub and completeness['inventory_problems'] the fixed sentence, so the rollback image
reads the record fail-closed (FINAL 12); completeness['event_coding'] for the overlay.

Imports nothing from studio.gi but the reference tables and only the FINAL 7.1 names of studio.validation.checks
(sentinel.CHECKS_ALLOWLIST; R-5).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Optional

from studio.gi import catalogue
from studio.gi.profiles import PROFILES, PROFILES_VERSION, family_for_code
from studio.interpretation import ENGINE_VERSION, combination, coverage, events, facts, identity, mapping, wording
from studio.participants import LABELS as PARTICIPANT_LABELS, PARTICIPANTS as PARTICIPANT_ORDER
from studio.reference.store import PFS, applied_sources
from studio.types import (CONTEXT_FACTS, PARTICIPANT_STATES, AssessmentResult, Check, ClarificationSpec, EvidenceSpan,
                          Fact, LocatedQuote, NormalizedResponse, ParticipantInput, ParticipantReading, PeerReview,
                          ProposalAssessment, ProviderCode, sha256_json)
from studio.validation import checks, questions

PROVIDER_STATUSES = ('succeeded', 'not_run', 'failed', 'unknown')
EXTRACTION_STATUSES = ('ok', 'partial', 'failed')
PRIMARY = 'corti'
DOCUMENTED = ('document', 'user')
# FINAL 4.3: what the new path writes into the legacy services slot, and the sentence that freezes the old image's
# read-time reconciliation (engine.py:3590-3592). Both are needed (FINAL 12.2).
SERVICES_STUB = {'version': ENGINE_VERSION, 'services': [], 'conflicts': [], 'attributions': [], 'problems': []}
INVENTORY_PROBLEMS = ('This assessment was made by a later release from an event inventory; this release does not '
                      're-read it.',)
NOT_PERFORMED_HERE = 'not_performed_at_this_encounter'  # types.NOT_CODED_REASONS' first
INDEPENDENT, PEER_REVIEW = 'independent', 'peer_review'
UNLOCATED = ('none of its quotes was found verbatim in the document text, and a quote that is not found is never '
             'evidence')  # engine.UNLOCATED (copied)
PARTICIPANT_PEER_ONLY = ("it was proposed only in peer review, after the participant had seen its peers' conclusions, and "
                         "only a code a participant's first reading proposes, before any peer conclusion is shown to it, "
                         'is checked for admission')  # engine.PARTICIPANT_PEER_ONLY (copied)
SECOND_REVIEW_NAMED = 4  # engine.SECOND_REVIEW_NAMED (copied)
SAME_DAY_COVERAGE_CHECK = Check(
    'em.same_day_coverage', 'Same-day procedures outside this document', 'not_verified',
    "No same-day procedure is documented in CPT Studio's reading of this document. A procedure documented elsewhere "
    'on the date of service (another report) holds this E/M only when its code is selected here; whether one was '
    'performed, which would need a significant, separately identifiable E/M service, is not verified.',
    wording.COVERAGE_SOURCE)


# --- one selected code -----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Selection:
    """One proposed code (duplicates merged): its scope, its kept exact evidence, its family and, when it is in scope
    with exact evidence (R1), the per-code rule's evaluation."""
    code: str
    units: int
    display: str
    code_kind: str
    scope_reason: str
    evidence: tuple
    dropped: tuple
    family: str
    evaluation: Optional[events.Evaluation] = None
    origin: str = 'primary'  # 'second_review' | 'participant'
    proposers: tuple = ()  # the participants that proposed it with an exact span (admitted: its only proposers)
    lead: str = ''  # a participant's own proposal: its rationale's first sentence

    @property
    def decidable(self) -> bool:
        return self.evaluation is not None

    @property
    def excluded(self) -> bool:
        return self.evaluation is None or self.evaluation.excluded


def _listable(code) -> bool:
    return isinstance(code, str) and 0 < len(code) <= wording.MAX_LISTED_CODE


def _merge_selected(codes: Sequence[ProviderCode]) -> list:
    """engine._merge_selected (copied): selected codes grouped by code, in order of first appearance."""
    groups: dict = {}
    for item in codes:
        if item.role == 'selected':
            groups.setdefault(item.code, []).append(item)
    return list(groups.values())


def _select(group, text: str, pages, reading: events.Reading) -> _Selection:
    code = group[0].code
    code_kind, scope_reason = checks.code_scope(code)
    kept, dropped = checks.exact_evidence([span for item in group for span in item.evidence], text, pages)
    displays = dict.fromkeys(item.display for item in group if item.display)
    selection = _Selection(code=code, units=len(group), display=' | '.join(displays), code_kind=code_kind,
                           scope_reason=scope_reason, evidence=kept, dropped=dropped, family=family_for_code(code))
    return _evaluated(selection, reading)


def _evaluated(selection: _Selection, reading: events.Reading) -> _Selection:
    if selection.scope_reason or not selection.evidence:
        return selection
    return replace(selection, evaluation=events.evaluate(selection.code, selection.evidence, reading))


def _keys(selections: Sequence[_Selection]) -> list:
    """engine._keys (copied): 'sel:<n>' or 'exc:<n>', counted within its bucket in selection order."""
    counts = {'sel': 0, 'exc': 0}
    keys = []
    for selection in selections:
        prefix = 'exc' if selection.excluded else 'sel'
        keys.append(f'{prefix}:{counts[prefix]}')
        counts[prefix] += 1
    return keys


# --- the context the rules read --------------------------------------------------------------------------------------

def _context(context) -> dict:
    out = {}
    for name, value in (context or {}).items():
        out[name] = value if isinstance(value, Fact) else facts.context_of({name: value})[name]
    return out


def _documented(fact) -> bool:
    return fact is not None and fact.origin in DOCUMENTED and fact.value not in (None, '')


def _context_date(context: Mapping) -> Optional[date]:
    fact = context.get('service_date')
    if not _documented(fact):
        return None
    try:
        return date.fromisoformat(fact.value)
    except (TypeError, ValueError):
        return None


def _billing(context: Mapping) -> str:
    """engine._billing (copied): the billing context as stored, for the PC/TC consideration."""
    from studio.context_facts import is_member_conflict

    fact = context.get('billing_context')
    if fact is not None and fact.origin == 'conflict':
        return ('in conflict: member-entered encounter metadata differs from the document' if is_member_conflict(fact)
                else 'conflicting documented values')
    if fact is not None and fact.origin == 'user' and _documented(fact):
        return f'{fact.value}, entered by a workspace member as encounter metadata'
    return str(fact.value) if _documented(fact) else 'not documented'


def _relevant_context(family: str, day: Optional[date], context: Mapping, pctc: bool) -> dict:
    """engine._relevant_context (copied): the context values a decision on the proposal depends on."""
    values = {'service_date': day.isoformat() if day else None}
    names = ('setting', 'patient_status', 'billing_context') if family in wording.EM_FAMILIES else (
        ('billing_context',) if pctc else ())
    for name in names:
        fact = context.get(name)
        values[name] = fact.value if _documented(fact) else None
    return values


@dataclass(frozen=True)
class FactState:
    """checks.FactState's fields (the allowed checks.required_facts_check and fact_clarifications read only these)."""
    name: str
    fact: Optional[Fact]
    problem: str  # '' | missing | conflict
    confirmed: str = ''


def _state(name: str, fact: Optional[Fact]) -> FactState:
    if _documented(fact):
        return FactState(name, fact, '')
    return FactState(name, fact, 'conflict' if fact is not None and fact.origin == 'conflict' else 'missing')


def _span_of(record: Optional[Mapping]):
    from studio.types import Span

    return (Span(record['start'], record['end'], record['text']),) if isinstance(record, Mapping) else ()


# DECISIONS D38: a colonoscopy examines the entire colon, from the rectum to the cecum, and may include the terminal ileum
# or the small intestine proximal to an anastomosis (the CPT colonoscopy definition). A verified reach short of those
# places, with no verified statement that the examination was incomplete, does not establish the colonoscopy's extent:
# R6 asks it (FRESH-2 W1S-112 r1: a reach Gemini took from "Moderate diverticulosis in the sigmoid and descending colon."
# made 45385 READY; the registry, and the installed release, hold it). A stated incomplete examination keeps its reach.
COLONOSCOPY_FULL_REACH = frozenset({'cecum', 'appendiceal_orifice', 'ileocecal_valve', 'terminal_ileum', 'ileum',
                                    'neo_terminal_ileum', 'small_bowel'})
# DECISIONS D44 (the S17 refutation of D38): a reach to an anastomosis completes a colonoscopy only where the colon
# proximal to it is gone - the encounter's one anastomosis placed on the right colon side (D34, mapping.anastomosis_place:
# an ileocolonic or ileocolic one). A colorectal, coloanal or ileorectal one is placed in the rectum, and D38 reads a
# rectal reach as short of the cecum ("The colonoscope was advanced to the colorectal anastomosis." at 12 cm is a
# sigmoidoscopy's reach); an unplaced one (no type word, an unknown type, several) does not establish the extent either.
# Fail-closed: R6 asks the extent (an ileorectal one, arguably complete, is asked too).
COLONOSCOPY_FULL_ANASTOMOSIS = frozenset({'right_colon'})


def _full_colonoscopy_reach(value: str, reading: events.Reading) -> bool:
    """Whether a verified colonoscopy reach ``value`` is the full colonoscopy reach (D38 as D44 amends it)."""
    if value in COLONOSCOPY_FULL_REACH:
        return True
    return (value == mapping.ANASTOMOSIS
            and mapping.anastomosis_place(reading.encounter) in COLONOSCOPY_FULL_ANASTOMOSIS)


def _stated_incomplete(examination: Mapping) -> bool:
    """Whether ``examination``'s completion is verified as incomplete (the reach's completion, contract 5.4)."""
    completion = examination.get('completion')
    return events.verify.usable(completion) and completion.get('value') == 'incomplete'


def _reach(family: str, reading: events.Reading, sessions_: Mapping) -> tuple:
    """The verified reach of ``family``'s session examination (contract 9.2's extent): (its landmark, its extent record);
    ('', the record or None) when the session has no single current examination or its reach is not verified or names
    no place - or, for a colonoscopy, when it is short of the full colonoscopy reach and the examination is not stated
    to be incomplete (D38)."""
    session = sessions_.get(family)
    exam = reading.events.get(session.event) if session is not None and session.event else None
    extent = exam.get('extent') if exam is not None else None
    if exam is not None and events.verify.usable(extent) and wording.landmark_label(extent.get('value', '')):
        if (family == 'gi.colonoscopy' and not _full_colonoscopy_reach(extent['value'], reading)
                and not _stated_incomplete(exam)):
            return '', extent
        return extent['value'], extent
    return '', extent


def _inventory_fact(name: str, family: str, selection: _Selection, reading: events.Reading,
                    sessions_: Mapping) -> Optional[Fact]:
    """contract 9.2's required facts, read from the inventory's verified attributes (FINAL 7.2 R6)."""
    session = sessions_.get(family)
    if name == 'extent':
        landmark, extent = _reach(family, reading, sessions_)
        if landmark:
            return Fact('extent', wording.landmark_label(landmark), 'document', _span_of(extent.get('words')))
        return None
    if name == 'target':
        candidates = [reading.events[eid] for eid in ((session.examinations if session is not None else ())
                                                     + tuple(selection.evaluation.supporting
                                                             if selection.evaluation is not None else ()))
                      if eid in reading.events]
        for event in candidates:
            landmark = mapping.target_landmark(event)
            if landmark:
                return Fact('target', wording.landmark_label(landmark), 'document',
                            _span_of(event['target'].get('words')))
        return None
    if name == 'cannulation':
        for event in reading.events.values():
            if event.get('family') != family or event.get('catalogue_kind') != 'cannulation':
                continue
            if not (events.usable(event, 'status') and events.value(event, 'status') in events.verify.POSITIVE
                    and events.usable(event, 'time') and events.value(event, 'time') == 'current_encounter'):
                continue
            landmark = mapping.target_landmark(event)
            if landmark:
                outcome = 'cannulated' if events.value(event, 'status') == 'performed' else 'not achieved'
                return Fact('cannulation', f'{wording.landmark_label(landmark)} {outcome}', 'document',
                            _span_of(events.words_of(event, 'status', 'target')))
        return None
    if name == 'em_basis':
        supporting = selection.evaluation.supporting if selection.evaluation is not None else ()
        basis = combination.visit_basis(reading, supporting)
        if basis is not None:
            return Fact('em_basis', basis['value'].replace('_', ' '), 'document', _span_of(basis.get('words')))
        return None
    return None


def _fact_states(selection: _Selection, context: Mapping, reading: events.Reading, sessions_: Mapping) -> tuple:
    profile = PROFILES[selection.family]
    names = tuple(profile.required_facts)
    if mapping.examination_class(selection.code) and 'extent' not in names:
        names += ('extent',)  # D28: an EUS examination class is read from the session's verified reach
    states = []
    for name in names:
        if name in CONTEXT_FACTS:
            states.append(_state(name, context.get(name)))
        else:
            states.append(_state(name, _inventory_fact(name, selection.family, selection, reading, sessions_)))
    return tuple(states)


def _examination_class(selection: _Selection, reading: events.Reading, sessions_: Mapping,
                       key: str) -> Optional[tuple]:
    """D28 (FINAL 7.2 R6), as D43 widens it: (check, clarification) of a code with an EUS examination class whose
    session's verified reach - the reach the extent fact reads - does not fit it: a full examination needs the reach at
    or beyond the duodenum (mapping.FULL_REACH) and an examination not stated incomplete, a limited one a reach short of
    it (mapping.SHORT_OF_DUODENUM); a lower-tract EUS code the reach of its endoscopy (mapping.SIGMOIDOSCOPIC_REACH,
    COLONOSCOPIC_REACH, and for a stoma code STOMA_REACH with the encounter's verified stoma); a reach in no class of the
    code fits none. None when it fits, when the code has no class, or when the reach is not verified (the extent fact
    the class adds to the code's required facts is then missing, and asked). Never an exclusion."""
    exam_class = mapping.examination_class(selection.code)
    if not exam_class:
        return None
    landmark, extent = _reach(selection.family, reading, sessions_)
    if not landmark:
        return None
    session = sessions_.get(selection.family)
    exam = reading.events.get(session.event) if session is not None and session.event else None
    # D43: a full examination stated incomplete ("The examination was limited to the ampulla ...") does not fit the full
    # class, whatever its reach; a colonoscopy through a stoma needs the encounter's verified stoma
    incomplete = exam_class == mapping.FULL and exam is not None and _stated_incomplete(exam)
    no_stoma = exam_class == mapping.STOMA and not mapping.has_stoma(reading.encounter)
    if landmark in mapping.CLASS_REACH[exam_class] and not incomplete and not no_stoma:
        return None
    words = extent['words']['text'] if isinstance(extent.get('words'), Mapping) else ''
    reason, question = wording.examination_class_hold(selection.code, exam_class, wording.landmark_label(landmark),
                                                      words, incomplete=incomplete)
    return (Check(*wording.EXAMINATION_CLASS_CHECK, 'warn', reason, wording.SOURCE),
            ClarificationSpec(scope='proposal', fact='extent', question=question, reason=reason,
                              family=selection.family, proposal_key=key))


def _procedural(selection: _Selection, ref) -> bool:
    """engine._procedural (copied): a non-E/M code of a procedure profile, or with a global period other than XXX; a
    code with no PFS row counts (fail-closed)."""
    if selection.family in wording.EM_FAMILIES or selection.evaluation is None:
        return False
    if PROFILES[selection.family].procedure:
        return True
    pfs = ref.pfs if ref is not None else None
    return not pfs or pfs.get('global_days') != 'XXX'


# --- the encounter --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Encounter:
    provider: str
    context: Mapping
    day: Optional[date]
    sources: tuple
    pfs_source: object
    refs: Mapping
    active_pfs: Mapping
    day_info: combination.ProcedureDay
    global_days: str
    bases: Mapping
    within: Mapping
    competes: Mapping
    sessions: Mapping
    coding: Mapping
    if_reinstated: tuple = ()
    gated_visits: tuple = ()


def _global_days(procedures: Sequence[_Selection], refs: Mapping, pfs_source, sources, day) -> str:
    if pfs_source is None:
        return wording.global_days_note((), '', wording.unavailable_reason('CMS Physician Fee Schedule', sources, PFS,
                                                                           day))
    entries = [(s.code, refs[s.code].pfs['global_days']) for s in procedures if refs[s.code].pfs]
    unavailable = (f'the same-day procedure codes are not listed in {pfs_source.release}.' if procedures
                   else 'no same-day procedure code is selected.')
    return wording.global_days_note(entries, pfs_source.release, unavailable)


# --- the proposals --------------------------------------------------------------------------------------------------

def _fingerprint(code, family, profile_version, evidence, found, context_values, units, status, basis) -> str:
    """FINAL 7.11: the engine, the code, its family, the profiles version, the evidence texts, the checks (id, status),
    the context values, the units, the status and the events the decision read (id, verified values, anchor texts).
    Decisions carry across an AGAIN recompute over the same inventory, never across engines or interpretations (D7)."""
    return sha256_json({'engine': ENGINE_VERSION, 'code': code, 'family': family, 'profile_version': profile_version,
                        'evidence': sorted(span.text for span in evidence),
                        'checks': sorted([check.id, check.status] for check in found),
                        'context': context_values, 'units': units, 'status': status, 'events': basis})


def _spec(question: events.Question, family: str, key: str) -> ClarificationSpec:
    return ClarificationSpec(scope='proposal', fact=question.fact, question=question.question, reason=question.reason,
                             family=family, proposal_key=key)


STATUS_CHECKS = {'performed': 'pass', 'incomplete': 'pass', 'not_performed': 'fail', 'uncertain': 'warn'}


def _summary_sentence(selection: _Selection, reading: events.Reading) -> str:
    """One plain sentence of CPT Studio's reading of the documented events the code was matched to (FINAL 7.11)."""
    evaluation = selection.evaluation
    name = events.service_label(selection.family)
    what = events.group_label(evaluation.link, events.accounted(evaluation.link)) if evaluation.link.linked else name
    if evaluation.state in ('performed', 'incomplete'):
        examination = f'The {name}' + (' (an incomplete examination)' if evaluation.state == 'incomplete' else '')
        acts = [events.event_label(reading, reading.events[eid]) for eid in evaluation.supporting
                if reading.events[eid].get('catalogue_kind') not in mapping.EXAMINATION_KINDS]
        if acts:
            more = f' and {len(acts) - 3} more' if len(acts) > 3 else ''
            return f'{examination} documents {wording.join(acts[:3])}{more}.'
        return f'{examination} is documented on the date of service.'
    if evaluation.state == 'not_performed':
        return f'The document states the {what} was not done on the date of service.'
    if evaluation.reason == events.CONFLICT:
        return f'The document states the {what} both as done and as not done.'
    return f'CPT Studio could not confirm the {what} as done on the date of service.'


def _lead(selection: _Selection, provider: str) -> str:
    times = f' {selection.units} times' if selection.units > 1 else ''
    if selection.origin == 'second_review':
        return f'Selected by {provider} in a second review limited to the unresolved documented service{times}.'
    if selection.origin == 'participant':
        return selection.lead
    return f'Selected by {provider}{times}.'


def _events_check(selection: _Selection, reading: events.Reading) -> list:
    """events.match ("Documented event"), events.attributes and events.relation (FINAL 7.11)."""
    evaluation = selection.evaluation
    out = []
    if evaluation.supporting:
        listed = '; '.join(f'{events.event_label(reading, reading.events[eid])} '
                           f'({wording.quote(events.statement_text(reading, reading.events[eid]), 100)})'
                           for eid in evaluation.supporting[:4])
        out.append(Check('events.match', 'Documented event',
                         'pass' if evaluation.state == 'performed' else 'warn',
                         f'CPT Studio reads the documented event this code accounts for as: {listed}.',
                         wording.EVENTS_SOURCE))
    elif evaluation.state == 'not_performed':
        out.append(Check('events.match', 'Documented event', 'fail', evaluation.detail, wording.EVENTS_SOURCE))
    else:
        out.append(Check('events.match', 'Documented event', 'warn', evaluation.detail, wording.EVENTS_SOURCE))
    if evaluation.unverified:
        named = '; '.join(f'{name.replace("_", " ")} of the {events.event_label(reading, reading.events[eid])}'
                          for eid, name in evaluation.unverified if eid in reading.events)
        out.append(Check('events.attributes', 'Attributes the decision read', 'warn',
                         f'Not confirmed from the document: {named}. This code is held, not excluded.',
                         wording.EVENTS_SOURCE))
    if evaluation.relation is not None:
        out.append(Check('events.relation', 'Statements that decide this code', 'warn', evaluation.detail,
                         wording.EVENTS_SOURCE))
    if evaluation.exclusion is not None:
        exclusion = evaluation.exclusion  # by citation only: no statement excludes a code that does not cite it (C-7)
        out.append(Check('events.relation', 'Statements that decide this code', 'fail',
                         f'{exclusion.reason} (the statement the code cites; basis: {exclusion.basis}).',
                         wording.EVENTS_SOURCE))
    return out


def _proposal(selection: _Selection, key: str, enc: _Encounter, reading: events.Reading, extra=()) -> ProposalAssessment:
    if selection.evaluation is None:
        return _excluded_early(selection, key, enc.provider)
    evaluation = selection.evaluation
    profile = PROFILES[selection.family]
    day, ref = enc.day, enc.refs[selection.code]
    release = enc.pfs_source.release if enc.pfs_source else ''
    session_id = coverage.session_of(enc.sessions, selection.family)
    session = enc.coding['sessions'].get(session_id) if session_id else None
    label = session['label'] if session is not None else None
    excluded = selection.excluded
    shown = events.support_spans(reading, evaluation, selection.evidence)
    found = [checks.scope_check(selection.code_kind, selection.scope_reason),
             *checks.evidence_checks(selection.evidence, selection.dropped),
             Check('service.status', 'Service performed on this encounter', STATUS_CHECKS[evaluation.state],
                   evaluation.detail, wording.STATUS_SOURCE),
             *_events_check(selection, reading),
             Check('evidence.support', 'Passages show the coded act', shown['status'], shown['detail'],
                   wording.EVENTS_SOURCE)]
    clarifications, considerations = [], []
    if evaluation.state == 'incomplete':
        found.append(wording.incomplete_check(evaluation.incomplete_words))
        considerations.append(wording.incomplete_consideration(selection.code, ref.pfs, release))
    elif evaluation.attempted:
        considerations.append(wording.incomplete_consideration(selection.code, ref.pfs, release))
    states = _fact_states(selection, enc.context, reading, enc.sessions)
    exam_class = _examination_class(selection, reading, enc.sessions, key)  # D28 (R6)
    if not excluded:
        if evaluation.question is not None:
            clarifications.append(_spec(evaluation.question, selection.family, key))
        included = enc.bases.get(selection.code)
        if included:
            held, question = combination.base_hold(selection.code, selection.family, key, included, label)
            found.append(held)
            clarifications.append(question)
        within = enc.within.get(selection.code)
        if within is not None and not included:
            held, question = combination.base_within_hold(selection.code, selection.family, key, within, label)
            found.append(held)
            clarifications.append(question)
        rivals = enc.competes.get(key)
        if rivals:
            held, question = combination.competing_hold(selection.code, selection.family, key, rivals, label)
            found.append(held)
            clarifications.append(question)
    facts_check = checks.required_facts_check(profile, states) if states else None
    if facts_check:
        found.append(facts_check)
    if exam_class is not None:
        found.append(exam_class[0])
    em = selection.family in wording.EM_FAMILIES
    documented = combination.separate_statement(reading, evaluation.supporting) if em else None
    if em and not enc.day_info.procedure_day:
        found.append(SAME_DAY_COVERAGE_CHECK)
        if selection.code in enc.gated_visits:
            found.append(checks.same_day_if_reinstated_check(enc.if_reinstated))
    if not excluded:
        clarifications += checks.fact_clarifications(states, profile, selection.family, key)
        if exam_class is not None:
            clarifications.append(exam_class[1])
        if em and enc.day_info.procedure_day:
            found.append(checks.em_procedure_check(enc.day_info.labels, enc.global_days, documented,
                                                   enc.day_info.possible))
            if documented is None:
                clarifications.append(checks.separate_em_clarification(enc.day_info.labels, selection.family, key,
                                                                        enc.day_info.possible))
            considerations.append(wording.SEPARATE_EM_CONSIDERATION)
        elif em and enc.day_info.undatable:  # C-3: an undatable procedure event: UNRESOLVED(time), never READY
            event = reading.events[enc.day_info.undatable[0]]
            act = events.event_label(reading, event)
            clarifications.append(ClarificationSpec(
                scope='proposal', fact='event_time', family=selection.family, proposal_key=key,
                question=wording.time_question(act, events.statement_text(reading, event)),
                reason=(f'{wording.time_reason(act)} A procedure done on the date of service would need a significant, '
                        'separately identifiable visit beside it.')))
        review = combination.modifier_review(reading, selection.code, key, {k: v for k, v in enc.coding['codes'].items()},
                                             [(k, c) for k, c in _counted_pairs(enc)])
        if review is not None:
            considerations.append(review['text'])
    if day is None:
        found.append(wording.PROPOSAL_DATE_CHECK)
    found += [checks.pfs_check(selection.code, ref, enc.sources, day),
              checks.mue_check(selection.code, selection.units, ref, enc.sources, day)]
    if profile.procedure or (ref.pfs and ref.pfs.get('endo_base')):
        found.append(checks.endoscopic_check(selection.code, ref, enc.active_pfs, enc.sources, day))
    found += checks.NOT_CONNECTED_CHECKS
    if selection.units > 1:
        found.append(checks.duplicate_check(selection.code, selection.units))
    pctc = checks.pctc_consideration(selection.code, ref.pfs, release, _billing(enc.context))
    if pctc:
        considerations.append(pctc)
    waits = []
    if excluded:
        holds = list(checks.fact_clarifications(states, profile, selection.family, key))
        if exam_class is not None:
            holds.append(exam_class[1])
        if em and enc.day_info.procedure_day and documented is None:
            holds.append(checks.separate_em_clarification(enc.day_info.labels, selection.family, key,
                                                          enc.day_info.possible))
        found.append(checks.reinstatement_check(holds, date_unknown=day is None))
        waits = [{'fact': spec.fact, 'question': spec.question} for spec in holds]
        if day is None:
            waits.insert(0, {'fact': 'service_date', 'question': 'the date of service is not established for this '
                                                                  'encounter.'})
        if any(code == selection.code for code, _ in enc.if_reinstated):
            found.append(checks.same_day_em_check(enc.gated_visits))
    found += list(extra)
    status = 'excluded' if excluded else 'needs_clarification' if clarifications or day is None else 'ready'
    context_values = _relevant_context(selection.family, day, enc.context, bool(pctc))
    basis = events.basis_of(reading, evaluation)
    support = _support(selection, evaluation, shown, reading, session_id, waits, enc, key)
    return ProposalAssessment(
        key=key, bucket='excluded' if excluded else 'selected', code=selection.code, code_kind=selection.code_kind,
        family=selection.family, profile_version=profile.version, status=status,
        exclusion_reason=evaluation.exclusion.reason if evaluation.exclusion is not None else '',
        reinstatable=excluded, provider_display=selection.display, evidence=selection.evidence,
        rationale=wording.selected_rationale(
            lead=_lead(selection, enc.provider), evidence_count=len(selection.evidence), family=selection.family,
            state=evaluation.state, events=[events.event_label(reading, reading.events[eid])
                                            for eid in evaluation.supporting[:4]],
            facts=[(state.name, str(state.fact.value)) for state in states if not state.problem
                   and state.fact is not None and state.fact.origin == 'document'],
            entered=[(state.name, str(state.fact.value)) for state in states if not state.problem
                     and state.fact is not None and state.fact.origin == 'user']),
        checks=tuple(found), modifier_considerations=tuple(considerations), units=selection.units,
        fingerprint=_fingerprint(selection.code, selection.family, profile.version, selection.evidence, found,
                                 context_values, selection.units, status, basis),
        clarifications=tuple(clarifications), support=support)


def _counted_pairs(enc: _Encounter) -> list:
    return [(key, record['code']) for key, record in enc.coding.get('_counted', {}).items()]


def _support(selection: _Selection, evaluation: events.Evaluation, shown: dict, reading: events.Reading,
             session_id: str, waits: list, enc: _Encounter, key: str) -> dict:
    # the acts the code accounts for (E*); for a code held by a contradiction, or because every act is part of another,
    # the acts in question - as reconcile.match's conflict and act_included matches carry them (customer_api words a
    # conflict's act from them)
    shown_acts = list(evaluation.supporting)
    if not shown_acts and evaluation.reason == events.CONFLICT and evaluation.question is not None:
        shown_acts = list(evaluation.question.events[:1])
    elif not shown_acts and evaluation.reason == events.BUNDLED:
        shown_acts = [eid for eid, _ in evaluation.bundled]
    acts = [{'id': eid, 'kind': reading.events[eid].get('catalogue_kind') or '',
             'label': events.event_label(reading, reading.events[eid]),
             'status': events.value(reading.events[eid], 'status')}
            for eid in shown_acts if eid in reading.events]
    source = list(shown['source'])
    if not evaluation.supporting and evaluation.question is not None:
        source = [dict(span) for span in evaluation.question.passages]  # 7.4: the candidate's own passages
    proposers = ([PRIMARY] if selection.origin in ('primary', 'second_review') else []) + list(selection.proposers)
    support = {'origin': selection.origin, 'proposed_by': list(dict.fromkeys(proposers)), 'family': selection.family,
               'session': session_id, 'state': evaluation.state, 'reason': evaluation.reason,
               'detail': evaluation.detail, 'status': shown['status'], 'supporting': list(shown['supporting']),
               'unrelated': list(shown['unrelated']), 'detail_support': shown['detail'], 'source': source,
               'acts': acts, 'lesions': sorted({lesion for lesion in (
                   identity.verified_lesion(reading.events[eid]) for eid in evaluation.supporting) if lesion}),
               'summary': _summary_sentence(selection, reading), 'event_reading': ENGINE_VERSION}
    if evaluation.question is not None:
        support['question_events'] = list(evaluation.question.events)
    if evaluation.exclusion is not None:
        exclusion = evaluation.exclusion
        support['exclusion'] = {'event': exclusion.event, 'attribute': exclusion.attribute, 'value': exclusion.value,
                                'basis': exclusion.basis, 'cover': exclusion.cover,
                                'words': dict(exclusion.words) if exclusion.words else None}
    if waits:
        support['reinstatement_waits'] = waits
    rivals = enc.competes.get(key) if not selection.excluded else None
    if rivals:
        support['competes'] = list(rivals)
    return support


def _excluded_early(selection: _Selection, key: str, provider: str) -> ProposalAssessment:
    """engine._excluded_early (copied): out of scope, or no exact evidence - not reinstatable, only the checks that ran."""
    found = [checks.scope_check(selection.code_kind, selection.scope_reason)]
    if not selection.scope_reason:
        found += checks.evidence_checks(selection.evidence, selection.dropped)
    profile = PROFILES[selection.family]
    reason = selection.scope_reason or wording.NO_EVIDENCE
    return ProposalAssessment(
        key=key, bucket='excluded', code=selection.code, code_kind=selection.code_kind, family=selection.family,
        profile_version=profile.version, status='excluded', exclusion_reason=reason, reinstatable=False,
        provider_display=selection.display, evidence=selection.evidence,
        rationale=wording.selected_rationale(lead=_lead(selection, provider), evidence_count=len(selection.evidence),
                                             family=selection.family, state='not_performed', events=(), facts=()),
        checks=tuple(found), modifier_considerations=(), units=selection.units,
        fingerprint=_fingerprint(selection.code, selection.family, profile.version, selection.evidence, found, {},
                                 selection.units, 'excluded', []),
        support={'origin': selection.origin, 'event_reading': ENGINE_VERSION})


def _alternative(index: int, item: ProviderCode, text: str, pages, provider: str, not_added: str = '',
                 key: str = '') -> ProposalAssessment:
    """engine._alternative (copied): an informational code; ``not_added`` says why a code the bounded second review
    selected is not added as a proposal."""
    code_kind, scope_reason = checks.code_scope(item.code)
    kept, _ = checks.exact_evidence(item.evidence, text, pages)
    family = family_for_code(item.code)
    found = (checks.scope_check(code_kind, scope_reason),)
    profile_version = PROFILES[family].version
    parent = item.parent_code if item.parent_code and checks.code_scope(item.parent_code)[0] != 'invalid' else None
    unlisted_parent = bool(item.parent_code) and parent is None
    return ProposalAssessment(
        key=key or f'alt:{index}', bucket='alternative', code=item.code, code_kind=code_kind, family=family,
        profile_version=profile_version, status='informational',
        exclusion_reason=wording.alternative_note(item.role, parent, unlisted_parent=unlisted_parent,
                                                  not_added=not_added),
        reinstatable=False, provider_display=item.display, evidence=kept,
        rationale=wording.alternative_rationale(provider=provider, role=item.role, parent_code=parent,
                                                evidence_count=len(kept), unlisted_parent=unlisted_parent,
                                                not_added=not_added),
        checks=found, modifier_considerations=(), units=1,
        fingerprint=_fingerprint(item.code, family, profile_version, kept, found, {}, 1, 'informational', []))


# --- the bounded second review (FINAL 7.10, D10) ---------------------------------------------------------------------

@dataclass(frozen=True)
class _SecondMerge:
    what: str
    asked: tuple
    refused: bool
    problems: tuple
    added: tuple
    listed: tuple
    accounts_for: tuple
    unlisted: int = 0


def _asked_items(labels: Sequence[str]) -> str:
    """engine._asked_items (copied)."""
    more = len(labels) - SECOND_REVIEW_NAMED
    return '; '.join(labels[:SECOND_REVIEW_NAMED]) + (f' and {more} more' if more > 0 else '')


def _counted_of(selections: Sequence[_Selection], keys: Sequence[str]) -> list:
    return [coverage.Counted(key=key, code=s.code, family=s.family, supporting=s.evaluation.supporting,
                             read=s.evaluation.read)
            for key, s in zip(keys, selections) if not s.excluded]


def _second_review(second: NormalizedResponse, scope: Mapping, selections: list, text: str, pages,
                   reading: events.Reading, sessions_: Mapping, procedure_day: bool) -> tuple:
    """A code the second review SELECTED becomes a proposal (origin 'second_review') only when it is not excluded and
    its E* intersects the events of the marked no_proposal and not_covered items the other proposals leave; every other
    code it lists is informational, with why. Nothing is promoted and nothing is invented."""
    cov = coverage.reconcile(reading, _counted_of(selections, _keys(selections)), procedure_day=procedure_day,
                             sessions_=sessions_)
    marked = [item for item in coverage.unresolved_record(cov.unresolved) if item['second_review']]
    have = {s.code for s in selections if s.decidable}
    listable = [c for c in second.codes if _listable(c.code)]
    added, listed, accounted = [], [], []
    for group in _merge_selected(listable):
        code = group[0].code
        if code in have:
            listed.append((group[0], 'a primary proposal already carries it'))
            continue
        candidate = _select(group, text, pages, reading)
        supporting = set(candidate.evaluation.supporting) if candidate.evaluation is not None else set()
        covered = [item['label'] for item in marked if supporting & set(item['events'])]
        if covered and not candidate.excluded:
            added.append(replace(candidate, origin='second_review'))
            have.add(code)
            accounted += covered
        else:
            listed.append((group[0], _not_added_why(candidate, bool(covered), marked)))
    alternatives = [_alternative(index, item, text, pages, f'{second.provider} (second review)', not_added=why,
                                 key=f'alt2:{index}')
                    for index, (item, why) in enumerate(listed + [(c, '') for c in listable if c.role != 'selected'])]
    alternatives = [replace(a, support={'origin': 'second_review'}) for a in alternatives]
    asked = [item for item in scope.get('items', []) if isinstance(item, str) and item]
    merge = _SecondMerge(what=_asked_items(asked) or 'the unresolved documented services', asked=tuple(asked),
                         refused=bool(second.refused), problems=tuple(second.problems),
                         added=tuple(s.code for s in added), listed=tuple(item.code for item, _ in listed),
                         accounts_for=tuple(dict.fromkeys(accounted)), unlisted=len(second.codes) - len(listable))
    return list(selections) + added, alternatives, merge


def _not_added_why(candidate: _Selection, accounts: bool, items: Sequence[dict],
                   left_by: str = 'the primary proposals') -> str:
    """engine._not_added_why, over events."""
    if catalogue.code_profile(candidate.code) is None:
        return 'the coverage catalogue does not establish which documented act it accounts for'
    if candidate.evaluation is None:
        return (candidate.scope_reason or wording.NO_EVIDENCE).rstrip('.')
    if not accounts and any(item['family'] == candidate.family and item['act'] == '' for item in items):
        return ('the document states the act it accounts for both as done and as not done (both are kept; neither is '
                'chosen)' if candidate.evaluation.reason == events.CONFLICT
                else 'the act it accounts for is part of another documented act, not a separate service'
                if candidate.evaluation.reason == events.BUNDLED
                else 'CPT Studio could not find the act it accounts for documented as done in the service left '
                     'unresolved')
    if not accounts:
        return f'it accounts for no documented service or act {left_by} left unresolved'
    return 'the document reads what it accounts for as not performed on the date of service'


def _second_review_check(merge: _SecondMerge, unresolved: Sequence[dict]) -> Check:
    """engine._second_review_check (copied, over the unresolved items' labels)."""
    asked, codes = f'A second review was requested for: {merge.what}.', ', '.join(merge.listed)
    if merge.refused:
        return Check('provider.second_review', 'Second review', 'fail',
                     f'{asked} Its response was not used ({"; ".join(merge.problems)}).', wording.PROVIDER_SOURCE)
    left = {u['label'] for u in unresolved}
    still = [label for label in dict.fromkeys(merge.asked) if label in left]
    alternatives = 'an alternative' if len(merge.listed) == 1 else 'alternatives'
    limited = ('It was limited to the text that documents '
               + ('this item' if len(merge.asked) == 1 else 'these items' if merge.asked else 'them'))
    if merge.added:
        one, added = len(merge.added) == 1, ', '.join(merge.added)
        accounted = [label for label in merge.accounts_for if label not in left]
        detail = (f'{asked} {limited} and selected {added}, added as {"a proposal" if one else "proposals"} for review '
                  '(marked as from the second review).')
        if accounted:
            detail += f' {added} {"accounts" if one else "account"} for: {"; ".join(accounted)}.'
        if merge.listed:
            detail += f' It also listed {codes}, shown as {alternatives} only.'
        if still:
            detail += f' Still unresolved: {"; ".join(still)}.'
        status = 'warn' if still else 'info'
    else:
        detail = (f'{asked} {limited} and added no proposal'
                  + (f' (it listed {codes}, shown as {alternatives} only, with why '
                     f'{"it is" if len(merge.listed) == 1 else "each is"} not added)' if merge.listed else '') + '.')
        if still and set(still) == set(merge.asked):
            detail += ' The item stays unresolved.' if len(merge.asked) == 1 else ' The items stay unresolved.'
        elif still:
            detail += f' Still unresolved: {"; ".join(still)}.'
        status = 'warn'
    if merge.problems:
        detail += ' ' + wording.response_problems(merge.problems, "the second review's response")
    if merge.unlisted:
        detail += ' ' + wording.unlisted_codes(merge.unlisted, wording.MAX_LISTED_CODE, 'The second review')
    if merge.problems or merge.unlisted:
        status = 'warn'
    return Check('provider.second_review', 'Second review', status, detail, wording.PROVIDER_SOURCE)


# --- the independent participants (P-ADMIT, FINAL 7.10) -------------------------------------------------------------

def _code_shaped(value) -> bool:
    from studio.participants.peer import code_shaped  # the one rule a participant's code is read by

    return code_shaped(value)


def _well_formed(reading) -> bool:
    if not isinstance(reading, ParticipantReading) or reading.refused:
        return False
    try:
        return all(isinstance(item.code, str) and all(isinstance(quote, LocatedQuote) and all(
            isinstance(span, EvidenceSpan) for span in quote.spans) for quote in item.evidence)
                   for item in tuple(reading.codes) + tuple(reading.not_coded))
    except (AttributeError, TypeError):
        return False


def _usable_inputs(participants: Sequence[ParticipantInput]) -> tuple:
    """The configured participants' inputs as CPT Studio reads them, in stage order (engine._usable_inputs, reduced): a
    malformed or refused reading is read as refused, never raised on (I10); an input that is no ParticipantInput, or
    that names no harness participant, is the caller's contract violation and raises."""
    order = {name: index for index, name in enumerate(PARTICIPANT_ORDER)}
    given: dict = {}
    for p in participants:
        if not isinstance(p, ParticipantInput):
            raise ValueError(f'A participant input must be a ParticipantInput, not {type(p).__name__}.')
        if not isinstance(p.provider, str) or p.provider not in order:
            raise ValueError(f'Unknown participant {p.provider!r}.')
        given.setdefault(p.provider, []).append(p)
    out = []
    for name, entries in sorted(given.items(), key=lambda item: order[item[0]]):
        p = entries[0]
        if len(entries) > 1 or p.state not in PARTICIPANT_STATES or (p.state == 'read' and (
                not _well_formed(p.reading) or p.reading.provider != p.provider)):
            out.append(ParticipantInput(name, 'refused', None, 'CPT Studio could not use its input'))
            continue
        peer = p.peer if p.state == 'read' and p.peer_state == 'read' and isinstance(p.peer, PeerReview) \
            and not p.peer.refused and p.peer.provider == p.provider else None
        out.append(replace(p, peer=peer, peer_state=p.peer_state if peer is not None or p.peer_state != 'read'
                           else 'refused'))
    return tuple(out)


class _Participants:
    """The participants' codes as CPT Studio reads them (module docstring): only exact slices of the revision text are
    evidence (I7); nothing a participant wrote in its own words reaches the result."""

    def __init__(self, participants: Sequence[ParticipantInput], text: str, pages):
        self.inputs = _usable_inputs(participants)
        self.text, self.pages = text, pages
        self.first: dict = {}  # code -> participant -> its exact first-reading spans
        self.located: dict = {}  # code -> participants that located any quote for it, in any phase
        self.peer: dict = {}  # code -> participant -> its exact peer-review spans
        self.advised: dict = {}  # code -> [(participant, phase, quote)] of not-performed-here advice and disputes
        self.order: list = []
        for p in self.inputs:
            if p.state != 'read':
                continue
            for item in p.reading.codes:
                self._said(item.code, p.provider, item.evidence, self.first)
            for item in p.reading.not_coded:
                if item.reason == NOT_PERFORMED_HERE and _code_shaped(item.code):
                    self._advice(item.code, p.provider, INDEPENDENT, item.evidence)
            if p.peer is not None:
                for item in p.peer.additional_codes:
                    self._said(item.code, p.provider, item.evidence, self.peer)
                for item in p.peer.positions:
                    if item.position == 'disputes' and _code_shaped(item.code):
                        self._advice(item.code, p.provider, PEER_REVIEW, item.evidence)

    def _exact(self, quotes) -> tuple:
        spans = [span for quote in quotes for span in quote.spans]
        good, _ = checks.exact_evidence(spans, self.text, self.pages)
        return good

    def _said(self, code, name: str, quotes, into: dict) -> None:
        if not _code_shaped(code):
            return
        if code not in self.order:
            self.order.append(code)
        if any(quote.spans for quote in quotes):
            self.located.setdefault(code, []).append(name)
        good = self._exact(quotes)
        if good:
            found = into.setdefault(code, {}).setdefault(name, {})
            for span in good:
                found.setdefault((span.start, span.end), span)

    def _advice(self, code, name: str, phase: str, quotes) -> None:
        good = self._exact(quotes)
        if good:
            self.advised.setdefault(code, []).append((name, phase, good[0].text))

    def proposers(self, code: str) -> tuple:
        return tuple(name for name in PARTICIPANT_ORDER if self.first.get(code, {}).get(name)
                     or self.peer.get(code, {}).get(name))

    def merge(self, selections: list, reading: events.Reading) -> tuple:
        """(the selections with each decidable code's participants recorded and the admitted codes after them, the
        participants' alternatives 'altp:<n>')."""
        carried = {s.code for s in selections if s.decidable}
        out = [replace(s, proposers=self.proposers(s.code)) if s.decidable and self.proposers(s.code) else s
               for s in selections]
        corti_any = {s.code for s in selections}
        admitted, alternatives = [], []
        for code in self.order:
            if code in carried:
                continue
            first = [name for name in PARTICIPANT_ORDER if self.first.get(code, {}).get(name)]
            names = first or list(self.proposers(code)) or list(dict.fromkeys(self.located.get(code, ())))
            who = _participant_names(names) if names else 'an independent participant'
            code_kind, scope_reason = checks.code_scope(code)
            why = ''
            if scope_reason:
                why = scope_reason.rstrip('.')
            elif not self.located.get(code):
                why = UNLOCATED
            elif not first and self.peer.get(code):
                why = PARTICIPANT_PEER_ONLY
            elif not first:
                why = wording.NO_EVIDENCE
            if why:
                alternatives.append(self._alternative(len(alternatives), code, names, who, why))
                continue
            spans = {}
            for name in first:
                spans.update(self.first[code][name])
            kept = tuple(spans[key] for key in sorted(spans))
            lead = (f'Proposed by {who}; Corti also selected this code, with no exact passage; it is listed apart, '
                    'excluded.' if code in corti_any else f'Proposed by {who}; Corti did not propose this code.')
            selection = _Selection(code=code, units=1, display='', code_kind=code_kind, scope_reason='',
                                   evidence=checks.exact_evidence(kept, self.text, self.pages)[0], dropped=(),
                                   family=family_for_code(code), origin='participant', proposers=tuple(first),
                                   lead=lead)
            admitted.append(_evaluated(selection, reading))
        return out + admitted, tuple(alternatives)

    def _alternative(self, index: int, code: str, names, who: str, why: str) -> ProposalAssessment:
        code_kind, scope_reason = checks.code_scope(code)
        spans = {}
        for name in names:
            spans.update(self.first.get(code, {}).get(name, {}))
            spans.update(self.peer.get(code, {}).get(name, {}))
        kept = tuple(spans[key] for key in sorted(spans))
        family = family_for_code(code)
        found = (checks.scope_check(code_kind, scope_reason),)
        profile_version = PROFILES[family].version
        return ProposalAssessment(
            key=f'altp:{index}', bucket='alternative', code=code, code_kind=code_kind, family=family,
            profile_version=profile_version, status='informational',
            exclusion_reason=f'Proposed by {who}, but not added as a proposal: {why}. Candidates and alternatives '
                             'cannot be approved.',
            reinstatable=False, provider_display='', evidence=kept,
            rationale=f'Proposed by {who}; not added as a proposal: {why}. Informational only.',
            checks=found, modifier_considerations=(), units=1,
            fingerprint=_fingerprint(code, family, profile_version, kept, found, {}, 1, 'informational', []),
            support={'origin': 'participant', 'proposed_by': list(names)})

    def disagreements(self, selection: _Selection) -> tuple:
        """participants.disagree: a warn on a decidable proposal of a code a participant advised not coding as not
        performed at this encounter, or disputed in peer review, quoting the document. It never changes the status."""
        out = []
        for name, phase, quoted in self.advised.get(selection.code, ()):
            label = PARTICIPANT_LABELS.get(name, name)
            when = 'in its independent reading' if phase == INDEPENDENT else 'in peer review'
            out.append(Check('participants.disagree', 'An independent reading disagrees', 'warn',
                             f'{label} reads this service as not performed at this encounter {when} '
                             f'({wording.quote(quoted, 120)}). The status here is CPT Studio\'s own reading of the '
                             'documented events.', 'cpt-studio:participants@1'))
        return tuple(out)

    def summary_check(self, admitted: int) -> Check:
        parts = []
        for p in self.inputs:
            label = PARTICIPANT_LABELS.get(p.provider, p.provider)
            if p.state == 'read':
                proposed = sum(1 for code in self.order if p.provider in self.first.get(code, {}))
                parts.append(f'{label} (independent participant): read; {wording.plural(proposed, "code")} proposed '
                             'with an exact passage.')
            else:
                parts.append(f'{label}: not read ({p.state}).')
        parts.append(f'{wording.plural(admitted, "participant code")} admitted as a proposal of its own; agreement '
                     'adds proposers and nothing else.')
        return Check('participants.summary', 'Independent readings', 'info', ' '.join(parts),
                     'cpt-studio:participants@1')


def _participant_names(names: Sequence[str]) -> str:
    """engine._participant_names (copied)."""
    return (wording.join([PARTICIPANT_LABELS.get(name, name) for name in names])
            + (' (independent participant)' if len(names) == 1 else ' (independent participants)'))


def codes_to_look_up(normalized: Optional[NormalizedResponse], second: Optional[NormalizedResponse] = None,
                     participants: Sequence[ParticipantInput] = ()) -> tuple:
    """Every code an assessment of these inputs may look up (the assess stage prefetches them for the bounded child,
    which has no database): the proposal provider's and the second review's selected codes, and every code in a code's
    shape a usable participant reading or peer review proposes with a located quote. A superset, never a code missed."""
    found = set()
    for response in (normalized, second):
        if response is not None:
            found |= {c.code for c in response.codes if c.role == 'selected' and _listable(c.code)}
    for p in _usable_inputs(participants) if participants else ():
        entries = list(p.reading.codes) if p.state == 'read' else []
        if p.state == 'read' and p.peer is not None:
            entries += list(p.peer.additional_codes)
        found |= {item.code for item in entries if _code_shaped(item.code) and any(q.spans for q in item.evidence)}
    return tuple(sorted(found))


# --- member answers (FINAL 7.10; engine._MemberAnswers without review_view) ------------------------------------------

class _MemberAnswers:
    """The revision's standing member answers, read as an input. Each is bound to the question it was given to
    (questions.bind over the questions these inputs ask WITHOUT any answer) and read there only; "Not documented" or
    "Cannot confirm" excludes the code whose question it answers - by that code's first open question a member answered,
    review_view's one rule - and nothing else: its cross-code effects are a competition it was a rival in released or
    narrowed, and the CMS endoscopic-family check of every other code read again without it. An answer this reader
    leaves to the read-time overlay (one with no fingerprint, or to a question a review decision can open or close) is
    recorded as such. No answer confirms a clinical fact, and none approves (D7)."""

    def __init__(self, given, text: str):
        self.text = text
        answers = []
        for answer in given:
            if not isinstance(answer, questions.MemberAnswerInput):
                raise ValueError(f'A member answer must be a MemberAnswerInput, not {type(answer).__name__}.')
            if not all(isinstance(getattr(answer, name), str)
                       for name in ('code', 'family', 'fact', 'value', 'question', 'answer_id')):
                raise ValueError('A member answer names its code, family, fact, value, question and id as text.')
            answers.append(answer)
        self.answers = sorted(answers, key=lambda a: (a.answer_id, a.code, a.family, a.fact, a.value, a.question))
        self.asked: dict = {}
        self.applied: list = []
        self.closed = 0

    @staticmethod
    def engine_reads(answer) -> bool:
        return bool(answer.code and answer.question) \
            and answer.fact not in questions.KEY_BOUND_FACTS + (combination.COMPETING_FACT,)

    def _proposal_questions(self, proposals) -> dict:
        pairs = []
        for p in proposals:
            for spec in p.clarifications:
                family = spec.family or p.family
                shown = questions.question_passages(SERVICES_STUB, family, spec.fact, p.evidence, p.support, self.text,
                                                    {})
                pairs.append((questions.member_key(p.code, family, spec.fact),
                              questions.instance(spec.scope, family, spec.fact, p.code, spec.question, spec.reason,
                                                 shown)))
        return questions.group(pairs)

    def apply(self, proposals: Sequence[ProposalAssessment], enc: _Encounter) -> tuple:
        asked = self._proposal_questions(proposals)
        self.asked.update(asked)
        bound, _ = questions.bind([a for a in self.answers if self.engine_reads(a)], asked)
        answer_of: dict = {}
        for answer in bound:
            answer_of.setdefault(questions.member_key(answer.code, answer.family, answer.fact), answer)
        if not answer_of:
            return tuple(proposals)
        away = {}
        for p in proposals:
            if p.bucket != 'selected':
                continue
            for spec in p.clarifications:
                key = questions.member_key(p.code, spec.family or p.family, spec.fact)
                if key in answer_of:
                    away[p.key] = spec.fact
                    break
        if not away:
            return tuple(proposals)
        gone = {p.code for p in proposals if p.key in away}
        rows = combination.endoscopic_rows((p.code, enc.refs[p.code].pfs) for p in proposals
                                           if p.bucket == 'selected' and p.key not in away and p.code in enc.refs)
        out = []
        for p in proposals:
            if p.key in away:
                out.append(self._excluded(p, away[p.key], answer_of))
                continue
            found, specs = list(p.checks), list(p.clarifications)
            rivals = [code for code in enc.competes.get(p.key, ()) if code not in gone]
            if p.key in enc.competes and len(rivals) < len(enc.competes[p.key]):
                session = enc.coding['sessions'].get(p.support.get('session', ''))
                if rivals:
                    check, spec = combination.competing_hold(p.code, p.family, p.key, rivals,
                                                             session['label'] if session else None)
                    found = [check if c.id == combination.COMPETING_CHECK else c for c in found]
                    specs = [spec if s.fact == combination.COMPETING_FACT else s for s in specs]
                else:
                    found = [c for c in found if c.id != combination.COMPETING_CHECK]
                    specs = [s for s in specs if s.fact != combination.COMPETING_FACT]
            if p.bucket == 'selected' and p.code in enc.refs:
                found = [checks.endoscopic_check(p.code, enc.refs[p.code], rows, enc.sources, enc.day)
                         if c.id == 'pfs.endoscopic_base' and c.status != 'not_verified' else c for c in found]
            if (tuple(found), tuple(specs)) == (tuple(p.checks), tuple(p.clarifications)):
                out.append(p)
                continue
            status = p.status
            if p.bucket == 'selected':
                status = 'needs_clarification' if specs or enc.day is None else 'ready'
            # another code's checks read again without an answered code keep that code's fingerprint (engine, cycle 4)
            out.append(replace(p, checks=tuple(found), clarifications=tuple(specs), status=status,
                               support={**p.support, **({'competes': rivals} if rivals else {})}
                               if 'competes' in p.support else p.support))
        return tuple(out)

    def _excluded(self, p: ProposalAssessment, fact: str, answer_of: Mapping) -> ProposalAssessment:
        keys = [questions.member_key(p.code, spec.family or p.family, spec.fact) for spec in p.clarifications]
        mine = [spec for spec, key in zip(p.clarifications, keys) if key in answer_of]
        answered = list(dict.fromkeys(key for key in keys if key in answer_of))
        deciding = answer_of.get(questions.member_key(p.code, p.family, fact)) or answer_of[answered[0]]
        subject = deciding.fact.split(':', 1)[1] if deciding.fact.startswith('conflict:') else ''
        what = (wording.MISSING[deciding.fact] if deciding.fact in wording.MISSING
                else questions.missing(deciding.fact, wording.act_label(subject) if subject else ''))
        reason = wording.member_answer_reason(deciding.value, what)
        found = tuple(p.checks) + (Check(wording.MEMBER_ANSWER_CHECK, 'Member answer', 'fail', reason,
                                         wording.MEMBER_ANSWER_SOURCE),)
        ids = sorted({answer_of[key].answer_id for key in answered})
        for key in answered:
            self.applied.append((answer_of[key], 'proposal', p.key))
        self.closed += len(mine)
        support = {**(p.support or {}),
                   questions.ANSWERED_SUPPORT: {'fact': deciding.fact, 'value': deciding.value, 'answers': ids}}
        return replace(p, bucket='excluded', status='excluded', exclusion_reason=reason, reinstatable=False,
                       checks=found, clarifications=tuple(mine), support=support,
                       fingerprint=wording.answered_fingerprint(p.fingerprint, found, 'excluded'))

    def close_service(self, specs: Sequence[ClarificationSpec]) -> None:
        pairs = [(questions.member_key('', spec.family, spec.fact),
                  questions.instance(spec.scope, spec.family, spec.fact, '', spec.question, spec.reason,
                                     questions.service_passages(SERVICES_STUB, spec.family, spec.fact, self.text)))
                 for spec in specs if spec.scope == 'service' and not spec.proposal_key]
        asked = questions.group(pairs)
        self.asked.update(asked)
        bound, _ = questions.bind([a for a in self.answers if not a.code], asked)
        counts: dict = {}
        for key, _ in pairs:
            counts[key] = counts.get(key, 0) + 1
        done = set()
        for answer in bound:
            key = questions.member_key('', answer.family, answer.fact)
            if key in done:
                continue
            done.add(key)
            self.applied.append((answer, 'service', ''))
            self.closed += counts.get(key, 0)

    def record(self) -> dict:
        applied: dict = {}
        for answer, scope, key in self.applied:
            entry = applied.setdefault(answer.answer_id, {
                'answer': answer.answer_id, 'scope': scope, 'code': answer.code, 'family': answer.family,
                'fact': answer.fact, 'value': answer.value, 'question': answer.question, 'proposals': [],
                'asked': self.asked.get(questions.member_key(answer.code, answer.family, answer.fact), '')})
            if key and key not in entry['proposals']:
                entry['proposals'].append(key)
        rest = [answer for answer in self.answers if answer.answer_id not in applied]
        _, earlier = questions.bind(rest, self.asked)
        why = {id(answer): reason for answer, reason in earlier}
        listed = [{'answer': a.answer_id, 'code': a.code, 'family': a.family, 'fact': a.fact, 'value': a.value,
                   'why': why.get(id(a)) or (wording.NOT_APPLIED if not a.code or self.engine_reads(a)
                                             else wording.OVERLAY_READ)}
                  for a in rest if a.value in questions.UNAVAILABLE]
        return {'form': questions.FORM, 'applied': list(applied.values()), 'earlier': listed}


# --- the encounter checks ---------------------------------------------------------------------------------------------

def _inventory_check(reading: events.Reading, sessions_: Mapping, included: Mapping) -> Check:
    done = [s for s in sessions_.values() if s.done]
    others = [s for s in sessions_.values() if not s.done]
    names = ', '.join(f'{s.label} ({"incomplete" if s.incomplete else "performed"}'
                      + (f', included in {sessions_[s.part_of].label}' if s.part_of in sessions_ else '') + ')'
                      for s in done) or 'none'
    detail = f"Documented as done on this encounter, in CPT Studio's reading of the documented events: {names}."
    if others:
        detail += ' Stated but not as done today: ' + ', '.join(s.label for s in others) + '.'
    attributed = sorted({events.event_label(reading, event) for event in reading.events.values()
                         if events.verified_other_performer(event) and events.usable(event, 'status')
                         and events.value(event, 'status') == 'performed'})
    if attributed:
        detail += (' Attributed to another clinician or facility: ' + ', '.join(attributed)
                   + ' (never coded for the documenting team).')
    return Check('services.inventory', 'Documented services', 'info',
                 detail + ' The reading is advisory: an act it does not record is not covered by this check.',
                 wording.EVENTS_SOURCE)


def _unresolved_check(unresolved: Sequence[dict], not_listed: Sequence) -> Check:
    """reconcile.unresolved_check (copied, over the unresolved items)."""
    one = len(not_listed) == 1
    named = (f'{len(not_listed)} documented service{"" if one else "s"} {"has" if one else "have"} no supported '
             f'proposal and {"is" if one else "are"} not listed as unresolved: '
             + ', '.join(coverage.uncounted_label(s) for s in not_listed)
             + f'; no proposal accounts for {"it" if one else "them"}.') if not_listed else ''
    if not unresolved and named:
        return Check('services.unresolved', 'Documented services without a supported proposal', 'warn',
                     named + ' Every other documented act that the coverage catalogue reconciles has a selected '
                     'proposal, or is not separately reported under a profile rule. An act the reading does not '
                     'record is not covered by this check.', wording.SOURCE)
    if not unresolved:
        return Check('services.unresolved', 'Documented services without a supported proposal', 'pass',
                     'Every documented act that the coverage catalogue reconciles has a selected proposal, or is not '
                     'separately reported under a profile rule. An act the reading does not record is not covered by '
                     'this check.', wording.SOURCE)
    items = '; '.join(f'{u["label"]}' + (f' ({wording.quote(u["evidence"][0]["text"], 100)})' if u['evidence'] else '')
                      for u in unresolved[:6])
    more = f' and {len(unresolved) - 6} more' if len(unresolved) > 6 else ''
    return Check('services.unresolved', 'Documented services without a supported proposal', 'warn',
                 f'Unresolved: {items}{more}. No code is added for them and no alternative is promoted.'
                 + (f' {named}' if named else ''), wording.SOURCE)


def _conflicts(reading: events.Reading) -> list:
    return [relation for relation in reading.relations if relation['type'] == 'contradiction']


def _conflicts_check(reading: events.Reading, sessions_: Mapping) -> Check:
    found = _conflicts(reading)
    if not found:
        return Check('services.conflicts', 'Conflicting statements', 'pass',
                     'No act is stated both as done and as not done for the same service and site.',
                     wording.EVENTS_SOURCE)
    items = []
    for relation in found[:4]:
        event = reading.events.get(relation['event']) or {}
        session = sessions_.get(event.get('family', ''))
        items.append(f'{events.event_label(reading, event)} in the '
                     f'{session.label if session is not None else events.service_label(event.get("family", ""))}: '
                     'stated as done and as not done')
    more = f' and {len(found) - 4} more' if len(found) > 4 else ''
    return Check('services.conflicts', 'Conflicting statements', 'warn',
                 'Conflicting statements, kept and not chosen between: ' + '; '.join(items) + more + '.',
                 wording.EVENTS_SOURCE)


def _unsupported(selections: Sequence[_Selection]) -> tuple:
    """engine._unsupported over selections: codes of a family with no GI profile, by their state."""
    entries: dict = {}
    held: dict = {}
    excluded: dict = {}
    for s in selections:
        profile = PROFILES[s.family]
        if profile.supported or s.evaluation is None:
            continue
        state = s.evaluation.state
        into = entries if state in ('performed', 'incomplete') else held if state == 'uncertain' else excluded
        entry = into.setdefault(s.family, {'family': s.family, 'label': profile.label,
                                           'status': state if into is entries else 'uncertain' if into is held
                                           else 'excluded',
                                           'detail': profile.note or 'Not covered by any GI profile in this release; '
                                                                     'review required.', 'codes': []})
        entry['codes'].append(s.code)
    return tuple(entries.values()) + tuple(held.values()) + tuple(excluded.values())


def _unsupported_check(entries: Sequence[dict]) -> Check:
    label = 'Services outside the GI profiles'
    if not entries:
        return Check('services.unsupported', label, 'not_verified',
                     'No selected code falls outside the GI profiles. A performed service of another kind with no '
                     'selected code is not verified.', wording.COVERAGE_SOURCE)
    performed = [entry['label'] for entry in entries if entry['status'] not in ('uncertain', 'excluded')]
    held = [f'{entry["label"]} ({wording.join(entry["codes"])})' for entry in entries if entry['status'] == 'uncertain']
    excluded = [f'{entry["label"]} ({wording.join(entry["codes"])})' for entry in entries
                if entry['status'] == 'excluded']
    parts = [f'Performed without a GI profile in this release: {wording.join(performed)}.'] if performed else []
    if held:
        parts.append(f'Selected without a GI profile in this release, not established as performed: '
                     f'{wording.join(held)}.')
    if excluded:
        parts.append(f'Selected without a GI profile in this release, excluded by its documented status (a reviewer '
                     f'may reinstate it): {wording.join(excluded)}.')
    return Check('services.unsupported', label, 'warn', f'{" ".join(parts)} Review required.', wording.COVERAGE_SOURCE)


def _summary(proposals: Sequence[ProposalAssessment], provider_status: str, extraction_status, day) -> dict:
    """engine._summary (copied)."""
    def count(field: str, value: str) -> int:
        return sum(1 for proposal in proposals if getattr(proposal, field) == value)
    return {'selected': count('bucket', 'selected'), 'alternatives': count('bucket', 'alternative'),
            'excluded': count('bucket', 'excluded'), 'ready': count('status', 'ready'),
            'needs_clarification': count('status', 'needs_clarification'), 'provider_status': provider_status,
            'extraction_status': extraction_status, 'service_date': day.isoformat() if day else None}


# --- the entry --------------------------------------------------------------------------------------------------------

def assess(*, inventory, context, normalized: Optional[NormalizedResponse], provider_status: str, reference,
           text: str, pages=(), date_state=None, extraction_status: Optional[str] = None,
           extraction_messages: Sequence[str] = (), second: Optional[NormalizedResponse] = None,
           second_scope: Optional[dict] = None, participants: Sequence[ParticipantInput] = (),
           member_answers: Sequence[questions.MemberAnswerInput] = ()) -> AssessmentResult:
    """The assessment of one revision from its event inventory (module docstring). ``date_state``: the
    checks.DateState of the gemini context (computed from ``context`` when not given)."""
    if provider_status not in PROVIDER_STATUSES:
        raise ValueError(f'Unknown provider status {provider_status!r}.')
    if extraction_status is not None and extraction_status not in EXTRACTION_STATUSES:
        raise ValueError(f'Unknown extraction status {extraction_status!r}.')
    participants, member_answers = tuple(participants), tuple(member_answers)
    response = normalized if provider_status == 'succeeded' else None
    if provider_status == 'succeeded' and response is None:
        raise ValueError('A succeeded provider status needs its normalized response.')
    reading = events.Reading.of(inventory)
    context = _context(context)
    if date_state is None:
        date_state = checks.service_date_state(context, _context_date(context))
    day = date_state.value
    sources = tuple(reference.sources())
    provider = list(checks.provider_checks(provider_status, response))
    sessions_ = coverage.sessions(reading)
    harness = _Participants(participants, text, pages) if participants else None
    answering = _MemberAnswers(member_answers, text) if member_answers else None
    selections: list = []
    alternatives: list = []
    merge = None
    if response is not None:
        listable = [c for c in response.codes if _listable(c.code)]
        if len(listable) < len(response.codes):
            provider.append(wording.unlisted_codes_check(len(response.codes) - len(listable),
                                                         wording.MAX_LISTED_CODE))
        selections = [_select(group, text, pages, reading) for group in _merge_selected(listable)]
        if second is not None:
            first_day = combination.procedure_day(reading, day).procedure_day
            selections, second_alternatives, merge = _second_review(second, second_scope or {}, selections, text,
                                                                    pages, reading, sessions_, first_day)
        else:
            second_alternatives = []
        alternatives = [_alternative(index, item, text, pages, response.provider)
                        for index, item in enumerate(c for c in listable if c.role != 'selected')]
        alternatives += second_alternatives
    participant_alternatives: tuple = ()
    if harness is not None:
        selections, participant_alternatives = harness.merge(selections, reading)
    keys = _keys(selections)
    refs = {s.code: reference.lookup(s.code, day) for s in selections if s.decidable}
    counted = [(key, s) for key, s in zip(keys, selections) if not s.excluded]
    members = [(s.code, s.family, coverage.session_of(sessions_, s.family)) for _, s in counted]
    coding = coverage.event_coding(reading, sessions_, {key: (coverage.session_of(sessions_, s.family),
                                                              s.evaluation.supporting)
                                                        for key, s in zip(keys, selections) if s.decidable})
    bases, within = dict(combination.base_included(members, coding)), dict(combination.base_within(members, coding))
    competes = combination.competition([(key, s.code, s.origin, s.evaluation.supporting) for key, s in counted])
    pfs_source = applied_sources(sources, day).get(PFS)
    procedural = [(s.code, s.family, s.evaluation.state, _procedural(s, refs[s.code]),
                   wording.service_name(s.code, s.family)) for _, s in counted]
    day_info = combination.procedure_day(reading, day, procedural)
    procedures = [s for _, s in counted if _procedural(s, refs[s.code])
                  and s.evaluation.state in ('performed', 'incomplete', 'uncertain')]
    reinstatable = [s for s in selections if s.excluded and s.evaluation is not None and _procedural(s, refs[s.code])]
    visits = [s for _, s in counted if s.family in wording.EM_FAMILIES
              and combination.separate_statement(reading, s.evaluation.supporting) is None]
    gate = bool(reinstatable and visits and not day_info.procedure_day)
    enc = _Encounter(
        provider=response.provider if response is not None else '', context=context, day=day, sources=sources,
        pfs_source=pfs_source, refs=refs,
        active_pfs=combination.endoscopic_rows((s.code, refs[s.code].pfs) for _, s in counted),
        day_info=day_info, global_days=_global_days(procedures, refs, pfs_source, sources, day), bases=bases,
        within=within, competes=competes, sessions=sessions_,
        coding={**coding, '_counted': {key: {'code': s.code, 'selection': s} for key, s in counted}},
        if_reinstated=tuple((s.code, PROFILES[s.family].label if PROFILES[s.family].supported else '')
                            for s in reinstatable) if gate else (),
        gated_visits=tuple(s.code for s in visits) if gate else ())
    selected, excluded = [], []
    for key, selection in zip(keys, selections):
        extra = harness.disagreements(selection) if harness is not None and selection.decidable else ()
        (excluded if selection.excluded else selected).append(_proposal(selection, key, enc, reading, extra))
    proposals = tuple(selected + excluded) + tuple(alternatives) + tuple(participant_alternatives)
    unanswered = proposals
    if answering is not None:
        proposals = answering.apply(proposals, enc)
    # the reconciliation counts every code the decisions leave selected, a code a member's answer excluded included: a
    # member's answer never releases what its code's presence covers or holds (engine.assess reads its selections)
    final = coverage.reconcile(reading, _counted_of(selections, keys), procedure_day=day_info.procedure_day,
                               sessions_=sessions_)
    if merge is not None:
        provider.append(_second_review_check(merge, final.unresolved))
    asked = {(c.family, c.fact) for p in unanswered for c in p.clarifications}
    service_questions = coverage.in_doubt_questions(reading, final, asked)
    unsupported = _unsupported(selections)
    answered = response is not None or (harness is not None and any(p.state == 'read' for p in harness.inputs))
    encounter_checks = [*provider, checks.extraction_check(extraction_status, extraction_messages),
                        checks.service_date_check(date_state),
                        _inventory_check(reading, sessions_, coverage.included_by(sessions_, final.covered))]
    if answered:
        encounter_checks.append(_unresolved_check(final.unresolved, final.not_listed))
    encounter_checks.append(_conflicts_check(reading, sessions_))
    encounter_checks.append(_unsupported_check(unsupported))
    if harness is not None:
        encounter_checks.append(harness.summary_check(sum(1 for s in selections if s.origin == 'participant')))
    clarification = checks.service_date_clarification(date_state)
    clarifications = ((clarification,) if clarification else ()) + tuple(service_questions)
    if answering is not None:
        answering.close_service(clarifications)
    open_questions = len(clarifications) + sum(len(p.clarifications) for p in proposals)
    if answering is not None:
        open_questions -= answering.closed
    unverified = {pair for _, s in counted for pair in s.evaluation.unverified}
    complete = coverage.completeness(final, sessions_, open_questions=open_questions,
                                     provider_ok=provider_status == 'succeeded' and response is not None
                                     and not response.refused, conflicts=len(_conflicts(reading)),
                                     unverified=len(unverified))
    complete.update({
        'unresolved_items': coverage.unresolved_record(final.unresolved),
        'bundled': final.bundled,
        'not_listed': [{'service': s.id, 'family': s.family, 'label': coverage.uncounted_label(s)}
                       for s in final.not_listed],
        'covered': final.covered, 'catalogue_version': catalogue.CATALOGUE_VERSION,
        'included_by': coverage.included_by(sessions_, final.covered),
        'inventory_problems': list(INVENTORY_PROBLEMS),
        'event_coding': coding,
    })
    if answering is not None:
        complete['member_answers'] = answering.record()
    return AssessmentResult(
        profiles_version=PROFILES_VERSION, engine_version=ENGINE_VERSION, proposals=proposals,
        encounter_checks=tuple(encounter_checks), clarifications=clarifications, unsupported=unsupported,
        reference_sources=checks.reference_source_entries(sources, day),
        summary=_summary(proposals, provider_status, extraction_status, day),
        services=dict(SERVICES_STUB, services=[], conflicts=[], attributions=[], problems=[]),
        completeness=complete)
