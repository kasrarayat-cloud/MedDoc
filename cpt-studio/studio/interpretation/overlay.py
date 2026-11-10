"""The read-time overlay of a new-path assessment (design/FINAL.md 8.1; DECISIONS D17; slice S11): the stored rows of an
assessment the events engine made, as its CURRENT decisions and member answers leave them, recomputed at read time.
Pure: stored rows, decisions and answers in, views out - no database, no clock, no provider, no document text.

It is review_view.review_view's orchestration (studio/validation/review_view.py:505-717), ported near-verbatim: the
counted and effective sets, member answers never lifting a hold (session decision (e), L7-01), the reinstatement gates
(L3-8), the same-day gate (B-05), the competing release (P-ADMIT2, L4-5), the base rule over the counted set (D14,
R8 D15) and the blockers of a decision the view no longer supports. Only the seams of FINAL 8.1 change:

- ``_inventory(services)`` and ``readable`` -> ``coding_of(completeness)``: completeness['event_coding'], read by a
  versioned reader that refuses an unknown version;
- ``_service`` (support['service'], reconcile.service_for) -> the session event_coding records for the code; for a
  reinstated code with none, its family's session;
- ``_bases`` (engine.base_within, engine.base_included) -> combination.base_within and combination.base_included;
- engine.base_hold, base_within_hold, competing_hold and endoscopic_rows -> combination's (the same builders, a session's
  label in place of a documented service);
- ``_modifier_review`` (engine.distinct_lesions, reconcile.describe_act, reconcile.lesion_words) -> the code's events and
  their lesions in event_coding, paired only on lesions verified DISTINCT (contract 6.3);
- ``summary(p, inventory)`` -> the stored support['summary']: nothing is recomputed;
- ``_reinstatement_waits`` (which parses the check's prose) -> the stored, structured support['reinstatement_waits'];
- ``answered_by_engine``'s engine.answered_away and engine.ANSWERED_SUPPORT -> questions.answered_away and
  questions.ANSWERED_SUPPORT (the same objects: engine re-exports them);
- ``_held_blocker``'s reconcile.service_label -> the session's label;
- checks._join, checks.SEPARATE_EM_QUESTION, checks.CLAIMS_EXAMPLE_* and checks.DISTINCT_LESION_* -> wording.join and
  copied constants (ADJUDICATION R-5: the new package names checks.py only by FINAL 7.1's names);
- ``service_answers``, ``_field`` and ``UNAVAILABLE_ANSWERS`` -> studio.code_shapes' (ADJUDICATION R-2: the one
  implementation, which review_view imports back).

Everything else - stored_from, counts, decidable, proposal_answers, answered_by_engine, _reinstatement_clear,
_unavailable_by, _open_facts, _gated, _same_day_question, _pfs_rows, _sources, _find, _question, _held_blocker, and the
_decided, _passage_sources and _example_passage helpers they need - is COPIED VERBATIM;
tests/test_interpretation_overlay.py pins each copy's AST equal to its original, modulo the seam names above, so a drift
is caught where it is made and a later change to a copy is deliberate.

UNREADABLE (FINAL 8.1, hazard 5: a quiet None never decides a new-path record). When event_coding cannot be read - absent,
another version, or a record of the wrong shape - the overlay fails closed: every stored check is kept, the base and the
competing checks are marked stale once the counted set moved (nothing is released or recomputed from a record it cannot
read), and review.readiness adds UNREADABLE_BLOCKER, so nothing is approved or exported until the code is assessed again.

What it never does: read SourceRevision.text, parse an EventInventory, parse check prose, call a function of the legacy
reader, choose a modifier, or read a participant. Its views are review_view's own dataclasses (Stored, Decided, View):
their generated methods are not the legacy reader's code (co_filename '<string>'; the sentinel allows them), and every
consumer reads one View shape whichever reader made it.

reviewed_completeness (FINAL 8.1): the documented-event coverage as the review leaves it - the codes a reviewer
reinstated counted as selected ones - re-run by coverage.reconcile over the FROZEN event inventory the assessment was
made from (``reading``, which readers.EventReader loads through interpretation.store's versioned reader) and the counted
codes' own evaluations: pure set logic over stored attributes, no text, no pattern. event_coding alone cannot carry it:
a session a reinstated code makes coded has its bundled, attempted and unsupported acts listed, which only the inventory
records.
"""
from __future__ import annotations

import functools
from typing import Mapping, Optional, Sequence

from studio.code_shapes import UNAVAILABLE_ANSWERS, _field, service_answers  # R-2: review_view's own objects
from studio.gi.profiles import PROFILES
from studio.interpretation import combination, coverage, events, wording
from studio.reference.store import PFS
from studio.types import CodeReference, EvidenceSpan, ReferenceSourceInfo, from_jsonable, to_jsonable
from studio.validation import checks, questions
# FINAL 8.1: the overlay's rows and views are review_view's own dataclasses - only these three names, whose methods are
# dataclass-generated (co_filename '<string>', never in the sentinel's deny set): every consumer reads one View shape.
from studio.validation.review_view import Decided, Stored, View

