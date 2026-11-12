"""Events and the catalogue (design/contract.md 9; design/FINAL.md C3, C6, C7, C8 and 7.3; design/ADJUDICATION.md C-1 and
C-6): the mapping fields every event carries (its catalogue kind, its technique class and its code key), the landmark
regions, the umbrellas, and how a proposed code links to events.

Reference tables only. This module reads studio.gi.profiles (the family a code routes to) and studio.gi.catalogue (what a
code accounts for, what a family reconciles, NOT_REPORTED, UNSUPPORTED_ACTS, READ_UNDER, UNRECONCILED_ACTS and
UNRECONCILED_REGIONS) - tables and pure lookups - and nothing else of studio.gi (FINAL 3.1; tests/test_interpretation_no_gi).
REGION_OF is this module's own copy of studio.gi.services.REGION_OF, keyed by the schema's LANDMARKS, and a test pins it
equal to the legacy table through a test-only import, so no gi.services code ever runs here (C8).

The mapping of an event (contract 9.1, map_events, the last of normalize.LINKED_STEPS):
- ``family``: normalize sets it ('gi.' + the procedure; other_gi is gi.other, not_gi gi.unsupported, unknown none).
- ``catalogue_kind``: an examination is the session, never an act (C-1): ``eus_exam`` in the EUS family, ``examination``
  in every other; an E/M visit is ``em_visit`` or ``em_prolonged``; a clip or an injection whose purpose ``hemostasis`` is
  verified is ``bleeding_control`` (COMMON_BUNDLED's clip rule, FINAL 7.7); ``removal`` and ``intervention`` are the
  umbrellas (6.5); ``other`` maps to none (listed for the reviewer, never reconciled); every other kind keeps its name.
- ``code_technique``: the technique class a code can depend on (CodeProfile.technique): ``balloon``, ``wire_bougie`` or
  the unguided ``bougie``, read from a VERIFIED device only; every other device is evidence only ('').
- ``key``: the event's code key - family, catalogue kind, service kind (an examination's), technique class, the region
  of its verified target landmark, its role for coverage (session, act, not_reported, unsupported, umbrella, listed) and
  an umbrella's members.

How a proposed code links to events (code_link; FINAL C7 as ADJUDICATION C-6 amends it - route (c) is REMOVED):
- (a) ``catalogue``: catalogue.code_profile(C) whose family is profiles.family_for_code(C). Its candidate kinds K(C) are
  its covers, an examination for a base code with none (the examination of C's family). C-1: the examination kinds are
  the SESSION, never an act - ``acts`` are the kinds besides them, and a code whose covers hold an examination kind and
  others needs a supporting event of EACH of the others (read by the engine, slice S08). DECISIONS D27 (FINAL 7.3, the
  defining kinds): D(C) is C's covers less every kind another code of C's family covers ALONE (a covers of one kind);
  where D(C) is non-empty and smaller than C's covers (DEFINING, computed from the catalogue at import), C is matched
  only by an event of a kind in D(C) - ``defining`` - so a balloon stone extraction never matches the lithotripsy code
  43265, which 43264 accounts for alone. C-1's acts of an EUS code are its D(C) (pinned).
- (b) ``unreconciled``: a code with no profile that catalogue.UNRECONCILED_ACTS names (46221): K(C) = code_acts(C), each
  candidate's verified target landmark mapped into UNRECONCILED_REGIONS[C] (in_regions).
- (d) ``none``: every other code - no catalogue profile (``unprofiled``: "outside CPT Studio's coding profiles; review
  required", never READY, C-6), or a profile of another family than the code routes to (``family_mismatch``). The engine
  holds it with ``performed_status``: which documented act it accounts for is not established.

DECISIONS D80 (the round-3 refutation, finding 19): a code on route (a) of a RECOGNISED-ONLY family - one the catalogue
recognises and lists for review but does not reconcile, or that gi.profiles marks not supported (recognised_only; today
gi.sedation's 99152 and 99153) - is not assessed: the engine holds it with ``performed_status``, never READY and never
excluded, whatever the inventory states.

Pure and Django-free.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from studio.gi import catalogue, profiles
from studio.interpretation import lexicon, schema, verify

# --- landmark regions (C8) ---------------------------------------------------------------------------------------------

# Each LANDMARK -> the region names catalogue.READ_UNDER and UNRECONCILED_REGIONS use (studio.gi.services.REGION_OF's
# regions), '' where this vocabulary places it in no region: not stated, other, and the surgically made places whose
# position in the tract cannot be told (an anastomosis, a stoma, a pouch; lexicon.ALTERED_LANDMARKS). Copied from
# services.REGION_OF (services.py:131) and pinned equal to it by tests/test_interpretation_mapping.py: every landmark whose
# canonical name is a services.ANATOMY name has that name's region, and every landmark has the region services' own
# vocabulary reads in its first surface form (the right and left colon are read there as the ascending and descending
# colon, the neo-terminal ileum as the terminal ileum, the proximal and distal colon as the colon).
REGION_OF = MappingProxyType({
    'not_stated': '',
    'esophagus': 'esophagus', 'proximal_esophagus': 'esophagus', 'mid_esophagus': 'esophagus',
    'distal_esophagus': 'esophagus', 'gastroesophageal_junction': 'esophagus',
    'stomach': 'stomach', 'gastric_cardia': 'stomach', 'gastric_fundus': 'stomach', 'gastric_body': 'stomach',
    'gastric_antrum': 'stomach', 'pylorus': 'stomach',
    'duodenum': 'duodenum', 'duodenal_bulb': 'duodenum', 'second_portion_duodenum': 'duodenum',
    'ampulla': 'biliary',
    'jejunum': 'small_bowel', 'ileum': 'small_bowel', 'terminal_ileum': 'small_bowel',
    'neo_terminal_ileum': 'small_bowel', 'small_bowel': 'small_bowel',
    'colon': 'colon', 'right_colon': 'colon', 'left_colon': 'colon', 'proximal_colon': 'colon', 'distal_colon': 'colon',
    'cecum': 'colon', 'appendiceal_orifice': 'colon', 'ileocecal_valve': 'colon', 'ascending_colon': 'colon',
    'hepatic_flexure': 'colon', 'transverse_colon': 'colon', 'splenic_flexure': 'colon', 'descending_colon': 'colon',
    'sigmoid_colon': 'colon', 'rectosigmoid': 'colon',
    'rectum': 'rectum', 'anal_canal': 'anus',
    'anastomosis': '', 'stoma': '', 'pouch': '',
    'common_bile_duct': 'biliary', 'bile_duct': 'biliary', 'pancreatic_duct': 'pancreas', 'pancreas': 'pancreas',
    'gallbladder': 'biliary', 'liver': 'liver', 'lymph_node': 'node',
    'other': '',
})


def region(landmark: str) -> str:
    """The region of a LANDMARK ('' for none, or for a value that is no landmark)."""
    return REGION_OF.get(landmark, '')


def in_regions(landmark: str, regions) -> bool:
    """Whether ``landmark`` lies in one of ``regions`` (route (b)'s UNRECONCILED_REGIONS, READ_UNDER's regions)."""
    found = region(landmark)
    return bool(found) and found in tuple(regions)


# --- families, service kinds, catalogue kinds (contract 9.1) -----------------------------------------------------------

# The service kind of a family's examination (the catalogue's FamilyEntry.kinds; contract 9.1), pinned against
# catalogue.CATALOGUE by a test.
SERVICE_KIND = MappingProxyType({
    'gi.egd': 'egd', 'gi.colonoscopy': 'colonoscopy', 'gi.flex_sig': 'flex_sig', 'gi.eus': 'eus', 'gi.ercp': 'ercp',
    'gi.enteroscopy': 'enteroscopy', 'gi.capsule': 'capsule', 'gi.motility': 'manometry', 'gi.reflux': 'ph_study',
    'gi.anorectal': 'anorectal_testing', 'gi.feeding_tube': 'feeding_tube', 'gi.office_em': 'office_em',
})
# The families an endoscope examines in a session: their examination event is the session every act of the family
# belongs to (FINAL 7.8), and the base or EUS code's examination kind.
ENDOSCOPIC_FAMILIES = frozenset({'gi.egd', 'gi.enteroscopy', 'gi.colonoscopy', 'gi.flex_sig', 'gi.eus', 'gi.ercp'})

EXAMINATION = 'examination'
EUS_EXAMINATION = 'eus_exam'
# The session, never an act (ADJUDICATION C-1): a code whose covers hold one of these besides other kinds needs a
# supporting event of each OTHER kind; the examination only places it in its session.
EXAMINATION_KINDS = frozenset({EXAMINATION, EUS_EXAMINATION})
REMOVAL, INTERVENTION = 'removal', 'intervention'
# The removal umbrella's methods (reconcile.REMOVAL_KINDS, reconcile.py:36).
REMOVAL_MEMBERS = ('snare', 'emr', 'hot_biopsy', 'esd')
# Every act kind besides the examination, the visit, prolonged visit time and moderate sedation (contract 6.5), in the
# schema's order; a positive removal (method not stated) is an intervention too.
_NOT_INTERVENTIONS = frozenset({'examination', 'em_visit', 'em_prolonged', 'moderate_sedation', 'intervention',
                                'other'})
INTERVENTION_MEMBERS = tuple(kind for kind in schema.KINDS if kind not in _NOT_INTERVENTIONS)
UMBRELLAS = MappingProxyType({REMOVAL: REMOVAL_MEMBERS, INTERVENTION: INTERVENTION_MEMBERS})
# A tattoo and an injection are one act for coding (catalogue.family_codes_act, catalogue.py:369-379).
ONE_ACT = frozenset({'tattoo', 'injection'})
# The catalogue kinds an event can carry: the two examination kinds, every act kind of the schema, and the umbrellas.
CATALOGUE_KINDS = (EXAMINATION, EUS_EXAMINATION) + tuple(
    kind for kind in schema.KINDS if kind not in (EXAMINATION, 'other'))
# The kinds a clip or an injection whose verified purpose is hemostasis is read as (COMMON_BUNDLED's clip rule).
HEMOSTASIS_KINDS = frozenset({'clip', 'injection'})
BLEEDING_CONTROL = 'bleeding_control'
# The technique classes a code can depend on (CodeProfile.technique, catalogue.py:27-42 and 66): the device values that
# name them. Every other device is evidence only.
TECHNIQUE_CLASS = MappingProxyType({'balloon': catalogue.BALLOON, 'wire_bougie': catalogue.WIRE_BOUGIE,
                                    'bougie': 'bougie'})

# An event's role for coverage (the key's ``role``).
SESSION, ACT, NOT_REPORTED, UNSUPPORTED, UMBRELLA, LISTED = (
    'session', 'act', 'not_reported', 'unsupported', 'umbrella', 'listed')


def family(procedure: str) -> str:
    """The family slug of a PROCEDURES value (lexicon.FAMILY_OF; '' for unknown)."""
    return lexicon.family_of(procedure)


def service_kind(family_slug: str) -> str:
    """The service kind of a family's examination (contract 9.1), '' for a family with none."""
    return SERVICE_KIND.get(family_slug, '')


