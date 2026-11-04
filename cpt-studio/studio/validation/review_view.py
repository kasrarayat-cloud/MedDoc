"""The effective review view (CORE-UX-DESIGN.md 4; R3 section 7): a persisted assessment as its CURRENT decisions and
member answers leave it, recomputed at read time. Pure: stored rows, decisions and answers in, views out - no database,
no clock, no provider.

The engine computes two combination gates once, over the codes it selected (engine._encounter): the diagnostic-base
rule (the services.base_included check and its base_included question) and the CMS PFS endoscopic-family check
(pfs.endoscopic_base). A reviewer's decision changes which codes go on together - a rejection takes one away, a
reinstatement brings an excluded one back - while Assessment and Proposal rows are immutable. So this overlay re-applies
the SAME rules (engine.base_included, engine.base_hold, engine.endoscopic_rows, checks.endoscopic_check: one
implementation, never a copy) over the effective set, and every gate and reader reads its view: review._actions,
_allowed and record_decision, readiness, coding completeness, the encounter state, the operator API, the report
snapshot, the customer API (review.effective_view) and the approved export (review.approved_items).

Positive control (I1 at read time): with no decision and no answer the effective set is the engine's own active set,
and every view reproduces its proposal's stored status, checks and open questions byte for byte (tests/test_cux_review).

Two sets, because a member's answer and a reviewer's decision are not the same act (session decision (e) of 2026-11-03:
member answers never release a code). The COUNTED set is the codes as the current decisions leave them - selected and not
rejected, or reinstated - whatever a member answered: every rule by which one code's presence holds another reads it (the
diagnostic-base rule, which also holds two E/M levels beside each other, and the same-day E/M gate of a reinstated
procedure). The EFFECTIVE set is the counted set without the codes a member's answer left without a needed detail: the
codes still in review, which the combination readings that hold nothing read (the endoscopic-family check, the modifier
review). So a member's "Not documented" or "Cannot confirm" excludes the code it answers and nothing else - it never
lifts a hold, drops another code's question or makes another code approvable; only a recorded decision does.

A reinstated exclusion is held to the gates a selected code meets (checks.reinstatement_check): while its stored
review.reinstatement check names what approval waits for, the view asks exactly that of it - the questions a selected
code of its family is asked - and reads it as needing clarification, never as ready (refutation round 2, L3-8).

What it never does: release a hold by any rule but the engine's own (a rejection releases a base only when nothing the
base rule reads still holds it), choose a modifier, or read a participant.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from studio.gi.profiles import PROFILES
from studio.reference.store import PFS
from studio.types import CodeReference, ReferenceSourceInfo, from_jsonable, to_jsonable
from studio.validation import checks, engine, reconcile

APPROVE, REJECT, REINSTATE, REVOKE, CONFIRM = 'approve', 'reject', 'reinstate', 'revoke', 'confirm'
SELECTED, EXCLUDED, ALTERNATIVE = 'selected', 'excluded', 'alternative'
READY, NEEDS_CLARIFICATION, STATUS_EXCLUDED = 'ready', 'needs_clarification', 'excluded'
BASE_CHECK, BASE_FACT = 'services.base_included', 'base_included'
ENDOSCOPIC_CHECK = 'pfs.endoscopic_base'
REINSTATEMENT_CHECK = 'review.reinstatement'
PRESENCE_CHECK = 'pfs.presence'
DATE_CHECK = checks.PROPOSAL_DATE_CHECK.id  # an unknown service date holds every proposal (engine._proposal)
SAME_DAY_EM_GATE = 'em.same_day_if_reinstated'  # review.SAME_DAY_EM_GATE
SAME_DAY_PROCEDURE = 'review.same_day_em'  # review.SAME_DAY_PROCEDURE
# A member's answer that a material detail is not in the documentation (P5's details flow): the code it is asked of
# leaves the effective set, needs no decision and is never approvable, until the answer is revoked. No other value is
# read here (a context fact goes through the context path and a new assessment).
DETAIL_UNAVAILABLE = 'detail_unavailable'
UNAVAILABLE_ANSWERS = ('not_documented', 'cannot_confirm')
ANSWER_WORDS = {'not_documented': 'not documented', 'cannot_confirm': 'cannot be confirmed'}
# The checks the engine records after a base hold (engine._proposal): an added base check goes before the first of them.
_AFTER_BASE = ('facts.required', 'em.same_day_coverage', SAME_DAY_EM_GATE, 'em.same_day_procedure', DATE_CHECK,
               PRESENCE_CHECK, 'mue.units', ENDOSCOPIC_CHECK, 'cpt.membership', 'cpt.descriptor', 'ncci.ptp')
MODIFIER_REVIEW = 'distinct_lesion'
# checks.reinstatement_check's wording of a date of service that is not established: the encounter's own date question
# asks it of every code, so a reinstated code is not asked it again.
DATE_WAIT = 'the date of service is not established for this encounter.'
# What a reinstated code is asked when its stored check withholds approval but names no wait this release words (a check
# recorded by an earlier release, or none at all): the documentation it needs, which only "Not documented", "Cannot
# confirm" or the physician's addendum answers - so it is held and asked, never shown as ready (fail-closed).
DOCUMENTATION_FACT = 'documentation'
DOCUMENTATION_QUESTION = 'Complete the documentation this reinstated code needs before it can be approved.'


@dataclass(frozen=True)
class Stored:
    """One persisted Proposal as the overlay reads it."""
    key: str
    code: str
    family: str
    bucket: str
    status: str
    reinstatable: bool = False
    units: int = 1
    checks: tuple = ()  # Proposal.checks, as stored: dicts {id, label, status, detail, source}
    holds: tuple = ()  # the facts of every proposal-scoped question the engine raised on it (its Clarification rows)
    questions: tuple = ()  # its OPEN questions (any scope naming it): dicts {id, scope, family, fact, question, reason}
    support: Optional[Mapping] = None  # Proposal.support: the documented service and acts it was matched to
    evidence: tuple = ()
    id: str = ''


@dataclass(frozen=True)
class Decided:
    """A proposal's current decision as the overlay reads it: its action and, on an approval, the modifier chosen."""
    action: str
    modifiers: tuple = ()