# review_view's constants, copied (tests/test_interpretation_overlay.py pins each equal to its original)
APPROVE, REJECT, REINSTATE, REVOKE, CONFIRM = 'approve', 'reject', 'reinstate', 'revoke', 'confirm'
SELECTED, EXCLUDED, ALTERNATIVE = 'selected', 'excluded', 'alternative'
READY, NEEDS_CLARIFICATION, STATUS_EXCLUDED = 'ready', 'needs_clarification', 'excluded'
BASE_CHECK, BASE_FACT = 'services.base_included', 'base_included'
ENDOSCOPIC_CHECK = 'pfs.endoscopic_base'
REINSTATEMENT_CHECK = 'review.reinstatement'
PRESENCE_CHECK = 'pfs.presence'
DATE_CHECK = wording.PROPOSAL_DATE_CHECK.id
SAME_DAY_EM_GATE = 'em.same_day_if_reinstated'
SAME_DAY_PROCEDURE = 'review.same_day_em'
SEPARATE_EM_FACT = 'separate_em'
DETAIL_UNAVAILABLE = 'detail_unavailable'
ANSWER_WORDS = {'not_documented': 'not documented', 'cannot_confirm': 'cannot be confirmed'}
_AFTER_BASE = ('facts.required', 'em.same_day_coverage', SAME_DAY_EM_GATE, 'em.same_day_procedure', DATE_CHECK,
               PRESENCE_CHECK, 'mue.units', ENDOSCOPIC_CHECK, 'cpt.membership', 'cpt.descriptor', 'ncci.ptp')
MODIFIER_REVIEW = 'distinct_lesion'
COMPETING_CHECK, COMPETING_FACT = combination.COMPETING_CHECK, combination.COMPETING_FACT
DATE_WAIT = 'the date of service is not established for this encounter.'
DOCUMENTATION_FACT = 'documentation'
DOCUMENTATION_QUESTION = 'Complete the documentation this reinstated code needs before it can be approved.'
# checks.py's constants the copies read, copied (pinned equal): the new package names checks.py only by FINAL 7.1's names
# (ADJUDICATION R-5), so the copies read these, and wording.join (checks._join's copy) in place of checks._join
SEPARATE_EM_QUESTION = ('Was a significant, separately identifiable evaluation and management service performed on '
                        'the date of service, beyond the usual pre-procedure assessment? If so, add that '
                        'documentation.')
CLAIMS_EXAMPLE_CODES = frozenset({'45380', '45385'})
CLAIMS_EXAMPLE_PASSAGE = 'item-13-example'
CLAIMS_EXAMPLE_TOPIC = 'claims.multiple_endoscopy'

# The event_coding version this reader reads (coverage.CODING_VERSION, the writer's); any other is unreadable.
CODING_VERSION = coverage.CODING_VERSION
# FINAL 8.1: the readiness blocker of a new-path assessment whose record of the documented events cannot be read.
UNREADABLE_BLOCKER = ("This assessment's record of the documented events could not be read; it cannot be approved or "
                      'exported until it is assessed again.')
# The reinstatement wait the engine records for an unknown date of service (assess._proposal): the encounter's own date
# question asks it of every code, so it is never asked of a reinstated code again (review_view's DATE_WAIT rule).
DATE_WAIT_FACT = 'service_date'


class UnreadableCoding(ValueError):
    """completeness['event_coding'] is absent, of another version, or not in the shape this release reads."""


# --- the versioned reader of event_coding (FINAL 8.1) -----------------------------------------------------------------

_SESSION_STRINGS = ('family', 'label', 'kind', 'part_of')
_ENTRY_STRINGS = ('event', 'kind', 'label')


def read_coding(completeness) -> dict:
    """completeness['event_coding'] as this release reads it, checked: version CODING_VERSION, and every session, code and
    lesion record in the shape the overlay reads. Raises UnreadableCoding; never returns a partial record."""
    coding = completeness.get('event_coding') if isinstance(completeness, Mapping) else None
    if not isinstance(coding, Mapping):
        raise UnreadableCoding('The assessment records no event coding.')
    if coding.get('version') != CODING_VERSION:
        raise UnreadableCoding(f'This release reads event coding {CODING_VERSION} only.')
    sessions, codes, lesions = coding.get('sessions'), coding.get('codes'), coding.get('lesions')
    if not (isinstance(sessions, Mapping) and isinstance(codes, Mapping) and isinstance(lesions, Mapping)):
        raise UnreadableCoding('The event coding has no sessions, codes or lesions.')
    for sid, session in sessions.items():
        if not (isinstance(sid, str) and sid and isinstance(session, Mapping)
                and all(isinstance(session.get(name), str) for name in _SESSION_STRINGS)
                and isinstance(session.get('done'), bool)):
            raise UnreadableCoding('A session of the event coding is not in the shape this release reads.')
        for part in ('reportable', 'doubted'):
            entries = session.get(part)
            if not isinstance(entries, list) or not all(
                    isinstance(entry, Mapping) and all(isinstance(entry.get(name), str) for name in _ENTRY_STRINGS)
                    and isinstance(entry.get('lesion'), (str, type(None))) for entry in entries):
                raise UnreadableCoding('A session\'s events are not in the shape this release reads.')
    for key, entry in codes.items():
        if not (isinstance(key, str) and isinstance(entry, Mapping) and isinstance(entry.get('session'), str)
                and isinstance(entry.get('events'), list) and all(isinstance(e, str) for e in entry['events'])
                and isinstance(entry.get('lesions'), list) and all(isinstance(e, str) for e in entry['lesions'])):
            raise UnreadableCoding('A code of the event coding is not in the shape this release reads.')
    for lid, lesion in lesions.items():
        if not (isinstance(lid, str) and isinstance(lesion, Mapping) and isinstance(lesion.get('label'), str)
                and isinstance(lesion.get('distinct_from'), list)
                and all(isinstance(other, str) for other in lesion['distinct_from'])):
            raise UnreadableCoding('A lesion of the event coding is not in the shape this release reads.')
    return coding


def coding_of(completeness) -> Optional[dict]:
    """read_coding, or None when the record cannot be read (the overlay then fails closed)."""
    try:
        return read_coding(completeness)
    except UnreadableCoding:
        return None