# --- a bleeding control in doubt (DECISIONS D115; the round-4 family parity audit, EGD gap D, critical) -----------------

# The catalogue kind of a clip or an injection done today whose hemostasis purpose is verified but for which its own
# words state no bleeding and name no hemostasis: "Two hemostatic clips were placed across the ulcer." beside "A 12 mm
# clean-based ulcer ...". The adjective names the device; a prophylactic clip is no control of bleeding (the installed
# release's HEMOSTATIC_ADJECTIVE rule, refutation multi-3, closed in ACCURACY-RESIDUALS). No code profile covers this
# kind, so no code is matched by it - neither the bleeding-control codes (43255, 43227, 44366, 44378, 44391, 45334,
# 45382: held with performed_status, never READY) nor the injection codes (43236, 43243: never READY on an act that may
# be a control of bleeding) - and the coverage reads it as a bleeding control in DOUBT (coverage.doubted), never as an
# absence: the base code beside it is held and the act is listed in doubt.
POSSIBLE_BLEEDING_CONTROL = 'possible_bleeding_control'
# D115: what states that bleeding is treated - the words the design names (bleeding, oozing, hemorrhage, a visible vessel,
# an adherent clot, stigmata of recent bleeding) with their inflections, and spurting (the installed BLEEDING_PRESENT's)
# - or names the hemostasis itself as the act (the noun: "for hemostasis", "to achieve hemostasis"; the installed rule
# reads any bleeding-control word but the adjective as the act). An inclusion list for the READY side: a word missing here
# leaves the act in doubt, a hold, never READY.
BLEEDING_STATED = ('bleeding', 'bleed', 'bleeds', 'bled', 'rebleeding', 'rebleed', 'oozing', 'ooze', 'oozes', 'oozed',
                   'hemorrhage', 'hemorrhages', 'hemorrhaged', 'hemorrhaging', 'haemorrhage', 'haemorrhages',
                   'haemorrhaged', 'haemorrhaging', 'spurting', 'spurt', 'spurts', 'spurted', 'visible vessel',
                   'visible vessels', 'adherent clot', 'adherent clots', 'stigmata of recent bleeding',
                   'stigmata of recent hemorrhage', 'stigmata of recent haemorrhage', 'hemostasis', 'haemostasis')
