"""Coverage and completeness over the event inventory (design/FINAL.md 7.7 and 7.8, as design/ADJUDICATION.md C-2, C-4 and
C-5 amend them): bundling, sessions, reportable events, what the counted codes cover, the unresolved items with their
second-review marks, and coding completeness - a port of reconcile.py:662-1023 onto structured fields. Pure set logic
over stored attributes: no text is read for meaning and no pattern is matched.

BUNDLING (7.7; COMMON_BUNDLED, catalogue.py:163-175):
- lift_injection: an injection or tattoo whose verified part_of names a current performed EMR or ESD, or whose verified
  purpose is lift_for_resection and whose verified lesion is that resection's; and (C-5) an injection - never a tattoo,
  never one whose hemostasis purpose is verified (that is bleeding control) - beside a current performed EMR or ESD of its
  session at compatible places, neither naming an unresolved lesion and the two not verified on two lesions. Where its
  lesion or place is unresolved the relations step recorded a bundling_identity: asked, never READY (bundling_doubt).
- resection_technique: a snare or hot biopsy part_of an EMR or ESD, or on the same verified lesion as one.
- procedural adjunct (DECISIONS D30): an ablation or a bleeding control verifiably part_of a current performed removal
  (snare, EMR, hot biopsy, ESD), or on that removal's verified lesion - the removal's adjunct coagulation, the control of
  bleeding it causes - is included in the removal and never reported alone (PROCEDURAL_ADJUNCT), as resection_technique.
  D79: a removal attempted and not completed is such a whole too (adjunct_whole), for this bundling and for the
  procedural_adjunct question (bundling_doubt).
- biopsy_of_removed_lesion: a biopsy of the same verified lesion as a current performed removal (snare, EMR, hot biopsy,
  ESD) where that lesion is single, or - whatever the multiplicity (C-2) - where the two acts cite a passage in common;
  a group lesion whose two acts sit in separate passages has a bundling_identity relation instead.
- stent_included (DECISIONS D45): an ERCP sphincterotomy or dilation beside a current performed ERCP stent placement or
  exchange of its session is part of the stent act of its duct (43274 and 43276 include "sphincterotomy, when performed"
  and pre- and post-dilation); both acts' ducts verified and different (a biliary sphincterotomy beside a pancreatic
  stent) keep it a separate service, and a duct verified on neither act - or the ampulla, which opens on both - never
  sets them apart (fail-closed: held as part of the stent, never READY alone).
- clip and cannulation: never separately reported (NOT_REPORTED); a clip whose hemostasis purpose is verified is
  bleeding control (its catalogue kind). Each family entry's own bundled kinds as the catalogue states them (the ERCP's
  contrast injection).

SESSIONS (7.8): a family's session is its current examination event (an endoscopic family's: any examination but a
digital one, whose device is verified as manual - FINAL 5.6, E13); two current examinations of one family leave it
unresolved for every rule that reads it. A session's examination ``part_of`` an examination of another family is that
session's included portion (C3), and - structurally (C-4) - a current performed EGD examination in an encounter with a
current performed upper-tract EUS examination is the EUS's endoscopic portion.

REPORTABLE (7.8): performed, current and by the documenting team (all usable); a kind of the family's catalogue acts,
not the examination, not NOT_REPORTED, not bundled. COVERED: an event a counted code's decision read (its supporting
events, or the candidates its question is about), or a session included through catalogue.includes_examination. The
unresolved items: no_proposal, not_covered, coverage_unknown and unsupported as reconcile.reconcile gives them, and
in_doubt - a reportable kind whose candidate a relation or an unusable attribute blocks and that no code depends on: it
gets a service-scope question and keeps coding completeness open. The second-review mark is True on a no_proposal or
not_covered item (its events are done: status, time and performer usable) with an index below SECOND_REVIEW_CHECKED.

Imports nothing from studio.gi but the reference tables (FINAL 3.1).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Optional

from studio.gi import catalogue
from studio.interpretation import ENGINE_VERSION, events, identity, lexicon, mapping, relations, verify, wording
from studio.types import ClarificationSpec

SECOND_REVIEW_CHECKED = 64  # engine.SECOND_REVIEW_CHECKED (copied, pinned equal)
COMMON = dict(catalogue.COMMON_BUNDLED)
RESECTIONS = frozenset({'emr', 'esd'})
# D30: the kinds a removal's procedural adjunct can be, and why such an adjunct is never separately reported (CPT Studio's
# own rule over the event structure, in COMMON_BUNDLED's form; the catalogue's table is the legacy one and is not edited)
ADJUNCT_KINDS = relations.PROCEDURAL_ADJUNCTS
PROCEDURAL_ADJUNCT = ('An ablation or a control of bleeding done as part of a removal at the same session - on the lesion '
                      'it removes, or of the bleeding it causes - is part of that removal, not a separate service '
                      '(internal profile rule).')
# D45: an ERCP stent placement or exchange includes a sphincterotomy and a dilation of its own duct.
ERCP = 'gi.ercp'
STENT_KINDS = frozenset({'stent', 'stent_exchange'})
STENT_INCLUDED_KINDS = frozenset({'sphincterotomy', 'dilation'})
DUCT_SIDES = frozenset({'biliary', 'pancreas'})
STENT_INCLUDED = ('A sphincterotomy or a dilation done at the same ERCP as a stent placement or exchange in the same duct '
                  'is part of that stent service (the stent code includes sphincterotomy and pre- and post-dilation, '
                  'when performed); one of the other duct is a separate service (internal profile rule).')
# The regions of the lower tract: an EUS event placed there is a lower EUS, of which no EGD is the endoscopic portion.
LOWER_REGIONS = frozenset({'colon', 'rectum', 'anus'})
NOT_ACT_KINDS = mapping.EXAMINATION_KINDS | frozenset(mapping.UMBRELLAS)
CODING_VERSION = ENGINE_VERSION  # event_coding's version: its reader (overlay.py) refuses any other


# --- bundling (7.7) -------------------------------------------------------------------------------------------------------

def possibly_current(event: Mapping) -> bool:
    """DECISIONS D62 (D54's review), as D68 and D98 complete it: whether ``event`` may be of this encounter - Gemini
    gave it a current_encounter time, verified or not, WHATEVER its reasons, or (D98) a time it gave as 'unknown'. A
    current time left unverified - D35's other occasion, D54's unanchored words, a date that differs from the service
    date or that no date checks (D67), words that do not bind - is a doubt about the event's own code, never an absence
    for the rules that hold OTHER codes by it: a session's examinations, a removal its parts are bundled into, the acts
    two codes compete for. Read as an absence, unverifying an aside's examination resolved today's session to the other
    examination (45385 READY on the index colonoscopy's snare), and unverifying a removal's time released the biopsy of
    the lesion it removed. D68: neither D35's marker nor a date_mismatch proves another occasion - "Next", "Later in the
    procedure" and "At that time" are sequence words within one procedure, and a clock time ("At 2030") reads as a year
    - so they are doubts too: the part stays held, and a mislabelled examination beside today's leaves the session
    unresolved (asked, never the other examination's). D98 (the round-4 refutation, finding 7): an explicit unknown is
    absent (FINAL C6) - it never supports a code and gives UNRESOLVED in pairing, and it never makes a non-match either:
    read as not current, a snare whose time Gemini left 'unknown' ("Once, a 22 mm polyp ... was removed piecemeal")
    released the biopsy of the polyp it removed, 45380 READY while 45385 was asked its time. Only an earlier_encounter
    or future time is not current, verified or not: Gemini placed the event on another occasion."""
    time = event.get('time')
    return isinstance(time, Mapping) and time.get('value') not in ('earlier_encounter', 'future')


def current_performed(event: Mapping) -> bool:
    """A whole a part can be bundled into: performed (usable), and current - its time current_encounter, verified or
    not (D62: possibly_current) - never a statement or an act Gemini places on another occasion."""
    return (events.usable(event, 'status') and events.value(event, 'status') == 'performed'
            and possibly_current(event))


def _same_session(reading, whole: Mapping, part: Mapping) -> bool:
    return relations.procedure_row(reading.context, whole, part).result != relations.DIFFERENT


def _part_of(event: Mapping) -> str:
    part = event.get('part_of')
    if isinstance(part, Mapping) and part.get('state') == 'verified' and not part.get('open'):
        return part.get('value') or ''
    return ''


def _purpose(event: Mapping) -> str:
    return events.value(event, 'purpose') if events.usable(event, 'purpose') else ''


def _wholes(reading, part: Mapping, kinds) -> list:
    return [whole for whole in reading.events.values() if whole is not part and whole.get('catalogue_kind') in kinds
            and current_performed(whole) and _same_session(reading, whole, part)]


def _compatible(first, second) -> bool:
    return bool(first) and bool(second) and all(lexicon.compatible(one, two) for one in first for two in second)


def duct_side(event: Mapping) -> str:
    """D45: the duct an ERCP event's verified target lies in - 'biliary' or 'pancreas' - else '': a target that is not
    verified or not placed, the ampulla (it opens on both ducts), or a place that is no duct."""
    landmark = mapping.target_landmark(event)
    if not landmark or landmark == 'ampulla':
        return ''
    side = mapping.region(landmark)
    return side if side in DUCT_SIDES else ''


def adjunct_whole(event: Mapping) -> bool:
    """DECISIONS D79 (the round-3 refutation, finding 12): a whole a removal's procedural adjunct (D30, D41) can belong
    to - a removal current as current_performed reads it (D62: possibly_current), and performed OR begun and not
    completed (status attempted_not_completed, usable). The bleeding an attempted snare causes, or the coagulation of an
    attempted resection's margins, is that attempt's own (CPT: control of bleeding the procedure causes), so beside an
    attempted removal the adjunct is asked (bundling_doubt) or bundled (bundled_reason) exactly as beside a performed
    one - never READY alone. A statement, a planned act and an act on another occasion are no whole."""
    return (events.usable(event, 'status') and events.value(event, 'status') in verify.POSITIVE
            and possibly_current(event))


def bundled_reason(reading, event: Mapping) -> str:
    """Why ``event`` is part of another documented act and never separately reported (module docstring), or ''."""
    kind = event.get('catalogue_kind') or ''
    raw = events.value(event, 'kind') or ''
    if kind in catalogue.NOT_REPORTED:
        return COMMON.get(kind, '')
    entry = catalogue.entry(event.get('family', ''))
    own = dict(entry.bundled) if entry is not None else {}
    if kind in own and kind not in COMMON and kind != 'biopsy':  # a family's own bundled kind (ERCP's contrast)
        return own[kind]
    whole_of = _part_of(event)
    lesion = identity.verified_lesion(event)
    if kind in mapping.ONE_ACT:
        for whole in _wholes(reading, event, RESECTIONS):
            if whole_of == whole['id']:
                return COMMON['lift_injection']
            other = identity.verified_lesion(whole)
            if lesion and other:
                if lesion == other and (raw == 'injection' or _purpose(event) == 'lift_for_resection'):
                    return COMMON['lift_injection']
                continue
            if raw != 'injection' or reading.relations_of(event['id'], (relations.BUNDLING,)):
                continue
            identities = (whole['target'].get('identity'), event['target'].get('identity'))
            places, own_places = reading.context.places(whole), reading.context.places(event)
            if identity.UNRESOLVED not in identities and _compatible(places, own_places):  # C-5
                return COMMON['lift_injection']
        return ''
    if kind in relations.RESECTION_TECHNIQUES:
        for whole in _wholes(reading, event, RESECTIONS):
            other = identity.verified_lesion(whole)
            if whole_of == whole['id'] or (lesion and lesion == other):
                return COMMON['resection_technique']
        return ''
    if event.get('family') == ERCP and kind in STENT_INCLUDED_KINDS:  # D45: part of the stent act of its duct
        side = duct_side(event)
        for whole in _wholes(reading, event, STENT_KINDS):
            other = duct_side(whole)
            if whole.get('family') == ERCP and (not side or not other or side == other):
                return STENT_INCLUDED
        return ''
    if kind in ADJUNCT_KINDS:  # D30: a removal's procedural adjunct, by its verified part_of or the removal's lesion -
        for whole in reading.events.values():  # D79: of a removal performed or attempted (adjunct_whole)
            if (whole is event or whole.get('catalogue_kind') not in mapping.REMOVAL_MEMBERS or not adjunct_whole(whole)
                    or not _same_session(reading, whole, event)):
                continue
            if whole_of == whole['id'] or (lesion and lesion == identity.verified_lesion(whole)):
                return PROCEDURAL_ADJUNCT
        return ''
    if kind == 'biopsy' and lesion:
        for whole in _wholes(reading, event, mapping.REMOVAL_MEMBERS):
            if identity.verified_lesion(whole) != lesion:
                continue
            single = (reading.lesions.get(lesion) or {}).get('multiplicity') == 'single'
            common = set(events.own_passages(event)) & set(events.own_passages(whole))
            if single or common:  # C-2: one passage in common bundles whatever the multiplicity
                return COMMON['biopsy_of_removed_lesion']
    return ''


def bundling_doubt(reading, event: Mapping) -> Optional[dict]:
    """The bundling_identity relation that makes ``event``'s bundling depend on an identity not established, whose
    whole is a current performed act (FINAL 7.7: asked, never READY) - or, for a removal's procedural adjunct, a removal
    performed or attempted (D79: adjunct_whole) - or None."""
    for relation in reading.relations_of(event['id'], (relations.BUNDLING,)):
        whole = reading.events.get(relation['statement'])
        if whole is not None and (current_performed(whole) or (relation.get('reason') == 'procedural_adjunct'
                                                               and adjunct_whole(whole))):
            return relation
    return None


# --- sessions (7.8) -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Session:
    """One family's documented service at this encounter: ``event`` its one current examination ('' for none, or when
    two leave it ``unresolved``), ``part_of`` the session it is the endoscopic portion of, ``possibly_part_of`` the
    session it may be the endoscopic portion of (DECISIONS D70: that session's examination is only possibly current;
    the base-within rule reads it, nothing reads the session as included), ``done`` whether the family has a done
    event, ``incomplete`` whether its examination was begun and not completed."""
    id: str
    family: str
    kind: str
    label: str
    event: str = ''
    examinations: tuple = ()
    part_of: str = ''
    unresolved: bool = False
    done: bool = False
    incomplete: bool = False
    events: tuple = ()
    possibly_part_of: str = ''
    # DECISIONS D87 (integration of round 3): the examinations D62 reads as only POSSIBLY this encounter's. They are
    # doubts and never facts: ``examinations`` holds the done ones alone, so no reader takes a fact (a target, a reach, a
    # class) from an examination that may be another occasion's; ``unresolved`` and ``event`` still count them (D62)
    possible: tuple = ()


def done_examinations(reading, family: str) -> list:
    """DECISIONS D69-D71: the examinations of ``family`` done at this encounter, in the reading's order - done
    (events.done: a usable performed or begun status, a usable current_encounter time and a usable documenting-team
    performer), a usable kind, an examination kind, and no digital examination (FINAL 5.6 E13). These are the
    examinations a session's own ``event`` is chosen from (sessions' ``exams``, pinned equal), never D62's possible
    ones, nor a planned, historical, denied or doubted examination."""
    return [event for event in reading.events.values() if event.get('family') == family and events.done(event)
            and events.usable(event, 'kind') and event.get('catalogue_kind') in mapping.EXAMINATION_KINDS
            and events.endoscopic_examination(event)]


# DECISIONS D96: the kinds of an EUS ACT that are the EUS's own - the catalogue's gi.eus acts besides the examination: the
# fine-needle aspiration or biopsy, an injection under EUS guidance (a celiac block or neurolysis, a fiducial marker) and
# a drainage - read from the catalogue (pinned equal to it). Any other kind filed under the EUS (a rectal medication read
# as 'other', a forceps biopsy, a clip) is no EUS act for C-4.
EUS_ACTS = tuple(kind for kind in catalogue.entry('gi.eus').acts if kind not in mapping.EXAMINATION_KINDS)


def eus_act(event: Mapping) -> bool:
    """DECISIONS D96 (the round-4 refutation, findings 0 and 2): a DONE EUS act C-4 may read the lower tract from - an
    event of the EUS family done at this encounter (events.done), its kind usable and one of EUS_ACTS, and its own
    PROCEDURE usable as 'eus'. An act whose family is in doubt (its procedure unsettled: a colonoscopy's 'Random biopsies
    were taken from the rectum.' filed under 'eus' with no words, D75) is a doubt, never a fact (D87): read as one, it
    made the EUS session lower and 43235 READY beside 43242. DECISIONS D121: with no done EUS examination, these acts
    are the session C-4 reads - placed nowhere lower, an upper EUS whose endoscopic portion today's EGD is."""
    return (event.get('family') == 'gi.eus' and event.get('catalogue_kind') in EUS_ACTS and events.done(event)
            and events.usable(event, 'kind') and events.usable(event, 'procedure')
            and events.value(event, 'procedure') == 'eus')


def lower_evidence(reading) -> list:
    """DECISIONS D96 (amends D88): what C-4 reads the lower tract from, in the reading's order - today's DONE endoscopic
    EUS examinations (done_examinations: never a digital or manual examination, FINAL 5.6 E13) and today's DONE EUS acts
    (eus_act). D88 read every done EUS event with a usable kind, so a digital rectal examination filed under the EUS
    heading ("Pre-procedure examination: digital rectal examination showed brown stool and no palpable mass.", the
    attested C2MEM-029 r1 E9 form) or a rectal medication read as an EUS event of kind 'other' made the EUS session lower:
    C-4 switched off and 43235 went READY beside 43242, where the installed release holds it base_included."""
    return done_examinations(reading, 'gi.eus') + [event for event in reading.events.values() if eus_act(event)]


def unsettled_eus_examinations(reading) -> list:
    """DECISIONS D97 (the round-4 refutation, finding 10): the EUS examinations whose KIND is not usable - an event of the
    EUS family that is an examination by its catalogue kind or by its unusable kind's value (kind words that do not
    locate: 'EUS' or 'endoscopic ultrasound' cited from an act line, or joined across two sentences) - stated performed or
    begun, possibly current (D62: its time current_encounter, verified or not) and no digital examination (FINAL 5.6 E13).
    Neither done_examinations nor D62's possible ones hold them (both need a usable kind), so C-4 skipped them: the EUS
    session had no examination, the EGD was part of nothing, and 43235 was READY beside 43242. They are possible upper EUS
    examinations instead (D70's doubt): a doubt, never a fact, so never the session and never lower evidence."""
    return [event for event in reading.events.values() if event.get('family') == 'gi.eus'
            and not events.usable(event, 'kind')
            and (event.get('catalogue_kind') in mapping.EXAMINATION_KINDS
                 or events.value(event, 'kind') == mapping.EXAMINATION)
            and events.endoscopic_examination(event) and possibly_current(event)
            and events.value(event, 'status') in verify.POSITIVE]


def doubted_eus_acts(reading) -> list:
    """DECISIONS D123 (the round-4 review of D96, problems 1 and 2): today's DONE acts filed under the EUS that C-4 cannot
    read as the EUS's own (eus_act) - an act of an EUS kind whose kind or procedure is not usable (an FNA filed under
    'eus' with no words: procedure_unsettled), or an act of a kind that is no EUS act (a forceps biopsy: 'Radial EUS was
    then performed; forceps biopsies of the rectal mass were taken.') - in the reading's order. They are doubts, never
    facts (D87): never lower evidence (D96 kept), and never the reason the EGD is read as the EUS's endoscopic portion. An
    examination (a digital rectal examination, FINAL 5.6 E13) and an event of no catalogue kind (a rectal medication read
    as 'other', DECISIONS D96 finding 0) are not acts here."""
    return [event for event in reading.events.values() if event.get('family') == 'gi.eus' and events.done(event)
            and event.get('catalogue_kind') and event.get('catalogue_kind') not in mapping.EXAMINATION_KINDS
            and not eus_act(event)]


def possible_eus_acts(reading) -> list:
    """DECISIONS D121 (D62's rule for an act): the EUS acts of an EUS kind (EUS_ACTS) stated performed or begun and only
    POSSIBLY of this encounter (possibly_current, not done: 'After the EGD, EUS-FNA of a 22 mm hypoechoic mass in the
    pancreatic body was performed ...', its time unanchored), in the reading's order. A possible upper EUS - a doubt,
    never the session and never lower evidence: read as an absence, it left 43235 READY beside 43242, where the
    installed release holds it base_included."""
    return [event for event in reading.events.values() if event.get('family') == 'gi.eus'
            and event.get('catalogue_kind') in EUS_ACTS and not events.done(event) and possibly_current(event)
            and events.value(event, 'status') in verify.POSITIVE]


# DECISIONS D123 (the round-4 review of D96, problem 0): the regions of a verified target landmark that place an act in no
# organ of its own - no region (an unplaced landmark, 'other') and a lymph node, which lies beside any organ - where the
# act's own target words are read for a landmark too (eus_places)
UNPLACED_REGIONS = frozenset({'', 'node'})


def eus_places(event: Mapping) -> list:
    """The places C-4 reads an EUS event at: its verified target landmark, its usable reach, and - for an ACT (DECISIONS
    D96, the round-4 refutation, finding 12) - every landmark its own verified target's words name (verify.landmark_words
    over those words, EB1's landmark literal): 'a perirectal lymph node in the rectum' at the verified landmark
    'lymph_node' names the rectum too. Read at its landmark alone, such an FNA placed the radial EUS nowhere lower, the
    EGD became its endoscopic portion, and the EGD's own no_proposal item and second-review mark were dropped.
    DECISIONS D123 (the round-4 review of D96, problem 0): the words are read only where the verified landmark places the
    act in no organ of its own (UNPLACED_REGIONS: a lymph node, or no region). An act verified at an organ is at that
    organ, whatever its words name beside it: read at 'pancreatic pseudocyst abutting the transverse colon', an upper
    drainage of the pancreas made the EUS lower, and 43235 was READY beside 43240 (and the same words cancelled D70's
    doubt beside 43242), where 437b708bb and the installed release hold it base_included."""
    places = [mapping.target_landmark(event)]
    extent = event.get('extent')
    if verify.usable(extent):
        places.append(extent.get('value', ''))
    target = event.get('target')
    if (event.get('catalogue_kind') not in mapping.EXAMINATION_KINDS and verify.usable(target)
            and mapping.region(places[0]) in UNPLACED_REGIONS):  # D123: never beside an organ landmark of its own
        words = target.get('words')
        text = (words.get('text') or '') if isinstance(words, Mapping) else ''
        if text:
            places.extend(verify.landmark_words(target.get('value') or '', text).literals.get('landmarks', ()))
    return places


def _lower_eus(found) -> bool:
    """Whether one of the EUS events ``found`` is placed in the lower tract (LOWER_REGIONS) at one of its places
    (eus_places). DECISIONS D69 (the round-3 refutation, finding 2): C-4 reads only the events it is given - today's
    done ones (lower_evidence, D96) - never every EUS event of the reading: a planned ("Plan: rectal EUS ... in 2 weeks"),
    historical ("a radial EUS of the rectum in 2024") or denied ("No rectal EUS was performed.") rectal EUS line made the
    EUS session lower and freed 43235 beside 43242, where the installed release holds it."""
    for event in found:
        if any(mapping.region(place) in LOWER_REGIONS for place in eus_places(event) if place):
            return True
    return False


def _placed_eus(found) -> bool:
    """DECISIONS D123: whether one of the EUS events ``found`` places the EUS at an organ of the tract or beside it - a place
    of a region that is neither lower (LOWER_REGIONS: _lower_eus reads those) nor UNPLACED_REGIONS (no region, a lymph
    node, which lies beside any organ)."""
    return any(mapping.region(place) not in LOWER_REGIONS | UNPLACED_REGIONS
               for event in found for place in eus_places(event) if place)


def sessions(reading) -> dict:
    """{session id (the family slug): Session} of every family with an event, in the families' order."""
    by_family: dict = {}
    for event in reading.events.values():
        family = event.get('family') or ''
        if family:
            by_family.setdefault(family, []).append(event)
    found = {}
    for family in sorted(by_family, key=lambda value: (lexicon.FAMILY_ORDER.index(value)
                                                       if value in lexicon.FAMILY_ORDER else 99, value)):
        members = by_family[family]
        done = [event for event in members if events.done(event) and events.usable(event, 'kind')]
        exams = [event for event in done if event.get('catalogue_kind') in mapping.EXAMINATION_KINDS
                 and events.endoscopic_examination(event)]  # FINAL 5.6 E13: a manual examination is no session
        # D62: an examination Gemini read as done at this encounter whose time is not verified may be this
        # encounter's too: beside a done one it leaves the session unresolved, and it is never the session itself
        possible = [event for event in members if event not in exams and events.usable(event, 'kind')
                    and event.get('catalogue_kind') in mapping.EXAMINATION_KINDS
                    and events.endoscopic_examination(event) and possibly_current(event)
                    and events.value(event, 'status') in events.verify.POSITIVE]
        service = mapping.service_kind(family)
        session = Session(id=family, family=family, kind=service,
                          label=wording.kind_label(service) if service else wording.family_label(family),
                          event=exams[0]['id'] if len(exams) == 1 and not possible else '',
                          examinations=tuple(event['id'] for event in exams),
                          possible=tuple(event['id'] for event in possible),  # D87
                          unresolved=len(exams) + len(possible) >= 2,
                          done=bool(done), incomplete=bool(exams) and all(
                              events.value(event, 'status') == 'attempted_not_completed' for event in exams),
                          events=tuple(event['id'] for event in members))
        found[family] = session
    # C-4 reads the gi.eus session's DONE examinations only (DECISIONS D69, D70): an EUS examination D62 reads as only
    # possibly current is never the session (D62), so it never makes today's EGD the EUS's endoscopic portion - read as
    # one, another occasion's EUS ("These were the findings at her index EUS") dropped the EGD's own no_proposal item and
    # its second-review mark. Such an examination is a doubt instead: an upper EUS examination that may be this
    # encounter's, beside no done one, leaves the EGD its own items and holds its base code as C-4 would
    # (``possibly_part_of``, which only combination.base_within reads), never READY.
    eus = found.get('gi.eus')
    done_eus = done_examinations(reading, 'gi.eus') if eus is not None else []
    done_ids = {event['id'] for event in done_eus}
    possible_eus = [reading.events[eid] for eid in (eus.possible if eus is not None else ()) if eid not in done_ids]
    # D88 (integration of D69/D70), as D96 narrows it: the lower tract is read from today's DONE endoscopic EUS
    # examinations and DONE EUS acts of the EUS's own kinds whose procedure is usable (lower_evidence) - an act's verified
    # target words as well as its landmark (a radial EUS naming no place whose done FNA samples 'a perirectal lymph node
    # in the rectum' is lower) - never from a digital examination, an act of another kind, an act whose family is in
    # doubt, or a POSSIBLE examination: a possible rectal aside cancelled D70's doubt and made 43235 READY beside 43242.
    # D70's doubt stands while some possible EUS examination - D62's, or (D97) one whose kind is not usable - is not
    # itself placed lower and no done EUS event is
    evidence = lower_evidence(reading) if eus is not None else []
    doubts = possible_eus + (unsettled_eus_examinations(reading) if eus is not None else [])  # D62's, and D97's
    lower = _lower_eus(evidence)
    # D121 (the round-4 parity audit, EUS gap 1): an EUS told only through its done acts - a done EUS act (eus_act: an
    # FNA, an injection, a drainage) and no done examination - is the session C-4 reads: today's EGD is its endoscopic
    # portion, as the installed release reads an EUS its act makes (services._included). Read from examinations alone,
    # 'EUS-FNA of a 22 mm hypoechoic mass in the pancreatic body was performed' beside an EGD left 43235 READY beside
    # 43242. Beside a possible examination (D62's, D97's) it is the doubt below, never the fact
    acts = [event for event in evidence if eus_act(event)]
    session_events = done_eus or acts
    # D123 (the round-4 review of D96, problems 1 and 2): a done act filed under the EUS that is not the EUS's own
    # (doubted_eus_acts: its family or kind in doubt, or a forceps biopsy) is never lower evidence (D96) - and, placed
    # lower where no done EUS event places the EUS, never lets C-4 read the EGD as the EUS's endoscopic portion either:
    # its doubt makes the upper reading a doubt (possibly_part_of), so the EGD keeps its own items and 43235 is held
    doubted = doubted_eus_acts(reading) if eus is not None else []
    possibly_lower = not lower and not _placed_eus(evidence) and _lower_eus(doubted)
    upper_eus = bool(session_events) and not lower and not possibly_lower and (bool(done_eus) or not doubts)
    # D87, D121: an act of an EUS kind whose own family or kind is in doubt, or that is only possibly of this encounter
    # (D62), is a possible upper EUS, never a fact
    upper_doubts = doubts + [event for event in doubted if event.get('catalogue_kind') in EUS_ACTS] + (
        possible_eus_acts(reading) if eus is not None else [])
    possibly_upper = not upper_eus and not lower and (
        bool(session_events) or any(not _lower_eus([event]) for event in upper_doubts))
    for family, session in list(found.items()):
        # D87: a session left unresolved only by POSSIBLE examinations keeps the structure of its one done examination
        # (C3, C-4) - read without it, an aside EGD ("Previously, ...") beside today's EGD within an upper EUS asked
        # 43235's extent instead of its base_included question
        own = session.event or (session.examinations[0] if len(session.examinations) == 1 else '')
        if not own:
            continue
        exam = reading.events[own]
        whole = reading.events.get(_part_of(exam))
        part_of = ''
        if whole is not None and whole.get('family') in found and whole.get('family') != family \
                and whole.get('catalogue_kind') in mapping.EXAMINATION_KINDS:
            part_of = whole['family']  # C3: the endoscopic portion of another examination
        elif family == 'gi.egd' and upper_eus:
            part_of = 'gi.eus'  # C-4: structurally, an EGD within an upper EUS
        elif family == 'gi.egd' and possibly_upper:
            found[family] = replace(session, possibly_part_of='gi.eus')  # D70: within an upper EUS, possibly
        if part_of:
            found[family] = replace(session, part_of=part_of)
    return found


def session_of(sessions_: Mapping, family: str) -> str:
    """The session id a code of ``family`` is matched to ('' when the family has none at this encounter)."""
    return family if family in sessions_ and sessions_[family].done else ''


# --- reportable and doubted events ---------------------------------------------------------------------------------------

def reportable_kind(event: Mapping) -> bool:
    entry = catalogue.entry(event.get('family', ''))
    kind = event.get('catalogue_kind') or ''
    return (entry is not None and kind in entry.acts and kind not in NOT_ACT_KINDS
            and kind not in catalogue.NOT_REPORTED)


def reportable(reading, event: Mapping) -> bool:
    """7.8: performed, current and by the documenting team, of a reportable kind, not bundled."""
    return (events.done(event) and events.value(event, 'status') == 'performed' and events.usable(event, 'kind')
            and events.usable(event, 'procedure') and reportable_kind(event) and not bundled_reason(reading, event))


def doubted(reading, event: Mapping) -> bool:
    """A reportable-kind event in doubt (FINAL 7.9 base rule (c), the event form of listed_in_doubt and
    listed_contradicted; fail-closed): stated positive or uncertain, not verified at another time or by another performer,
    and its status uncertain, a CONTRADICTION, DOUBT or UNRESOLVED relation on it, or an attribute of its own statement
    (kind, status, time, performer) unusable - or (DECISIONS D75, round 3, finding 17) stated positive and possibly
    current (D62) with its PROCEDURE not usable (unverified or opened: Gemini's 'EGD' heading cited for the biopsies
    under it, too short to locate, with two current families the default does not settle) while its family has a
    current session (a done examination). Such an act may belong to any current family, so it is never an absence: read
    as one, it was neither reportable nor doubted and 43235 went READY beside four EGD biopsies, where the installed
    release asks base_included. Unverified is a doubt, never an absence (D62's rule, for the procedure). This reads the
    act in the session of the family its procedure names, the one session event_coding lists it in; an act whose
    procedure is absent has no family and no session (the cross-family part of D75 is recorded, not built here)."""
    if not reportable_kind(event) or events.value(event, 'status') not in verify.POSITIVE + ('uncertain',):
        return False
    if events.verified_other_time(event) or events.verified_other_performer(event):
        return False
    if events.value(event, 'status') == 'uncertain' or reading.relations_of(event['id']):
        return True
    if not all(events.usable(event, name) for name in ('kind', 'status', 'time', 'performer')):
        return True
    return (not events.usable(event, 'procedure') and possibly_current(event) and any(
        other.get('family') == event.get('family') and events.done(other) and events.usable(other, 'kind')
        and other.get('catalogue_kind') in mapping.EXAMINATION_KINDS and events.endoscopic_examination(other)
        for other in reading.events.values()))


def _entry(reading, event: Mapping) -> dict:
    lesion = identity.verified_lesion(event)
    return {'event': event['id'], 'kind': event.get('catalogue_kind') or '',
            'label': wording.act_label(event.get('catalogue_kind') or ''), 'lesion': lesion,
            'describe': events.event_label(reading, event)}


# --- coverage and the unresolved items (reconcile.py:793-923, ported onto events) ---------------------------------------

@dataclass(frozen=True)
class Counted:
    """A counted, decidable code as coverage reads it: its key, code, family and the events its decision read (its
    supporting events first)."""
    key: str
    code: str
    family: str
    supporting: tuple = ()
    read: tuple = ()


@dataclass
class Coverage:
    unresolved: list = field(default_factory=list)  # item dicts (completeness['unresolved_items'] without the mark)
    bundled: list = field(default_factory=list)
    covered: dict = field(default_factory=dict)  # session id -> codes
    not_listed: list = field(default_factory=list)  # sessions done with no proposal and not listed
    unestablished: int = 0
    in_doubt: list = field(default_factory=list)  # (item, event id)


def inclusion_asks_no_code(sessions_: Mapping, session: Session, counted: Sequence[Counted]) -> bool:
    """reconcile.inclusion_asks_no_code over sessions: a session read as included in another asks for no code of its
    own while that other session has no counted code, or when one of its counted codes includes the examination."""
    including = sessions_.get(session.part_of) if session.part_of else None
    if including is None:
        return False
    codes = [item.code for item in counted if item.family == including.family]
    return not codes or any(catalogue.includes_examination(code, session.kind) for code in codes)


def _item(session: Session, event_ids, act: str, label: str, reason: str, evidence) -> dict:
    return {'service': session.id, 'family': session.family, 'act': act, 'label': label, 'reason': reason,
            'evidence': [dict(span) for span in list(evidence)[:2]], 'events': list(event_ids)}


def reconcile(reading, counted: Sequence[Counted], *, procedure_day: bool = False, sessions_=None) -> Coverage:
    """The unresolved items, bundled acts and covered sessions for the counted codes (module docstring), as
    reconcile.reconcile gives them over a documented-service reading."""
    sessions_ = sessions_ if sessions_ is not None else sessions(reading)
    out = Coverage()
    read_by = {}
    for item in counted:
        for eid in tuple(item.supporting) + tuple(item.read):
            read_by.setdefault(eid, []).append(item)
    any_other_done = {family for family, session in sessions_.items() if session.done}
    for session in sessions_.values():
        entry = catalogue.entry(session.family)
        if not session.done or entry is None or entry.support != catalogue.SUPPORTED:
            continue
        codes = [item for item in counted if item.family == session.family]
        out.covered[session.id] = [item.code for item in codes]
        members = [reading.events[eid] for eid in session.events]
        anchor = reading.events.get(session.event) or next((event for event in members if events.done(event)), None)
        evidence = events.anchors(reading, anchor) if anchor is not None else []
        if not codes and inclusion_asks_no_code(sessions_, session, counted):
            pass  # the including session's code covers the examination; its own acts still count
        elif not codes:
            if session.family == 'gi.office_em' and (procedure_day or any_other_done - {session.family}):
                continue  # never push an office visit beside a same-day procedure (listed as not_listed below)
            done_ids = [event['id'] for event in members if events.done(event)]
            out.unresolved.append(_item(session, done_ids, '', f'{session.label} (documented as '
                                        f'{"incomplete" if session.incomplete else "performed"}) has no supported '
                                        'proposal', 'no_proposal', evidence))
            for event in members:
                if reportable_kind(event) and events.done(event) and event.get('catalogue_kind') in \
                        catalogue.UNSUPPORTED_ACTS:
                    out.unresolved.append(_item(session, [event['id']], event['catalogue_kind'],
                                                f'{events.event_label(reading, event)}: no supported code profile',
                                                'unsupported', events.anchors(reading, event)))
            continue
        unknown = any(mapping.code_link(item.code).route != mapping.CATALOGUE_ROUTE for item in codes)
        for event in members:  # reconcile.reconcile's order: a bundled act is read before its kind is
            kind = event.get('catalogue_kind') or ''
            if kind in NOT_ACT_KINDS or not kind:
                continue
            why = bundled_reason(reading, event)
            if not events.done(event) or events.value(event, 'status') != 'performed':
                # an act no code of the family accounts for is listed whatever its outcome (reconcile, compl-1)
                if (events.value(event, 'status') in ('attempted_not_completed', 'uncertain') and not why
                        and kind in entry.acts and kind not in catalogue.UNSUPPORTED_ACTS
                        and not events.verified_other_time(event) and not events.verified_other_performer(event)
                        and not catalogue.family_codes_act(session.family, kind)):
                    out.unresolved.append(_item(session, [event['id']], kind,
                                                f'{events.event_label(reading, event)} in the {session.label}, attempted '
                                                'or in doubt: no code profile of this service accounts for it',
                                                'unsupported', events.anchors(reading, event)))
                continue
            if kind in catalogue.UNSUPPORTED_ACTS:
                out.unresolved.append(_item(session, [event['id']], kind,
                                            f'{events.event_label(reading, event)}: no supported code profile',
                                            'unsupported', events.anchors(reading, event)))
                continue
            under = _read_under(reading, sessions_, session, event)
            if under is not None:
                if under:
                    out.unresolved.append(_item(session, [event['id']], kind,
                                                f'{events.event_label(reading, event)} in the {session.label}: {under}, '
                                                'and no code profile of this service accounts for it', 'unsupported',
                                                events.anchors(reading, event)))
                else:
                    out.bundled.append({'service': session.id, 'act': kind, 'label': events.event_label(reading, event),
                                        'why': dict(entry.bundled).get(kind, ''), 'event': event['id']})
                continue
            if why:
                out.bundled.append({'service': session.id, 'act': kind, 'label': events.event_label(reading, event),
                                    'why': why, 'event': event['id']})
                continue
            if kind not in entry.acts:
                continue
            if bundling_doubt(reading, event) is not None and event['id'] in read_by:
                continue  # a code depends on its identity and asks it (act_target)
            if not catalogue.family_codes_act(session.family, kind):
                out.unresolved.append(_item(session, [event['id']], kind,
                                            f'{events.event_label(reading, event)} in the {session.label}: no code '
                                            'profile of this service accounts for it', 'unsupported',
                                            events.anchors(reading, event)))
                continue
            if any(item.family == session.family for item in read_by.get(event['id'], ())):
                continue
            out.unresolved.append(_item(session, [event['id']], kind,
                                        f'{events.event_label(reading, event)} in the {session.label}',
                                        'coverage_unknown' if unknown else 'not_covered', events.anchors(reading, event)))
    for session in sessions_.values():  # in doubt: a reportable kind blocked, that no code depends on (7.8)
        entry = catalogue.entry(session.family)
        if entry is None or entry.support != catalogue.SUPPORTED:
            continue
        for eid in session.events:
            event = reading.events[eid]
            if not doubted(reading, event) or eid in read_by or bundled_reason(reading, event):
                continue
            item = _item(session, [eid], event['catalogue_kind'],
                         f'{events.event_label(reading, event)} in the {session.label}: CPT Studio could not confirm '
                         'from the document that it was done at this encounter', 'in_doubt',
                         events.anchors(reading, event))
            out.unresolved.append(item)
            out.in_doubt.append((item, eid))
    merged: dict = {}
    for item in out.unresolved:  # one item per (session, act kind): a second site of one service is the same code
        key = (item['service'], item['act'])
        if key not in merged:
            merged[key] = item
        else:
            merged[key]['events'] = list(dict.fromkeys(merged[key]['events'] + item['events']))
    out.unresolved = list(merged.values())
    # D89 (integration of round 3): every in_doubt event of a merged item keeps its question - kept only for the item
    # that survived the merge, a newly doubted act listed first took the service question of another (an unsettled
    # procedure's "procedure" displaced "Earlier that day, ... biopsies"'s "done at this encounter?")
    out.in_doubt = [(merged[(item['service'], item['act'])], eid) for item, eid in out.in_doubt
                    if (item['service'], item['act']) in merged]
    listed = {item['service'] for item in out.unresolved}
    for session in sessions_.values():  # reconcile.uncounted: a session done with no proposal, not listed or included
        if session.id in out.covered and not out.covered[session.id] and not session.part_of \
                and session.id not in listed:
            out.not_listed.append(session)
    for family, session in sessions_.items():  # unestablished: a family stated, none of it done, read by no code
        if session.done or catalogue.entry(family) is None or any(item.family == family for item in counted):
            continue
        members = [reading.events[eid] for eid in session.events]
        if any(events.value(event, 'status') in verify.POSITIVE + ('uncertain',) and not events.verified_other_time(event)
               and not events.verified_other_performer(event) for event in members):
            out.unestablished += 1
    return out


def _read_under(reading, sessions_: Mapping, session: Session, event: Mapping) -> Optional[str]:
    """reconcile._read_under over events (catalogue.READ_UNDER: an EUS forceps biopsy read under the EGD): '' when the
    rule holds - its verified place is in the rule's regions and a done session of that family has a performed act of
    the kind - else why nothing reads it; None for any other act. A biopsy taken with the needle is the sampling."""
    rule = catalogue.READ_UNDER.get((session.family, event.get('catalogue_kind') or ''))
    if rule is None:
        return None
    family, label, tract, regions = rule
    if not mapping.in_regions(mapping.target_landmark(event), regions):
        return (f'the document does not place it at an {tract} site of an {tract} examination, so no {label} of this '
                'encounter reads it')
    other = sessions_.get(family)
    reads = other is not None and other.done and any(
        reading.events[eid].get('catalogue_kind') == event.get('catalogue_kind') and events.done(reading.events[eid])
        and events.value(reading.events[eid], 'status') == 'performed' for eid in other.events)
    return '' if reads else f'no {label} documented at this encounter reads it'


def unresolved_record(items: Sequence[dict]) -> list:
    """completeness['unresolved_items']: each item with its second-review mark (FINAL 7.8, D10): True on a no_proposal or
    not_covered item - whose events are done (status, time and performer usable) - with an index below
    SECOND_REVIEW_CHECKED."""
    return [{**item, 'second_review': index < SECOND_REVIEW_CHECKED and item['reason'] in ('no_proposal', 'not_covered')}
            for index, item in enumerate(items)]


def in_doubt_questions(reading, coverage: Coverage, asked=()) -> list:
    """A service-scope question for each in_doubt item, with the fact of 7.4 for its event (FINAL 7.8), once per (family,
    fact), never one a proposal of the family already asks (``asked``: (family, fact) pairs)."""
    # D89: ``asked`` holds (family, fact, question) of the proposals' questions; a code's question suppresses a service
    # question only when it IS that question (its fact and its words, which name the act) - a code asking
    # statement_scope about its snare no longer silences the service's statement_scope about another act's denial
    codes_asked = {tuple(entry) for entry in asked}
    seen = set()
    out = []
    for item, eid in coverage.in_doubt:
        question = events.focus_question(reading, reading.events[eid])
        if question is None or (item['family'], question.fact) in seen \
                or (item['family'], question.fact, question.question) in codes_asked:
            continue
        seen.add((item['family'], question.fact))
        out.append(ClarificationSpec(scope='service', fact=question.fact, question=question.question,
                                     reason=question.reason, family=item['family']))
    return out


# --- completeness (reconcile.completeness; copied wording, pinned equal) -------------------------------------------------

UNVERIFIED_REASON = "CPT Studio's reading left {count} attribute{s} unverified that a decision read"


def completeness(coverage: Coverage, sessions_: Mapping, *, open_questions: int, provider_ok: bool, conflicts: int,
                 unverified: int = 0) -> dict:
    """The encounter's coding completeness at assessment time, worded as reconcile.completeness words it, plus FINAL
    7.8's reason for the attributes left unverified that a decision read."""
    reasons = []
    unresolved = coverage.unresolved
    not_listed = coverage.not_listed
    if not provider_ok:
        reasons.append('the provider response was not available')
    if unresolved:
        reasons.append(f'{len(unresolved)} documented service{"s" if len(unresolved) != 1 else ""} or act'
                       f'{"s" if len(unresolved) != 1 else ""} without a supported proposal')
    if coverage.unestablished:
        reasons.append(f'{coverage.unestablished} documented service{"s" if coverage.unestablished != 1 else ""} not '
                       'established as performed and read by no proposal')
    if not_listed:
        reasons.append(f'{len(not_listed)} documented service{"s" if len(not_listed) != 1 else ""} without a supported '
                       'proposal and not listed as unresolved: ' + ', '.join(uncounted_label(s) for s in not_listed))
    if conflicts:
        reasons.append(f'{conflicts} conflict{"s" if conflicts != 1 else ""} in the record')
    if open_questions:
        reasons.append(f'{open_questions} open question{"s" if open_questions != 1 else ""}')
    if unverified:
        reasons.append(UNVERIFIED_REASON.format(count=unverified, s='' if unverified == 1 else 's'))
    performed = [session for session in sessions_.values() if session.done]
    return {
        'state': 'incomplete' if reasons else 'complete_pending_review',
        'reasons': reasons,
        'services': len(performed),
        'unresolved': len(unresolved),
        'conflicts': conflicts,
        'statement': ('Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.') if reasons else (
            'Every documented service has a proposal to review. This is not verified coding: code-set membership '
            'and NCCI edits are not verified, and each proposal still needs a reviewer.'),
    }


def uncounted_label(session: Session) -> str:
    """reconcile.uncounted_label over a session (copied)."""
    return session.label + (' beside a procedure done or possibly done the same day'
                            if session.family == 'gi.office_em' else '')


def included_by(sessions_: Mapping, covered: Mapping) -> dict:
    """engine._included_by over sessions: {session id: the counted codes of the session it is read as part of that
    include its examination} for every done session read as part of another."""
    out = {}
    for session in sessions_.values():
        if session.done and session.part_of:
            out[session.id] = [code for code in covered.get(session.part_of, ())
                               if catalogue.includes_examination(code, session.kind)]
    return out


# --- event_coding (FINAL 7.8): what the overlay, the reports and the customer API read -----------------------------------

def event_coding(reading, sessions_: Mapping, codes: Mapping) -> dict:
    """{version, sessions, codes, lesions} (module docstring; FINAL 7.8). ``codes``: {proposal key: (session id, E*
    event ids)} of the decidable proposals."""
    coded_sessions = {}
    for session in sessions_.values():
        members = [reading.events[eid] for eid in session.events]
        coded_sessions[session.id] = {
            'family': session.family, 'event': session.event, 'part_of': session.part_of, 'label': session.label,
            'possibly_part_of': session.possibly_part_of,  # D70: the base-within rule reads it at read time too
            'kind': session.kind, 'unresolved': session.unresolved, 'done': session.done,
            'incomplete': session.incomplete, 'examinations': list(session.examinations),
            'possible': list(session.possible),
            # the session's own service is never an act beside itself: an office visit's visit event (lexicon.EM_KINDS)
            'reportable': [_entry(reading, event) for event in members if reportable(reading, event)
                           and events.value(event, 'kind') not in lexicon.EM_KINDS],
            'doubted': [_entry(reading, event) for event in members if doubted(reading, event)
                        and events.value(event, 'kind') not in lexicon.EM_KINDS],
        }
    coded_codes = {}
    for key, (session, supporting) in codes.items():
        lesions = sorted({identity.verified_lesion(reading.events[eid]) for eid in supporting
                          if eid in reading.events and identity.verified_lesion(reading.events[eid])})
        coded_codes[key] = {'session': session, 'events': list(supporting), 'lesions': lesions}
    coded_lesions = {}
    for lid, lesion in reading.lesions.items():
        site = lesion.get('site') or {}
        coded_lesions[lid] = {'words': lesion.get('words'), 'landmark': site.get('value', 'not_stated')
                              if verify.usable(site) else 'not_stated', 'multiplicity': lesion.get('multiplicity'),
                              'distinct_from': list(lesion.get('distinct_from') or ()),
                              'label': events.lesion_words(reading, lid)}
    return {'version': CODING_VERSION, 'sessions': coded_sessions, 'codes': coded_codes, 'lesions': coded_lesions}