def _session(coding, session_id) -> Optional[dict]:
    """The session ``session_id`` of ``coding`` with its id, or None."""
    record = (coding.get('sessions') or {}).get(session_id) if coding is not None and session_id else None
    return {**record, 'id': session_id} if isinstance(record, Mapping) else None


def _family_session(coding, family) -> Optional[dict]:
    """The session of ``family`` the coding documents - one with a done event when there is one (the event form of
    reconcile.service_for, which prefers the service performed today) - or None."""
    found = [sid for sid, record in (coding.get('sessions') or {}).items() if record.get('family') == family]
    done = [sid for sid in found if coding['sessions'][sid].get('done')]
    return _session(coding, (done or found or [''])[0])


def _session_label(session) -> str:
    """A session's label, as reconcile.service_label words a documented service."""
    return str(session.get('label') or '') or 'service'


# --- copied verbatim from review_view (FINAL 8.1; pinned by AST) ------------------------------------------------------

def stored_from(proposal, clarifications=None) -> Stored:
    """A Stored row from a Proposal (or any object with its fields) and that proposal's Clarification rows (objects with
    scope, family, fact, question, reason, state and pk), or from an engine ProposalAssessment, whose ClarificationSpecs
    are its own and all open (as persisting them leaves them)."""
    if clarifications is None:
        own = getattr(proposal, 'clarifications', ())
        clarifications = own if isinstance(own, (list, tuple)) else ()
    questions, holds = [], []
    for row in clarifications:
        if getattr(row, 'scope', '') == 'proposal':
            holds.append(row.fact)
        if getattr(row, 'state', 'open') == 'open':
            questions.append({'id': str(getattr(row, 'pk', '') or ''), 'scope': row.scope, 'family': row.family,
                              'fact': row.fact, 'question': row.question, 'reason': row.reason})
    return Stored(key=proposal.key, code=proposal.code, family=proposal.family, bucket=proposal.bucket,
                  status=proposal.status, reinstatable=bool(proposal.reinstatable), units=proposal.units,
                  checks=tuple(to_jsonable(list(proposal.checks or ()))), holds=tuple(holds),
                  questions=tuple(questions), support=to_jsonable(dict(proposal.support or {})),
                  evidence=tuple(to_jsonable(list(proposal.evidence or ()))),
                  id=str(getattr(proposal, 'pk', '') or ''))


def _decided(value) -> Decided:
    if isinstance(value, Decided):
        return value
    if isinstance(value, str):
        return Decided(value)
    return Decided(str(getattr(value, 'action', '')), tuple(getattr(value, 'modifiers', None) or ()))


def proposal_answers(answers) -> dict:
    """{(code, family, fact): value} of the current member answers given for a code (P5 binds an answer to the code,
    family and fact it was asked of, never to a key) that leave its detail unavailable."""
    out = {}
    for answer in answers or ():
        code, value = _field(answer, 'code') or '', _field(answer, 'value') or ''
        if code and value in UNAVAILABLE_ANSWERS:
            out.setdefault((str(code), str(_field(answer, 'family') or ''), str(_field(answer, 'fact') or '')), value)
    return out


def answered_by_engine(p: Stored) -> tuple[str, str]:
    """(fact, value) of the member answer the engine excluded ``p`` by (engine.answered_away: completion repair
    2026-11-06, the answers read as an input), ('', '') for any other code."""
    if not questions.answered_away(p):
        return '', ''
    marker = (p.support or {}).get(questions.ANSWERED_SUPPORT) or {}
    return str(marker.get('fact') or ''), str(marker.get('value') or '')


def counts(p: Stored, decided: Optional[Decided]) -> bool:
    """Whether ``p`` is decided like a code that is billed, before any member answer: a selected code not rejected, or
    an excluded, reinstatable code with a current reinstatement (or the approval that rests on one). A code the engine
    excluded by a member's answer counts as the selected code it was (session decision (e): its presence still holds
    every code it held), exactly as one this overlay leaves detail_unavailable does."""
    action = decided.action if decided is not None else ''
    if answered_by_engine(p)[0]:
        return True
    if p.bucket == SELECTED:
        return action != REJECT
    return p.bucket == EXCLUDED and p.reinstatable and action in (REINSTATE, APPROVE)


def decidable(p: Stored) -> bool:
    """review.decidable: selected, or excluded and reinstatable."""
    return p.bucket == SELECTED or (p.bucket == EXCLUDED and p.reinstatable)


def _find(items, check_id) -> Optional[int]:
    return next((i for i, item in enumerate(items) if item.get('id') == check_id), None)


def _question(spec, *, ident='') -> dict:
    return {'id': ident, 'scope': spec.scope, 'family': spec.family, 'fact': spec.fact, 'question': spec.question,
            'reason': spec.reason}


def _reinstatement_clear(p: Stored) -> bool:
    """Its stored review.reinstatement check passes (review._reinstatement_clear: fail-closed, no check is no pass)."""
    return any(c.get('id') == REINSTATEMENT_CHECK and c.get('status') == 'pass' for c in p.checks)


def _open_facts(p: Stored, held, readable: bool, counted: bool = False, same_day: bool = False) -> list:
    """The facts of ``p``'s open proposal-scoped questions once the base rule is read over the counted set (``held``:
    what it holds ``p`` beside there, None when it does not), in order; for a reinstated exclusion (``counted``), also
    what its approval waits for (_reinstatement_waits); for a visit a reinstated same-day procedure holds
    (``same_day``), also the separately identifiable visit it waits for (_same_day_question)."""
    facts = [q.get('fact') for q in p.questions if q.get('scope') == 'proposal']
    if readable:
        facts = [fact for fact in facts if fact != BASE_FACT] + ([BASE_FACT] if held else [])
    if counted and p.bucket == EXCLUDED:
        facts += [q['fact'] for q in _reinstatement_waits(p)]
    if same_day and SEPARATE_EM_FACT not in facts:
        facts.append(SEPARATE_EM_FACT)
    return facts


