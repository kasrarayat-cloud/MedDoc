"""The combination rules over the event coding (design/FINAL.md 7.9, as design/ADJUDICATION.md C-3 and C-4 amend it): base,
base-within, competing, the same-day E/M, the separate-lesion modifier review and the endoscopic rows. The engine
applies them at assess time over the codes it counts; the read-time overlay (slice S11) applies the same functions over
a reviewer's counted set - one implementation each, so the two cannot drift (engine.py:3045-3175's comment).

Copied from engine.py:3045-3175 with the two cue predicates (gi.services.listed_in_doubt and listed_contradicted)
replaced by event states (event_coding's ``doubted``: an uncertain status, a CONTRADICTION, DOUBT or UNRESOLVED relation,
an unusable attribute of the act's own statement - fail-closed), and with the examination-only EUS codes read as
their family's base codes (``_base``: the events engine supports them by the EUS examination itself, FINAL 7.3, which
the legacy reader never did). The holds' wording is the engine builders' own,
copied, with a session's label in place of a documented service's; tests/test_interpretation_combination.py pins each
builder equal to its legacy original for equivalent inputs.

``members``: (code, family, session id or '') of every COUNTED code, in order; ``coding``: the event_coding record
(coverage.event_coding: its ``sessions`` with their reportable and doubted events and ``part_of``).

Imports nothing from studio.gi but the reference tables (FINAL 3.1).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Optional

from studio.gi import catalogue, profiles
from studio.interpretation import events, facts, identity, lexicon, mapping, verify, wording
from studio.types import Check, ClarificationSpec
from studio.validation import checks

SOURCE = wording.SOURCE  # reconcile.SOURCE
COMPETING_CHECK, COMPETING_FACT = 'proposals.competing', 'competing_codes'  # engine's, copied
# engine.DISTINCT_LESION_KINDS (copied, pinned equal): the acts a separate-lesion modifier consideration can concern.
DISTINCT_LESION_KINDS = mapping.REMOVAL_MEMBERS + ('biopsy', 'ablation', 'injection', 'tattoo')
DISTINCT_LESION_OPTIONS = ('59', 'XS')  # checks.DISTINCT_LESION_OPTIONS (copied)
DISTINCT_LESION_NOT_CHECKED = ('NCCI procedure-to-procedure edits', 'payer modifier policy')  # checks' (copied)
MODIFIER_REVIEW = 'modifier_review'  # review_view.MODIFIER_REVIEW


def _session(coding: Mapping, session_id: str) -> Optional[Mapping]:
    return (coding.get('sessions') or {}).get(session_id) if session_id else None


def _base(code: str) -> bool:
    """A base code: a base profile (CodeProfile.base: an endoscopic family's diagnostic examination, or an office visit
    code - the legacy rule reads E/M profiles as base codes that cover the visit, so two E/M codes of one visit hold each
    other), or a code whose covers are all examination kinds: an examination-only EUS code (43231, 43237, 43259, 45341,
    45391, 44406 cover only ``eus_exam``). FINAL 7.3 makes the EUS examination such a code's act (``eus_exam`` for EUS),
    so the base rules hold it beside a code of its session that accounts for an act and beside its session's reportable
    acts, and the EUS examination is never accounted for twice. An E/M add-on (99417, prolonged visit time) is neither."""
    profile = catalogue.code_profile(code)
    if profile is None:
        return False
    return profile.base or (bool(profile.covers) and all(kind in mapping.EXAMINATION_KINDS for kind in profile.covers))


# --- base (engine.base_included) ---------------------------------------------------------------------------------------

def base_included(members: Sequence[tuple], coding: Mapping) -> tuple:
    """A family's base (diagnostic) code matched to session S is held, never excluded, beside (a) another counted code
    of its family matched to S that accounts for an act (its profile covers one), (b) S's reportable events, or (c) S's
    doubted reportable-kind events: (base code, the other codes - or, with none, the labels of those acts), in member
    order."""
    bases = []
    for index, (code, family, session_id) in enumerate(members):
        session = _session(coding, session_id)
        if not _base(code) or session is None:
            continue
        others = tuple(other for position, (other, other_family, other_session) in enumerate(members)
                       if position != index and other_family == family
                       and (catalogue.code_profile(other) or catalogue.CodeProfile('')).covers
                       and other_session == session_id)
        reportable = session.get('reportable') or ()
        doubted = session.get('doubted') or ()
        if others or reportable or doubted:
            bases.append((code, others or tuple(sorted({item['label'] for item in reportable}
                                                       | {item['label'] + ' (stated in doubt)' for item in doubted}))))
    return tuple(bases)


def base_within(members: Sequence[tuple], coding: Mapping) -> tuple:
    """engine.base_within: a base code whose session is the endoscopic portion of another (C3, C-4: an EGD inside an
    upper EUS) is held: (base code, the counted codes of that session that include the examination, or () when that
    session has no counted code). No entry when the code is no base, its session is part of no other, or that session's
    counted codes include no such examination. DECISIONS D70: a session that may be the endoscopic portion of another
    (``possibly_part_of``: that session's EUS examination is only possibly current) is held as one that is - fail-closed,
    never READY - while nothing reads it as included; the overlay applies this rule at read time over the same record."""
    held = []
    for index, (code, family, session_id) in enumerate(members):
        session = _session(coding, session_id)
        whole = (session.get('part_of') or session.get('possibly_part_of')) if session is not None else ''
        if not _base(code) or session is None or not whole:
            continue
        including = [other for position, (other, _family, other_session) in enumerate(members)
                     if position != index and other_session == whole]
        if not including:
            held.append((code, ()))
            continue
        codes = tuple(other for other in including if catalogue.includes_examination(other, session.get('kind', '')))
        if codes:
            held.append((code, codes))
    return tuple(held)


def base_within_hold(code: str, family: str, key: str, within: Sequence[str], label: Optional[str]
                     ) -> tuple[Check, ClarificationSpec]:
    """engine.base_within_hold (copied): ``label`` is the session's label (the documented service's, legacy)."""
    service_name = label or 'service'
    coded = f', which {", ".join(within)} {"accounts" if len(within) == 1 else "account"} for' if within else ''
    reason = (f'The documented {service_name} is the endoscopic portion of the endoscopic ultrasound documented with '
              f'it{coded}; that examination is normally included in it, not reported separately (internal profile '
              'rule; NCCI procedure-to-procedure edits are not connected). Held for the reviewer, not excluded.')
    return (Check('services.base_included', 'Diagnostic examination beside its interventions', 'warn', reason, SOURCE),
            ClarificationSpec(scope='proposal', fact='base_included', family=family, proposal_key=key, reason=reason,
                              question=f'Is {code} reported separately from '
                                       f'{", ".join(within) or "the endoscopic ultrasound"} for this examination?'))


def base_hold(code: str, family: str, key: str, included: Sequence[str], label: Optional[str]
              ) -> tuple[Check, ClarificationSpec]:
    """engine.base_hold (copied): ``label`` is the session's label."""
    service_name = label or 'service'
    if all(other[:1].isdigit() for other in included):
        reason = (f'The documented {service_name} has interventions that {", ".join(included)} account for; its '
                  'diagnostic examination is normally included in them (internal profile rule; NCCI procedure-to-'
                  'procedure edits are not connected). Held for the reviewer, not excluded.')
    else:
        reason = (f'The documented {service_name} includes {", ".join(included)}, which this diagnostic code does '
                  'not account for (internal profile rule). Held for the reviewer, not excluded.')
    return (Check('services.base_included', 'Diagnostic examination beside its interventions', 'warn', reason, SOURCE),
            ClarificationSpec(scope='proposal', fact='base_included', family=family, proposal_key=key, reason=reason,
                              question=f'Is {code} reported separately from {", ".join(included)} for this examination?'))