# D115: a word before such a word in the same words that negates it ("without stigmata of recent bleeding", "no active
# bleeding, oozing or visible vessel", "non-bleeding"): lexicon.NEGATORS and the words of an absence. Fail-closed: any
# one of them anywhere before it, whatever stands between (a list keeps its negation across its commas).
BLEEDING_NEGATORS = frozenset(lexicon.NEGATORS) | frozenset({'non', 'absent', 'absence', 'free', 'negative'})
# D115: words that make the bleeding words wherever they stand a prevention, a risk, a hedge, a condition or another
# occasion - no bleeding treated today ("to prevent delayed bleeding", "to ensure hemostasis", "if bleeding recurs", "a
# previously bleeding ulcer"). The act then stays in doubt (fail-closed).
NOT_BLEEDING_NOW = frozenset({
    'prevent', 'prevents', 'prevented', 'preventing', 'prevention', 'preventive', 'preventative', 'prophylaxis',
    'prophylactic', 'prophylactically', 'risk', 'risks', 'reduce', 'reduces', 'reduced', 'reducing', 'minimize',
    'minimise', 'minimizing', 'minimising', 'avoid', 'avoids', 'avoiding', 'ensure', 'ensures', 'ensuring', 'secure',
    'securing', 'maintain', 'maintaining', 'delayed', 'future', 'potential', 'potentially', 'possible', 'possibly',
    'probable', 'probably', 'suspected', 'suspicion', 'concern', 'concerning', 'anticipated', 'if', 'unless', 'should',
    'would', 'could', 'may', 'might', 'history', 'historical', 'previous', 'previously', 'prior', 'ago'})
_BLEEDING_PHRASES = tuple(tuple(lexicon.fold(phrase).split()) for phrase in BLEEDING_STATED)
_WORD = re.compile(r"\w+(?:'\w+)*")  # a folded word, a contraction kept whole ("wasn't")
# D115: the event's own words read (EB1: the act's own attribute words, never a passage, a neighbouring sentence or
# another record): its kind, status, target, device and purpose words.
HEMOSTASIS_WORDS = ('kind', 'status', 'target', 'technique', 'purpose')


def bleeding_stated(text: str) -> bool:
    """D115: whether one span of words ``text`` states bleeding treated, or names the hemostasis as the act: a
    BLEEDING_STATED phrase (folded, whole words) with no BLEEDING_NEGATORS word (or a contraction in n't) anywhere before
    it in the span, in a span holding no NOT_BLEEDING_NOW word."""
    tokens = _WORD.findall(lexicon.fold(text))
    if any(token in NOT_BLEEDING_NOW for token in tokens):
        return False
    for start in range(len(tokens)):
        if not any(tuple(tokens[start:start + len(phrase)]) == phrase for phrase in _BLEEDING_PHRASES):
            continue
        if not any(token in BLEEDING_NEGATORS or token.endswith("n't") for token in tokens[:start]):
            return True
    return False


def hemostasis_in_doubt(event: Mapping) -> bool:
    """DECISIONS D115: whether ``event`` is a clip or an injection whose hemostasis purpose is verified (usable), stated
    done (its status a usable 'performed'), for which none of its own words (HEMOSTASIS_WORDS) states bleeding or names
    the hemostasis as the act (bleeding_stated): its catalogue kind is then POSSIBLE_BLEEDING_CONTROL, a bleeding control
    in doubt, never one done. A statement that is not a usable 'performed' - a denial, a plan, a doubt, an attempt, a
    status whose words do not bind - keeps the bleeding control: its own rule holds or excludes it as before (a denial of
    "hemostatic clipping" still denies a control of bleeding). Reads only the event's own attribute words (EB1), so a
    bleeding stated only for its lesion, elsewhere ("A 12 mm ulcer with an oozing visible vessel ..."), is not read here
    (the event alone carries no lesion record): that act stays in doubt too - fail-closed, as the installed release
    reads it - recorded with D115.

    DECISIONS D142 (round 5c; the round-5b review of D115, problem 0, critical): an event whose OWN kind is the bleeding
    control (Gemini's bleeding_control) is read the same way, by the same five words - named by the adjective (D149
    below). Gemini files "Hemostatic cautery was applied to the ulcer base." beside a clean-based ulcer as kind
    bleeding_control worded 'Hemostatic cautery' (technique electrocautery 'cautery', purpose hemostasis 'Hemostatic' -
    the filing FRESH-2 attests, in its denials, for 'hemostatic cautery' and 'injection for bleeding'); read as a
    bleeding control done, 43255 was READY on it (45382 in a colonoscopy), where the installed release holds it ("leaves
    the bleeding control in doubt"). Named only by the adjective, it is a bleeding control in doubt too; the 14 performed
    bleeding_control events of FRESH-2 each state the oozing they treat ("Minor oozing from the cut mucosal edge resolved
    ...") and keep it.

    DECISIONS D149 (round 5d; the round-5c review of D142, review_egd3.json problem 1): D142's arm for an event of the
    bleeding_control kind whose purpose is NOT a verified hemostasis reads it only when its own words NAME THE CONTROL BY
    THE ADJECTIVE - 'hemostatic' or 'hemostasis' (or 'haemostatic', 'haemostasis') a whole word of its kind, technique or
    purpose words - as the installed release keys its rule (c2e53f8e services.py:7075-7081: a bleeding control named by
    HEMOSTATIC_ADJECTIVE alone, no bleeding stated). D142 read every such event whatever its purpose, so "Epinephrine was
    injected into the ulcer base, followed by bipolar cautery." beside an oozing visible vessel (Gemini's bleeding_control
    worded 'bipolar cautery', purpose not_stated) held 43255 where c2e53f8e and 46e461e7f are READY; named by its device,
    not the adjective, it keeps the bleeding control. One whose hemostasis purpose IS verified is read as D115 reads a
    clip or an injection (RF1's 'Hemostatic', the hemostatic injection filed as bleeding_control). Its words are read
    whatever their state: an adjective in words that do not bind still puts the act in doubt (a hold, never READY).

    DECISIONS D157 (round 5f; the round-5d review of D149, egd4 problem 0, critical; D154's stopped withdrawal paired
    with its companions): D149's adjective key is WITHDRAWN for an event of a family whose catalogue acts list the
    bleeding control (catalogue.entry(family).acts: the upper endoscopy, the enteroscopy, the colonoscopy and the
    flexible sigmoidoscopy) - there D142's arm stands as e5628be56 has it, whatever its purpose and whatever names
    it. Keyed on the adjective, a device the installed release does not read as a bleeding control went READY:
    "Cautery was applied at this site." after "A 4 mm angioectasia was seen in the cecum." (FRESH's attested
    'cautery' filing, performed) gave 45382 READY, and "Cautery was applied to the ulcer base." beside a clean-based
    ulcer 43255 READY, where e5628be56 and c2e53f8e hold both. In a family whose catalogue lists no bleeding control
    (the ERCP, the EUS ...) the key stays, so a device-named control there keeps the bleeding control and stays
    listed not covered, as on 4f82e5056 ("Cautery was applied to the sphincterotomy site." beside 43262). The cost
    that returns is round 5c's egd3 problem 1: "Epinephrine was injected into the ulcer base, followed by bipolar
    cautery." and "Bipolar cautery was applied to the ulcer base." beside an oozing visible vessel hold 43255 again
    where c2e53f8e is READY. A denial of the kind cited alone no longer excludes the code beside such a doubt
    (events._exclusion, D157 (2))."""
    kind = event['kind']['value']
    purpose = event.get('purpose') or {}
    hemostasis = verify.usable(purpose) and purpose.get('value') == 'hemostasis'
    if kind == BLEEDING_CONTROL:  # D142; D149's adjective key only where the family lists no bleeding control (D157)
        entry = catalogue.entry(event.get('family', ''))
        listed = entry is not None and BLEEDING_CONTROL in entry.acts
        named = {token for name in ('kind', 'technique', 'purpose')
                 for token in _WORD.findall(lexicon.fold(_words_text(event.get(name) or {})))}
        if not listed and not hemostasis and not named & {'hemostatic', 'hemostasis', 'haemostatic', 'haemostasis'}:
            return False
    elif kind not in HEMOSTASIS_KINDS or not hemostasis:
        return False
    status = event.get('status')
    if not (verify.usable(status) and status.get('value') == 'performed'):
        return False
    return not any(bleeding_stated(_words_text(event.get(name) or {})) for name in HEMOSTASIS_WORDS)


