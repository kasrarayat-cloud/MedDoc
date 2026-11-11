"""The examination class of a small-bowel enteroscopy code (DECISIONS D108; FINAL 7.2 R6; the round-4 refutation,
finding 24): a code of the enteroscopy family is READY only when its CLASS fits its session examination's verified reach -
the reach R6's extent fact reads (assess._reach) - and, for the stoma and pouch codes, the encounter's verified route.

The classes, by the code ranges their CPT descriptors name (cited here for the engineer, never shown to a customer; no
descriptor is connected):
- 44360-44373, "Small intestinal endoscopy, enteroscopy beyond second portion of duodenum, not including ileum": a
  verified reach beyond the second portion of the duodenum that is not the ileum - the jejunum (JEJUNAL);
- 44376-44379, "... enteroscopy beyond second portion of duodenum, including ileum": a verified ileal reach - the ileum,
  the terminal ileum or the neo-terminal ileum (ILEAL);
- 44380-44384, "Ileoscopy, through stoma": the encounter's verified stoma (mapping.has_stoma, D43's reading of a stoma
  code's route) and a verified ileal reach (STOMA);
- 44385-44386, "Endoscopic evaluation of small intestinal pouch (eg, Kock pouch, ileal reservoir [S or J])": the
  encounter's verified pouch (an altered-anatomy pouch entry, read as has_stoma reads a stoma) and a verified reach in
  the pouch or the ileum (POUCH).
A reach at the duodenal bulb, the second portion (whose landmark also takes "third portion" words), the duodenum or
ampulla, the small bowel named only as such (it may be the jejunum or the ileum), an anastomosis, or anywhere before the
duodenum or beyond the ileum fits no enteroscopy class. As D43 reads the full EUS class, an examination stated
incomplete in ANY state (D56: verified, unverified or opened) or whose status is attempted_not_completed (D72) never fits
the class that needs the deeper reach, ILEAL; JEJUNAL, like D43's limited class, reads its reach only.

DECISIONS D114 (the round-4 review of D108, problems 0, 2 and 4): with a verified stoma or pouch in the encounter, an
ileal reach fits a class only through the EXAMINATION's own route. The encounter's anatomy says a stoma or a pouch
exists; it never says the examination went through it (an oral double-balloon enteroscopy in a patient with an end
ileostomy reaches the same ileum as an ileoscopy through that ileostomy). So, beside a verified stoma or pouch, an ileal
reach fits ILEAL only when the examination's route is verified oral, STOMA only when it is verified through the stoma,
and POUCH only when it is verified through the pouch; a route not verified fits none of them, and every such code is
held with the route question (fact ``extent``), never READY. The route is verified when the words of the examination's
own statement - its procedure, kind, technique and status words, usable (EB1: the words Gemini cited, located in their
own passages; never a passage scanned) - name exactly one route of ROUTE_WORDS, and no other route is named in ANY of
its own located words (its reach, completion, time and performer words too): a route named anywhere else in its words
is a doubt (D87), and its reach words may name a stoma or a pouch only as a place ("the pre-pouch ileum", "20 cm
proximal to the ileostomy"), so they never verify a route. Without a verified stoma or pouch, the classes read as D108
built them; a reach at the pouch itself is the pouch's (D108).

A code whose class does not fit is held, never excluded and never READY, with the extent question (fact ``extent``),
worded as D43's EUS form words it: the class question ("... reached the jejunum. Was <its class> performed on the date
of service?") where the reach fits another class, or fits the code's own class and only the route is not verified (D43's
stoma arm) - with the examination's route named where D114 verified it; D114's route question where the reach, the
anatomy and the incompleteness fit the code's own class and only the examination's route is not verified; its incomplete
form where only the incompleteness keeps the code's own class from fitting (D43's incomplete arm); and R6's own extent
question where the reach fits no class at all (the bulb, the second portion). A reach that is not verified, or a session
with no single current examination, is R6's: the enteroscopy profile requires the extent, so the missing fact is asked
(no second question).

DECISIONS D114 (the round-4 review of D108, parity note 1): an act whose session for coding is not the enteroscopy's -
coverage.sessions groups an act Gemini files under the enteroscopy, verified in the upper tract an EGD examines, into a
done EGD session (coverage.coding_family; the installed release's services.FAMILY_REGIONS) - supports no enteroscopy
code there: a code each of whose supporting acts, for one of its requirement groups, its own session does not hold is
held (service.act_elsewhere; performed_status), never READY and never excluded, whatever its class. The enteroscopy's
diagnostic code, which such an act held base_included in its own session, stays held beside it (the act's procedure
question): Gemini's reading of the act as the enteroscopy's is a doubt (D87), never an absence that would release it.
Where its class does not fit either, the one question asks both (D89: a doubt never takes another doubt's question) -
the class question first, then the act's: its class check carries both reasons.

Read only from the inventory's verified structure (the reach's landmark, the examination's completion and status, the
encounter's anatomy, the sessions coverage groups) and the examination's own located words (D114's route) - no passage
read (EB1). Pure and Django-free; imports nothing from studio.gi but the reference table gi.catalogue.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Optional

from studio.gi import catalogue
from studio.interpretation import coverage, events, lexicon, mapping, verify, wording
from studio.types import Check, ClarificationSpec

FAMILY = 'gi.enteroscopy'
JEJUNAL, ILEAL, STOMA, POUCH = 'jejunal', 'ileal', 'stoma', 'pouch'
CLASSES = (JEJUNAL, ILEAL, STOMA, POUCH)
# (first code, last code, class): the descriptors' ranges, every catalogue code of the family in exactly one
# (tests/test_interpretation_r4_enteroscopy.py pins it, so a code added to the catalogue is never classless)
RANGES = ((44360, 44373, JEJUNAL), (44376, 44379, ILEAL), (44380, 44384, STOMA), (44385, 44386, POUCH))
ILEAL_REACH = frozenset({'ileum', 'terminal_ileum', 'neo_terminal_ileum'})
CLASS_REACH = MappingProxyType({JEJUNAL: frozenset({'jejunum'}), ILEAL: ILEAL_REACH, STOMA: ILEAL_REACH,
                                POUCH: ILEAL_REACH | frozenset({'pouch'})})
ROUTES = MappingProxyType({STOMA: 'stoma', POUCH: 'pouch'})  # the altered-anatomy landmark each route needs
DEEPER = frozenset({ILEAL})  # never fits an examination stated incomplete (D43, D56, D72)

# D114: the examination's own route. Each route's words, matched in lexicon.fold's form, word-bounded (lexicon.found):
# the spec's own ('orally', 'peroral', 'per os', 'through the mouth', 'antegrade'; the ileostomy, the stoma, the pouch)
# and their forms. A closed list read only in the examination's own located words; a word missing here leaves the route
# not verified - held, never READY.
ORAL, THROUGH_STOMA, THROUGH_POUCH = 'oral', 'stoma', 'pouch'
ROUTE_WORDS = MappingProxyType({
    ORAL: ('orally', 'oral', 'peroral', 'perorally', 'per oral', 'per os', 'transoral', 'transorally',
           'through the mouth', 'via the mouth', 'by mouth', 'antegrade', 'antegradely', 'anterograde',
           'anterogradely'),
    THROUGH_STOMA: ('ileostomy', 'ileostomies', 'stoma', 'stomas', 'stomal', 'ostomy', 'ostomies'),
    THROUGH_POUCH: ('pouch', 'pouches', 'pouchoscopy', 'reservoir'),
})
CLASS_ROUTE = MappingProxyType({ILEAL: ORAL, STOMA: THROUGH_STOMA, POUCH: THROUGH_POUCH})  # the route each class needs
# the examination's attributes whose words state the examination itself (a route they name is verified), and every
# attribute whose located words are its own (a route any of them names is a doubt against another)
ROUTE_STATED = ('procedure', 'kind', 'technique', 'status')
ROUTE_READ = ROUTE_STATED + ('target', 'time', 'performer', 'scope', 'purpose', 'extent', 'completion')
ROUTE_PHRASES = MappingProxyType({ORAL: 'through the mouth', THROUGH_STOMA: 'through a stoma',
                                  THROUGH_POUCH: 'through a pouch'})

# CPT Studio's own words for each class (never a descriptor), and the check's id and label: the EUS class check's id
# (wording.EXAMINATION_CLASS_CHECK), with the enteroscopy's label
CLASS_WORDS = MappingProxyType({
    JEJUNAL: 'a small-bowel enteroscopy past the second portion of the duodenum that stops short of the ileum',
    ILEAL: 'a small-bowel enteroscopy past the second portion of the duodenum that reaches the ileum',
    STOMA: 'an examination of the ileum through a stoma',
    POUCH: 'an endoscopic examination of a small-intestinal pouch'})
CHECK = ('facts.examination_class', 'Small-bowel enteroscopy examination class')
# D114 (parity note 1): the installed release's check id and label for a coded act documented in another service
# (reconcile.placed_check; customer_api.EXCLUSION_REASONS words it "documented in another procedure")
ELSEWHERE_CHECK = ('service.act_elsewhere', 'Coded act documented in another service')
# checks.FACT_QUESTIONS['extent'] (copied; pinned equal to the question R6 asks of an unverified enteroscopy reach)
EXTENT_QUESTION = '{label}: confirm the furthest extent reached.'


def code_class(code) -> str:
    """The class of a catalogue code of the enteroscopy family ('' for any other code)."""
    profile = catalogue.code_profile(code) if isinstance(code, str) else None
    if profile is None or profile.family != FAMILY or not code.isdigit():
        return ''
    number = int(code)
    return next((name for first, last, name in RANGES if first <= number <= last), '')


def routes(encounter: Mapping) -> frozenset:
    """The routes the encounter's anatomy verifies: 'stoma' (mapping.has_stoma, D43's own reader) and 'pouch' (a usable
    altered-anatomy pouch entry, read the same way)."""
    pouch = any(isinstance(entry, Mapping) and entry.get('value') == 'pouch' and entry.get('anatomy') == 'altered'
                and verify.usable(entry) for entry in (encounter.get('anatomy') or ()))
    return frozenset(name for name, held in (('stoma', mapping.has_stoma(encounter)), ('pouch', pouch)) if held)


def incomplete(examination: Optional[Mapping]) -> bool:
    """D56 and D72, as assess._examination_class reads them for the full EUS class: the examination's completion is
    'incomplete' in ANY state, or its status is attempted_not_completed (fail-closed)."""
    if examination is None:
        return False
    completion = examination.get('completion')
    return ((isinstance(completion, Mapping) and completion.get('value') == 'incomplete')
            or events.value(examination, 'status') == 'attempted_not_completed')


def _words(record) -> str:
    """The located words of an attribute record ('' when it has none)."""
    words = record.get('words') if isinstance(record, Mapping) else None
    return (words.get('text') or '') if isinstance(words, Mapping) else ''


def named_routes(examination: Mapping, names, usable_only: bool) -> dict:
    """D114: {route: the first words naming it} over the located words of ``examination``'s attributes ``names`` - only
    the usable ones (verified, not opened) when ``usable_only``."""
    found = {}
    for name in names:
        record = examination.get(name)
        if usable_only and not verify.usable(record):
            continue
        text = _words(record)
        for route_name, phrases in ROUTE_WORDS.items():
            if text and route_name not in found and lexicon.holds(text, phrases):
                found[route_name] = text
    return found


def examination_route(examination: Optional[Mapping]) -> tuple:
    """D114: (the examination's verified route, the words that state it): ('', '') unless the usable words of its own
    statement (ROUTE_STATED) name exactly one route and none of its own located words (ROUTE_READ) names another."""
    if examination is None:
        return '', ''
    stated = named_routes(examination, ROUTE_STATED, True)
    if len(stated) != 1 or set(named_routes(examination, ROUTE_READ, False)) != set(stated):
        return '', ''
    return next(iter(stated.items()))


def route_read(verified_routes, landmark: str) -> bool:
    """D114: whether the examination's own route decides the class - an ileal reach beside the encounter's verified
    stoma or pouch (a pouch reach is the pouch's; with neither, D108's classes as built)."""
    return bool(verified_routes) and landmark in ILEAL_REACH


def fits(exam_class: str, landmark: str, verified_routes, stated_incomplete: bool, taken: Optional[str] = None) -> bool:
    """Whether a verified reach at ``landmark`` fits ``exam_class``, with the encounter's ``verified_routes``, the
    examination ``stated_incomplete`` or not, and (D114, where route_read) the examination's verified route ``taken``
    ('' when not verified; None when the route decides nothing)."""
    if landmark not in CLASS_REACH[exam_class]:
        return False
    if exam_class in ROUTES and ROUTES[exam_class] not in verified_routes:
        return False
    if taken is not None and exam_class in CLASS_ROUTE and taken != CLASS_ROUTE[exam_class]:
        return False  # D114: the examination did not verifiably go the class's way
    return not (stated_incomplete and exam_class in DEEPER)


CLASS_FORM, INCOMPLETE_FORM, EXTENT_FORM, ROUTE_FORM = 'class', 'incomplete', 'extent', 'route'


def _through(verified_routes) -> str:
    """The ways the encounter's anatomy opens, as ROUTE_FORM names them."""
    ways = ' or '.join(f'through the documented {name}' for name in sorted(verified_routes))
    return ways or 'through a stoma or pouch'


def class_hold(code: str, exam_class: str, reached: str, words: str, form: str, *, route: str = '',
               route_words: str = '', through=(), stated_incomplete: bool = False) -> tuple[str, str]:
    """(reason, question) of a code whose class the verified reach does not fit, in D43's form (wording.
    examination_class_hold's): ``form`` CLASS_FORM the class question, INCOMPLETE_FORM its incomplete form, EXTENT_FORM
    R6's own extent question, ROUTE_FORM (D114) the route question - the examination's route not stated beside the
    encounter's stoma or pouch (``through``: the routes its anatomy verifies; ``stated_incomplete``: the examination is
    stated incomplete too, so the one question names both). ``route`` and ``route_words`` (D114): the examination's
    verified route and the words that state it, named in the class question."""
    required = CLASS_WORDS[exam_class]
    said, shown = (f' ({wording.quote(words)})', f' ({wording.quote(words, 120)})') if words else ('', '')
    stated = ' and as incomplete' if form == INCOMPLETE_FORM else ''
    if form == ROUTE_FORM:
        ways = _through(through)
        also, also_shown = (' and as incomplete', ' and is stated to be incomplete') if stated_incomplete else ('', '')
        reason = (f'The enteroscopy is documented as reaching the {reached}{said}{also}, and CPT Studio could not '
                  f'confirm from the document whether it was passed through the mouth or {ways}; {code} accounts for '
                  f'{required}, which CPT Studio could not find in the document.')
        question = (f'The documented enteroscopy{shown} reached the {reached}{also_shown}; CPT Studio could not '
                    f'confirm from the document whether it was passed through the mouth or {ways}. Was {required} '
                    'performed on the date of service?')
        return reason, question
    way = (f' {ROUTE_PHRASES[route]} ({wording.quote(route_words)})', f' {ROUTE_PHRASES[route]} '
           f'({wording.quote(route_words, 120)})') if route in ROUTE_PHRASES and form == CLASS_FORM else ('', '')
    reason = (f'The enteroscopy is documented as reaching the {reached}{said}{way[0]}{stated}; {code} accounts for '
              f'{required}, which CPT Studio could not find in the document.')
    if form == INCOMPLETE_FORM:
        question = (f'The documented enteroscopy{shown} is stated to be incomplete. Was {required} performed on the date '
                    'of service?')
    elif form == CLASS_FORM:
        question = (f'The documented enteroscopy{shown} reached the {reached}{way[1]}. Was {required} performed on the '
                    'date of service?')
    else:
        question = EXTENT_QUESTION.format(label=wording.family_label(FAMILY))
    return reason, question


def act_elsewhere(code: str, reading, sessions_: Mapping) -> Optional[tuple]:
    """D114 (parity note 1): (the act, the session that holds it, what the code accounts for - '' for a code that
    accounts for the examination itself) when the code's act is held by another family's session for coding.
    coverage.sessions groups an act by coverage.coding_family, so an enteroscopy act verified in the upper tract beside
    a done EGD is the EGD session's. An act code: for one of its requirement groups, every event that supports it
    (events.supports) is held by another family's session. A code that accounts for the examination itself (its
    session's examination never moves): an act Gemini filed under the enteroscopy, reportable or doubted
    (coverage.reportable, coverage.doubted - what holds the base code base_included in its session), is held by another
    family's session; at 1caaf0609 that act held the base code base_included, and Gemini's own reading of it as the
    enteroscopy's is a doubt (D87), so the base code stays held, never READY. None otherwise."""
    link = mapping.code_link(code)
    if not link.linked:
        return None
    own = sessions_.get(FAMILY)
    mine = frozenset(own.events) if own is not None else frozenset()

    def holder_of(event: Mapping):
        return next((session for session in sessions_.values()
                     if session.family != FAMILY and event['id'] in session.events), None)

    if events.examination_code(link):
        for event in reading.events.values():
            if (event.get('family') == FAMILY and event['id'] not in mine and holder_of(event) is not None
                    and (coverage.reportable(reading, event) or coverage.doubted(reading, event))):
                return event, holder_of(event), ''
        return None
    for group in events.requirements(link):
        found = [event for event in reading.events.values() if events.supports(reading, link, group, event)]
        if not found or any(event['id'] in mine for event in found):
            continue
        for event in found:
            holder = holder_of(event)
            if holder is not None:
                return event, holder, events.group_label(link, group)
    return None


def elsewhere_hold(code: str, family: str, key: str, reading, event: Mapping, holder, what: str) -> tuple:
    """D114: (check, clarification) of an enteroscopy code whose act ``event`` the session ``holder`` holds for coding,
    in another_site's form: held, never READY and never excluded - an act code with performed_status, and a code that
    accounts for the examination itself (``what`` '') with the act's procedure question (wording.procedure_question)."""
    place = wording.landmark_label(mapping.target_landmark(event))
    words = _words(event.get('target'))
    said, shown = (f' ({wording.quote(words)})', f' ({wording.quote(words, 120)})') if words else ('', '')
    act, kind = events.event_label(reading, event), wording.event_kind_label(event.get('catalogue_kind') or '')
    if not what:
        reason = (f'The {act} is filed under the small-bowel enteroscopy and documented at the {place}{said}, which '
                  f'the {holder.label} of this encounter examines, so CPT Studio reads it as an act of the '
                  f'{holder.label}; if it was done in the enteroscopy, {code} is included in the code for it.')
        return (Check(*ELSEWHERE_CHECK, 'warn', reason, wording.SOURCE),
                ClarificationSpec(scope='proposal', fact='procedure', question=wording.procedure_question(kind, words),
                                  reason=reason, family=family, proposal_key=key))
    reason = (f'The {act} is documented at the {place}{said}, which the {holder.label} of this encounter examines, so '
              f'CPT Studio reads it as an act of the {holder.label}; {code} accounts for {what} in a small-bowel '
              'enteroscopy, which CPT Studio could not find in the document.')
    question = (f'The documented {kind}{shown} is at the {place}, which the {holder.label} of this encounter examines. '
                f'Was {what} performed in the small-bowel enteroscopy on the date of service?')
    return (Check(*ELSEWHERE_CHECK, 'warn', reason, wording.SOURCE),
            ClarificationSpec(scope='proposal', fact='performed_status', question=question, reason=reason,
                              family=family, proposal_key=key))


def enteroscopy_hold(code: str, family: str, key: str, reading, sessions_: Mapping, reach: tuple) -> Optional[tuple]:
    """D108: (check, clarification) of an enteroscopy code whose class its session examination's verified reach - the
    extent fact's (``reach``: assess._reach's (landmark, extent record)) - the encounter's routes and (D114) the
    examination's own route do not fit (class_misfit), or (D114) whose act another session holds (act_elsewhere), in
    assess._examination_class's shape so the engine treats both alike (a warn check; one question, a reinstatement wait
    on an excluded code). Where both hold the code, D89's rule (questions are never displaced) keeps both doubts in the
    one question, the class question first: the class check, its detail and the question naming both. None when the code
    has no enteroscopy class, when it fits and its acts are its session's, or when the reach is not verified and its
    acts are its session's (R6 asks the missing extent). Never an exclusion."""
    exam_class = code_class(code)
    if not exam_class or family != FAMILY:
        return None
    misfit = class_misfit(code, exam_class, family, key, reading, sessions_, reach)
    elsewhere = act_elsewhere(code, reading, sessions_)  # D114 (parity note 1)
    if elsewhere is None:
        return misfit
    region = elsewhere_hold(code, family, key, reading, *elsewhere)
    if misfit is None:
        return region
    check, spec = misfit
    return (replace(check, detail=f'{check.detail} {region[0].detail}'),
            replace(spec, question=f'{spec.question} {region[1].question}', reason=f'{spec.reason} {region[1].reason}'))


def class_misfit(code: str, exam_class: str, family: str, key: str, reading, sessions_: Mapping,
                 reach: tuple) -> Optional[tuple]:
    """D108 and D114's route: (check, clarification) of an enteroscopy code of ``exam_class`` whose class its session
    examination's verified reach, the encounter's routes and the examination's own route do not fit; None when it fits
    or the reach is not verified."""
    landmark, extent = reach if isinstance(reach, tuple) and len(reach) == 2 else ('', None)
    if not landmark:
        return None
    session = sessions_.get(FAMILY)
    examination = reading.events.get(session.event) if session is not None and session.event else None
    verified_routes = routes(reading.encounter)
    stated = incomplete(examination)
    taken, taken_words = examination_route(examination) if route_read(verified_routes, landmark) else (None, '')
    if fits(exam_class, landmark, verified_routes, stated, taken):
        return None
    if stated and fits(exam_class, landmark, verified_routes, False, taken):
        form = INCOMPLETE_FORM  # only the incompleteness keeps its own class from fitting (D43, D56, D72)
    elif taken == '' and fits(exam_class, landmark, verified_routes, False):
        form = ROUTE_FORM  # D114: its reach and the encounter's anatomy fit; the examination's route is not verified
    elif landmark in CLASS_REACH[exam_class] or any(fits(other, landmark, verified_routes, stated)
                                                    for other in CLASSES if other != exam_class):
        form = CLASS_FORM  # its own reach without its route (D43's stoma arm), or the reach of another class
    else:
        form = EXTENT_FORM  # a reach no class fits
    record = extent.get('words') if isinstance(extent, Mapping) else None
    words = (record.get('text') or '') if isinstance(record, Mapping) else ''
    reason, question = class_hold(code, exam_class, wording.landmark_label(landmark), words, form, route=taken or '',
                                  route_words=taken_words, through=verified_routes, stated_incomplete=stated)
    return (Check(*CHECK, 'warn', reason, wording.SOURCE),
            ClarificationSpec(scope='proposal', fact='extent', question=question, reason=reason, family=family,
                              proposal_key=key))