def _unavailable_by(p: Stored, held, readable: bool, answered: Mapping, counted: bool = False,
                    same_day: bool = False) -> tuple[str, str]:
    """(fact, value) of the first open question of ``p`` a member answered as unavailable, ('', '') when none."""
    for fact in _open_facts(p, held, readable, counted, same_day):
        value = answered.get((p.code, p.family, fact))
        if value:
            return fact, value
    return '', ''


def _gated(p: Stored) -> bool:
    """An E/M the engine marked as held if a same-day procedure is reinstated (its em.same_day_if_reinstated check)."""
    return any(c.get('id') == SAME_DAY_EM_GATE for c in p.checks)


def _same_day_question(p: Stored, procedures: Sequence[Stored]) -> dict:
    """The question a visit the reinstatement of ``procedures`` (marked same-day procedures) holds is asked: whether a
    significant, separately identifiable visit is documented - the engine's own question beside a procedure it selected
    (checks.separate_em_clarification), with a reason naming the reinstated codes. A dict {id: '', scope, family, fact,
    question, reason}, as the overlay's other added questions."""
    codes = [procedure.code for procedure in procedures]
    verb = 'was reinstated as a same-day procedure' if len(codes) == 1 else 'were reinstated as same-day procedures'
    return {'id': '', 'scope': 'proposal', 'family': p.family, 'fact': SEPARATE_EM_FACT,
            'question': SEPARATE_EM_QUESTION,
            'reason': (f'{wording.join(codes)} {verb}; a significant, separately identifiable E/M service is not '
                       'established by this document.')}


def _pfs_rows(retrieval) -> dict:
    """code -> the PFS row the assessment's own retrieval trace recorded for it (each 'pfs.<field>' fact, with its
    source key), None for a traced code with no PFS row. A failed retrieval traces no code."""
    rows = {}
    for entry in retrieval or ():
        if not isinstance(entry, Mapping) or not isinstance(entry.get('code'), str) or not entry.get('code'):
            continue
        row = {}
        for fact in entry.get('facts') or ():
            if isinstance(fact, Mapping) and isinstance(fact.get('field'), str) and fact['field'].startswith('pfs.'):
                row[fact['field'][4:]] = fact.get('value')
                row['source_key'] = fact.get('source_key')
        rows[entry['code']] = row or None
    return rows


def _sources(reference_sources) -> tuple:
    fields = ReferenceSourceInfo.__dataclass_fields__
    return tuple(ReferenceSourceInfo(**{name: str(entry.get(name) or '') for name in fields})
                 for entry in reference_sources or () if isinstance(entry, Mapping) and entry.get('key')
                 and entry.get('kind'))


@functools.lru_cache(maxsize=1)
def _passage_sources() -> dict:
    """(source key, release) -> (title, effective start) of each CMS passage source this release ships
    (studio/reference/data): the citation names the source and the date its window opens."""
    from studio.reference import passages  # local import: only a modifier review's citation reads it
    sources = {}
    for path in passages.bundled_files():
        try:
            source = passages.read_data_file(path).source
        except Exception:  # noqa: BLE001 - a file this release cannot read names no title, and its citation shows none
            continue
        sources[(source['key'], source['release'])] = (source['title'], str(source.get('effective_start') or ''))
    return sources


def _example_passage(codes: Sequence[str], retrieval) -> Optional[Mapping]:
    """The claims-manual example passage the assessment's retrieval recorded for one of ``codes``, or None."""
    for entry in retrieval or ():
        if not isinstance(entry, Mapping) or entry.get('code') not in codes:
            continue
        for passage in entry.get('passages') or ():
            if (isinstance(passage, Mapping) and passage.get('passage_key') == CLAIMS_EXAMPLE_PASSAGE
                    and passage.get('topic') == CLAIMS_EXAMPLE_TOPIC and passage.get('release')):
                return passage
    return None


def _held_blocker(p: Stored, held, counted: Sequence[Stored], service) -> str:
    """The readiness blocker of an approval a base rule now holds (D14); ``held``: _bases's (rule, codes) over the
    ``counted`` set, which names the codes that hold it."""
    rule, held = held if held else ('included', ())
    held = tuple(held or ())
    if rule == 'within':
        return (f'{p.code} was approved, but its examination is the endoscopic portion of the endoscopic ultrasound '
                'documented with it and is normally included in it; revoke the approval')
    if held and all(other[:1].isdigit() for other in held):
        by_code = {other.code: other for other in counted}
        reinstated = all(by_code.get(code) is not None and by_code[code].bucket == EXCLUDED for code in held)
        one = len(held) == 1
        verb = ('was reinstated' if one else 'were reinstated') if reinstated else ('is selected' if one else
                                                                                     'are selected')
        return (f'{p.code} was approved, but {wording.join(list(held))} {verb}: its diagnostic examination is normally '
                f'included in {"that intervention" if one else "those interventions"}; revoke one of the decisions')
    name = _session_label(service) if service is not None else 'service'
    return (f'{p.code} was approved, but the documented {name} includes {wording.join(list(held))}, which this '
            'diagnostic code does not account for; revoke the approval')


# --- the seams (FINAL 8.1): each reads what the events engine stored, never what review_view parsed ------------------

def _service(p: Stored, coding, decided: Optional[Decided]):
    """The session ``p`` was matched to (event_coding's record of its code), or - for a code a reviewer reinstated whose
    own decision matched none - the session of its family the coding documents; None otherwise, and with no coding."""
    if coding is None:
        return None
    session_id = ((coding.get('codes') or {}).get(p.key) or {}).get('session')
    if session_id:
        return _session(coding, session_id)
    if p.bucket == EXCLUDED and decided is not None and decided.action in (REINSTATE, APPROVE):
        return _family_session(coding, p.family)
    return None