# --- competing (P-ADMIT2; engine.competing_hold) ------------------------------------------------------------------------

def competing_hold(code: str, family: str, key: str, rivals: Sequence[str], label: Optional[str]
                   ) -> tuple[Check, ClarificationSpec]:
    """engine.competing_hold (copied): no proposer is named; the question is the same for every origin."""
    service_name = label or 'service'
    codes = wording.join([code, *rivals])
    reason = (f'{codes} are each proposed for one same documented act of the {service_name}. CPT Studio does not '
              'choose between them: each is held for the reviewer, not excluded, until the others are rejected.')
    return (Check(COMPETING_CHECK, 'Codes proposed for the same documented act', 'warn', reason, SOURCE),
            ClarificationSpec(scope='proposal', fact=COMPETING_FACT, family=family, proposal_key=key, reason=reason,
                              question=(f'{codes} are proposed for the same documented act. Reject the code or codes '
                                        'the documentation does not support; the one left is then ready for review.')))


def competition(entries: Sequence[tuple]) -> dict:
    """FINAL 7.9 Competing, as the installed engine's completion repair (2026-11-06; engine._competition) and DECISIONS
    D40 amend P-ADMIT2: ``entries`` (key, code, origin, E* event ids) of the decidable codes; two of them with different
    codes whose E* sets intersect - the same documented act - are each held with one question naming the others,
    WHOEVER proposed either: two codes the proposal provider alone selected for one act compete as any other two do
    (the S17 refutation: Corti's 43249 and 43233 for one dilation were both READY here, where the installed release
    holds both). ``origin`` is kept in the entry and no longer read. {key: (the rival codes, in entry order)} of every
    held code."""
    out: dict = {}
    for key, code, _origin, supporting in entries:
        rivals = [other_code for other_key, other_code, _other_origin, other_events in entries
                  if other_key != key and other_code != code and set(supporting) & set(other_events)]
        if rivals:
            out[key] = tuple(dict.fromkeys(rivals))
    return out


