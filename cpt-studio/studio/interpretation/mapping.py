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
  others needs a supporting event of EACH of the others (read by the engine, slice S08).
- (b) ``unreconciled``: a code with no profile that catalogue.UNRECONCILED_ACTS names (46221): K(C) = code_acts(C), each
  candidate's verified target landmark mapped into UNRECONCILED_REGIONS[C] (in_regions).
- (d) ``none``: every other code - no catalogue profile (``unprofiled``: "outside CPT Studio's coding profiles; review
  required", never READY, C-6), or a profile of another family than the code routes to (``family_mismatch``). The engine
  holds it with ``performed_status``: which documented act it accounts for is not established.

Pure and Django-free.
"""
from __future__ import annotations

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


def catalogue_kind(event: Mapping) -> str:
    """The catalogue kind of an event (module docstring): its kind's value read in its family, with a clip's or an
    injection's VERIFIED hemostasis purpose. The kind's own state is not read here: a consumer reads it (7.3 line 1)."""
    kind = event['kind']['value']
    if kind == EXAMINATION:
        return EUS_EXAMINATION if event.get('family') == 'gi.eus' else EXAMINATION
    if kind == 'other' or kind not in schema.KINDS:
        return ''
    purpose = event.get('purpose') or {}
    if kind in HEMOSTASIS_KINDS and verify.usable(purpose) and purpose.get('value') == 'hemostasis':
        return BLEEDING_CONTROL
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
    ``support`` its catalogue entry's support level ('' with no entry): the engine reads them."""
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
                        addon=profile.addon, technique=profile.technique, includes=tuple(profile.includes), **common)
    acts = catalogue.UNRECONCILED_ACTS.get(code)
    if acts:
        return CodeLink(route=UNRECONCILED_ROUTE, kinds=tuple(acts), acts=tuple(acts),
                        regions=tuple(catalogue.UNRECONCILED_REGIONS.get(code, ())), **common)
    return CodeLink(route=NO_ROUTE, reason=UNPROFILED, **common)


def candidate(link: CodeLink, event: Mapping) -> bool:
    """Whether ``event`` is a candidate of the linked code (FINAL 7.3): an event of a kind in K(C), or of an umbrella
    that covers a kind of K(C), whose family is C's (route (a)); or, on route (b), an event of a kind in K(C) whose
    VERIFIED target landmark lies in the code's regions, in any family. Never on route (d). Verification of the kind
    and family is the consumer's (7.3 line 1)."""
    if not link.linked:
        return False
    kind = catalogue_kind(event)
    if link.route == UNRECONCILED_ROUTE:
        return kind in link.kinds and in_regions(target_landmark(event), link.regions)
    if event.get('family') != link.family:
        return False
    return any(covers(kind, wanted) for wanted in link.kinds)
