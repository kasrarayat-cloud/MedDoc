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

A code whose class does not fit is held, never excluded and never READY, with the extent question (fact ``extent``),
worded as D43's EUS form words it: the class question ("... reached the jejunum. Was <its class> performed on the date of
service?") where the reach fits another class, or fits the code's own class and only the route is not verified (D43's
stoma arm); its incomplete form where only the incompleteness keeps the code's own class from fitting (D43's incomplete
arm); and R6's own extent question where the reach fits no class at all (the bulb, the second portion). A reach that is
not verified, or a session with no single current examination, is R6's: the enteroscopy profile requires the extent, so
the missing fact is asked (no second question).

Read only from the inventory's verified structure (the reach's landmark, the examination's completion and status, the
encounter's anatomy) - no word list, no passage read (EB1). Pure and Django-free; imports nothing from studio.gi but the
reference table gi.catalogue.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Optional

from studio.gi import catalogue
from studio.interpretation import events, mapping, verify, wording
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

# CPT Studio's own words for each class (never a descriptor), and the check's id and label: the EUS class check's id
# (wording.EXAMINATION_CLASS_CHECK), with the enteroscopy's label
CLASS_WORDS = MappingProxyType({
    JEJUNAL: 'a small-bowel enteroscopy past the second portion of the duodenum that stops short of the ileum',
    ILEAL: 'a small-bowel enteroscopy past the second portion of the duodenum that reaches the ileum',
    STOMA: 'an examination of the ileum through a stoma',
    POUCH: 'an endoscopic examination of a small-intestinal pouch'})
CHECK = ('facts.examination_class', 'Small-bowel enteroscopy examination class')
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


def fits(exam_class: str, landmark: str, verified_routes, stated_incomplete: bool) -> bool:
    """Whether a verified reach at ``landmark`` fits ``exam_class``, with the encounter's ``verified_routes`` and the
    examination ``stated_incomplete`` or not."""
    if landmark not in CLASS_REACH[exam_class]:
        return False
    if exam_class in ROUTES and ROUTES[exam_class] not in verified_routes:
        return False
    return not (stated_incomplete and exam_class in DEEPER)


CLASS_FORM, INCOMPLETE_FORM, EXTENT_FORM = 'class', 'incomplete', 'extent'


def class_hold(code: str, exam_class: str, reached: str, words: str, form: str) -> tuple[str, str]:
    """(reason, question) of a code whose class the verified reach does not fit, in D43's form (wording.
    examination_class_hold's): ``form`` CLASS_FORM the class question, INCOMPLETE_FORM its incomplete form, EXTENT_FORM
    R6's own extent question."""
    required = CLASS_WORDS[exam_class]
    said, shown = (f' ({wording.quote(words)})', f' ({wording.quote(words, 120)})') if words else ('', '')
    stated = ' and as incomplete' if form == INCOMPLETE_FORM else ''
    reason = (f'The enteroscopy is documented as reaching the {reached}{said}{stated}; {code} accounts for {required}, '
              'which CPT Studio could not find in the document.')
    if form == INCOMPLETE_FORM:
        question = (f'The documented enteroscopy{shown} is stated to be incomplete. Was {required} performed on the date '
                    'of service?')
    elif form == CLASS_FORM:
        question = (f'The documented enteroscopy{shown} reached the {reached}. Was {required} performed on the date of '
                    'service?')
    else:
        question = EXTENT_QUESTION.format(label=wording.family_label(FAMILY))
    return reason, question


def enteroscopy_hold(code: str, family: str, key: str, reading, sessions_: Mapping, reach: tuple) -> Optional[tuple]:
    """D108: (check, clarification) of an enteroscopy code whose class its session examination's verified reach - the
    extent fact's (``reach``: assess._reach's (landmark, extent record)) - and the encounter's routes do not fit, in
    assess._examination_class's shape so the engine treats both alike (a warn check; the extent question, a
    reinstatement wait on an excluded code). None when the code has no enteroscopy class, when it fits, or when the
    reach is not verified (R6 asks the missing extent). Never an exclusion."""
    exam_class = code_class(code)
    landmark, extent = reach if isinstance(reach, tuple) and len(reach) == 2 else ('', None)
    if not exam_class or family != FAMILY or not landmark:
        return None
    session = sessions_.get(FAMILY)
    examination = reading.events.get(session.event) if session is not None and session.event else None
    verified_routes = routes(reading.encounter)
    stated = incomplete(examination)
    if fits(exam_class, landmark, verified_routes, stated):
        return None
    if stated and fits(exam_class, landmark, verified_routes, False):
        form = INCOMPLETE_FORM  # only the incompleteness keeps its own class from fitting (D43, D56, D72)
    elif landmark in CLASS_REACH[exam_class] or any(fits(other, landmark, verified_routes, stated)
                                                    for other in CLASSES if other != exam_class):
        form = CLASS_FORM  # its own reach without its route (D43's stoma arm), or the reach of another class
    else:
        form = EXTENT_FORM  # a reach no class fits
    record = extent.get('words') if isinstance(extent, Mapping) else None
    words = (record.get('text') or '') if isinstance(record, Mapping) else ''
    reason, question = class_hold(code, exam_class, wording.landmark_label(landmark), words, form)
    return (Check(*CHECK, 'warn', reason, wording.SOURCE),
            ClarificationSpec(scope='proposal', fact='extent', question=question, reason=reason, family=family,
                              proposal_key=key))