def catalogue_kind(event: Mapping) -> str:
    """The catalogue kind of an event (module docstring): its kind's value read in its family, with a clip's or an
    injection's VERIFIED hemostasis purpose - a bleeding control, or (DECISIONS D115) a bleeding control in doubt where
    its own words state no bleeding (hemostasis_in_doubt), as (D142) an event of the bleeding_control kind itself whose
    own words state none - with no verified hemostasis purpose, only one its kind, technique or purpose words name by
    the adjective (D149); with a verified one, whatever names it (D154: a device-named event is in doubt too). The kind's
    own state is not read here: a consumer reads it (7.3 line 1)."""
    kind = event['kind']['value']
    if kind == EXAMINATION:
        return EUS_EXAMINATION if event.get('family') == 'gi.eus' else EXAMINATION
    if kind == 'other' or kind not in schema.KINDS:
        return ''
    purpose = event.get('purpose') or {}
    if kind == BLEEDING_CONTROL or (kind in HEMOSTASIS_KINDS and verify.usable(purpose)
                                    and purpose.get('value') == 'hemostasis'):  # D115, D142
        return POSSIBLE_BLEEDING_CONTROL if hemostasis_in_doubt(event) else BLEEDING_CONTROL
    return kind


def code_technique(event: Mapping) -> str:
    """The technique class of an event's VERIFIED device (TECHNIQUE_CLASS), '' when its device is no class a code
    depends on, or is not verified."""
    technique = event['technique']
    if not verify.usable(technique):
        return ''
    return TECHNIQUE_CLASS.get(technique['value'], '')


def role(kind: str) -> str:
    """A catalogue kind's role for coverage: the session (an examination), an umbrella, an act the catalogue never
    reports separately (NOT_REPORTED) or reconciles with no code (UNSUPPORTED_ACTS), an act, or listed only ('')."""
    if kind in EXAMINATION_KINDS:
        return SESSION
    if kind in UMBRELLAS:
        return UMBRELLA
    if not kind:
        return LISTED
    if kind in catalogue.NOT_REPORTED:
        return NOT_REPORTED
    if kind in catalogue.UNSUPPORTED_ACTS:
        return UNSUPPORTED
    return ACT


def covers(statement_kind: str, act_kind: str) -> bool:
    """Whether a statement of catalogue kind ``statement_kind`` concerns an act of catalogue kind ``act_kind``
    (contract 6.4-6.5): the same kind, a tattoo and an injection as one act, or an umbrella covering its members."""
    if not statement_kind or not act_kind:
        return False
    if statement_kind == act_kind:
        return True
    if statement_kind in ONE_ACT and act_kind in ONE_ACT:
        return True
    return act_kind in UMBRELLAS.get(statement_kind, ())


def target_landmark(event: Mapping) -> str:
    """The event's target landmark when it is verified and placed by this vocabulary, else ''."""
    target = event['target']
    if not verify.usable(target) or target['value'] in lexicon.UNPLACED_LANDMARKS:
        return ''
    return target['value']


# --- the place an anastomosis takes (DECISIONS D34) ---------------------------------------------------------------------

ANASTOMOSIS = 'anastomosis'
# The families whose examination reaches each place an anastomosis can take (lexicon.ANASTOMOSIS_TYPES): an upper
# endoscopy (EGD, EUS, ERCP, enteroscopy) the esophagus and the stomach side, a colonoscopy or a sigmoidoscopy the right
# colon side and the rectum. An act of any other family (or of none) is not at the encounter's one listed anastomosis -
# the document then names another, whose ambiguity it keeps - so it takes no place.
_UPPER = frozenset({'gi.egd', 'gi.eus', 'gi.ercp', 'gi.enteroscopy'})
_LOWER = frozenset({'gi.colonoscopy', 'gi.flex_sig'})
ANASTOMOSIS_FAMILIES = MappingProxyType({'esophagus': _UPPER, 'stomach': _UPPER, 'right_colon': _LOWER,
                                         'rectum': _LOWER})


def _words_text(record: Mapping) -> str:
    words = record.get('words') if isinstance(record, Mapping) else None
    return (words.get('text') or '') if isinstance(words, Mapping) else ''


def anastomosis_place(encounter: Mapping) -> str:
    """D34: the place the encounter's anastomosis takes, read only from its anatomy entry's OWN words (EB1): exactly one
    anatomy entry names an anastomosis - whatever that entry's state, so an unverified second entry still counts as a
    second anastomosis - and that entry is a usable (verified, not opened) altered structure whose words name ONE type
    (lexicon.anastomosis_places: a type word directly before the noun), name no type word of another place anywhere,
    and name no plural "anastomoses". Otherwise '' - several anastomoses, no type word, an unknown type, two types -
    and the anastomosis keeps its ambiguity (lexicon.ALTERED_LANDMARKS)."""
    entries = [entry for entry in (encounter.get('anatomy') or ()) if isinstance(entry, Mapping)
               and entry.get('value') == ANASTOMOSIS]
    if len(entries) != 1 or entries[0].get('anatomy') != 'altered' or not verify.usable(entries[0]):
        return ''
    text = _words_text(entries[0])
    places = lexicon.anastomosis_places(text)
    if len(places) != 1 or set(lexicon.anastomosis_type_places(text)) != set(places) or lexicon.holds(
            text, lexicon.ANASTOMOSES):
        return ''
    return places[0]


