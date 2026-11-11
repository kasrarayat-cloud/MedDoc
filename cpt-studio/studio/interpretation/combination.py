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

# DECISIONS D119 (the round-4 family parity audit, EGD gap H): a PEG Gemini files under the feeding-tube procedure is an
# act of the EGD done with it too - the one cross-family reading of the base rule, for the PEG kind only (the
# catalogue's own note: "A PEG placed during an EGD is reconciled under the upper GI family (its own EGD code)"; the
# installed release reads a PEG placed during an upper endoscopy as that endoscopy's act, services.py:196-200).
EGD, FEEDING_TUBE, PEG = 'gi.egd', 'gi.feeding_tube', 'peg'


def _acts_beside(family: str, session: Mapping, coding: Mapping, part: str) -> list:
    """The ``part`` ('reportable' or 'doubted') entries the base rule reads beside a base code of ``family`` matched to
    ``session``: the session's own, and - for an EGD code (DECISIONS D119) - the PEG entries of the encounter's
    feeding-tube session."""
    found = list(session.get(part) or ())
    if family == EGD:
        tube = _session(coding, FEEDING_TUBE) or {}
        found += [item for item in tube.get(part) or () if isinstance(item, Mapping) and item.get('kind') == PEG]
    return found


def base_included(members: Sequence[tuple], coding: Mapping) -> tuple:
    """A family's base (diagnostic) code matched to session S is held, never excluded, beside (a) another counted code
    of its family matched to S that accounts for an act (its profile covers one), (b) S's reportable events, or (c) S's
    doubted reportable-kind events: (base code, the other codes - or, with none, the labels of those acts), in member
    order. DECISIONS D119: an EGD base code matched to a done EGD session reads, as (b) and (c), the reportable and
    doubted PEG placements of the encounter's feeding-tube session too - "A 20 Fr pull-type PEG tube was placed under
    endoscopic guidance without difficulty." under "UPPER ENDOSCOPY WITH PEG PLACEMENT", which Gemini attributes to the
    feeding-tube procedure, left 43235 READY where the installed release reads the PEG as the EGD's act and holds it
    base_included. The overlay applies the same rule at read time over the same record."""
    bases = []
    for index, (code, family, session_id) in enumerate(members):
        session = _session(coding, session_id)
        if not _base(code) or session is None:
            continue
        others = tuple(other for position, (other, other_family, other_session) in enumerate(members)
                       if position != index and other_family == family
                       and (catalogue.code_profile(other) or catalogue.CodeProfile('')).covers
                       and other_session == session_id)
        reportable = _acts_beside(family, session, coding, 'reportable')  # D119
        doubted = _acts_beside(family, session, coding, 'doubted')
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
UNIDENTIFIED_PROCEDURE = 'A procedure CPT Studio could not identify'  # D94: the label of an act of family ''
# DECISIONS D109 (the round-4 refutation, findings 15 and 16; D94 narrowed): an act of gi.unsupported, or of no family
# (Gemini's procedure 'unknown'), never counts when its performer is verified to another clinician or facility, nor as
# an act Gemini places at another encounter that nothing places on the date. A CT "interpreted separately by the
# radiology service" (fb13's attested shape) and an imaging study named in the indication with an earlier time whose
# marker is missing (fb14's) made a procedure day, or asked the E/M's event_time, where c2e53f8e is READY; the office
# excision (D94) and an unidentified act today still count. DECISIONS D111 (the review of D109, problems 0-2): their
# date is read by C-3's one currency rule, as every other act's is (procedure_day) - never by Gemini's time value alone.
CURRENT_ONLY_FAMILIES = frozenset({'gi.unsupported', ''})
# DECISIONS D109 (findings 13 and 23): the same-day rule reads an act by its KIND, not only its family. An in-office
# band ligation Gemini files under the visit (procedure office_em: the note's only heading is the visit's) has family
# gi.office_em, outside SAME_DAY_FAMILIES, and made no procedure day: 99213 was READY where c2e53f8e holds it with
# separate_em. SAME_DAY_KINDS: every kind a procedural family's catalogue entry lists (its acts, bundled and unsupported
# acts), the examination kinds (an endoscopic examination such as an anoscopy; never one whose device is verified
# manual - a digital rectal examination, E13) and the umbrellas: every act kind but the visit's, prolonged time,
# moderate sedation and 'other'. Such an act of a family outside SAME_DAY_FAMILIES (gi.office_em, gi.em_other,
# gi.sedation) is another GI service (OTHER_GI's label, as the installed routing reads it) when C-3 counts it.
# DECISIONS D111 (the review of D109, problem 2): the kind arm reads an act of gi.unsupported or of no family too (a
# band ligation whose procedure Gemini left 'unknown' is another GI service, as c2e53f8e words it), and every arm reads
# its date by one currency rule (procedure_day).
SAME_DAY_KINDS = frozenset(
    kind for family in sorted(lexicon.PROCEDURAL_FAMILIES) if family in catalogue.CATALOGUE
    for kind in (catalogue.CATALOGUE[family].acts + tuple(item for item, _ in catalogue.CATALOGUE[family].bundled)
                 + tuple(item for item, _ in catalogue.CATALOGUE[family].unsupported_acts))
    if kind in mapping.CATALOGUE_KINDS) | mapping.EXAMINATION_KINDS | frozenset(mapping.UMBRELLAS)