@dataclass(frozen=True)
class View:
    key: str
    code: str
    bucket: str
    decision: str  # the current decision's action, '' when none
    # counted: selected and not rejected, or excluded and reinstated - a code a member's answer left detail_unavailable
    # included, since its presence still holds every code it held (session decision (e)); its reason says it is excluded
    active: bool
    status: str  # ready | needs_clarification | excluded | informational, after the overlay
    reason: str  # 'detail_unavailable' when a member answer leaves a material detail unavailable, else ''
    checks: tuple  # the stored checks with the recomputed ones in their place (dicts)
    questions: tuple  # its open questions after the overlay (dicts; one the overlay adds has id '')
    added: tuple  # facts of the questions the overlay adds
    released: tuple  # facts of the stored questions the overlay releases
    withheld_by: str  # the check that withholds approve because of the overlay or a reinstatement gate, else ''
    reinstatement_clear: bool  # an excluded code: approve may follow its reinstatement (its own gates and the overlay's)
    same_day_held: bool  # an E/M a reviewer's reinstatement of a same-day procedure holds (review's SAME_DAY_EM_GATE)
    blocker: str  # the readiness blocker of a current decision the view no longer supports, else ''
    recomputed: tuple  # ids of the checks whose recomputed form differs from the stored one (added, changed, released)
    stale: tuple  # ids of the checks that could not be recomputed although the effective set moved
    modifier_review: Optional[dict]  # the structured separate-lesion modifier review, None when none applies
    modifiers: tuple  # the modifier chosen on the current approval ('59' or 'XS'), () when none
    summary: str  # one plain sentence of CPT Studio's own reading of the documented service and act, '' when none
    answer: str  # the member answer that made it detail_unavailable ('not_documented' | 'cannot_confirm'), else ''


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


def _inventory(services):
    """The documented services the assessment recorded, rebuilt as engine.reviewed_completeness rebuilds them; None when
    it recorded none, or a record this release cannot read (then nothing that needs it is recomputed)."""
    if not isinstance(services, Mapping) or not services.get('services'):
        return None
    try:
        return from_jsonable(engine.gi_services.ServiceInventory, services)
    except (TypeError, KeyError, ValueError, AttributeError):
        return None


def _field(answer, name):
    return answer.get(name) if isinstance(answer, Mapping) else getattr(answer, name, None)