def compared_landmark(event: Mapping, anastomosis: str) -> str:
    """The event's target landmark as the place comparisons (relations.Context.places) and D29 (events.site_places)
    read it: target_landmark, except that a verified 'anastomosis' takes ``anastomosis``, the place of the encounter's
    one anastomosis (D34, anastomosis_place) - unless the event's family does not reach that place
    (ANASTOMOSIS_FAMILIES), or the target's OWN words name a type of another place or several anastomoses (the document
    then names a second one, whose ambiguity it keeps). For comparisons and D29 only: the target's value, its region and
    every label keep the anastomosis."""
    own = target_landmark(event)
    if own != ANASTOMOSIS or not anastomosis or event.get('family') not in ANASTOMOSIS_FAMILIES.get(anastomosis, ()):
        return own
    text = _words_text(event['target'])
    if any(place != anastomosis for place in lexicon.anastomosis_type_places(text)) or lexicon.holds(
            text, lexicon.ANASTOMOSES):
        return own
    return anastomosis


def key(event: Mapping) -> dict:
    """The event's code key (module docstring)."""
    kind = catalogue_kind(event)
    family_slug = event.get('family', '')
    return {
        'family': family_slug,
        'catalogue_kind': kind,
        'service': service_kind(family_slug) if kind in EXAMINATION_KINDS else '',
        'technique': code_technique(event),
        'region': region(target_landmark(event)),
        'role': role(kind),
        'members': list(UMBRELLAS.get(kind, ())),
    }


def map_events(draft) -> None:
    """normalize's last linked step (normalize.LINKED_STEPS): every event's catalogue_kind, code_technique and key
    (contract 4.1 step 9, 9.1). normalize has set ``family``. Changes the draft's events in place; reads no text."""
    for event in draft.events.values():
        event['catalogue_kind'] = catalogue_kind(event)
        event['code_technique'] = code_technique(event)
        event['key'] = key(event)


# --- what depends on what (contract 9.2) -------------------------------------------------------------------------------

def technique_dependent(family_slug: str, kind: str) -> bool:
    """Whether a code of ``family_slug`` that accounts for ``kind`` depends on the technique (a profile with
    CodeProfile.technique set: the dilation codes). With no family, any family's profile counts (fail toward asking)."""
    return any(profile.technique and kind in profile.covers and (not family_slug or profile.family == family_slug)
               for profile in catalogue.CODES.values())


def read_under(family_slug: str, kind: str, landmark: str) -> str:
    """The family an act of ``kind`` documented in ``family_slug`` at ``landmark`` is read under (catalogue.READ_UNDER:
    an EUS forceps biopsy at an upper GI landmark is read under the EGD), or '' when no rule applies or the landmark lies
    in none of the rule's regions."""
    rule = catalogue.READ_UNDER.get((family_slug, kind))
    if rule is None or not in_regions(landmark, rule[3]):
        return ''
    return rule[0]


def included(code: str, event: Mapping) -> bool:
    """Whether ``code`` includes the examination ``event`` (an EGD examination inside an EGD-with-EUS code;
    catalogue.includes_examination, contract 9.1)."""
    if catalogue_kind(event) not in EXAMINATION_KINDS:
        return False
    kind = service_kind(event.get('family', ''))
    return bool(kind) and catalogue.includes_examination(code, kind)


# --- the defining kinds of a code (DECISIONS D27; FINAL 7.3) -------------------------------------------------------------

def _defining(code: str, profile: catalogue.CodeProfile) -> tuple:
    """D(C): the kinds of C's covers that no other code of C's family covers ALONE (as its one covered kind), in covers
    order; () unless that set is non-empty and smaller than C's covers (a code all of whose kinds are its own, or whose
    every kind another code accounts for alone, is not narrowed)."""
    alone = {other.covers[0] for other_code, other in catalogue.CODES.items()
             if other_code != code and other.family == profile.family and len(other.covers) == 1}
    kinds = tuple(kind for kind in profile.covers if kind not in alone)
    return kinds if kinds and set(kinds) < set(profile.covers) else ()


# code -> D(C), for every catalogue code D27 narrows (computed at import; tests/test_interpretation_mapping.py pins it:
# 43265 lithotripsy, the EUS sampling, drainage and injection codes their act, 44365 hot_biopsy, 49440 peg).
DEFINING = MappingProxyType({code: kinds for code, kinds in ((code, _defining(code, profile))
                                                              for code, profile in catalogue.CODES.items()) if kinds})


# --- the target of a defining act (DECISIONS D120; the round-4 parity audit, EUS gap 0) ---------------------------------

# 43240 is the transmural drainage of a PSEUDOCYST (its covers: the EUS examination and a drainage; D27 narrows it to the
# drainage). The catalogue states that an EUS-guided drainage of anything else - biliary, the gallbladder, a
# gastroenterostomy - has no profiled code (the gi.eus entry's unsupported_acts, UNSUPPORTED_SERVICES), and the installed
# release never READYs 43240. DEFINING_TARGETS: code -> what its defining act's VERIFIED target words, or the words of the
# lesion its target is verified to be, must name - here a pancreatic fluid collection (a pseudocyst, walled-off necrosis,
# a pancreatic or peripancreatic fluid collection). It is an inclusion list for SUPPORT, so it fails closed: a drainage
# whose words name none of these never supports the code (held, never READY), whatever they name instead.
# DEFINING_TARGET_APART: the regions where a verified place of the act (its target landmark, its lesion's verified site)
# sets it apart whatever its words name - a drainage at the gallbladder, a bile duct or the liver is another drainage.
PANCREATIC_FLUID_COLLECTION = ('pseudocyst', 'pseudocysts', 'walled off necrosis', 'walled off pancreatic necrosis',
                               'won', 'pancreatic fluid collection', 'pancreatic fluid collections',
                               'peripancreatic fluid collection', 'peripancreatic fluid collections',
                               'pancreatic collection', 'peripancreatic collection', 'pfc', 'necrotic collection',
                               'necrotic collections', 'pancreatic necrosis')
DEFINING_TARGETS = MappingProxyType({'43240': PANCREATIC_FLUID_COLLECTION})
DEFINING_TARGET_APART = frozenset({'biliary', 'liver'})


def defining_target(code: str, event: Mapping, lesion: Mapping | None = None) -> bool:
    """DECISIONS D120: whether ``event`` - an act of ``code``'s defining kind - meets the code's defining-target
    requirement (DEFINING_TARGETS): True for a code with none. For 43240: the event's own target is usable and its words
    name a pancreatic fluid collection, or ``lesion`` - the record of the lesion its target is verified to be (the
    caller's identity.verified_lesion; this table module reads no identity rule) - has words that name one; and no verified
    place of it (its target landmark, that lesion's verified site) lies in DEFINING_TARGET_APART. Reads the attribute's
    own words (EB1) and verified values only, never a passage."""
    names = DEFINING_TARGETS.get(code)
    if names is None:
        return True
    target = event.get('target') or {}
    lesion = lesion or {}
    site = lesion.get('site') or {}
    places = [target_landmark(event)] + ([site.get('value', '')] if verify.usable(site) else [])
    if any(region(place) in DEFINING_TARGET_APART for place in places if place):
        return False
    texts = [_words_text(target) if verify.usable(target) else '', _words_text(lesion)]
    return any(text and lexicon.holds(text, names) for text in texts)