# DECISIONS D130 (the round-4 em-same-day repair's parity note (a)): an act of kind 'other' that Gemini files under the
# visit (procedure office_em or em_other: VISIT_FAMILIES) made no procedure day, so the office excision of a sebaceous
# cyst read that way left 99213 READY where c2e53f8e, whose routing reads "Excision ... was performed" as gi.other,
# holds it with separate_em ("Other GI service is documented as performed on the same date"). Such an act is a
# POSSIBLE same-day procedure (never a done one: its kind names no procedure, D87) when the date of service is its own
# (facts.day_of ON) and its own STATUS words state that it was performed (DONE_STATEMENTS, read whole and word-bounded
# in those words only, EB1) - and never when the words that name the act (its kind and target words: NAMING_WORDS)
# name a test, an order, an interpretation, a lab or imaging, or counseling (NOT_PROCEDURES). Words that state neither
# ("was excised", "I performed", no status words) leave it uncounted, as before: a recorded cost, never a READY this
# rule makes.
VISIT_FAMILIES = frozenset(lexicon.family_of(procedure) for procedure in lexicon.EM_PROCEDURES)
DONE_STATEMENTS = ('was performed', 'were performed', 'was done', 'were done', 'underwent')
NAMING_WORDS = ('kind', 'target')  # the attributes whose words name the act (its status words state its status)
NOT_PROCEDURES = (
    ('test', ('test', 'tests', 'testing', 'ecg', 'ekg', 'electrocardiogram')),
    ('order', ('order', 'orders', 'ordered')),
    ('interpretation', ('interpretation', 'interpretations', 'interpreted')),
    ('lab', ('lab', 'labs', 'laboratory', 'laboratories', 'bloodwork', 'blood work')),
    ('imaging', ('imaging', 'image', 'images', 'ct', 'mri', 'mrcp', 'ultrasound', 'sonogram', 'sonography', 'x ray',
                 'x rays', 'xray', 'radiograph', 'radiographs', 'fluoroscopy', 'scan', 'scans')),
    ('counseling', ('counseling', 'counselling', 'counseled', 'counselled')),
)


def _own_words(event: Mapping, name: str) -> str:
    """The text of the words an event's attribute ``name`` cites ('' when it cites none)."""
    record = event.get(name)
    words = record.get('words') if isinstance(record, Mapping) else None
    return words.get('text') or '' if isinstance(words, Mapping) else ''