def _bases(effective: Sequence[Stored], service: Mapping[str, object], readable: bool, coding) -> dict:
    """code -> (rule, codes): what the two base rules hold it beside over ``effective``, by code (review_view._bases over
    combination.base_within and combination.base_included: the ordinary rule wins); {} when the coding cannot be read."""
    if not readable:
        return {}
    members = [(p.code, p.family, (service[p.key] or {}).get('id', '')) for p in effective]
    held = {code: ('within', codes) for code, codes in combination.base_within(members, coding)}
    held.update({code: ('included', others) for code, others in combination.base_included(members, coding)})
    return held


def _reinstatement_waits(p: Stored) -> tuple:
    """The questions an excluded code's approval waits for once it is reinstated, from the engine's STRUCTURED record
    (support['reinstatement_waits']: [{fact, question}], FINAL 7.11 - never the check's prose), each as a dict {id: '',
    scope, family, fact, question, reason}; () when its stored review.reinstatement check passes. The date of service's
    wait is the encounter's own question and is not asked again (review_view's DATE_WAIT rule). A check that withholds
    approval with no structured wait recorded - or a record this release cannot read - asks for the documentation
    itself (DOCUMENTATION_FACT): fail-closed, the code is asked and held, never shown as ready."""
    if _reinstatement_clear(p):
        return ()
    check = next((c for c in p.checks if c.get('id') == REINSTATEMENT_CHECK), None)
    detail = str((check or {}).get('detail') or '')
    reason = detail or 'Approval after reinstatement is not established for this code.'
    stored = (p.support or {}).get('reinstatement_waits')
    waits = stored if isinstance(stored, (list, tuple)) else ()
    readable = all(isinstance(wait, Mapping) and isinstance(wait.get('fact'), str) and wait['fact']
                   and isinstance(wait.get('question'), str) and wait['question'] for wait in waits)
    asked, dated = [], False
    for wait in (waits if readable else ()):
        if wait['fact'] == DATE_WAIT_FACT:
            dated = True
        elif (wait['fact'], wait['question']) not in asked:
            asked.append((wait['fact'], wait['question']))
    if not asked and not dated:
        asked.append((DOCUMENTATION_FACT, DOCUMENTATION_QUESTION))
    return tuple({'id': '', 'scope': 'proposal', 'family': p.family, 'fact': fact, 'question': question,
                  'reason': reason} for fact, question in asked)


def summary(p: Stored) -> str:
    """The stored sentence of CPT Studio's own reading of the documented events ``p`` was matched to (support['summary'],
    the engine's: FINAL 7.11); '' when none was stored. Nothing is recomputed."""
    value = (p.support or {}).get('summary')
    return value if isinstance(value, str) else ''


def _coded_acts(p: Stored, coding, session) -> Optional[list]:
    """(event id, lesion, words) of each of ``p``'s supporting events (event_coding's codes[key].events) of a kind a
    separate-lesion modifier can concern (combination.DISTINCT_LESION_KINDS), its verified lesion and its words as the
    session's event entries record them; None when one of them is not recorded there (fail-closed: no review is offered
    on what cannot be read), [] when none is of such a kind."""
    entry = ((coding.get('codes') or {}).get(p.key) or {}) if coding is not None else {}
    known = {item['event']: item for item in list(session.get('reportable') or ()) + list(session.get('doubted') or ())}
    kinds = {str(act.get('id')): act.get('kind') for act in (p.support or {}).get('acts') or ()
             if isinstance(act, Mapping)}
    out = []
    for event_id in entry.get('events') or ():
        kind = kinds.get(event_id) or (known.get(event_id) or {}).get('kind')
        if not kind:
            return None
        if kind not in combination.DISTINCT_LESION_KINDS:
            continue
        item = known.get(event_id)
        if item is None:
            return None
        out.append((event_id, item.get('lesion') or '', str(item.get('describe') or item.get('label') or '')))
    return out


def _distinct(coding, first, second) -> bool:
    lesions = coding.get('lesions') or {}
    return bool(first) and bool(second) and all(
        two in ((lesions.get(one) or {}).get('distinct_from') or ()) for one in first for two in second)


def _lesion_label(coding, lesion: str) -> str:
    return str(((coding.get('lesions') or {}).get(lesion) or {}).get('label') or '')