def proposal_answers(answers) -> dict:
    """{(code, family, fact): value} of the current member answers given for a code (P5 binds an answer to the code,
    family and fact it was asked of, never to a key) that leave its detail unavailable."""
    out = {}
    for answer in answers or ():
        code, value = _field(answer, 'code') or '', _field(answer, 'value') or ''
        if code and value in UNAVAILABLE_ANSWERS:
            out.setdefault((str(code), str(_field(answer, 'family') or ''), str(_field(answer, 'fact') or '')), value)
    return out


def service_answers(answers) -> set:
    """{(family, fact)} of the current member answers given for a documented service (no code): they close that
    question and change nothing else."""
    return {(str(_field(answer, 'family') or ''), str(_field(answer, 'fact') or '')) for answer in answers or ()
            if not _field(answer, 'code') and _field(answer, 'value') in UNAVAILABLE_ANSWERS}


def counts(p: Stored, decided: Optional[Decided]) -> bool:
    """Whether ``p`` is decided like a code that is billed, before any member answer: a selected code not rejected, or
    an excluded, reinstatable code with a current reinstatement (or the approval that rests on one)."""
    action = decided.action if decided is not None else ''
    if p.bucket == SELECTED:
        return action != REJECT
    return p.bucket == EXCLUDED and p.reinstatable and action in (REINSTATE, APPROVE)


def decidable(p: Stored) -> bool:
    """review.decidable: selected, or excluded and reinstatable."""
    return p.bucket == SELECTED or (p.bucket == EXCLUDED and p.reinstatable)


def _service(p: Stored, inventory, decided: Optional[Decided]):
    """The documented service ``p`` was matched to (its support), or - for a code a reviewer reinstated whose own reading
    matched none (both readers agreed it was not done) - the service of its family the inventory documents, the one
    reconcile.match would have matched (R3 7.3); None otherwise."""
    if inventory is None:
        return None
    service_id = (p.support or {}).get('service')
    if service_id:
        return inventory.service(service_id)
    if p.bucket == EXCLUDED and decided is not None and decided.action in (REINSTATE, APPROVE):
        return reconcile.service_for(inventory, p.family)
    return None


def _act_ids(p: Stored) -> set:
    return {str(act.get('id')) for act in (p.support or {}).get('acts') or () if isinstance(act, Mapping)}


def _bases(effective: Sequence[Stored], service: Mapping[str, object], readable: bool) -> dict:
    """code -> (rule, codes): what the engine's two base rules hold it beside over ``effective``, by code, exactly as
    engine._proposal reads enc.bases_included and enc.bases_within: ('included', the other codes or act labels) from
    engine.base_included, else ('within', the including service's codes, possibly none) from engine.base_within (R8
    D15: an EGD that is the endoscopic portion of an EUS) - the ordinary rule wins, as in _proposal; {} when the
    inventory cannot be read. Both rules, because a stored base_included hold from either one must be re-derived, never
    released by reading only the other."""
    if not readable:
        return {}
    members = [(p.code, p.family, service[p.key]) for p in effective]
    held = {code: ('within', codes) for code, codes in engine.base_within(members)}
    held.update({code: ('included', others) for code, others in engine.base_included(members)})
    return held


def _find(items, check_id) -> Optional[int]:
    return next((i for i, item in enumerate(items) if item.get('id') == check_id), None)


def _question(spec, *, ident='') -> dict:
    return {'id': ident, 'scope': spec.scope, 'family': spec.family, 'fact': spec.fact, 'question': spec.question,
            'reason': spec.reason}


def _reinstatement_clear(p: Stored) -> bool:
    """Its stored review.reinstatement check passes (review._reinstatement_clear: fail-closed, no check is no pass)."""
    return any(c.get('id') == REINSTATEMENT_CHECK and c.get('status') == 'pass' for c in p.checks)


