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


def drainage_step(reading, event: Mapping) -> Optional[Mapping]:
    """DECISIONS D171 (1) (refute6 families finding 4): the transmural drainage of which ``event`` - an EUS fine-needle
    aspiration or biopsy (an aspiration of a collection included) - is a STEP, or None. It is a step of a drainage of its
    session, current as adjunct_whole reads a whole (performed or begun and not completed, possibly current: D62, D79),
    when its verified part_of names that drainage (Gemini's step: 'Under EUS guidance, the pseudocyst was punctured from
    the gastric body with a 19-gauge needle and 20 mL of clear fluid was aspirated and sent for amylase and CEA.' part_of
    'EUS-guided transmural drainage of the pseudocyst was then performed with a 15 mm lumen-apposing metal stent.'), or
    when its verified lesion is the drainage's own verified lesion (the same aspiration with no part_of: the needle access
    and aspiration of the collection the drainage drains). The drainage's code includes that access, so the code that
    stands on the aspiration is held (assess._examination_class) - never READY beside 43240 on the same lesion. An FNA of
    ANOTHER lesion ('EUS-guided fine-needle aspiration of the pancreatic tail mass ...' beside the pseudocyst's drainage)
    is no step. Read for that hold only: bundled_reason does not read it, so coverage still lists the aspiration where no
    counted code reads it (D171's recorded stop: bundling it would drop that listing). Structure only: no words.

    DECISIONS D177 (3) (round 5h, narrowing only; review:eus7 problem 3, critical, pre-existing): a drainage IN DOUBT is
    a doubt, never an absence (D62, D87). Read as absent, the FNA of its own lesion went READY: X6 (the drainage
    verified to the FNA's lesion, its status words not binding: no usable status, so no adjunct_whole) and X3 (the
    drainage's target tied to no lesion and unverified, FRESH's commonest unverified reason: no verified lesion to
    meet). Where no drainage is the FNA's step as above, the FNA is a POSSIBLE step of a drainage of its session that
    may have been done today - its status performed, begun or uncertain in ANY state (verify.POSITIVE, 'uncertain'),
    possibly current (D62), by any performer (as a done drainage is read above) - when its verified part_of names that
    drainage, or, for an FNA of a verified lesion, when the drainage may be of that lesion: its target verified to that
    lesion or to one possibly the same (6.3), or not verified to any (identity 'none' or 'unresolved') and not
    ESTABLISHED apart from it - the lesion its target names is not one the FNA's lesion is distinct from (identity's
    distinct_from), and no verified place of the drainage is disjoint (lexicon.disjoint, contract 6.3) from every
    verified place of the FNA (relations' Context.places). A drainage verified to a lesion distinct from the FNA's,
    stated not performed or planned, or placed on another occasion is no whole of it, as before. The caller (assess's
    EUS code checks) holds the code that stands on such a step, and its reason says what the document leaves in doubt.
    Structure only: no words."""
    if event.get('family') != 'gi.eus' or event.get('catalogue_kind') != 'fna':
        return None
    whole_of = _part_of(event)
    lesion = identity.verified_lesion(event)
    drainages = [whole for whole in reading.events.values()
                 if whole is not event and whole.get('family') == 'gi.eus' and whole.get('catalogue_kind') == 'drainage'
                 and _same_session(reading, whole, event)]
    for whole in drainages:
        if adjunct_whole(whole) and (whole_of == whole['id'] or (lesion and lesion == identity.verified_lesion(whole))):
            return whole
    for whole in drainages:  # D177 (3): a drainage in doubt still makes a same-lesion FNA a possible step
        if events.value(whole, 'status') not in verify.POSITIVE + ('uncertain',) or not possibly_current(whole):
            continue
        if whole_of == whole['id'] or (lesion and _possibly_of_lesion(reading, whole, event, lesion)):
            return whole
    return None