def _modifier_review(p: Stored, effective: Sequence[Stored], service: Mapping[str, object], coding,
                     retrieval) -> Optional[dict]:
    """The separate-lesion modifier review of ``p`` over the effective set (review_view._modifier_review's shape and its
    claims-manual citation): ``p``'s own supporting events lie on verified lesions, and another code of the effective
    set, matched to the same session, accounts for events on lesions every one of which is verified DISTINCT from each of
    ``p``'s (contract 6.3; an unresolved identity never pairs, E15). None otherwise - so it is dropped as soon as that
    other code leaves the effective set. Options 59 or XS; nothing is chosen here."""
    own = service.get(p.key)
    if own is None or coding is None:
        return None
    acts = _coded_acts(p, coding, own)
    lesions = sorted({lesion for _, lesion, _ in acts or () if lesion})
    if not lesions:
        return None
    partners = []
    for other in effective:
        if other.key == p.key or other.code == p.code or service.get(other.key) is None \
                or service[other.key]['id'] != own['id']:
            continue
        theirs = _coded_acts(other, coding, own)
        kept = sorted({lesion for _, lesion, _ in theirs or () if lesion})
        if kept and _distinct(coding, lesions, kept):
            partners.append((other, [act for act in theirs if act[1] in kept]))
    if not partners:
        return None
    codes = [p.code] + [other.code for other, _ in partners]
    cited = None
    if p.code in CLAIMS_EXAMPLE_CODES and any(code in CLAIMS_EXAMPLE_CODES and code != p.code for code in codes):
        cited = _example_passage(sorted(CLAIMS_EXAMPLE_CODES & set(codes)), retrieval)
    sources = []
    if cited is not None:
        key, release = str(cited.get('source_key') or ''), str(cited.get('release') or '')
        # the title of a source this release bundles; a source it does not bundle has none here - its key is never a
        # title (refutation round 2, L4-4: the key reached the customer's modifier review)
        title, effective_start = _passage_sources().get((key, release), ('', ''))
        sources.append({'key': key, 'title': title, 'release': release, 'effective_start': effective_start,
                        'section': str(cited.get('section') or ''), 'page': str(cited.get('page') or ''),
                        'passage_key': str(cited.get('passage_key') or '')})
    here = [words for _, lesion, words in acts if lesion in lesions]
    pair = [(other.code, [words for _, _, words in theirs]) for other, theirs in partners]
    lesion_words = {p.code: [_lesion_label(coding, lesion) for lesion in lesions]}
    for other, theirs in partners:
        lesion_words[other.code] = sorted({_lesion_label(coding, lesion) for _, lesion, _ in theirs})
    return {'kind': MODIFIER_REVIEW, 'codes': codes, 'service': own['id'], 'lesions': lesion_words,
            'options': list(combination.DISTINCT_LESION_OPTIONS),
            'text': checks.distinct_lesion_review_text(p.code, here, pair, sources[0]['release'] if sources else ''),
            'sources': sources, 'not_checked': list(combination.DISTINCT_LESION_NOT_CHECKED)}


# --- the orchestration (review_view.review_view, ported; FINAL 8.1) ---------------------------------------------------