def _stated_procedure(event: Mapping) -> bool:
    """D130: whether an act of kind 'other' states by its own words that a procedure was performed - its status words
    hold a DONE_STATEMENTS phrase, and none of the words that name it (its kind and target words, NAMING_WORDS) names a
    NOT_PROCEDURES class. Reads those words only, never a passage."""
    if not lexicon.holds(_own_words(event, 'status'), DONE_STATEMENTS):
        return False
    named = [phrase for _, phrases in NOT_PROCEDURES for phrase in phrases]
    return not any(lexicon.holds(_own_words(event, name), named) for name in NAMING_WORDS)


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
    """The procedure day by DATE OF SERVICE (C-3). The acts it reads, never an E/M visit, stated done or in doubt, by
    any performer (as derived.procedure_day reads it, contract 8.3): an act of a procedure family or gi.other
    (SAME_DAY_FAMILIES, DECISIONS D81); an act of gi.unsupported or of no family (D94), never one whose performer is
    verified to another clinician or facility (D109); and an act of a procedural KIND (SAME_DAY_KINDS, D109) whatever
    procedure it is filed under - gi.office_em, gi.em_other, gi.sedation, and (DECISIONS D111) gi.unsupported or none -
    read as another GI service, done only with its kind usable too; and (DECISIONS D130) an act of kind 'other' filed
    under the visit (VISIT_FAMILIES) whose own status words state it was performed and whose own statement names no
    test, order, interpretation, lab, imaging or counseling (_stated_procedure): another GI service, only ever POSSIBLE,
    and only ON the date of service (D130's spec: "placed on the date") - OFF or UNDATABLE, it is not counted.
    DECISIONS D111: ONE currency rule for every one of them but D130's, facts.day_of - never Gemini's time value alone:
    - ON (a usable current time, or its own words or literals place it on the date: an earlier_encounter time worded
      "Earlier today" or "Earlier in the day" included): done with status, time, performer and procedure usable and
      positive, possible otherwise;
    - OFF (a usable earlier or future time whose words place it on no such day): never counts;
    - UNDATABLE (a time 'unknown', a current time that does not verify, an open time): listed for the E/M's time
      question - UNRESOLVED(time), never READY - except an act outside the procedure families and gi.other that Gemini
      places at another encounter (earlier_encounter or future, its marker missing): a history mention (finding 16's
      study named in the indication, an indication's banding) never counts, as at D109; an act of a procedure family or
      gi.other keeps C-3's question (D81: a hold, never a READY).
    ``codes``: (code, family, state, procedural, label) of the counted codes - a counted procedural code adds its label
    to the done (performed) or possible (held) list, as engine._encounter adds the selected procedural codes."""
    labels, possible, undatable = [], [], []
    for event in reading.events.values():
        family = event.get('family') or ''
        kind = events.value(event, 'kind')
        if kind in lexicon.EM_KINDS:
            continue
        by_family = family in SAME_DAY_FAMILIES and family not in CURRENT_ONLY_FAMILIES  # D81: procedure or gi.other
        manual = (kind == mapping.EXAMINATION and events.usable(event, 'technique')
                  and events.value(event, 'technique') == events.DIGITAL)
        by_kind = not by_family and kind in SAME_DAY_KINDS and not manual  # D109; D111: gi.unsupported and '' too
        by_statement = (kind == 'other' and family in VISIT_FAMILIES
                        and _stated_procedure(event))  # D130: possibly a procedure, by its own status words
        if not (by_family or by_kind or by_statement or family in CURRENT_ONLY_FAMILIES):
            continue  # an act of no procedural kind filed under the visit, its sedation or another E/M (D109)
        if family in CURRENT_ONLY_FAMILIES and events.verified_other_performer(event):
            continue  # D109 (finding 15): never another clinician's or facility's verified read
        day = facts.day_of(event, effective)
        if day == facts.OFF or (by_statement and day != facts.ON):
            continue  # C-3: another date; D130: an act read by its statement counts only ON the date
        if (day == facts.UNDATABLE and not by_family
                and events.value(event, 'time') in ('earlier_encounter', 'future')):
            continue  # D109, D111 (finding 16): a history mention Gemini places at another encounter
        status = events.value(event, 'status')
        if status not in verify.POSITIVE + ('uncertain',):
            continue
        label = (profiles.PROFILES[OTHER_GI].label if by_kind or by_statement
                 else profiles.PROFILES[family].label if family in profiles.PROFILES
                 else family or UNIDENTIFIED_PROCEDURE)  # D94; D109, D130: by its kind or statement, another GI service
        if day == facts.ON:
            needed = ('status', 'performer', 'procedure', 'time') + (('kind',) if by_kind else ())
            if (not by_statement and status in verify.POSITIVE
                    and all(events.usable(event, name) for name in needed)):  # D130: never done by its words alone
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
    form), read from TODAY's visit only (DECISIONS D113; FINAL 7.9: "its visit event's separately_identifiable"): the
    words of the first usable ``stated`` separately_identifiable of the visit events ``event_ids`` (the code's own),
    else of another visit event of this encounter - a usable current_encounter time and no performer verified to
    another clinician or facility. Never another encounter's visit ("At her office visit on 10/01/2026, a significant,
    separately identifiable E/M service was provided."): the installed reader refuses a statement about another
    encounter. A ``stated`` value whose own words are negated (lexicon.negation, the reader a denial is verified by) is
    no statement, and a denial never releases; neither silences another visit's statement (FRESH-2 fb10: the GERD
    visit stated beside the rectal bleeding assessment that "is not a separate E/M service"). None when there is
    none."""
    own = [reading.events[eid] for eid in dict.fromkeys(event_ids) if eid in reading.events]
    mine = {event['id'] for event in own}
    today = [event for event in reading.events.values() if event['id'] not in mine
             and events.usable(event, 'time') and events.value(event, 'time') == 'current_encounter'
             and not events.verified_other_performer(event)]
    for event in own + today:
        visit = event.get('visit')
        separate = visit.get('separately_identifiable') if isinstance(visit, Mapping) else None
        if not verify.usable(separate) or separate.get('value') != 'stated' or not separate.get('words'):
            continue
        words = separate['words']['text']
        if not lexicon.negation(words):
            return words
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