def _reinstatement_waits(p: Stored) -> tuple:
    """The questions an excluded code's approval waits for once it is reinstated, as its stored review.reinstatement
    check names them (checks.reinstatement_check: the required facts its profile asks - checks.fact_clarifications'
    wording - and the separately identifiable E/M on a procedure day), each as a dict {id: '', scope, family, fact,
    question, reason}; () when the check passes. Each is recognised by the check's own wording of it, rebuilt here
    from its family's profile; a date of service that is not established is the encounter's own question. A check that
    withholds approval but names nothing this release words - or a missing check - asks for the documentation itself
    (DOCUMENTATION_FACT): fail-closed, the code is asked and held, never shown as ready."""
    if _reinstatement_clear(p):
        return ()
    check = next((c for c in p.checks if c.get('id') == REINSTATEMENT_CHECK), None)
    detail = str((check or {}).get('detail') or '')
    reason = detail or 'Approval after reinstatement is not established for this code.'
    profile = PROFILES.get(p.family)
    asked = []
    for name in (profile.required_facts if profile is not None else ()):
        template = checks.FACT_QUESTIONS.get(name)
        question = (template.format(label=profile.label) if template
                    else f'{profile.label}: confirm the documented {checks.fact_label(name)}.')
        if question in detail:
            asked.append((name, question))
    if checks.SEPARATE_EM_QUESTION in detail:
        asked.append(('separate_em', checks.SEPARATE_EM_QUESTION))
    if not asked and DATE_WAIT not in detail:
        asked.append((DOCUMENTATION_FACT, DOCUMENTATION_QUESTION))
    return tuple({'id': '', 'scope': 'proposal', 'family': p.family, 'fact': fact, 'question': question,
                  'reason': reason} for fact, question in asked)


def _open_facts(p: Stored, held, readable: bool, counted: bool = False) -> list:
    """The facts of ``p``'s open proposal-scoped questions once the base rule is read over the counted set (``held``:
    what it holds ``p`` beside there, None when it does not), in order; for a reinstated exclusion (``counted``), also
    what its approval waits for (_reinstatement_waits)."""
    facts = [q.get('fact') for q in p.questions if q.get('scope') == 'proposal']
    if readable:
        facts = [fact for fact in facts if fact != BASE_FACT] + ([BASE_FACT] if held else [])
    if counted and p.bucket == EXCLUDED:
        facts += [q['fact'] for q in _reinstatement_waits(p)]
    return facts


def _unavailable_by(p: Stored, held, readable: bool, answered: Mapping, counted: bool = False) -> tuple[str, str]:
    """(fact, value) of the first open question of ``p`` a member answered as unavailable, ('', '') when none."""
    for fact in _open_facts(p, held, readable, counted):
        value = answered.get((p.code, p.family, fact))
        if value:
            return fact, value
    return '', ''


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
            if (isinstance(passage, Mapping) and passage.get('passage_key') == checks.CLAIMS_EXAMPLE_PASSAGE
                    and passage.get('topic') == checks.CLAIMS_EXAMPLE_TOPIC and passage.get('release')):
                return passage
    return None


def _modifier_review(p: Stored, effective: Sequence[Stored], service: Mapping[str, object], retrieval) -> Optional[dict]:
    """The separate-lesion modifier review of ``p`` over the effective set: ``p``'s own acts are on documented lesions,
    and another code of the effective set, matched to the same documented service, accounts for a performed act on
    another documented lesion (engine.distinct_lesions: the reading the stored consideration words). None otherwise - so
    it is dropped as soon as that other code leaves the effective set. Options 59 or XS; nothing is chosen here."""
    own = service.get(p.key)
    if own is None:
        return None
    ids = _act_ids(p)
    acts = [a for a in own.acts if a.id in ids]
    lesions, others = engine.distinct_lesions(own, acts)
    if not lesions or not others:
        return None
    partners = []
    for other in effective:
        if other.key == p.key or other.code == p.code or service.get(other.key) is None \
                or service[other.key].id != own.id:
            continue
        theirs = [a for a in others if a.id in _act_ids(other)]
        if theirs:
            partners.append((other, theirs))
    if not partners:
        return None
    codes = [p.code] + [other.code for other, _ in partners]
    cited = None
    if p.code in checks.CLAIMS_EXAMPLE_CODES and any(code in checks.CLAIMS_EXAMPLE_CODES and code != p.code
                                                     for code in codes):
        cited = _example_passage(sorted(checks.CLAIMS_EXAMPLE_CODES & set(codes)), retrieval)
    sources = []
    if cited is not None:
        key, release = str(cited.get('source_key') or ''), str(cited.get('release') or '')
        # the title of a source this release bundles; a source it does not bundle has none here - its key is never a
        # title (refutation round 2, L4-4: the key reached the customer's modifier review)
        title, effective = _passage_sources().get((key, release), ('', ''))
        sources.append({'key': key, 'title': title, 'release': release, 'effective_start': effective,
                        'section': str(cited.get('section') or ''), 'page': str(cited.get('page') or ''),
                        'passage_key': str(cited.get('passage_key') or '')})
    here = [reconcile.describe_act(own, a) for a in acts if a.lesion in lesions]
    pair = [(other.code, [reconcile.describe_act(own, a) for a in theirs]) for other, theirs in partners]
    lesion_words = {p.code: [reconcile.lesion_words(own, lesion) for lesion in lesions]}
    for other, theirs in partners:
        lesion_words[other.code] = sorted({reconcile.lesion_words(own, a.lesion) for a in theirs})
    return {'kind': MODIFIER_REVIEW, 'codes': codes, 'service': own.id, 'lesions': lesion_words,
            'options': list(checks.DISTINCT_LESION_OPTIONS),
            'text': checks.distinct_lesion_review_text(p.code, here, pair, sources[0]['release'] if sources else ''),
            'sources': sources, 'not_checked': list(checks.DISTINCT_LESION_NOT_CHECKED)}