def review_view(stored: Sequence[Stored], decisions: Mapping, *, completeness=None, retrieval=(), reference_sources=(),
                service_date=None, answers=()) -> dict[str, View]:
    """{proposal key: View} of ``stored`` (one new-path assessment's proposals, in their stored order) under
    ``decisions`` ({key: current action, a Decided, or a Decision}) and ``answers`` (the current member answers: mappings
    or objects with code, family, fact and value), exactly as review_view.review_view reads a legacy assessment, with the
    seams of the module docstring. ``completeness``: Assessment.completeness, whose event_coding the seams read (an
    unreadable one fails closed); ``retrieval``, ``reference_sources``, ``service_date``: as review_view's."""
    rows = list(stored)
    decided = {key: _decided(value) for key, value in (decisions or {}).items()}
    coding = coding_of(completeness)
    readable = coding is not None
    answered, closed = proposal_answers(answers), service_answers(answers)
    service = {p.key: _service(p, coding, decided.get(p.key)) for p in rows}
    # The COUNTED set: the codes as the current decisions leave them - selected and not rejected, or reinstated - whatever
    # a member answered. Every hold reads it, so the base rule is read once, here, over it: a member's answer never lifts
    # a hold another code's presence makes (session decision (e); refutation round 2, L7-01).
    candidates = [p for p in rows if counts(p, decided.get(p.key))]
    counted = {p.key for p in candidates}
    bases = _bases(candidates, service, readable, coding)
    # a reinstated same-day procedure holds the gated E/M (a hold: the counted set, whatever a member answered of it)
    same_day_procedures = [p for p in rows if p.key in counted and p.bucket == EXCLUDED
                           and any(c.get('id') == SAME_DAY_PROCEDURE for c in p.checks)]
    reinstated_procedures = bool(same_day_procedures)
    # Member answers (one pass: no answer moves a hold, so no answer moves another code's questions)
    unavailable = {}
    for p in rows:
        if answered_by_engine(p)[0]:
            # the engine read the member's answer already: the same view, never read twice
            unavailable[p.key] = answered_by_engine(p)
            continue
        if p.key in counted:
            by = _unavailable_by(p, bases.get(p.code), readable, answered, counted=True,
                                 same_day=reinstated_procedures and _gated(p))
        else:
            by = _unavailable_by(p, None, False, answered)
        if by[0]:
            unavailable[p.key] = by
    # The EFFECTIVE set: the counted codes still in review, which the combination readings that hold nothing read.
    effective = [p for p in candidates if p.key not in unavailable]
    keys = {p.key for p in effective}
    selected = {p.key for p in rows if p.bucket == SELECTED}
    engine_counted = selected | {p.key for p in rows if answered_by_engine(p)[0]}
    moved, counted_moved = keys != selected, counted != engine_counted
    pfs = _pfs_rows(retrieval)
    sources = _sources(reference_sources)
    pfs_keys = {s.key for s in sources if s.kind == PFS}
    pfs_complete = all(pfs.get(p.code) and pfs[p.code].get('source_key') in pfs_keys for p in rows
                       if decidable(p) and any(c.get('id') == PRESENCE_CHECK and c.get('status') == 'pass'
                                               for c in p.checks))
    active_rows = combination.endoscopic_rows((p.code, pfs.get(p.code)) for p in effective)
    views = {}
    for p in rows:
        d = decided.get(p.key)
        action = d.action if d is not None else ''
        chosen = tuple(d.modifiers) if d is not None and action == APPROVE else ()
        same_day = _gated(p) and reinstated_procedures
        if p.key in unavailable:
            fact, value = unavailable[p.key]
            words = ANSWER_WORDS.get(value, 'unavailable')
            views[p.key] = View(
                key=p.key, code=p.code, bucket=p.bucket, decision=action, active=p.key in counted,
                status=STATUS_EXCLUDED,
                reason=DETAIL_UNAVAILABLE, checks=tuple(dict(c) for c in p.checks), questions=(), added=(),
                released=(), withheld_by='', reinstatement_clear=False, same_day_held=same_day,
                blocker=(f'{p.code} was approved, but a detail it needs was answered as {words}: revoke the approval'
                         if action == APPROVE else ''),
                recomputed=(), stale=(), modifier_review=None, modifiers=chosen, summary=summary(p),
                answer=value, answered=fact)
            continue
        items = [dict(c) for c in p.checks]
        questions = [dict(q) for q in p.questions
                      if not (q.get('scope') != 'proposal' and (q.get('family'), q.get('fact')) in closed)]
        holds = list(p.holds)
        added, released, recomputed, stale = [], [], [], []
        active = p.key in keys
        stored_clear = _reinstatement_clear(p)
        held = bases.get(p.code) if active else None
        if active and readable:
            at = _find(items, BASE_CHECK)
            if held:
                rule, codes = held
                hold = combination.base_hold if rule == 'included' else combination.base_within_hold
                check, spec = hold(p.code, p.family, p.key, codes, _session_label(service[p.key]))
                new = to_jsonable(check)
                if at is None:
                    items.insert(next((i for i, item in enumerate(items) if item.get('id') in _AFTER_BASE),
                                      len(items)), new)
                    recomputed.append(BASE_CHECK)
                    added.append(BASE_FACT)
                    holds.append(BASE_FACT)
                    questions.append(_question(spec))
                    at = _find(items, REINSTATEMENT_CHECK) if p.bucket == EXCLUDED else None
                    if at is not None:
                        # a reinstated code's approval-after-reinstatement gate, with the question its reinstatement
                        # raises: what checks.reinstatement_check makes of its stored waits and this one
                        old = items[at]
                        items[at] = (to_jsonable(checks.reinstatement_check([spec], date_unknown=False))
                                     if old.get('status') == 'pass'
                                     else dict(old, detail=f'{old.get("detail", "")} {spec.question}'))
                        recomputed.append(REINSTATEMENT_CHECK)
                elif items[at] != new:
                    items[at] = new
                    recomputed.append(BASE_CHECK)
                    questions = [dict(q, question=spec.question, reason=spec.reason) if q.get('fact') == BASE_FACT
                                  else q for q in questions]
            elif at is not None:
                del items[at]
                recomputed.append(BASE_CHECK)
                released.append(BASE_FACT)
                holds = [fact for fact in holds if fact != BASE_FACT]
                questions = [q for q in questions if q.get('fact') != BASE_FACT]
        elif active and counted_moved and _find(items, BASE_CHECK) is not None:
            stale.append(BASE_CHECK)  # the base rule reads the counted set
        base_added = bool(added)
        # P-ADMIT2: a competing hold stands only while one of the codes it names is still counted; once a reviewer has
        # rejected the others it is released. A coding this release cannot read releases nothing (FINAL 8.1): the stored
        # check stands, and it is marked stale once the counted set moved.
        at = _find(items, COMPETING_CHECK) if active else None
        if at is not None and not readable:
            if counted_moved:
                stale.append(COMPETING_CHECK)
        elif at is not None:
            rivals = set((p.support or {}).get('competes') or ())
            # refutation round 1 of harness repair 3 (L4-5): a rival a member's answer to one of its own questions left
            # unavailable is no longer in review; an answer to the competing question itself never counts
            live = sorted({q.code for q in candidates if q.key != p.key and q.code in rivals
                           and unavailable.get(q.key, ('', ''))[0] in ('', COMPETING_FACT)})
            if not live:
                del items[at]
                recomputed.append(COMPETING_CHECK)
                released.append(COMPETING_FACT)
                holds = [fact for fact in holds if fact != COMPETING_FACT]
                questions = [q for q in questions if q.get('fact') != COMPETING_FACT]
            elif len(live) < len(rivals):
                check, spec = combination.competing_hold(p.code, p.family, p.key, live,
                                                         _session_label(service.get(p.key) or {}))
                new = to_jsonable(check)
                if items[at] != new:
                    items[at] = new
                    recomputed.append(COMPETING_CHECK)
                    questions = [dict(q, question=spec.question, reason=spec.reason)
                                  if q.get('fact') == COMPETING_FACT else q for q in questions]
        # a reinstated exclusion is asked what its stored gate says its approval waits for (refutation round 2, L3-8)
        waits = _reinstatement_waits(p) if p.bucket == EXCLUDED and active else ()
        for wait in waits:
            questions.append(dict(wait))
            added.append(wait['fact'])
        if decidable(p):
            at = _find(items, ENDOSCOPIC_CHECK)
            if at is not None and items[at].get('status') != 'not_verified':
                row = pfs.get(p.code)
                if pfs_complete and row and row.get('source_key') in pfs_keys:
                    ref = CodeReference(code=p.code, pfs=row, applicable_sources=(str(row['source_key']),))
                    new = to_jsonable(checks.endoscopic_check(p.code, ref, active_rows, sources, service_date))
                    if new != items[at]:
                        items[at] = new
                        recomputed.append(ENDOSCOPIC_CHECK)
                elif moved:
                    stale.append(ENDOSCOPIC_CHECK)
        if p.bucket == SELECTED and active and (added or released):
            status = NEEDS_CLARIFICATION if holds or _find(items, DATE_CHECK) is not None else READY
        elif p.bucket == EXCLUDED and active and (base_added or not stored_clear):
            # a reinstated exclusion whose approval waits on a question needs clarification: never ready
            status = NEEDS_CLARIFICATION
        else:
            status = p.status
        withheld = ''
        if p.bucket == SELECTED and active and not action and base_added and status == NEEDS_CLARIFICATION:
            withheld = BASE_CHECK
        elif p.bucket == EXCLUDED and action == REINSTATE:
            withheld = (REINSTATEMENT_CHECK if not stored_clear else BASE_CHECK if base_added
                        else SAME_DAY_EM_GATE if same_day else '')
        review = _modifier_review(p, effective, service, coding, retrieval) if active else None
        blocker = ''
        if action == APPROVE:
            if (p.bucket == SELECTED and status == NEEDS_CLARIFICATION and held) or (p.bucket == EXCLUDED
                                                                                    and base_added):
                blocker = _held_blocker(p, held, candidates, service.get(p.key))
            elif status == NEEDS_CLARIFICATION:
                blocker = f'{p.code} was approved, but it now needs clarification; revoke the approval'
            elif chosen and (review is None or any(m not in review['options'] for m in chosen)):
                blocker = (f'{p.code} was approved with modifier {", ".join(chosen)}, but the separate-lesion '
                           'modifier review no longer applies to it; revoke the approval and decide it again')
        if same_day and active and not any(q.get('fact') == SEPARATE_EM_FACT for q in questions):
            # A visit a reinstated same-day procedure holds is asked the separate visit it waits for and needs
            # clarification (refutation round 3, B-05), asked once; approve stays withheld (same_day_held).
            questions.append(_same_day_question(p, same_day_procedures))
            added.append(SEPARATE_EM_FACT)
            status = NEEDS_CLARIFICATION
        views[p.key] = View(
            key=p.key, code=p.code, bucket=p.bucket, decision=action, active=active, status=status, reason='',
            checks=tuple(items), questions=tuple(questions), added=tuple(added), released=tuple(released),
            withheld_by=withheld, reinstatement_clear=stored_clear and not base_added, same_day_held=same_day,
            blocker=blocker, recomputed=tuple(dict.fromkeys(recomputed)), stale=tuple(dict.fromkeys(stale)),
            modifier_review=review, modifiers=chosen, summary=summary(p), answer='')
    return views