# --- a transmural code's act read apart: an injection of the wall (DECISIONS D171 (4); refute6 judges finding 12) ---------

# 43253 is the EGD's EUS-guided TRANSMURAL injection - of a diagnostic or therapeutic substance, or of fiducial markers
# (its CPT descriptor; D27 narrows it to its injection, and mapping.ONE_ACT makes a tattoo that injection). An injection
# or a tattoo made through the echoendoscope INTO THE WALL is a submucosal injection - the EGD's 43236, 'directed
# submucosal injection(s), any substance' - and never 43253's act: its own route or depth words name the submucosa
# ('The gastric wall 2 cm proximal to the lesion was tattooed with a submucosal injection of 2 mL of India ink ...',
# 'A submucosal tattoo was placed ...', 'A submucosal injection of 5 mL of saline was made beside the lesion ...'), or
# its purpose is a lift for resection, or it is a tattoo whose own words name an ink ('India ink', 'Spot ink': an
# endoscopic tattoo marks the wall). Read only for HOLDING the code (assess._examination_class, D171 (4)): the words are
# no inclusion list for support, nothing they match ever releases a code, and a fiducial placement read as 'tattoo'
# (D145), a celiac plexus block or any injection whose own words say neither keeps D27's reading. EB1: the act's own
# attribute words, in any state, never a passage.
TRANSMURAL_INJECTION_CODES = frozenset({'43253'})
SUBMUCOSAL_WORDS = ('submucosal', 'submucosa', 'sub mucosal', 'sub mucosa')
INK_WORDS = ('ink', 'inks')
INJECTION_OWN_WORDS = ('kind', 'technique', 'target', 'purpose')
# DECISIONS D177 (2) (round 5h, narrowing only; review:eus7 problem 2, critical, pre-existing): a TATTOO's route is read
# from the act's kind and its own place, never from a word of its material. A tattoo marks the site it is injected into,
# so a tattoo placed in the WALL of the tract - a place of the luminal tract (WALL_REGIONS: REGION_OF's regions from the
# esophagus to the anal canal) or a surgically made place of it (lexicon.ALTERED_LANDMARKS: an anastomosis, a stoma, a
# pouch) - is a submucosal injection, whatever it is made of. 'A carbon-particle tattoo was placed in the gastric wall 2
# cm proximal to the lesion for surgical localization.' (kind 'carbon-particle tattoo', technique not stated, target the
# stomach) met none of D171 (4)'s arms - its tattoo arm reads an ink word - and 43253 was READY. A tattoo-read
# placement VERIFIED at a structure BESIDE the tract (the pancreas, the biliary tree, the liver, a lymph node: D145's
# fiducials into the pancreatic head, verify-eus-1's U) keeps D27's reading. Read only for HOLDING 43253, as D171 (4)'s
# arms are.
WALL_REGIONS = frozenset({'esophagus', 'stomach', 'duodenum', 'small_bowel', 'colon', 'rectum', 'anus'})


def wall_place(event: Mapping, lesion: Mapping | None = None) -> str:
    """DECISIONS D177 (2): the landmark of ``event``'s own place when it lies in the wall of the tract (WALL_REGIONS, or
    a surgically made place: lexicon.ALTERED_LANDMARKS), else ''. A VERIFIED, placed target landmark (verify.usable, not
    lexicon.UNPLACED_LANDMARKS) is the act's place, alone. Otherwise every place the act may be at is read, in ANY state
    (fail-closed: read only to hold), and the first in the wall is its place: its target's landmark value - the value
    Gemini gave, unverified; the site value of ``lesion``, the record of the lesion its target names (the caller reads
    it: this table module reads no identity rule); and the landmarks its own target words name (lexicon.landmarks_named,
    the vocabulary every place reader shares - EB1: the act's own words, never a passage). Structure only: no word of a
    material or a route is read."""
    target = event.get('target') if isinstance(event.get('target'), Mapping) else {}

    def wall(place: str) -> bool:
        return bool(place) and place not in lexicon.UNPLACED_LANDMARKS and (region(place) in WALL_REGIONS
                                                                            or place in lexicon.ALTERED_LANDMARKS)

    own = target.get('value') or ''
    if own and own not in lexicon.UNPLACED_LANDMARKS and verify.usable(target):
        return own if wall(own) else ''
    site = (lesion or {}).get('site')
    site = (site.get('value') or '') if isinstance(site, Mapping) else ''
    places = [own, site, *lexicon.landmarks_named(_words_text(target))]
    return next((place for place in places if wall(place)), '')


def submucosal_act(event: Mapping, lesion: Mapping | None = None, place: bool = True) -> bool:
    """DECISIONS D171 (4): whether ``event`` - an injection or a tattoo - is an injection of the WALL, which a transmural
    code (TRANSMURAL_INJECTION_CODES) never stands on: the own words of its kind, technique, target or purpose name the
    submucosa (SUBMUCOSAL_WORDS); or its purpose is a lift for resection (a lift injection is submucosal by definition:
    FINAL 7.7's lift_injection); or it is a tattoo (its catalogue kind, or the kind Gemini gave) whose own words name an
    ink (INK_WORDS). Any state of the words and the purpose is read (fail-closed: it only ever holds).

    DECISIONS D177 (2): or it is a tattoo - by the same kind reading - whose route is submucosal: its own place lies in
    the wall of the tract (wall_place, over ``lesion``, the record of the lesion its target names). By the act's kind
    and place, never by a word of its material ('A carbon-particle tattoo was placed in the gastric wall ...').
    ``place`` False reads D171 (4)'s arms alone (the caller's wording says which arm holds)."""
    texts = [_words_text(event.get(name) or {}) for name in INJECTION_OWN_WORDS]
    if any(text and lexicon.holds(text, SUBMUCOSAL_WORDS) for text in texts):
        return True
    purpose = event.get('purpose') if isinstance(event.get('purpose'), Mapping) else {}
    if purpose.get('value') == 'lift_for_resection':
        return True
    kind = event.get('kind') if isinstance(event.get('kind'), Mapping) else {}
    tattoo = event.get('catalogue_kind') == 'tattoo' or kind.get('value') == 'tattoo'
    if tattoo and any(text and lexicon.holds(text, INK_WORDS) for text in texts):
        return True
    return place and tattoo and bool(wall_place(event, lesion))  # D177 (2): the tattoo's kind and its own place


# --- the EUS examination class (DECISIONS D28; FINAL 7.2 R6) -------------------------------------------------------------