def endoscopic_rows(pairs) -> dict:
    """engine.endoscopic_rows (copied): code -> PFS row of every (code, PFS row or None) pair that has a row."""
    return {code: pfs for code, pfs in pairs if pfs}


# --- the same-day E/M (D21 as ADJUDICATION C-3 amends it: by date of service) -------------------------------------------

OTHER_GI = 'gi.other'  # engine.OTHER_GI
# DECISIONS D81 (the round-3 refutation, finding 20): the families whose events make a procedure day. FINAL 7.2 R8 copies
# the legacy same-day rule, and engine._same_day_family counts a routed family that is a procedure profile
# (gi.profiles procedure=True: lexicon.PROCEDURAL_FAMILIES) or another GI service (gi.other: anoscopy, hemorrhoid
# banding, rigid proctosigmoidoscopy, ...) - with no code its global period is unknown, so it counts as a code with no
# fee-schedule row does (fail-closed). Reading the procedural families alone, a hemorrhoid banding done in the office
# made no procedure day, separate_em was never asked and 99213 was READY. The pin holds it equal to the legacy rule over
# gi.profiles.
SAME_DAY_FAMILIES = lexicon.PROCEDURAL_FAMILIES | frozenset({OTHER_GI, 'gi.unsupported'})  # D94: a non-GI procedure too


@dataclass(frozen=True)
class ProcedureDay:
    """``labels``: the procedure families documented as done on the date of service; ``possible``: those whose doing on
    that date is not established (fail-closed, as checks._same_day_subject words them); ``undatable``: procedure events
    whose date CPT Studio could not establish (C-3: an E/M code gets UNRESOLVED(time), a question, never READY)."""
    labels: tuple = ()
    possible: tuple = ()
    undatable: tuple = ()

    @property
    def procedure_day(self) -> bool:
        return bool(self.labels or self.possible)


def procedure_day(reading, effective, codes: Sequence[tuple] = ()) -> ProcedureDay:
    """The procedure day by DATE OF SERVICE (C-3). Every procedure event (of a procedural family or gi.other -
    SAME_DAY_FAMILIES, DECISIONS D81 - and not an E/M visit) stated done or in doubt, by any performer (as
    derived.procedure_day reads it, contract 8.3, gi.other added by D81), is ON the date (facts.day_of:
    a usable current time, or a time whose own words or literals place it on the effective date), OFF it, or UNDATABLE.
    ON with status, time, performer and procedure usable and positive: done; ON otherwise: possible; UNDATABLE: listed
    for the E/M's time question. ``codes``: (code, family, state, procedural, label) of the counted codes - a counted
    procedural code adds its label to the done (performed) or possible (held) list, as engine._encounter adds the
    selected procedural codes."""
    labels, possible, undatable = [], [], []
    for event in reading.events.values():
        family = event.get('family') or ''
        if family not in SAME_DAY_FAMILIES or events.value(event, 'kind') in lexicon.EM_KINDS:  # D81: gi.other too
            continue
        status = events.value(event, 'status')
        if status not in verify.POSITIVE + ('uncertain',):
            continue
        label = profiles.PROFILES[family].label if family in profiles.PROFILES else family
        day = facts.day_of(event, effective)
        if day == facts.ON:
            if status in verify.POSITIVE and all(events.usable(event, name)
                                                 for name in ('status', 'performer', 'procedure', 'time')):
                labels.append(label)
            else:
                possible.append(label)
        elif day == facts.UNDATABLE:
            undatable.append(event['id'])
    for code, family, state, procedural, label in codes:
        if not procedural:
            continue
        if state in ('performed', 'incomplete'):
            labels.append(label)
        elif state == 'uncertain':
            possible.append(label)
    labels = list(dict.fromkeys(labels))
    possible = [label for label in dict.fromkeys(possible) if label not in labels]
    return ProcedureDay(tuple(labels), tuple(possible), tuple(undatable))