# --- the documented-event coverage as the review leaves it (FINAL 8.1; engine.reviewed_completeness's event form) -----

def counted_codes(proposals, reinstated_keys, reading) -> list:
    """coverage.Counted of every code the review counts - the selected ones, the ones the engine excluded by a member's
    answer (the engine counted them: assess's reconciliation reads its selections before the answers), and the
    reinstated ones (``reinstated_keys``) - each with its supporting and read events as the per-code rule decides them
    over ``reading`` from the code's own stored exact evidence: the evaluation the engine made, made again (pure)."""
    out = []
    for proposal in proposals:
        reinstated = proposal.key in reinstated_keys
        if not (proposal.bucket == SELECTED or questions.answered_away(proposal) or reinstated):
            continue
        kept = tuple(from_jsonable(EvidenceSpan, span) for span in proposal.evidence or ())
        evaluation = events.evaluate(proposal.code, kept, reading)
        out.append(coverage.Counted(key=proposal.key, code=proposal.code, family=proposal.family,
                                    supporting=evaluation.supporting, read=evaluation.read))
    return out


def reviewed_completeness(completeness, reading, counted, reinstated) -> dict:
    """The coverage the assessment recorded (``completeness``) as the review leaves it: coverage.reconcile over the
    frozen ``reading`` with ``counted`` (counted_codes, the reinstated codes among them) - what each session's codes
    cover, include and leave unresolved, and the coding completeness that follows, worded as the engine words them.
    ``reinstated``: (code, family) of the reinstated codes. The second-review mark is carried from the item the
    assessment recorded, never added; the open questions, the provider's state, the conflicts and the unverified
    attributes are the assessment's own (its reasons and counts). Pure."""
    stored = [item for item in completeness.get('unresolved_items') or () if isinstance(item, Mapping)]
    # the assessment's own procedure-day reading: it listed an office visit only on a date with no procedure; a
    # reinstated procedural code makes the date a procedure day (engine.reviewed_completeness's rule)
    procedure_day = (not any(item.get('family') == 'gi.office_em' and item.get('reason') == 'no_proposal'
                             for item in stored)
                     or any(PROFILES[family].procedure for _, family in reinstated if family in PROFILES))
    sessions_ = coverage.sessions(reading)
    found = coverage.reconcile(reading, counted, procedure_day=procedure_day, sessions_=sessions_)
    reasons = [str(reason) for reason in completeness.get('reasons') or ()]
    asked = next((int(word) for reason in reasons if 'open question' in reason
                  for word in [reason.split(' ', 1)[0]] if word.isdigit()), 0)
    unverified = next((int(word) for reason in reasons if reason.startswith("CPT Studio's reading left ")
                       for word in [reason.split(' ')[4]] if word.isdigit()), 0)
    fresh = coverage.completeness(found, sessions_, open_questions=asked,
                                  provider_ok='the provider response was not available' not in reasons,
                                  conflicts=int(completeness.get('conflicts') or 0), unverified=unverified)
    marks = {(item.get('service'), item.get('act'), item.get('reason')): bool(item.get('second_review'))
             for item in stored}
    return {**completeness, **fresh,
            'unresolved_items': [{**item, 'second_review': marks.get((item['service'], item['act'], item['reason']),
                                                                     False)} for item in found.unresolved],
            'bundled': found.bundled,
            'not_listed': [{'service': s.id, 'family': s.family, 'label': coverage.uncounted_label(s)}
                           for s in found.not_listed],
            'covered': found.covered, 'included_by': coverage.included_by(sessions_, found.covered),
            'reinstated': list(dict.fromkeys(code for code, _ in reinstated))}