FULL, LIMITED = 'full', 'limited'
EXAMINATION_CLASSES = (FULL, LIMITED)  # catalogue.CodeProfile.exam
# The verified reach of the session's EUS examination each class needs (D28): a FULL examination at or beyond the
# duodenum - exactly D28's list: the duodenum, its bulb, its second portion, the ampulla, the jejunum; a LIMITED one
# short of the duodenum - the landmarks of the tract before it, the esophagus's and the stomach's (D29's esophageal class
# and the stomach's half of its gastric class). A reach at any other place (the small bowel named as such, an
# anastomosis, an organ beside the tract) fits neither class, so either code holds on it, as on an unverified reach.
FULL_REACH = frozenset({'duodenum', 'duodenal_bulb', 'second_portion_duodenum', 'ampulla', 'jejunum'})
SHORT_OF_DUODENUM = frozenset({'esophagus', 'proximal_esophagus', 'mid_esophagus', 'distal_esophagus',
                               'gastroesophageal_junction', 'stomach', 'gastric_cardia', 'gastric_fundus',
                               'gastric_body', 'gastric_antrum', 'pylorus'})
# DECISIONS D43 (the S17 refutation, finding 8): the lower-tract EUS codes, to which the catalogue gives no class, take
# the class of the lower endoscopy they are done through, read from the same verified reach: a flexible sigmoidoscopy
# examines the rectum and the sigmoid colon and may include a portion of the descending colon; a colonoscopy goes
# beyond the splenic flexure, to the cecum (the CPT definitions); a colonoscopy through a stoma also needs the encounter's
# verified stoma. A reach of the upper tract, the splenic flexure itself, an anastomosis or an organ beside the tract fits
# none of them - so 45392 on an echoendoscope in the duodenum, or at the rectosigmoid, is held, never READY.
SIGMOIDOSCOPIC, COLONOSCOPIC, STOMA = 'sigmoidoscopic', 'colonoscopic', 'stoma'
LOWER_EUS_CLASS = MappingProxyType({'45341': SIGMOIDOSCOPIC, '45342': SIGMOIDOSCOPIC, '45391': COLONOSCOPIC,
                                    '45392': COLONOSCOPIC, '44406': STOMA, '44407': STOMA})
SIGMOIDOSCOPIC_REACH = frozenset({'rectum', 'rectosigmoid', 'sigmoid_colon', 'descending_colon', 'left_colon',
                                  'distal_colon'})
COLONOSCOPIC_REACH = frozenset({'transverse_colon', 'hepatic_flexure', 'ascending_colon', 'right_colon', 'proximal_colon',
                                'cecum', 'appendiceal_orifice', 'ileocecal_valve', 'terminal_ileum', 'ileum',
                                'neo_terminal_ileum'})
STOMA_REACH = SIGMOIDOSCOPIC_REACH | COLONOSCOPIC_REACH | frozenset({'colon', 'stoma'})
CLASS_REACH = MappingProxyType({FULL: FULL_REACH, LIMITED: SHORT_OF_DUODENUM, SIGMOIDOSCOPIC: SIGMOIDOSCOPIC_REACH,
                                COLONOSCOPIC: COLONOSCOPIC_REACH, STOMA: STOMA_REACH})


def examination_class(code: str) -> str:
    """The EUS examination class of ``code``: the catalogue's ('full' | 'limited'), or D43's lower-tract class
    ('sigmoidoscopic' | 'colonoscopic' | 'stoma'); '' for a code with none."""
    profile = catalogue.code_profile(code)
    if profile is not None and profile.exam in EXAMINATION_CLASSES:
        return profile.exam
    return LOWER_EUS_CLASS.get(code, '')


# DECISIONS D171 (2) (refute6 families finding 5): the tract of an EUS code. The EUS codes of an UPPER endoscopy - an
# esophagoscopy's (43231, 43232) and an EGD's (43237, 43238, 43240, 43242, 43253, 43259), whose CPT descriptors are
# transoral - need an upper-tract EUS session: on a lower-tract EUS (an echoendoscope advanced to the sigmoid colon, a
# fiducial placed into a rectal mass) none describes what was done, and the catalogue gives 43240 and 43253 no class,
# so no reach was read for them (43253 READY on a rectal EUS's fiducials). The lower-tract codes are D43's
# (LOWER_EUS_CLASS). The set is pinned equal to the catalogue's gi.eus codes less LOWER_EUS_CLASS
# (tests/test_interpretation_r5g_eus_class.py).
UPPER_TRACT, LOWER_TRACT = 'upper', 'lower'
UPPER_EUS_CODES = frozenset({'43231', '43232', '43237', '43238', '43240', '43242', '43253', '43259'})
# DECISIONS D171 (3): the EGD's limited EUS codes, whose class CPT states as an examination 'limited to the esophagus,
# stomach or duodenum, and adjacent structures' (an examination limited to the duodenum included) - D28's 'short of the
# duodenum' misstates it - and the full-examination codes, which need the esophagus, the stomach and the duodenum.
EGD_LIMITED_EUS_CODES = frozenset({'43237', '43238'})
# the regions (REGION_OF) of the upper tract's EUS stations, in the order an upper EUS passes them; and every region an
# upper endoscopy's EUS examines or samples from them (the stations, and the pancreas, the biliary tree and the liver
# beside them) - a place there makes no EUS a lower-tract one (assess._lower_place)
UPPER_STATIONS = ('esophagus', 'stomach', 'duodenum')
UPPER_TRACT_REGIONS = frozenset(UPPER_STATIONS) | frozenset({'pancreas', 'biliary', 'liver'})


def eus_tract(code: str) -> str:
    """DECISIONS D171 (2): UPPER_TRACT for an upper endoscopy's EUS code (UPPER_EUS_CODES), LOWER_TRACT for D43's
    lower-tract EUS codes, '' for any other code."""
    if code in UPPER_EUS_CODES:
        return UPPER_TRACT
    return LOWER_TRACT if code in LOWER_EUS_CLASS else ''


def has_stoma(encounter: Mapping) -> bool:
    """D43: whether the encounter's anatomy holds a usable (verified, not opened) altered-anatomy stoma entry."""
    return any(isinstance(entry, Mapping) and entry.get('value') == 'stoma' and entry.get('anatomy') == 'altered'
               and verify.usable(entry) for entry in (encounter.get('anatomy') or ()))


# --- the site of a dilation (DECISIONS D29; FINAL 7.2 R4) ----------------------------------------------------------------