def separate_statement(reading, event_ids: Sequence[str]) -> Optional[str]:
    """The documented statement of a significant, separately identifiable E/M (checks.separate_em_statement's event
    form): the words of a usable ``stated`` separately_identifiable of the visit events ``event_ids``, else of any visit
    event; None when there is none."""
    visits = [reading.events[eid] for eid in event_ids if eid in reading.events]
    visits += [event for event in reading.events.values() if event not in visits]
    for event in visits:
        visit = event.get('visit')
        if not isinstance(visit, Mapping):
            continue
        separate = visit.get('separately_identifiable')
        if verify.usable(separate) and separate.get('value') == 'stated' and separate.get('words'):
            return separate['words']['text']
    return None


def visit_basis(reading, event_ids: Sequence[str]) -> Optional[dict]:
    """The usable basis of the visit events ``event_ids`` (contract 9.2's em_basis), else None."""
    for eid in event_ids:
        visit = (reading.events.get(eid) or {}).get('visit')
        if isinstance(visit, Mapping):
            basis = visit.get('basis')
            if verify.usable(basis) and basis.get('value') not in ('', 'not_stated'):
                return basis
    return None


# --- the separate-lesion modifier review (FINAL 7.9) ---------------------------------------------------------------------

def _lesions_of(reading, event_ids: Sequence[str]) -> list:
    out = []
    for eid in event_ids:
        event = reading.events.get(eid)
        if event is None or (event.get('catalogue_kind') or '') not in DISTINCT_LESION_KINDS:
            continue
        lesion = identity.verified_lesion(event)
        if lesion and lesion not in out:
            out.append(lesion)
    return out


def _distinct(reading, first: Sequence[str], second: Sequence[str]) -> bool:
    return bool(first) and bool(second) and all(
        two in ((reading.lesions.get(one) or {}).get('distinct_from') or ()) for one in first for two in second)


def modifier_review(reading, code: str, key: str, coded: Mapping, counted: Sequence[tuple]) -> Optional[dict]:
    """The separate-lesion modifier review of ``code`` (review_view._modifier_review's shape; never assigned): its own
    acts lie on verified lesions, and another counted code of its session accounts for acts on lesions every one of which
    is verified DISTINCT from its own (contract 6.3; an unresolved identity never pairs). ``coded``: {key: {session,
    events}}; ``counted``: (key, code) of the codes counted. None otherwise."""
    own = coded.get(key) or {}
    session = own.get('session') or ''
    lesions = _lesions_of(reading, own.get('events') or ())
    if not session or not lesions:
        return None
    partners = []
    for other_key, other_code in counted:
        theirs = coded.get(other_key) or {}
        if other_key == key or other_code == code or theirs.get('session') != session:
            continue
        other_lesions = _lesions_of(reading, theirs.get('events') or ())
        if _distinct(reading, lesions, other_lesions):
            partners.append((other_code, other_lesions, theirs.get('events') or ()))
    if not partners:
        return None

    def described(event_ids, kept) -> list:
        return [events.event_label(reading, reading.events[eid]) for eid in event_ids if eid in reading.events
                and identity.verified_lesion(reading.events[eid]) in kept]

    here = described(own.get('events') or (), lesions)
    pair = [(other, described(event_ids, kept)) for other, kept, event_ids in partners]
    words = {code: [events.lesion_words(reading, lesion) for lesion in lesions]}
    for other, kept, _ in partners:
        words[other] = sorted({events.lesion_words(reading, lesion) for lesion in kept})
    return {'kind': MODIFIER_REVIEW, 'codes': [code] + [other for other, _, _ in partners], 'service': session,
            'lesions': words, 'options': list(DISTINCT_LESION_OPTIONS),
            'text': checks.distinct_lesion_review_text(code, here, pair, ''), 'sources': [],
            'not_checked': list(DISTINCT_LESION_NOT_CHECKED)}