def _what(p: Stored) -> str:
    profile = reconcile.catalogue.code_profile(p.code)
    return ' or '.join(reconcile.act_label(kind) for kind in (profile.covers if profile is not None else ()))


def summary(p: Stored, inventory) -> str:
    """One plain sentence of CPT Studio's own reading of the documented service and act ``p`` was matched to (its
    support and the recorded inventory: service kinds, act kinds and the reader's lesion words - never a provider's
    wording); '' when the inventory documents no service it was matched to."""
    support = p.support or {}
    service = inventory.service(support.get('service')) if inventory is not None and support.get('service') else None
    if service is None:
        return ''
    name, state, reason = reconcile.service_label(service), support.get('state', ''), support.get('reason', '')
    ids = _act_ids(p)
    acts = [a for a in service.acts if a.id in ids]
    what = _what(p) or name
    if state in ('performed', 'incomplete'):
        examination = f'The {name}' + (' (an incomplete examination)' if state == 'incomplete' else '')
        if acts:
            listed = checks._join([reconcile.describe_act(service, a) for a in acts[:3]])
            more = f' and {len(acts) - 3} more' if len(acts) > 3 else ''
            return f'{examination} documents {listed}{more}.'
        return f'{examination} is documented on the date of service.'
    if state == 'uncertain':
        if reason == 'conflict':
            return f'The document states the {what} both as done and as not done.'
        return f'The document does not establish the {what} as done on the date of service.'
    if state == 'not_performed':
        if reason == 'service_negative':
            return f'The document gives the {name} as {service.status}, not as done on the date of service.'
        return f'The document states the {what} was not done.'
    return ''


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
        return (f'{p.code} was approved, but {checks._join(list(held))} {verb}: its diagnostic examination is normally '
                f'included in {"that intervention" if one else "those interventions"}; revoke one of the decisions')
    name = reconcile.service_label(service) if service is not None else 'service'
    return (f'{p.code} was approved, but the documented {name} includes {checks._join(list(held))}, which this '
            'diagnostic code does not account for; revoke the approval')