ESOPHAGEAL, GASTRIC_DUODENAL = 'esophageal', 'gastric_duodenal'
# Each site class's landmarks, exactly as D29 lists them (no containment is read: the GE junction is esophageal, the
# ampulla, the jejunum and every surgically made place are in neither class).
SITE_CLASSES = MappingProxyType({
    ESOPHAGEAL: frozenset({'esophagus', 'proximal_esophagus', 'mid_esophagus', 'distal_esophagus',
                           'gastroesophageal_junction'}),
    GASTRIC_DUODENAL: frozenset({'stomach', 'gastric_cardia', 'gastric_fundus', 'gastric_body', 'gastric_antrum',
                                 'pylorus', 'duodenum', 'duodenal_bulb', 'second_portion_duodenum'}),
})
# The site-specific dilation codes of the catalogue and their site class, by the structure their CPT descriptors name
# (cited for the engineer, never shown to a customer; no descriptor is connected): 43213 esophagoscopy "with dilation of
# esophagus, by balloon or dilator, retrograde"; 43214 esophagoscopy "with dilation of esophagus with balloon (30 mm
# diameter or larger)"; 43220 esophagoscopy "with transendoscopic balloon dilation (less than 30 mm diameter)" and 43226
# esophagoscopy "with insertion of guide wire followed by passage of dilator(s) over guide wire" (an esophagoscopy's
# dilation is of the esophagus); 43233 EGD "with dilation of esophagus with balloon (30 mm diameter or larger)"; 43248
# EGD "with insertion of guide wire followed by passage of dilator(s) through esophagus over guide wire"; 43249 EGD "with
# transendoscopic balloon dilation of esophagus (less than 30 mm diameter)"; 43245 EGD "with dilation of gastric/duodenal
# stricture(s) (eg, balloon, bougie)". Every other dilation code (the colon's, the enteroscopy's, the ERCP's) is not here.
DILATION_SITES = MappingProxyType({
    '43213': ESOPHAGEAL, '43214': ESOPHAGEAL, '43220': ESOPHAGEAL, '43226': ESOPHAGEAL, '43233': ESOPHAGEAL,
    '43248': ESOPHAGEAL, '43249': ESOPHAGEAL, '43245': GASTRIC_DUODENAL,
})


# --- how a proposed code links to events (FINAL C7 as ADJUDICATION C-6 amends it) --------------------------------------

CATALOGUE_ROUTE, UNRECONCILED_ROUTE, NO_ROUTE = 'catalogue', 'unreconciled', 'none'
ROUTES = (CATALOGUE_ROUTE, UNRECONCILED_ROUTE, NO_ROUTE)  # (a), (b), (d): there is no route (c)
UNPROFILED, FAMILY_MISMATCH = 'unprofiled', 'family_mismatch'
NO_ROUTE_REASONS = (UNPROFILED, FAMILY_MISMATCH)


@dataclass(frozen=True)
class CodeLink:
    """How a proposed code links to events (FINAL C7, C-1, C-6). ``kinds`` is K(C), the catalogue kinds of its
    candidates; ``session`` the examination kind of the session it belongs to ('' for none); ``acts`` the kinds besides
    the examination kinds, each needing a supporting event of its own (C-1); ``regions`` route (b)'s regions. On route
    ``none`` every tuple is empty and ``reason`` says why. ``supported`` is the routed family's gi.profiles flag and
    ``support`` its catalogue entry's support level ('' with no entry): the engine reads them. ``defining`` is D(C) (D27;
    DEFINING), the only kinds that match the code where it narrows it, () otherwise."""
    code: str
    route: str
    family: str
    kinds: tuple = ()
    session: str = ''
    acts: tuple = ()
    base: bool = False
    addon: bool = False
    technique: str = ''
    includes: tuple = ()
    regions: tuple = ()
    supported: bool = False
    support: str = ''
    reason: str = ''
    defining: tuple = ()

    @property
    def linked(self) -> bool:
        return self.route != NO_ROUTE


def code_link(code: str) -> CodeLink:
    """The link route of ``code`` (module docstring): (a) the catalogue, (b) an unreconciled act, or (d) none."""
    routed = profiles.family_for_code(code)
    profile_ = profiles.PROFILES.get(routed)
    entry = catalogue.entry(routed)
    common = {'code': code, 'family': routed, 'supported': bool(profile_ and profile_.supported),
              'support': entry.support if entry is not None else ''}
    profile = catalogue.code_profile(code)
    if profile is not None:
        if profile.family != routed:
            return CodeLink(route=NO_ROUTE, reason=FAMILY_MISMATCH, **common)
        session = (EUS_EXAMINATION if routed == 'gi.eus' else EXAMINATION) if routed in ENDOSCOPIC_FAMILIES else ''
        kinds = tuple(profile.covers) or ((session,) if profile.base and session else ())
        return CodeLink(route=CATALOGUE_ROUTE, kinds=kinds, session=session,
                        acts=tuple(kind for kind in kinds if kind not in EXAMINATION_KINDS), base=profile.base,
                        addon=profile.addon, technique=profile.technique, includes=tuple(profile.includes),
                        defining=DEFINING.get(code, ()), **common)
    acts = catalogue.UNRECONCILED_ACTS.get(code)
    if acts:
        return CodeLink(route=UNRECONCILED_ROUTE, kinds=tuple(acts), acts=tuple(acts),
                        regions=tuple(catalogue.UNRECONCILED_REGIONS.get(code, ())), **common)
    return CodeLink(route=NO_ROUTE, reason=UNPROFILED, **common)


# --- codes of a recognised-only family (DECISIONS D80; the round-3 refutation, finding 19) -------------------------------

RECOGNISED_ONLY = 'recognised_only'  # the reason (events.Evaluation.reason) of the hold D80 puts on such a code


def recognised_only(link: CodeLink) -> bool:
    """DECISIONS D80: whether ``link`` is a code on route (a) of a family CPT Studio RECOGNISES and lists for review but
    does not ASSESS - the catalogue does not reconcile the family's acts with codes (its FamilyEntry.support is not
    SUPPORTED: 'recognised', as gi.sedation's "moderate sedation is recognised and listed, not reconciled" and gi.other's,
    'unsupported', or no catalogue entry), or gi.profiles marks the family not supported (gi.sedation: "Sedation checks
    are not implemented in this release; review required."). Either one marks it (fail-closed). Today these are exactly
    gi.sedation's 99152 and 99153, the only catalogue codes of such a family (pinned). CodeLink.supported and
    CodeLink.support are read here. Route (b) (46221, C7 (b)'s own route) and route (d) (held already, C-6) are not."""
    return link.route == CATALOGUE_ROUTE and not (link.supported and link.support == catalogue.SUPPORTED)


def documentation(family: str) -> tuple:
    """What the catalogue states ``family`` requires documented (FamilyEntry.documentation), () with no entry: the
    D80 hold names what CPT Studio does not check for a recognised-only family's code."""
    entry = catalogue.entry(family)
    return tuple(entry.documentation) if entry is not None else ()


def candidate(link: CodeLink, event: Mapping) -> bool:
    """Whether ``event`` is a candidate of the linked code (FINAL 7.3): an event of a kind in K(C) - D(C) where D27
    narrows it - or of an umbrella that covers such a kind, whose family is C's (route (a)); or, on route (b), an event
    of a kind in K(C) whose VERIFIED target landmark lies in the code's regions, in any family. Never on route (d).
    Verification of the kind and family is the consumer's (7.3 line 1)."""
    if not link.linked:
        return False
    kind = catalogue_kind(event)
    if link.route == UNRECONCILED_ROUTE:
        return kind in link.kinds and in_regions(target_landmark(event), link.regions)
    if event.get('family') != link.family:
        return False
    return any(covers(kind, wanted) for wanted in link.defining or link.kinds)