def _possibly_of_lesion(reading, whole: Mapping, event: Mapping, lesion: str) -> bool:
    """DECISIONS D177 (3): whether the drainage ``whole`` may be of ``lesion``, the verified lesion of the FNA ``event``
    (drainage_step's possible step): its target verified to that lesion, or to a lesion possibly the same as it
    (contract 6.3: never established distinct - identity.same_or_possibly_same); or verified to none, and not
    established apart from it - neither the lesion its target names is one ``lesion`` is distinct from, nor is every
    verified place of the drainage disjoint from every verified place of the FNA. A drainage verified to a lesion
    distinct from it is apart."""
    other = identity.verified_lesion(whole)
    if other:  # verified to the FNA's lesion, or to one not established apart from it (6.3: possibly the same)
        return identity.same_or_possibly_same(reading, lesion, other)
    named = (whole.get('target') or {}).get('lesion') or ''
    if named and named != lesion and named in ((reading.lesions.get(lesion) or {}).get('distinct_from') or ()):
        return False
    places, own = reading.context.places(whole), reading.context.places(event)
    return not (places and own and all(lexicon.disjoint(one, two) for one in places for two in own))


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
    are the session C-4 reads - placed nowhere lower, an upper EUS whose endoscopic portion today's EGD is - and
    (DECISIONS D135) so is every other done EUS-guided act (eus_guided_act); only these acts are lower EVIDENCE."""
    return (event.get('family') == 'gi.eus' and event.get('catalogue_kind') in EUS_ACTS and events.done(event)
            and events.usable(event, 'kind') and events.usable(event, 'procedure')
            and events.value(event, 'procedure') == 'eus')


def eus_guided_act(event: Mapping) -> bool:
    """DECISIONS D135 (the round-5 review of D121, problem 0): a DONE EUS-guided act of ANY kind - an event of the EUS
    family done at this encounter (events.done) that is no examination, its kind usable (an act of no catalogue kind,
    Gemini's 'other', included) and its own PROCEDURE usable as 'eus'. With no done EUS examination these acts, not
    eus_act's alone, are the session C-4 reads (D121): an EUS told only through 'EUS-guided through-the-needle
    microforceps biopsy of the 3 cm cyst in the pancreatic body was performed.' (a biopsy), an EUS-guided
    radiofrequency ablation, a gastroenterostomy's lumen-apposing stent or a coil embolization ('other') is an EUS as one
    told through its FNA is - read from EUS_ACTS alone, it left today's EGD part of nothing and 43235 READY beside 43242,
    43259 and alone, where the installed release holds it base_included. They are the EUS's for the SESSION only: an
    act of a kind that is not the EUS's own is never lower evidence (D96, eus_act), and placed lower it is a doubt
    about the EUS's place (D123, sessions)."""
    return (event.get('family') == 'gi.eus' and event.get('catalogue_kind') not in mapping.EXAMINATION_KINDS
            and events.done(event) and events.usable(event, 'kind') and events.usable(event, 'procedure')
            and events.value(event, 'procedure') == 'eus')


def eus_unprofiled_entries(reading, members, doubted: bool = False) -> list:
    """DECISIONS D137 (the round-5 review of D122, problem 2): the event-coding entries (_entry's) of the EUS-guided acts
    among ``members`` whose kind the EUS's catalogue entry does not list among its acts - a gastroenterostomy's
    lumen-apposing stent, a radiofrequency ablation, a coil embolization read as 'other', a tattoo - and that are part of
    no other act (bundled_reason: never a clip, NOT_REPORTED). The examination is the endoscopic portion of that
    procedure, and the examination-only EUS codes do not account for the act: event_coding records it among the
    session's entries, so an examination-only EUS code beside it (combination._base: 43231, 43237, 43259, 45341, 45391,
    44406) is held base_included, by combination.base_included at assess time and by the read-time overlay over the same
    record. Read as no act, 'From the gastric body, a 20 mm lumen-apposing metal stent was deployed into a distended
    jejunal loop.' beside its EUS examination left 43259 READY with coding complete_pending_review, where the installed
    release holds 43259.

    DECISIONS D145 (the round-5c review of D137, problem 5) corrects the premise D137 stated here, that no EUS code
    accounts for such an act: a tattoo is an injection for coding (mapping.ONE_ACT), so 43253 is supported by 'EUS-guided
    placement of three gold fiducial markers into the pancreatic head mass was performed.' read as 'tattoo'. The act is
    recorded all the same - the examination-only code does not account for it, and the installed release holds 43259
    beside it - and such an act (a kind mapping.ONE_ACT makes one act with the injection) is labelled by its own kind
    words before its catalogue label: read by the label first, the fiducial placement was asked 'Is 43259 reported
    separately from submucosal tattoo for this examination?'. Any other act keeps D137's label: its catalogue label,
    else its own kind words ('coil embolization'; EB1); and either, else its event label (events.event_label), never
    ''.

    DECISIONS D145 (problem 4): the 'reportable' entries (``doubted`` False) are the DONE EUS-guided acts
    (eus_guided_act) whose status is a usable 'performed', reportable's 7.8 frame. The 'doubted' entries (``doubted``
    True) are the ones begun and not completed - recorded as reportable, an attempted and failed stent was printed as a
    stent placement among the EUS service's acts (readers.EventReader.services_section reads 'reportable') - and
    (problem 0) the acts of the class in doubt (eus_unprofiled_doubt). The base rule holds the examination-only code
    beside either."""
    listed = catalogue.entry('gi.eus').acts
    out = []
    for event in members:
        if event.get('family') != 'gi.eus' or (event.get('catalogue_kind') or '') in listed:
            continue
        guided, status = eus_guided_act(event), events.value(event, 'status')
        if doubted:  # D145: begun and not completed, or in doubt
            chosen = (guided and status == 'attempted_not_completed') or eus_unprofiled_doubt(reading, event)
        else:  # D145: performed (reportable's 7.8 frame)
            chosen = guided and status == 'performed'
        if not chosen or bundled_reason(reading, event):
            continue
        entry = _entry(reading, event)
        words = events.words_of(event, 'kind')
        named = ' '.join((words.get('text') or '').split()) if words else ''
        # D145: an act read as a tattoo - an injection for coding (mapping.ONE_ACT) - by its own words first
        first, then = (named, entry['label']) if entry['kind'] in mapping.ONE_ACT else (entry['label'], named)
        out.append({**entry, 'label': first or then or events.event_label(reading, event)})
    return out


def eus_unprofiled_doubt(reading, event: Mapping) -> bool:
    """DECISIONS D145 (the round-5c review of D137, problem 0, critical): whether ``event`` is an act of D137's class IN
    DOUBT - an event of the EUS family that is no examination, of a kind the EUS's catalogue entry does not list among
    its acts, stated positive or uncertain and neither verified at another time nor by another performer
    (_stated_here), and in doubt: its PROCEDURE not usable while it is possibly current (D75's arm: 'A 20 mm
    lumen-apposing metal stent was deployed from the gastric body into a distended jejunal loop.' filed under 'eus' with
    no procedure words where an EGD and an EUS are both current - procedure_unsettled), its status uncertain, its time
    only possibly current (not done and possibly_current, possible_eus_acts' class: the same stent told 'Later, ...'),
    or a CONTRADICTION, DOUBT or UNRESOLVED relation on it. A doubt, never an absence (D87): eus_unprofiled_entries
    records it among the session's 'doubted' entries, so an examination-only EUS code beside it is held base_included
    (combination.base_included's doubt arm). D137 read only the done acts whose procedure is usable, so the first stent
    left 43259 READY alone and beside 43235, and the second beside its EUS examination, where the installed release
    holds it.

    DECISIONS D156 (round 5e; the round-5d eus4 builder's disagreement 3 and the review of D145, problem 5):
    - (1) a DONE act of the class whose KIND is not usable is in doubt too, as the procedure arm treats one whose
      procedure is not usable: the lumen-apposing stent named 'LAMS' (kind words that do not locate) beside its EUS
      examination is no D137 act (eus_guided_act needs a usable kind) and had no arm here, so 43259 was READY, coding
      complete_pending_review, where the installed release holds it. Done only: an act not done and possibly current is
      the possible acts' arm already.
    - (3) the relation arm never takes an act already reportable - done by eus_guided_act and a usable 'performed',
      D137's 'reportable' entry in eus_unprofiled_entries - so such an act is recorded once: a done stent beside 'No
      stent was placed across the pylorus.' (an UNRESOLVED relation on it) was recorded as reportable AND doubted, and
      43259 asked 'Is 43259 reported separately from stent placement, stent placement (stated in doubt) for this
      examination?'. Wording only: the reportable entry holds 43259 base_included as before."""
    kind = event.get('catalogue_kind') or ''
    if (event.get('family') != 'gi.eus' or kind in mapping.EXAMINATION_KINDS or kind in catalogue.entry('gi.eus').acts
            or not _stated_here(event)):
        return False
    reportable = eus_guided_act(event) and events.value(event, 'status') == 'performed'  # D156 (3): D137's entry
    return ((not events.usable(event, 'procedure') and possibly_current(event))  # D75's arm
            or events.value(event, 'status') == 'uncertain'
            or (not events.done(event) and possibly_current(event))  # possible_eus_acts' class
            or (events.done(event) and not events.usable(event, 'kind'))  # D156 (1): its kind not usable
            or (bool(reading.relations_of(event['id'])) and not reportable))  # D156 (3): never recorded twice


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


def doubted_eus_acts(reading, unnamed: bool = False) -> list:
    """DECISIONS D123 (the round-4 review of D96, problems 1 and 2): today's DONE acts filed under the EUS that C-4 cannot
    read as the EUS's own (eus_act) - an act of an EUS kind whose kind or procedure is not usable (an FNA filed under
    'eus' with no words: procedure_unsettled), or an act of a kind that is no EUS act (a forceps biopsy: 'Radial EUS was
    then performed; forceps biopsies of the rectal mass were taken.') - in the reading's order. They are doubts, never
    facts (D87): never lower evidence (D96 kept), and never the reason the EGD is read as the EUS's endoscopic portion. An
    examination (a digital rectal examination, FINAL 5.6 E13) and an event of no catalogue kind (a rectal medication read
    as 'other', DECISIONS D96 finding 0) are not acts here. DECISIONS D135: with ``unnamed`` (C-4's upper doubts, which
    take every kind), an act of no catalogue kind that is no EUS-guided act (eus_guided_act: its kind or its procedure
    not usable - 'Coil embolization of the gastric fundal varix was performed.' filed under 'eus' with no words) is a
    doubted act too."""
    return [event for event in reading.events.values() if event.get('family') == 'gi.eus' and events.done(event)
            and event.get('catalogue_kind') not in mapping.EXAMINATION_KINDS
            and (event.get('catalogue_kind') or (unnamed and not eus_guided_act(event))) and not eus_act(event)]


def possible_eus_acts(reading) -> list:
    """DECISIONS D121 (D62's rule for an act): the EUS acts stated performed or begun and only POSSIBLY of this encounter
    (possibly_current, not done: 'After the EGD, EUS-FNA of a 22 mm hypoechoic mass in the pancreatic body was performed
    ...', its time unanchored), in the reading's order. A possible upper EUS - a doubt, never the session and never lower
    evidence: read as an absence, it left 43235 READY beside 43242, where the installed release holds it base_included.
    DECISIONS D135: an act of ANY kind, not of EUS_ACTS alone ('After the EGD, EUS-guided radiofrequency ablation of the
    15 mm insulinoma in the pancreatic tail was performed.': 43235 READY beside 43259 and alone, held base_included by
    the installed release). DECISIONS D138 (the round-5 review of D121, problem 3): never an act verified at another time
    or by another performer, as doubted reads a doubt - an FNA 'performed by Dr. Lena Ortiz (fictional) of the advanced
    endoscopy service', its performer verified as another clinician, is that clinician's act, not a possible upper EUS of
    this encounter: read as one, it held 43235 base_included where d353e64df and the installed release are READY."""
    return [event for event in reading.events.values() if event.get('family') == 'gi.eus'
            and event.get('catalogue_kind') not in mapping.EXAMINATION_KINDS and not events.done(event)
            and possibly_current(event) and events.value(event, 'status') in verify.POSITIVE
            and not events.verified_other_time(event) and not events.verified_other_performer(event)]


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


# DECISIONS D114 (the round-4 review of D108, parity note 1): the regions an EGD examines, as the installed release's
# services.FAMILY_REGIONS gives them ('gi.egd': the upper tract - the esophagus, the stomach and the duodenum;
# 'gi.enteroscopy': the small bowel alone, a region mapping.REGION_OF keeps apart from the duodenum's)
EGD_REGIONS = frozenset({'esophagus', 'stomach', 'duodenum'})
# DECISIONS D141 (the round-5 review of D114, problem 1): the EGD's regions in the order its examination reaches them,
# and the duodenum's portions in order (its generic landmark names none). DECISIONS D148 (the round-5c review of D141,
# problems 1 and 2): the last portion is the place beyond the second portion, which no landmark names - DECISIONS D153
# (the round-5d review of D148, problems 0-2): only an EGD reach is placed there, by its own words (BEYOND_SECOND_WORDS);
# an act never is, so no act lies beyond a verified reach at the second portion
UPPER_ORDER = ('esophagus', 'stomach', 'duodenum')
DUODENAL_PORTIONS = ('duodenal_bulb', 'second_portion_duodenum', 'beyond_second_portion')
GENERIC_DUODENUM = 'duodenum'
# DECISIONS D148: the words that name a duodenal portion beyond the second, matched in lexicon.fold's form, word-bounded
# (lexicon.holds). DECISIONS D153: read only in an EGD reach's own located words, where a form found keeps the reach from
# stopping short (fail-closed) and a form missing changes nothing; never in an act's words, where 'distal duodenum' or
# 'just proximal to the third portion' moved an act inside the gastroscope's verified reach out of it.
BEYOND_SECOND_WORDS = ('third portion', 'fourth portion', 'third part', 'fourth part', 'd3', 'd4', 'distal duodenum')


def beyond_reach(examination: Mapping, landmark: str) -> bool:
    """DECISIONS D141: whether the done EGD ``examination``'s VERIFIED reach stops short of ``landmark``, an act's place
    in EGD_REGIONS - in an earlier region (UPPER_ORDER: a reach in the stomach is short of the duodenum), or, in the
    duodenum, at an earlier portion (DUODENAL_PORTIONS: a reach at the bulb is short of the second portion). Never
    short, and so possibly covering the act (fail-closed: the act moves), when the reach is not verified, lies beyond
    the upper tract or in no region of it, or where either is the generic duodenum's landmark (which names no
    portion).

    DECISIONS D148 (the round-5c review of D141, problems 1 and 2), as D153 narrows it (the round-5d review of D148,
    problems 0-2): the reach's own located words are read - a reach at the second portion's landmark whose words name a
    portion beyond the second (BEYOND_SECOND_WORDS) is placed beyond it (DUODENAL_PORTIONS' last) and never stops short
    of an act (fail-closed). An act's own words are never read: only its verified landmark places it, as D141 reads it.
    Read in the act's words, 'Biopsies of the distal duodenum' (the post-bulbar duodenum a standard EGD samples) and 'an
    angioectasia in the second portion of the duodenum, just proximal to the third portion' were placed beyond a reach
    verified at the second portion, and 44361, 44369 and 43235 went READY where e5628be56 and the installed release
    hold them."""
    extent = examination.get('extent')
    if not verify.usable(extent):
        return False
    reach = extent.get('value') or ''
    reached, at = mapping.region(reach), mapping.region(landmark)
    if reached not in UPPER_ORDER or at not in UPPER_ORDER:
        return False
    if reached != at:
        return UPPER_ORDER.index(reached) < UPPER_ORDER.index(at)
    record = extent.get('words')
    reach_words = (record.get('text') or '') if isinstance(record, Mapping) else ''
    reach = (DUODENAL_PORTIONS[-1] if reach == DUODENAL_PORTIONS[1] and lexicon.holds(reach_words, BEYOND_SECOND_WORDS)
             else reach)  # D148: a reach the second portion's landmark takes from third-portion words
    if reach not in DUODENAL_PORTIONS or landmark not in DUODENAL_PORTIONS:
        return False
    return DUODENAL_PORTIONS.index(reach) < DUODENAL_PORTIONS.index(landmark)


def coding_family(reading, event: Mapping) -> str:
    """DECISIONS D114 (the round-4 review of D108, parity note 1): the family whose session ``event`` belongs to for
    coding - Gemini's (normalize's ``family``), except an ACT Gemini files under the enteroscopy whose VERIFIED target
    lies in a region the EGD examines (EGD_REGIONS), outside the small bowel the enteroscopy examines, in an encounter
    with a DONE EGD examination (done_examinations): that act is the EGD session's, as the installed release gives an
    act to the family whose regions hold its site (services._family_for_act_in over FAMILY_REGIONS). Read as the
    enteroscopy's, "Two gastric antral angioectasias were treated with argon plasma coagulation." beside a done EGD and
    a push enteroscopy left 43235 READY beside it, where the installed release holds 43235 base_included (and holds
    44369, classes.act_elsewhere's rule). An act whose place is not verified (mapping.target_landmark: '' for an
    unusable or unplaced target) kept Gemini's family until D153 (below), and an examination (the session itself) never
    moves.

    DECISIONS D141 (the round-5 review of D114, problem 1): only an act at a place within the done EGD's verified reach
    moves. An act beyond it - every done EGD examination's verified reach short of its place (beyond_reach: a reach at
    the bulb beside an act at the second portion) - keeps Gemini's family.

    DECISIONS D148 (the round-5c review of D141, problems 1 and 2): D141's shared-passage test is gone - it compared
    every passage an attribute cites, never the one its words stand in, and could not tell an act the gastroscope did
    before the exchange from one told in the enteroscopy's sentence. DECISIONS D153 (the round-5d review of D148,
    problems 0-2): and an act's own target words never place it beyond the EGD's verified reach - only its verified
    landmark does (beyond_reach). An act at the generic duodenum or at the second portion beside an EGD whose verified
    reach is in the duodenum, or not verified, moves as D114 moved it, wherever it is told and whatever portion its words
    name: "An angioectasia in the third portion of the duodenum was treated with argon plasma coagulation." moves beside
    an EGD verified to the second portion (44369 held, 43235 base_included, as e5628be56 and the installed release hold
    them on a line of its own; the installed release READYs both when the act is told in the push enteroscopy's
    sentence - a recorded cost), and so do "Biopsies of the distal duodenum ..." and the exchange sentence. D141's
    earlier region stands: a verified reach at the bulb is short of the second portion, and one in the stomach of the
    duodenum.

    DECISIONS D153 (the round-5d review of D148, problem 6): an act whose place is NOT verified (mapping.target_landmark:
    '' - its target unverified, opened or absent, or unplaced) is a doubt of family (D87) in an encounter with a done EGD
    examination: it is the EGD session's for coding, as D114's moved act is, so it never makes an enteroscopy code READY
    by itself (classes.act_elsewhere holds it) and the EGD's base code is held beside it. Kept with Gemini's family,
    "Biopsies of the distal duodenum were taken with cold forceps ..." at the second portion's landmark (whose forms do
    not take 'distal duodenum') left 44361 and 43235 READY, where the installed release holds both. Without a done EGD
    the act keeps Gemini's family."""
    family = event.get('family') or ''
    kind = event.get('catalogue_kind') or ''
    if family != 'gi.enteroscopy' or not kind or kind in NOT_ACT_KINDS:
        return family
    landmark = mapping.target_landmark(event)
    egds = done_examinations(reading, 'gi.egd')
    if not landmark:  # D153: a place not verified is a doubt of family (D87) beside a done EGD
        return 'gi.egd' if egds else family
    if mapping.region(landmark) not in EGD_REGIONS:
        return family
    if not egds or all(beyond_reach(examination, landmark) for examination in egds):  # D141 (D153: the landmark alone)
        return family
    return 'gi.egd'


def sessions(reading) -> dict:
    """{session id (the family slug): Session} of every family with an event, in the families' order."""
    by_family: dict = {}
    for event in reading.events.values():
        family = coding_family(reading, event)  # D114: the family an act belongs to for coding, by its region
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
    # 43242. Beside a possible examination (D62's, D97's) it is the doubt below, never the fact. D135 (the round-5 review
    # of D121, problem 0): every done EUS-guided act, whatever its kind (eus_guided_act: an EUS-guided microforceps
    # biopsy, a radiofrequency ablation, a gastroenterostomy's stent, a coil embolization read as 'other'), not eus_act's
    # alone - read from EUS_ACTS only, those EUSes left the EGD part of nothing and 43235 READY
    acts = [event for event in reading.events.values() if eus_guided_act(event)] if eus is not None else []
    session_events = done_eus or acts
    # D123 (the round-4 review of D96, problems 1 and 2): a done act filed under the EUS that is not the EUS's own
    # (doubted_eus_acts: its family or kind in doubt, or a forceps biopsy) is never lower evidence (D96) - and, placed
    # lower where no done EUS event places the EUS, never lets C-4 read the EGD as the EUS's endoscopic portion either:
    # its doubt makes the upper reading a doubt (possibly_part_of), so the EGD keeps its own items and 43235 is held.
    # D135: so does an act-only session's own act placed lower, an act of no catalogue kind included ('EUS-guided
    # injection of the rectal varix was performed.' read as 'other', which doubted_eus_acts does not hold): no lower
    # evidence (D96), and never the premise of an upper EUS either
    doubted = doubted_eus_acts(reading) if eus is not None else []
    possibly_lower = not lower and not _placed_eus(evidence) and _lower_eus(doubted + ([] if done_eus else acts))
    upper_eus = bool(session_events) and not lower and not possibly_lower and (bool(done_eus) or not doubts)
    # D87, D121: an act whose own family or kind is in doubt, or that is only possibly of this encounter (D62), is a
    # possible upper EUS, never a fact - D135: whatever its kind (doubted_eus_acts with unnamed, possible_eus_acts), not
    # an act of EUS_ACTS alone
    upper_doubts = doubts + (doubted_eus_acts(reading, unnamed=True) + possible_eus_acts(reading)
                             if eus is not None else [])
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

# DECISIONS D116 (the round-4 family parity audit, EGD gap A): the stent's own acts besides its placement. Gemini files
# "The fully covered esophageal stent was removed by its retrieval loop without difficulty." as a stent_removal and "The
# esophageal stent was exchanged for a new 18 mm fully covered esophageal stent ..." as a stent_exchange (prompt.py's
# KINDS), and only the ERCP's catalogue entry lists them: read as no act of the EGD, they left 43235 READY beside them,
# where the installed release reads a stent act there and holds it base_included.
STENT_ACTS = frozenset({'stent_removal', 'stent_exchange'})


def reportable_kind(event: Mapping) -> bool:
    """A kind of the family's catalogue acts - not the examination, an umbrella or NOT_REPORTED - or (DECISIONS D116) a
    stent removal or a stent exchange in a family whose catalogue acts hold the stent placement (the EGD, the
    enteroscopy, the colonoscopy, the sigmoidoscopy; the ERCP lists them itself): a reportable kind of its session for
    the base rule, and doubted when in doubt, whether or not a code profile of the family accounts for it."""
    entry = catalogue.entry(event.get('family', ''))
    kind = event.get('catalogue_kind') or ''
    if entry is None or kind in NOT_ACT_KINDS or kind in catalogue.NOT_REPORTED:
        return False
    return kind in entry.acts or (kind in STENT_ACTS and 'stent' in entry.acts)  # D116


def reportable(reading, event: Mapping) -> bool:
    """7.8: performed, current and by the documenting team, of a reportable kind, not bundled."""
    return (events.done(event) and events.value(event, 'status') == 'performed' and events.usable(event, 'kind')
            and events.usable(event, 'procedure') and reportable_kind(event) and not bundled_reason(reading, event))


def _stated_here(event: Mapping) -> bool:
    """Stated positive or uncertain, and neither verified at another time nor by another performer (doubted's frame)."""
    return (events.value(event, 'status') in verify.POSITIVE + ('uncertain',)
            and not events.verified_other_time(event) and not events.verified_other_performer(event))


def _removal_in_doubt(event: Mapping) -> bool:
    """DECISIONS D117: a positive or uncertain removal of unstated method (the 'removal' umbrella), not verified at
    another time or by another performer, in a family whose catalogue acts hold a removal method
    (mapping.REMOVAL_MEMBERS: the EGD, the enteroscopy, the colonoscopy, the sigmoidoscopy)."""
    entry = catalogue.entry(event.get('family', ''))
    return (event.get('catalogue_kind') == mapping.REMOVAL and entry is not None
            and any(member in entry.acts for member in mapping.REMOVAL_MEMBERS) and _stated_here(event))


def _bleeding_control_in_doubt(reading, event: Mapping) -> bool:
    """DECISIONS D115: a bleeding control in doubt (mapping.POSSIBLE_BLEEDING_CONTROL) of a family whose catalogue acts
    hold the bleeding control, not verified at another time or by another performer, that read as the bleeding control
    would not be part of a removal (bundled_reason: D30's procedural adjunct, D79's attempted whole)."""
    entry = catalogue.entry(event.get('family', ''))
    return (event.get('catalogue_kind') == mapping.POSSIBLE_BLEEDING_CONTROL and entry is not None
            and mapping.BLEEDING_CONTROL in entry.acts and _stated_here(event)
            and not bundled_reason(reading, {**event, 'catalogue_kind': mapping.BLEEDING_CONTROL}))


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
    procedure is absent has no family and no session (the cross-family part of D75 is recorded, not built here).

    Two acts no code can rest on are doubts of their session, never absences:
    - DECISIONS D117 (the round-4 family parity audit, EGD gap B): a removal whose method is not stated (Gemini's
      'removal' umbrella: "A polypectomy of the gastric body polyp was performed.", attested in fb08, v4 and fb09)
      stated positive or uncertain, in a family whose catalogue acts hold a removal method (_removal_in_doubt). It may
      be any of those reportable acts; as an umbrella (NOT_ACT_KINDS) it was neither reportable nor doubted, and 43235
      alone was READY with coding complete, where the installed release reads a snare there and holds it base_included.
    - DECISIONS D115 (the round-4 family parity audit, EGD gap D, critical): a bleeding control in doubt
      (mapping.POSSIBLE_BLEEDING_CONTROL: a hemostatic clip or injection whose own words state no bleeding), in a family
      whose catalogue acts hold the bleeding control (_bleeding_control_in_doubt) - unless, read as the bleeding control,
      it would be part of a removal (D30, D79: bundled_reason's procedural-adjunct arm), which no rule reports alone.
      Read as an absence, "Two hemostatic clips were placed across the ulcer." beside a clean-based ulcer left 43235
      READY, where 437b708bb held it base_included beside the bleeding control it read there."""
    if _removal_in_doubt(event) or _bleeding_control_in_doubt(reading, event):  # D117, D115
        return True
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
            # never push an office visit beside a procedure DONE on the date of service (listed as not_listed
            # below): DECISIONS D134 - beside one only POSSIBLY done it stays listed, 'has no supported proposal'.
            # ``procedure_day`` is the assessment's combination.ProcedureDay (its done ``labels`` are read here, never
            # its ``possible``: DECISIONS D151 withdrew D144's ``unidentified``), or a bool where only that answer is
            # known (the read-time overlay's, from the items the assessment listed)
            if session.family == 'gi.office_em' and (getattr(procedure_day, 'labels', procedure_day)
                                                     or any_other_done - {session.family}):
                continue
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
                # DECISIONS D142 (round 5c; the round-5b review of D116, problem 2, and the committed eus2 review's
                # problems 1-2, the listing): a done act of a kind its session's family does not list among its acts -
                # the EGD's stent removal or exchange ("The fully covered esophageal stent was removed by its retrieval
                # loop ..." beside 43239), an EUS-guided gastroenterostomy's stent beside 43259 - is listed as not
                # covered when it is reportable and no proposed code covers it: its kind and procedure usable, a kind a
                # supported family of the catalogue lists among its acts (never an E/M visit, which is never an act of a
                # procedure; never D115's bleeding control in doubt, a kind no family lists - in a family that holds the
                # bleeding control it is listed in doubt below), and read by no counted code. Skipped, it left 43239
                # READY with coding complete, where the installed release lists the stent not covered. Never the
                # examination, an umbrella (D117's removal, listed in doubt below) or a bundled, unsupported or
                # read-under act: each is decided above
                if (event['id'] not in read_by and events.usable(event, 'kind') and events.usable(event, 'procedure')
                        and kind not in lexicon.EM_KINDS and any(
                            kind in other.acts for other in catalogue.CATALOGUE.values()
                            if other.support == catalogue.SUPPORTED)):
                    out.unresolved.append(_item(session, [event['id']], kind,
                                                f'{events.event_label(reading, event)} in the {session.label}',
                                                'coverage_unknown' if unknown else 'not_covered',
                                                events.anchors(reading, event)))
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


def in_doubt_questions(reading, coverage: Coverage, asked=(), holding=()) -> list:
    """A service-scope question for each in_doubt item, with the fact of 7.4 for its event (FINAL 7.8), once per (family,
    fact), never one a proposal of the family already asks (``asked``: the (family, fact, question) of the proposals'
    questions - D89: only that very question). One service question per (family, fact): the act it names is the first
    in doubt, in the reading's order, that no proposed code names in its own question (DECISIONS D149, replacing D142's
    order; its claim corrected by D154). ``holding``: the event ids the proposed codes hold on.

    DECISIONS D157 (3) (round 5f; D154's class (ii), and the round-5e review of D154, problem 1): ``holding`` is LIVE -
    assess passes the events that the question of every proposal held NOT DOCUMENTED names (events.Question.events,
    support['question_events']; assess.py's one call, narrowed at the round 5f integration: a bundling identity's
    act_target names a whole act, never an act in doubt). An act in doubt that a proposed code's own question already names is asked through that
    code: it yields its (family, fact) service slot to the next act in doubt no code's question names, and keeps the
    slot only when no such act is left - so which facts are asked never depends on the order (no question is dropped),
    only which act each one names. Act identity only (event ids), never a fact or a wording: a different act's question
    is never suppressed (D89 stands). "At that time, cautery was applied to the ulcer base." (a bleeding control in
    doubt, D142; 43255 held not documented names it, D157) before "At that time, biopsies of the gastric antrum were
    taken with cold forceps.": the biopsy's "done at this encounter?", whose answer decides the missing 43239, is asked,
    as f9013e12e and e5628be56 ask it; the cautery's had taken the slot (D154's class (ii)). Nothing here reads which
    act's answer decides a code that is missing, so that question is still NOT guaranteed where the act named by a code
    is not the one that takes the slot: beside 43245 READY on the pyloric dilation, Corti's 43249 held another_site
    names E2, the pyloric dilation (not in doubt), so the doubted esophageal dilation's "done at this encounter?" is
    asked and the biopsy's, which decides the missing 43239, is not. The other act stays listed in doubt (a structural
    residual of one service question per (family, fact), recorded with D154)."""
    # D89: ``asked`` holds (family, fact, question) of the proposals' questions; a code's question suppresses a service
    # question only when it IS that question (its fact and its words, which name the act) - a code asking
    # statement_scope about its snare no longer silences the service's statement_scope about another act's denial
    codes_asked = {tuple(entry) for entry in asked}
    held = frozenset(holding)

    def accounted(eid: str) -> bool:
        """DECISIONS D149 (round 5d; the round-5c review of D142, review_egd3.json problem 0): whether a proposed code
        holds on the act - ``eid`` among ``holding``, the events the proposals' own questions name (D157 (3): assess
        passes them). Never a profile that covers the act's kind: D142 read one, and "At that time, the
        distal esophageal stricture was dilated with an 18 mm balloon." (in doubt) beside "The pyloric stricture was
        dilated with a 15 mm balloon." (43245 READY on it) was read as accounted for by 43245, whose covers hold the
        dilation kind though it reads only the pyloric dilation - so "At that time, biopsies of the gastric antrum were
        taken ..." took the family's event_time question, and the dilation's, whose answer decides a missing 43249, was
        not asked. An act in doubt is never among the counted codes' supporting or read events (reconcile lists in doubt
        only an act no counted code reads), so only the events a code's question names can hold one; which act's answer
        decides a missing code is never read here (D154)."""
        return eid in held

    # D149 (its claim corrected by D154; live since D157 (3)): one question per (family, fact) - an act a proposed code
    # names in its own question (``holding``) is asked after the others, each group in the reading's order (stable), so
    # it yields the slot and is asked itself only when no other act takes that (family, fact): no fact is ever dropped
    seen = set()
    out = []
    for item, eid in sorted(coverage.in_doubt, key=lambda pair: accounted(pair[1])):
        question = events.focus_question(reading, reading.events[eid])
        if question is None or (item['family'], question.fact) in seen \
                or (item['family'], question.fact, question.question) in codes_asked:
            continue
        seen.add((item['family'], question.fact))
        out.append(ClarificationSpec(scope='service', fact=question.fact, question=question.question,
                                     reason=question.reason, family=item['family']))
    return out


def service_extent_questions(reading, sessions_: Mapping, asked=()) -> list:
    """DECISIONS D125 (the round-4 parity audit: colon-sig gap 1, egd gap I; the enteroscopy review's parity note 2):
    the service-scope extent question of the installed release's reconcile.documentation_clarifications (c2e53f8e
    reconcile.py:960-967, asked through engine._service_questions) - for each documented session (a done event: the
    services the reconciliation reads) of a colonoscopy, a flexible sigmoidoscopy, an upper endoscopy or an enteroscopy
    whose done examinations (done_examinations) state neither a reach nor a completion, and for which no proposal of
    the family already asks the extent (``asked``: the (family, fact[, question]) of the proposals' questions, as assess
    passes in_doubt_questions; an excluded proposal asks none), once per family: the catalogue's own question
    (catalogue.ENDOSCOPIC_QUESTIONS, "How far was the instrument advanced (the landmark reached)?"), counted among the
    open questions as there.

    A reach or a completion counts as stated when it is usable (verified, or default-accepted, and not opened) - a reach
    that names a place (not 'not_stated'), a completion stated complete or incomplete. One that is unverified or opened
    is a doubt, never a fact (DECISIONS D87): it establishes no extent, so the question is asked, never dropped; so is a
    reach only an examination D62 reads as possibly current states (never ``done_examinations``'), and a session told
    only by its acts, which no reach entry can name. A question only: no code's status changes."""
    families = ('gi.egd', 'gi.colonoscopy', 'gi.flex_sig', 'gi.enteroscopy')  # reconcile.py:961-962's (c2e53f8e)
    proposed = {(entry[0], entry[1]) for entry in asked}
    out = []
    for session in sessions_.values():
        family = session.family
        entry = catalogue.entry(family)
        if family not in families or not session.done or entry is None or entry.support != catalogue.SUPPORTED:
            continue
        question = dict(entry.questions).get('extent')
        if not question or (family, 'extent') in proposed:
            continue
        stated = False
        for exam in done_examinations(reading, family):
            reach, completion = exam.get('extent'), exam.get('completion')
            if (verify.usable(reach) and reach.get('value') not in ('', 'not_stated')) or (
                    verify.usable(completion) and completion.get('value') in ('complete', 'incomplete')):
                stated = True
                break
        if stated:
            continue
        proposed.add((family, 'extent'))
        out.append(ClarificationSpec(
            scope='service', fact='extent', question=question, family=family,
            reason=(f"CPT Studio's reading of the documented {session.label} does not establish how far the instrument "
                    'was advanced or whether the examination was completed.')))
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
                           and events.value(event, 'kind') not in lexicon.EM_KINDS]
                          + eus_unprofiled_entries(reading, members),  # D137: an act no EUS code accounts for
            'doubted': [_entry(reading, event) for event in members if doubted(reading, event)
                        and events.value(event, 'kind') not in lexicon.EM_KINDS]
                       + eus_unprofiled_entries(reading, members, doubted=True),  # D145: such an act begun or in doubt
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