def review_view(stored: Sequence[Stored], decisions: Mapping, *, services=None, retrieval=(), reference_sources=(),
                service_date=None, answers=()) -> dict[str, View]:
    """{proposal key: View} of ``stored`` (one assessment's proposals, in their stored order) under ``decisions``
    ({key: current action, a Decided, or a Decision}: approve | reject | reinstate | confirm - a revoked or invalidated
    decision is none) and ``answers`` (P5's current member answers: mappings or objects with code, family, fact and
    value; a code's 'not_documented' or 'cannot_confirm' answer to one of its open proposal-scoped questions makes it
    detail_unavailable; an answer with no code closes that service's question only).

    ``services``: Assessment.services, None when the assessment's documented-service reading was inconsistent (it then
    decided nothing, and nothing here re-reads it); ``retrieval``: Assessment.retrieval (the PFS rows the endoscopic-family
    check reads, and the dated CMS passage a modifier review cites); ``reference_sources``: Assessment.reference_sources;
    ``service_date``: the assessment's service date (read only where no PFS source applies, a check kept as stored)."""
    rows = list(stored)
    decided = {key: _decided(value) for key, value in (decisions or {}).items()}
    inventory = _inventory(services)
    readable = inventory is not None
    answered, closed = proposal_answers(answers), service_answers(answers)
    service = {p.key: _service(p, inventory, decided.get(p.key)) for p in rows}
    # The COUNTED set: the codes as the current decisions leave them - selected and not rejected, or reinstated - whatever
    # a member answered. Every hold reads it, so the base rule is read once, here, over it: a member's answer never lifts
    # a hold another code's presence makes (session decision (e); refutation round 2, L7-01: "Cannot confirm" on 45385's
    # snare had released 45378's base question, and "Not documented" on one E/M level had made the other approvable).
    candidates = [p for p in rows if counts(p, decided.get(p.key))]
    counted = {p.key for p in candidates}
    bases = _bases(candidates, service, readable)
    # Member answers: a code whose open question (as that reading leaves it; for a reinstated exclusion, also what its
    # approval waits for) a member answered as not documented or not confirmable is detail_unavailable - that code, and
    # nothing else. One pass: no answer moves a hold, so no answer moves another code's questions. A code no decision
    # leaves billed is closed by an answered open question too.
    unavailable = {}
    for p in rows:
        if p.key in counted:
            by = _unavailable_by(p, bases.get(p.code), readable, answered, counted=True)
        else:
            by = _unavailable_by(p, None, False, answered)
        if by[0]:
            unavailable[p.key] = by
    # The EFFECTIVE set: the counted codes still in review. The combination readings that hold nothing read it (the
    # endoscopic-family check, the modifier review): a code a member answered away is no longer billed beside the others.
    effective = [p for p in candidates if p.key not in unavailable]
    keys = {p.key for p in effective}
    # Whether a set is the engine's own (the selected codes, none rejected, none reinstated, none answered away): when it
    # is not, a check that could not be recomputed over it is marked stale rather than shown as current.
    selected = {p.key for p in rows if p.bucket == SELECTED}
    moved, counted_moved = keys != selected, counted != selected
    pfs = _pfs_rows(retrieval)
    sources = _sources(reference_sources)
    pfs_keys = {s.key for s in sources if s.kind == PFS}
    # The endoscopic-family check is recomputed only from a trace that carries the PFS row of every decidable code the
    # engine read one for (its pfs.presence passed), each from an applied PFS source: else every such check is kept.
    pfs_complete = all(pfs.get(p.code) and pfs[p.code].get('source_key') in pfs_keys for p in rows
                       if decidable(p) and any(c.get('id') == PRESENCE_CHECK and c.get('status') == 'pass'
                                               for c in p.checks))
    active_rows = engine.endoscopic_rows((p.code, pfs.get(p.code)) for p in effective)
    # a reinstated same-day procedure holds the gated E/M (a hold: the counted set, whatever a member answered of it)
    reinstated_procedures = any(p.key in counted and p.bucket == EXCLUDED
                                and any(c.get('id') == SAME_DAY_PROCEDURE for c in p.checks) for p in rows)
    views = {}
    for p in rows:
        d = decided.get(p.key)
        action = d.action if d is not None else ''
        chosen = tuple(d.modifiers) if d is not None and action == APPROVE else ()
        same_day = any(c.get('id') == SAME_DAY_EM_GATE for c in p.checks) and reinstated_procedures
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
                recomputed=(), stale=(), modifier_review=None, modifiers=chosen, summary=summary(p, inventory),
                answer=value)
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
                hold = engine.base_hold if rule == 'included' else engine.base_within_hold
                check, spec = hold(p.code, p.family, p.key, codes, service[p.key])
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
            # a reinstated exclusion whose approval waits on a question - its stored gate's, the encounter's date, or the
            # base rule's - needs clarification, as a selected code held on the same question does: never ready
            status = NEEDS_CLARIFICATION
        else:
            status = p.status
        withheld = ''
        if p.bucket == SELECTED and active and not action and base_added and status == NEEDS_CLARIFICATION:
            withheld = BASE_CHECK
        elif p.bucket == EXCLUDED and action == REINSTATE:
            withheld = (REINSTATEMENT_CHECK if not stored_clear else BASE_CHECK if base_added
                        else SAME_DAY_EM_GATE if same_day else '')
        review = _modifier_review(p, effective, service, retrieval) if active else None
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
        views[p.key] = View(
            key=p.key, code=p.code, bucket=p.bucket, decision=action, active=active, status=status, reason='',
            checks=tuple(items), questions=tuple(questions), added=tuple(added), released=tuple(released),
            withheld_by=withheld, reinstatement_clear=stored_clear and not base_added, same_day_held=same_day,
            blocker=blocker, recomputed=tuple(dict.fromkeys(recomputed)), stale=tuple(dict.fromkeys(stale)),
            modifier_review=review, modifiers=chosen, summary=summary(p, inventory), answer='')
    return views
