"""Step 1e's tables (docs/gemini-migration/FINAL-V2.md, 8.1 step 1e: engine/anatomy.py and engine/catalogue.py), TEXT-ONLY
and SYNTHETIC: no document, no provider, no network.

The done-when of 8.1 step 1e, each proved here:
- "for all 163 codes every ported value equals v1's (computed from v1 in the test, by value)": the 163 codes are counted
  from v1's catalogue (studio.gi.catalogue.CODES) here; for each, its profile, link, requirement groups, defining kinds,
  technique, site, EUS and enteroscopy classes, tract and included examination equal v1's; routing and linking equal v1's
  for every five-digit code and for strings that are no code; and every table that is not keyed by a code (anatomy,
  umbrellas, covers, technique classes, class reaches, family maps) equals v1's by value (FINAL-V2 5.0);
- "NoWordLists holds": 5.7 measure 4's rules (step 0b's measure_4, the same implementation test_types.py runs) find
  nothing in either module, each rule refuses a planted control, and no module-level assignment holds a string at all.
Also: engine/ imports no retired module at runtime and nothing of studio.gi (a fresh interpreter); only this test imports
v1. And the arbiter triage's rulings for this step (docs/gemini-migration/DECISIONS.md): the Kind-valued parts of each
catalogue entry's bundled and unsupported_acts equal v1's FamilyEntry for every family (D191); K3's reach equals v1's
FAMILY_REGIONS (D192); the two new duodenal portions stand where v1's duodenum stands (D204); and no file of the step
cites the builders' report, whose readings DECISIONS records (D207).

v1 is computed HERE, from v1's own modules - mapping, classes, lexicon, events and assess (retired: 5.0), and the gi
reference tables catalogue and profiles, and services' FAMILY_REGIONS - which this module alone imports, read only.

"By value": a family is compared by its v1 slug (lexicon.FAMILY_OF of the SessionKind's value); a kind by v1's catalogue
kind of that kind in that family (Kind.EXAMINATION is 'eus_exam' in the EUS family and 'examination' elsewhere: C-1;
other is ''); every other member by its value, and None as v1's ''. The two landmarks LANDMARKS2 adds
(third_portion_duodenum, fourth_portion_duodenum) and EXTENTS' stated_depth have no v1 value: they are compared by the
rule engine/catalogue.py states for them, pinned below.
"""
from __future__ import annotations

import ast
import enum
import itertools
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

# v1, read only for the parity proofs (computed here); engine/ never imports these
from studio.gi import catalogue as v1_catalogue, profiles as v1_profiles, services as v1_services
from studio.interpretation import assess as v1_assess, classes as v1_classes, events as v1_events
from studio.interpretation import lexicon as v1_lexicon, mapping as v1_mapping, schema as v1_schema
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy, catalogue
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
ENGINE = APP / 'studio' / 'interpretation' / 'engine'
MODULES = {'engine/anatomy': ENGINE / 'anatomy.py', 'engine/catalogue': ENGINE / 'catalogue.py'}

Kind, SessionKind, Landmark, Extent = ct.Kind, ct.SessionKind, ct.Landmark, ct.Extent
SLUG = {family: v1_lexicon.FAMILY_OF[family.value] for family in SessionKind}
FAMILY_OF_SLUG = {slug: family for family, slug in SLUG.items()}
NEW_LANDMARKS = frozenset({'third_portion_duodenum', 'fourth_portion_duodenum'})  # LANDMARKS2's two (FINAL-V2 1.4)
V1_LANDMARKS = tuple(value for value in v1_schema.LANDMARKS if value != 'not_stated')

# every five-digit code, and strings that are no catalogue code (each v1 reads somehow): non-ASCII digits (some of which
# v1's string comparison routes into a range), spaces, signs, separators, other lengths, letters
ODD_CODES = ('', '4323', '432355', 'abcde', '４３２３５', '4323５', '4323²',
             '٤٣٢٣٥', ' 4323', '43235 ', '+4323', '4323_', '43_235', '-4323', '043235',
             '45305', '46600', '91200', '99999', '12345', '46221')
FIVE_DIGIT = tuple(f'{n:05d}' for n in range(100000))


def v1_kind(kind, family) -> str:
    """v1's catalogue kind of ``kind`` in ``family`` (module docstring)."""
    if kind is None or kind is Kind.OTHER:
        return ''
    if kind is Kind.EXAMINATION and family is SessionKind.EUS:
        return 'eus_exam'
    return kind.value


def v1_value(member) -> str:
    return '' if member is None else member.value


def v1_values(members) -> set:
    return {member.value for member in members}


def link_of_v1(link) -> dict:
    """A v1 mapping.CodeLink's fields."""
    return {'code': link.code, 'route': link.route, 'family': link.family, 'kinds': tuple(link.kinds),
            'session': link.session, 'acts': tuple(link.acts), 'base': link.base, 'addon': link.addon,
            'technique': link.technique, 'includes': tuple(link.includes), 'regions': tuple(link.regions),
            'supported': link.supported, 'support': link.support, 'reason': link.reason,
            'defining': tuple(link.defining), 'linked': link.linked}


def link_by_value(link: catalogue.CodeLink) -> dict:
    """A v2 catalogue.CodeLink's fields, written as v1 writes them (module docstring)."""
    family = link.family
    return {'code': link.code, 'route': link.route.value, 'family': SLUG[family],
            'kinds': tuple(v1_kind(kind, family) for kind in link.kinds), 'session': v1_kind(link.session, family),
            'acts': tuple(v1_kind(kind, family) for kind in link.acts), 'base': link.base, 'addon': link.addon,
            'technique': v1_value(link.technique), 'includes': tuple(v1_value(item) for item in link.includes),
            'regions': tuple(v1_value(item) for item in link.regions), 'supported': link.supported,
            'support': v1_value(link.support), 'reason': v1_value(link.reason),
            'defining': tuple(v1_kind(kind, family) for kind in link.defining), 'linked': link.linked}


def v1_event(kind: str, *, family: str, purpose: str = 'not_stated', purpose_state: str = 'verified',
             technique: str = 'not_stated', technique_state: str = 'absent') -> dict:
    """A v1 event in its stored shape, as far as mapping reads it, with NO words and NO status: so mapping.catalogue_kind
    takes its enumeration arm (D115, D142, D149 and D157's word arms need a usable 'performed' status to read words)."""
    def record(value, state):
        return {'value': value, 'state': state, 'open': False, 'basis': 'stated' if state == 'verified' else 'absent'}
    return {'id': 'E1', 'family': family, 'kind': record(kind, 'verified'), 'purpose': record(purpose, purpose_state),
            'technique': record(technique, technique_state), 'target': record('not_stated', 'absent')}


# --- the codes --------------------------------------------------------------------------------------------------------


class CodeTests(SimpleTestCase):
    def test_the_catalogue_holds_163_codes_and_the_port_holds_exactly_them_in_its_order(self):
        self.assertEqual(len(v1_catalogue.CODES), 163)  # counted from v1's catalogue, as the row asks
        self.assertEqual([str(code) for code in catalogue.CODES], list(v1_catalogue.CODES))
        self.assertTrue(all(type(code) is int and str(code) == f'{code:05d}' for code in catalogue.CODES))

    def test_every_profile_equals_v1s(self):
        for code, profile in v1_catalogue.CODES.items():
            mine = catalogue.CODES[int(code)]
            with self.subTest(code=code):
                self.assertEqual(
                    (SLUG[mine.family], tuple(v1_kind(kind, mine.family) for kind in mine.covers), mine.base,
                     v1_value(mine.exam), mine.addon, tuple(v1_value(item) for item in mine.includes),
                     v1_value(mine.technique)),
                    (profile.family, profile.covers, profile.base, profile.exam, profile.addon, profile.includes,
                     profile.technique))
                self.assertIs(catalogue.code_profile(code), mine)

    def test_every_code_links_as_v1_links_it(self):
        for code in v1_catalogue.CODES:
            with self.subTest(code=code):
                self.assertEqual(link_by_value(catalogue.code_link(code)), link_of_v1(v1_mapping.code_link(code)))
                self.assertEqual(catalogue.code_link(code).route, catalogue.LinkRoute.CATALOGUE)

    def test_every_five_digit_code_and_every_odd_string_routes_and_links_as_v1(self):
        mismatched = [code for code in FIVE_DIGIT + ODD_CODES
                      if SLUG[catalogue.family_for_code(code)] != v1_profiles.family_for_code(code)
                      or link_by_value(catalogue.code_link(code)) != link_of_v1(v1_mapping.code_link(code))]
        self.assertEqual(mismatched, [])
        routes = {route: sum(1 for code in FIVE_DIGIT if catalogue.code_link(code).route is route)
                  for route in catalogue.LinkRoute}
        self.assertEqual(routes, {catalogue.LinkRoute.CATALOGUE: 163, catalogue.LinkRoute.UNRECONCILED: 1,
                                  catalogue.LinkRoute.NONE: 100000 - 164})
        # v1's string comparison routes some strings of non-ASCII digits into a range; the port keeps it
        self.assertEqual(catalogue.family_for_code('4323５'), SessionKind.EGD)
        for odd in (None, 43235, 4.3235e4, b'43235'):  # not a str: routed nowhere and linked to nothing, as in v1
            with self.subTest(odd=odd):
                self.assertEqual(SLUG[catalogue.family_for_code(odd)], v1_profiles.family_for_code(odd))
                self.assertIsNone(catalogue.code_profile(odd))

    def test_route_b_and_route_d(self):
        link = catalogue.code_link('46221')
        self.assertEqual((link.route, link.kinds, link.regions, link.family),
                         (catalogue.LinkRoute.UNRECONCILED, (Kind.BAND_LIGATION,),
                          (anatomy.Region.RECTUM, anatomy.Region.ANUS), SessionKind.OTHER_GI))
        for code in ('45305', '46600', '91200', '99999', '12345', 'abcde'):
            link = catalogue.code_link(code)
            with self.subTest(code=code):
                self.assertEqual((link.route, link.reason, link.kinds, link.linked),
                                 (catalogue.LinkRoute.NONE, catalogue.NoRouteReason.UNPROFILED, (), False))

    def test_a_profile_of_another_family_has_no_route_as_in_v1(self):
        planted = catalogue.Profile(SessionKind.EGD, (Kind.BIOPSY,))
        mine = catalogue._link('45380', {**catalogue.CODES, 45380: planted})
        with mock.patch.dict(v1_catalogue.CODES, {'45380': v1_catalogue._c('gi.egd', ('biopsy',))}):
            theirs = v1_mapping.code_link('45380')
        self.assertEqual(link_by_value(mine), link_of_v1(theirs))
        self.assertEqual((mine.route, mine.reason), (catalogue.LinkRoute.NONE, catalogue.NoRouteReason.FAMILY_MISMATCH))

    def test_every_codes_requirement_groups_and_link_rules_equal_v1s(self):
        for code in tuple(v1_catalogue.CODES) + ODD_CODES:
            mine, theirs = catalogue.code_link(code), v1_mapping.code_link(code)
            family = mine.family
            with self.subTest(code=code):
                self.assertEqual(tuple(tuple(v1_kind(kind, family) for kind in group)
                                       for group in catalogue.requirements(mine)),
                                 tuple(tuple(group) for group in v1_events.requirements(theirs)))
                self.assertEqual(tuple(v1_kind(kind, family) for kind in catalogue.accounted(mine)),
                                 tuple(v1_events.accounted(theirs)))
                self.assertEqual(catalogue.examination_code(mine), v1_events.examination_code(theirs))
                self.assertEqual(catalogue.recognised_only(mine), v1_mapping.recognised_only(theirs))
        self.assertEqual(sorted(code for code in v1_catalogue.CODES
                                if catalogue.recognised_only(catalogue.code_link(code))), ['99152', '99153'])  # D80

    def test_the_defining_kinds_equal_v1s(self):
        self.assertEqual({str(code): tuple(v1_kind(kind, catalogue.CODES[code].family) for kind in kinds)
                          for code, kinds in catalogue.DEFINING.items()}, dict(v1_mapping.DEFINING))
        self.assertEqual(sorted(catalogue.DEFINING), [43232, 43238, 43240, 43242, 43253, 43265, 44365, 44407, 45342,
                                                      45392, 49440])  # FINAL-V2 4.3 DEF:k's eleven (D27)
        for code in v1_catalogue.CODES:
            with self.subTest(code=code):
                self.assertEqual(tuple(v1_kind(kind, catalogue.CODES[int(code)].family)
                                       for kind in catalogue.defining(code)), v1_mapping.DEFINING.get(code, ()))

    def test_every_codes_class_tract_site_and_transmural_reading_equal_v1s(self):
        for code in FIVE_DIGIT + ODD_CODES:
            mine = (v1_value(catalogue.examination_class(code)), v1_value(catalogue.eus_tract(code)),
                    v1_value(catalogue.code_class(code)), v1_value(catalogue.site_class(code)),
                    catalogue.number(code) in catalogue.TRANSMURAL_INJECTION_CODES)
            theirs = (v1_mapping.examination_class(code), v1_mapping.eus_tract(code), v1_classes.code_class(code),
                      v1_mapping.DILATION_SITES.get(code, ''), code in v1_mapping.TRANSMURAL_INJECTION_CODES)
            if mine != theirs:
                self.fail(f'{code!r}: {mine} != {theirs}')

    def test_every_codes_included_examinations_equal_v1s(self):
        for code in tuple(v1_catalogue.CODES) + ODD_CODES:
            for family in SessionKind:
                with self.subTest(code=code, family=family):
                    self.assertEqual(catalogue.includes_examination(code, family), v1_catalogue.includes_examination(
                        code, v1_mapping.service_kind(SLUG[family])))


# --- the anatomy chain ------------------------------------------------------------------------------------------------


class AnatomyTests(SimpleTestCase):
    def test_every_landmarks_region_equals_v1s(self):
        self.assertEqual(tuple(anatomy.REGION_OF), tuple(Landmark))  # total, in Landmark's order
        self.assertEqual(v1_values(Landmark) - set(v1_mapping.REGION_OF), NEW_LANDMARKS)
        self.assertEqual(set(v1_mapping.REGION_OF) - v1_values(Landmark), {'not_stated'})
        for value in V1_LANDMARKS:
            with self.subTest(landmark=value):
                self.assertEqual(v1_value(anatomy.REGION_OF[Landmark(value)]), v1_mapping.REGION_OF[value])
                self.assertEqual(v1_value(anatomy.region(Landmark(value))), v1_mapping.region(value))
        self.assertEqual(v1_values(anatomy.Region), set(v1_mapping.REGION_OF.values()) - {''})

    def test_contains_compatible_and_disjoint_equal_v1s_for_every_pair(self):
        for first, second in itertools.product(V1_LANDMARKS, repeat=2):
            mine = (anatomy.contains(Landmark(first), Landmark(second)),
                    anatomy.compatible(Landmark(first), Landmark(second)),
                    anatomy.disjoint(Landmark(first), Landmark(second)))
            theirs = (v1_lexicon.contains(first, second), v1_lexicon.compatible(first, second),
                      v1_lexicon.disjoint(first, second))
            if mine != theirs:
                self.fail(f'{first}, {second}: {mine} != {theirs}')

    def test_the_closure_equals_v1s_with_the_two_new_portions_under_the_duodenum(self):
        for landmark in Landmark:
            with self.subTest(landmark=landmark):
                inside = v1_values(anatomy.CONTAINS[landmark])
                if landmark.value in NEW_LANDMARKS:
                    self.assertEqual(inside, set())  # they contain nothing
                    continue
                self.assertEqual(inside - NEW_LANDMARKS, set(v1_lexicon.CONTAINS[landmark.value]))
                # FINAL-V2 1.4: containment under duodenum - and so under whatever contains the duodenum
                expected = NEW_LANDMARKS if landmark in (Landmark.DUODENUM, Landmark.SMALL_BOWEL) else set()
                self.assertEqual(inside & NEW_LANDMARKS, expected)
        third, fourth = Landmark.THIRD_PORTION_DUODENUM, Landmark.FOURTH_PORTION_DUODENUM
        self.assertTrue(anatomy.disjoint(Landmark.SECOND_PORTION_DUODENUM, third))
        self.assertTrue(anatomy.disjoint(third, fourth))
        self.assertTrue(anatomy.disjoint(Landmark.AMPULLA, third))
        self.assertTrue(anatomy.compatible(Landmark.DUODENUM, fourth))
        self.assertFalse(anatomy.disjoint(Landmark.SMALL_BOWEL, third))
        self.assertEqual((anatomy.region(third), anatomy.region(fourth)), (anatomy.Region.DUODENUM,) * 2)

    def test_unplaced_and_altered_equal_v1s(self):
        self.assertEqual(v1_values(anatomy.UNPLACED), set(v1_lexicon.UNPLACED_LANDMARKS) - {'not_stated'})
        self.assertEqual(v1_values(anatomy.ALTERED), set(v1_lexicon.ALTERED_LANDMARKS))
        for place in anatomy.UNPLACED | anatomy.ALTERED:
            with self.subTest(place=place):
                self.assertFalse(any(anatomy.disjoint(place, other) or anatomy.disjoint(other, place)
                                     for other in Landmark))

    def test_in_regions_equals_v1s(self):
        region_sets = [tuple(rule[3]) for rule in v1_catalogue.READ_UNDER.values()]
        region_sets += [tuple(regions) for regions in v1_catalogue.UNRECONCILED_REGIONS.values()]
        region_sets += [(region,) for region in sorted(v1_values(anatomy.Region))] + [()]
        for value, regions in itertools.product(V1_LANDMARKS, region_sets):
            with self.subTest(landmark=value, regions=regions):
                self.assertEqual(anatomy.in_regions(Landmark(value), {anatomy.Region(r) for r in regions}),
                                 v1_mapping.in_regions(value, regions))

    def test_an_extent_and_a_station_are_read_as_their_landmark(self):
        for extent, landmark in itertools.product(Extent, Landmark):
            if extent is Extent.STATED_DEPTH:
                continue
            same = Landmark(extent.value)
            with self.subTest(extent=extent, landmark=landmark):
                self.assertEqual(
                    (anatomy.contains(extent, landmark), anatomy.contains(landmark, extent),
                     anatomy.compatible(extent, landmark), anatomy.disjoint(extent, landmark),
                     anatomy.region(extent)),
                    (anatomy.contains(same, landmark), anatomy.contains(landmark, same),
                     anatomy.compatible(same, landmark), anatomy.disjoint(same, landmark), anatomy.region(same)))
        for station in ct.Station:
            self.assertIs(anatomy.landmark_of(station), Landmark(station.value))
        self.assertIsNot(Extent.CECUM, Landmark.CECUM)  # plain Enums: only the functions here relate the two

    def test_a_stated_depth_is_no_place(self):
        depth = Extent.STATED_DEPTH
        self.assertIsNone(anatomy.landmark_of(depth))
        self.assertIsNone(anatomy.region(depth))
        self.assertTrue(anatomy.compatible(depth, depth))
        for other in tuple(Landmark) + tuple(Extent):
            with self.subTest(other=other):
                self.assertFalse(anatomy.contains(depth, other) or anatomy.contains(other, depth))
                self.assertFalse(anatomy.disjoint(depth, other) or anatomy.disjoint(other, depth))
                if other is not depth:
                    self.assertFalse(anatomy.compatible(depth, other))

    def test_the_anastomosis_places_are_the_enumeration_part_of_v1s_type_table(self):
        for subtype in ct.AnastomosisSubtype:
            theirs = next((place for place, forms in v1_lexicon.ANASTOMOSIS_TYPES.items() if subtype.value in forms), '')
            with self.subTest(subtype=subtype):
                self.assertEqual(v1_value(anatomy.anastomosis_place(subtype)), theirs)
        # what is left out: the type table's other entries, each a spelling of a type already placed (surface forms)
        forms = {form for place_forms in v1_lexicon.ANASTOMOSIS_TYPES.values() for form in place_forms}
        self.assertEqual(forms - v1_values(ct.AnastomosisSubtype), {
            'ileocolonic', 'ileo colonic', 'ileo colic', 'colo rectal', 'colo anal', 'ileo rectal', 'gastro jejunal',
            'oesophagojejunal', 'oesophagogastric', 'esophago jejunal', 'esophago gastric', 'oesophago jejunal',
            'oesophago gastric'})
        self.assertEqual(set(v1_values(anatomy.ANASTOMOSIS_PLACE.values())), set(v1_lexicon.ANASTOMOSIS_TYPES))


# --- kinds: umbrellas, covers, the catalogue kind, techniques ---------------------------------------------------------


class KindTests(SimpleTestCase):
    def test_the_umbrellas_and_the_one_act_equal_v1s(self):
        self.assertEqual(tuple(v1_value(kind) for kind in catalogue.REMOVAL_MEMBERS), v1_mapping.REMOVAL_MEMBERS)
        self.assertEqual(tuple(v1_value(kind) for kind in catalogue.INTERVENTION_MEMBERS),
                         v1_mapping.INTERVENTION_MEMBERS)
        self.assertEqual({v1_value(kind): tuple(v1_value(member) for member in members)
                          for kind, members in catalogue.UMBRELLAS.items()}, dict(v1_mapping.UMBRELLAS))
        self.assertEqual(v1_values(catalogue.ONE_ACT), set(v1_mapping.ONE_ACT))
        self.assertEqual(v1_values(catalogue.HEMOSTASIS_KINDS), set(v1_mapping.HEMOSTASIS_KINDS))
        self.assertEqual(v1_values(catalogue.NOT_REPORTED), set(v1_catalogue.NOT_REPORTED))
        self.assertEqual(v1_values(catalogue.UNSUPPORTED_ACTS), set(v1_catalogue.UNSUPPORTED_ACTS))

    def test_covers_equals_v1s_for_every_pair_of_kinds_in_every_family(self):
        kinds = tuple(Kind) + (None,)
        for family in SessionKind:
            for statement, act in itertools.product(kinds, repeat=2):
                if catalogue.covers(statement, act) != v1_mapping.covers(v1_kind(statement, family),
                                                                         v1_kind(act, family)):
                    self.fail(f'{family}: covers({statement}, {act})')

    def test_the_catalogue_kind_equals_v1s_enumeration_arm(self):
        purposes = tuple(ct.Purpose) + (None,)
        for family, kind, purpose in itertools.product(SessionKind, Kind, purposes):
            event = v1_event(kind.value, family=SLUG[family], purpose=v1_value(purpose) or 'not_stated')
            with self.subTest(family=family, kind=kind, purpose=purpose):
                self.assertEqual(v1_kind(catalogue.catalogue_kind(kind, purpose), family),
                                 v1_mapping.catalogue_kind(event))
        # a purpose v1 did not verify is no purpose here (the caller passes a supported purpose only)
        for kind in catalogue.HEMOSTASIS_KINDS:
            event = v1_event(kind.value, family='gi.egd', purpose='hemostasis', purpose_state='unverified')
            self.assertEqual(v1_kind(catalogue.catalogue_kind(kind, None), SessionKind.EGD),
                             v1_mapping.catalogue_kind(event))

    def test_the_technique_classes_equal_v1s(self):
        self.assertEqual({v1_value(device): v1_value(kind) for device, kind in catalogue.TECHNIQUE_CLASS.items()},
                         dict(v1_mapping.TECHNIQUE_CLASS))
        for device in tuple(ct.Device) + (None,):
            event = v1_event('dilation', family='gi.egd', technique=v1_value(device) or 'not_stated',
                             technique_state='verified' if device else 'absent')
            with self.subTest(device=device):
                self.assertEqual(v1_value(catalogue.technique_class(device)), v1_mapping.code_technique(event))
        self.assertEqual(v1_values(catalogue.TechniqueClass) - {'bougie'},
                         {profile.technique for profile in v1_catalogue.CODES.values() if profile.technique})

    def test_technique_dependence_and_family_coding_equal_v1s(self):
        for family, kind in itertools.product(tuple(SessionKind) + (None,), Kind):
            slug = SLUG[family] if family is not None else ''
            with self.subTest(family=family, kind=kind):
                self.assertEqual(catalogue.technique_dependent(family, kind),
                                 v1_mapping.technique_dependent(slug, v1_kind(kind, family)))
                if family is not None:
                    self.assertEqual(catalogue.family_codes_act(family, kind),
                                     v1_catalogue.family_codes_act(slug, v1_kind(kind, family)))


# --- the class tables -------------------------------------------------------------------------------------------------

# Every class table over landmarks or extents (the new-landmark rule reads them all).
CLASS_TABLES = {
    'FULL_REACH': catalogue.FULL_REACH, 'SHORT_OF_DUODENUM': catalogue.SHORT_OF_DUODENUM,
    'SIGMOIDOSCOPIC_REACH': catalogue.SIGMOIDOSCOPIC_REACH, 'COLONOSCOPIC_REACH': catalogue.COLONOSCOPIC_REACH,
    'STOMA_REACH': catalogue.STOMA_REACH, 'COLONOSCOPY_FULL_REACH': catalogue.COLONOSCOPY_FULL_REACH,
    'COLONOSCOPY_FULL_ANASTOMOSIS': catalogue.COLONOSCOPY_FULL_ANASTOMOSIS,
    **{f'EUS_CLASS_REACH[{name.value}]': reach for name, reach in catalogue.EUS_CLASS_REACH.items()},
    **{f'ENTEROSCOPY_CLASS_REACH[{name.value}]': reach for name, reach in catalogue.ENTEROSCOPY_CLASS_REACH.items()},
    **{f'SITE_CLASSES[{name.value}]': places for name, places in catalogue.SITE_CLASSES.items()},
}


class ClassTableTests(SimpleTestCase):
    def test_the_eus_class_tables_equal_v1s(self):
        self.assertEqual(tuple(v1_value(name) for name in catalogue.EXAMINATION_CLASSES), v1_mapping.EXAMINATION_CLASSES)
        self.assertEqual({v1_value(name): v1_values(reach) - NEW_LANDMARKS
                          for name, reach in catalogue.EUS_CLASS_REACH.items()},
                         {name: set(reach) for name, reach in v1_mapping.CLASS_REACH.items()})
        for name in ('FULL_REACH', 'SHORT_OF_DUODENUM', 'SIGMOIDOSCOPIC_REACH', 'COLONOSCOPIC_REACH', 'STOMA_REACH'):
            with self.subTest(table=name):
                self.assertEqual(v1_values(getattr(catalogue, name)) - NEW_LANDMARKS, set(getattr(v1_mapping, name)))
        self.assertEqual({str(code): v1_value(name) for code, name in catalogue.LOWER_EUS_CLASS.items()},
                         dict(v1_mapping.LOWER_EUS_CLASS))
        self.assertEqual({str(code) for code in catalogue.UPPER_EUS_CODES}, set(v1_mapping.UPPER_EUS_CODES))
        self.assertEqual({str(code) for code in catalogue.EGD_LIMITED_EUS_CODES}, set(v1_mapping.EGD_LIMITED_EUS_CODES))
        self.assertEqual({str(code) for code in catalogue.TRANSMURAL_INJECTION_CODES},
                         set(v1_mapping.TRANSMURAL_INJECTION_CODES))
        self.assertEqual(tuple(v1_value(station) for station in catalogue.UPPER_STATIONS), v1_mapping.UPPER_STATIONS)
        self.assertEqual(v1_values(catalogue.UPPER_TRACT_REGIONS), set(v1_mapping.UPPER_TRACT_REGIONS))
        self.assertEqual(v1_values(catalogue.DEFINING_TARGET_APART), set(v1_mapping.DEFINING_TARGET_APART))
        self.assertEqual(v1_value(ct.Tract.UPPER), v1_mapping.UPPER_TRACT)
        self.assertEqual(v1_value(ct.Tract.LOWER), v1_mapping.LOWER_TRACT)

    def test_the_enteroscopy_class_tables_equal_v1s(self):
        self.assertEqual(tuple(v1_value(name) for name in catalogue.EnteroscopyClass), v1_classes.CLASSES)
        self.assertEqual(tuple((first, last, v1_value(name)) for first, last, name in catalogue.ENTEROSCOPY_RANGES),
                         v1_classes.RANGES)
        self.assertEqual(v1_values(catalogue.ILEAL_REACH), set(v1_classes.ILEAL_REACH))
        self.assertEqual({v1_value(name): v1_values(reach) for name, reach in catalogue.ENTEROSCOPY_CLASS_REACH.items()},
                         {name: set(reach) for name, reach in v1_classes.CLASS_REACH.items()})
        self.assertEqual(v1_values(catalogue.ENTEROSCOPY_DEEPER), set(v1_classes.DEEPER))
        # classes.CLASS_ROUTE's routes as approaches; FINAL-V2 4.3 ENT asks the oral approach of the jejunal class too
        route_approach = {v1_classes.ORAL: ct.Approach.ORAL, v1_classes.THROUGH_STOMA: ct.Approach.THROUGH_STOMA,
                          v1_classes.THROUGH_POUCH: ct.Approach.THROUGH_POUCH}
        expected = {catalogue.EnteroscopyClass(name): route_approach[route]
                    for name, route in v1_classes.CLASS_ROUTE.items()}
        expected[catalogue.EnteroscopyClass.JEJUNAL] = ct.Approach.ORAL
        self.assertEqual(dict(catalogue.ENTEROSCOPY_CLASS_APPROACH), expected)
        # classes.ROUTES: the anatomy each route's class needs - the stoma, and (D141) the SMALL-INTESTINAL pouch, which
        # FINAL-V2 4.3 ENT names as an ileal_pouch entry
        self.assertEqual({v1_value(name) for name in catalogue.ENTEROSCOPY_CLASS_ANATOMY}, set(v1_classes.ROUTES))
        self.assertEqual(dict(catalogue.ENTEROSCOPY_CLASS_ANATOMY),
                         {catalogue.EnteroscopyClass.STOMA: ct.AnatomyType.STOMA,
                          catalogue.EnteroscopyClass.POUCH: ct.AnatomyType.ILEAL_POUCH})
        self.assertEqual(v1_value(catalogue.ENTEROSCOPY_CLASS_ANATOMY[catalogue.EnteroscopyClass.STOMA]),
                         v1_classes.ROUTES[v1_classes.STOMA])
        # every catalogue code of the family is in exactly one range (classes' own pin)
        family = [code for code, profile in catalogue.CODES.items() if profile.family is SessionKind.ENTEROSCOPY]
        self.assertTrue(family)
        self.assertTrue(all(catalogue.code_class(str(code)) is not None for code in family))

    def test_the_colonoscopy_full_reach_equals_v1s(self):
        self.assertEqual(v1_values(catalogue.COLONOSCOPY_FULL_REACH), set(v1_assess.COLONOSCOPY_FULL_REACH))
        self.assertEqual(v1_values(catalogue.COLONOSCOPY_FULL_ANASTOMOSIS), set(v1_assess.COLONOSCOPY_FULL_ANASTOMOSIS))
        # D44's right-colon-side anastomosis as subtypes: those whose v1 type place is a full-reach anastomosis place
        theirs = {subtype for subtype in ct.AnastomosisSubtype
                  if any(subtype.value in v1_lexicon.ANASTOMOSIS_TYPES.get(place, ())
                         for place in v1_assess.COLONOSCOPY_FULL_ANASTOMOSIS)}
        self.assertEqual(set(catalogue.COLONOSCOPY_FULL_SUBTYPES), theirs)
        self.assertEqual(set(catalogue.COLONOSCOPY_FULL_SUBTYPES), {ct.AnastomosisSubtype.ILEOCOLIC})  # 4.3 COLFULL

    def test_the_dilation_site_tables_equal_v1s(self):
        self.assertEqual({v1_value(name): v1_values(places) - NEW_LANDMARKS
                          for name, places in catalogue.SITE_CLASSES.items()},
                         {name: set(places) for name, places in v1_mapping.SITE_CLASSES.items()})
        self.assertEqual({str(code): v1_value(name) for code, name in catalogue.DILATION_SITES.items()},
                         dict(v1_mapping.DILATION_SITES))

    def test_the_two_new_duodenal_portions_stand_where_v1s_duodenum_stands(self):
        """The rule engine/catalogue.py states for LANDMARKS2's two new values (DECISIONS D204): in every class table
        they stand where v1's duodenal landmarks (duodenum, second_portion_duodenum - which agree in every table) stand;
        stated_depth is in none."""
        for name, table in CLASS_TABLES.items():
            values = v1_values(table)
            with self.subTest(table=name):
                self.assertEqual('duodenum' in values, 'second_portion_duodenum' in values)
                self.assertEqual('third_portion_duodenum' in values, 'duodenum' in values)
                self.assertEqual('fourth_portion_duodenum' in values, 'duodenum' in values)
                self.assertNotIn('stated_depth', values)
        holding = sorted(name for name, table in CLASS_TABLES.items() if 'third_portion_duodenum' in v1_values(table))
        self.assertEqual(holding, ['EUS_CLASS_REACH[full]', 'FULL_REACH', 'SITE_CLASSES[gastric_duodenal]'])


# --- the design's own code lists (FINAL-V2 4.3 and Appendix A), read from the ported tables -----------------------------


def _codes(predicate) -> list:
    return sorted(code for code, profile in catalogue.CODES.items() if predicate(code, profile))


class DesignRowTests(SimpleTestCase):
    """The code lists FINAL-V2 4.3's rows and Appendix A's templates name, each reproduced from the ported tables: the
    tables agree with the governing design, not only with v1."""

    def test_the_code_specific_rows_of_4_3(self):
        technique = catalogue.TechniqueClass
        self.assertEqual(_codes(lambda code, p: p.technique is technique.BALLOON),
                         [43214, 43220, 43233, 43249, 43277, 44381, 44405, 45340, 45386])  # TECH:c balloon
        self.assertEqual(_codes(lambda code, p: p.technique is technique.WIRE_BOUGIE), [43226, 43248])
        self.assertEqual(_codes(lambda code, p: Kind.BLEEDING_CONTROL in p.covers),
                         [43227, 43255, 44366, 44378, 44391, 45334, 45382])  # CAUSE: C's table
        self.assertEqual(_codes(lambda code, p: p.addon), [43273, 91013, 99153, 99417])  # ADDON
        self.assertEqual(sorted(catalogue.DILATION_SITES),
                         [43213, 43214, 43220, 43226, 43233, 43245, 43248, 43249])  # SITE:s
        self.assertEqual(sorted(catalogue.UPPER_EUS_CODES), [43231, 43232, 43237, 43238, 43240, 43242, 43253, 43259])
        self.assertEqual(sorted(catalogue.LOWER_EUS_CLASS), [44406, 44407, 45341, 45342, 45391, 45392])  # TRACT, LOWER
        self.assertEqual(_codes(lambda code, p: p.exam is catalogue.EusClass.FULL), [43242, 43259])  # STATIONS
        self.assertEqual(_codes(lambda code, p: p.exam is catalogue.EusClass.LIMITED),
                         [43231, 43232, 43237, 43238])  # LIMITED
        self.assertEqual(sorted(catalogue.TRANSMURAL_INJECTION_CODES), [43253])  # ROUTE
        ent = {name: [code for code in sorted(catalogue.CODES) if catalogue.code_class(str(code)) is name]
               for name in catalogue.EnteroscopyClass}
        self.assertEqual(ent, {  # ENT: 44360-44373 jejunal, 44376-44379 ileal, 44380-44384 stoma, 44385-44386 pouch
            catalogue.EnteroscopyClass.JEJUNAL: [44360, 44361, 44363, 44364, 44365, 44366, 44369, 44370, 44372, 44373],
            catalogue.EnteroscopyClass.ILEAL: [44376, 44377, 44378, 44379],
            catalogue.EnteroscopyClass.STOMA: [44380, 44381, 44382, 44384],
            catalogue.EnteroscopyClass.POUCH: [44385, 44386]})
        self.assertEqual(v1_values(catalogue.COLONOSCOPY_FULL_REACH),  # COLFULL's FULL_REACH landmarks
                         {'cecum', 'appendiceal_orifice', 'ileocecal_valve', 'terminal_ileum', 'ileum',
                          'neo_terminal_ileum', 'small_bowel'})

    def test_appendix_a_templates_partition_the_163_codes(self):
        eus = lambda p: p.family is SessionKind.EUS  # noqa: E731
        templates = {
            'BASE': _codes(lambda c, p: p.base and p.family in catalogue.ENDOSCOPIC_FAMILIES),
            'EUS_EXAM': _codes(lambda c, p: eus(p) and p.covers == (Kind.EXAMINATION,)),
            'EUS_ACT': _codes(lambda c, p: eus(p) and len(p.covers) > 1),
            'ADDON_ACT': _codes(lambda c, p: p.addon and p.family not in catalogue.EM_FAMILIES
                                and p.family is not SessionKind.SEDATION),
            'FEEDING': _codes(lambda c, p: p.family is SessionKind.FEEDING_TUBE),
            'TEST': _codes(lambda c, p: p.family in (SessionKind.CAPSULE, SessionKind.MOTILITY, SessionKind.REFLUX,
                                                       SessionKind.ANORECTAL) and not p.addon),
            'EM': _codes(lambda c, p: p.family is SessionKind.OFFICE_EM and p.base),
            'EM_ADDON': _codes(lambda c, p: p.family is SessionKind.OFFICE_EM and p.addon),
            'RECOGNISED': _codes(lambda c, p: catalogue.recognised_only(catalogue.code_link(str(c)))),
        }
        self.assertEqual({name: len(codes) for name, codes in templates.items()},
                         {'BASE': 11, 'EUS_EXAM': 6, 'EUS_ACT': 8, 'ADDON_ACT': 2, 'FEEDING': 8, 'TEST': 15, 'EM': 13,
                          'EM_ADDON': 1, 'RECOGNISED': 2})
        self.assertEqual(templates['BASE'], [43197, 43200, 43235, 43260, 44360, 44376, 44380, 44385, 44388, 45330,
                                             45378])
        self.assertEqual(templates['EUS_EXAM'], [43231, 43237, 43259, 44406, 45341, 45391])
        self.assertEqual(templates['EUS_ACT'], [43232, 43238, 43240, 43242, 43253, 44407, 45342, 45392])
        self.assertEqual(templates['ADDON_ACT'], [43273, 91013])
        named = [code for codes in templates.values() for code in codes]
        self.assertEqual(len(named), len(set(named)))  # each code in exactly one
        self.assertEqual(len(catalogue.CODES) - len(named), 97)  # ACT: the therapeutic endoscopic codes


# --- the family maps --------------------------------------------------------------------------------------------------


class FamilyMapTests(SimpleTestCase):
    def test_the_family_order_and_family_sets_equal_v1s(self):
        self.assertEqual(tuple(SLUG[family] for family in catalogue.FAMILY_ORDER), v1_profiles.FAMILY_ORDER)
        self.assertEqual(tuple(SLUG[family] for family in catalogue.FAMILY_ORDER), v1_lexicon.FAMILY_ORDER)
        self.assertEqual({SLUG[family] for family in catalogue.PROCEDURAL_FAMILIES}, set(v1_lexicon.PROCEDURAL_FAMILIES))
        self.assertEqual({SLUG[family] for family in catalogue.PROCEDURAL_FAMILIES},
                         {slug for slug, profile in v1_profiles.PROFILES.items() if profile.procedure})
        self.assertEqual({SLUG[family] for family in catalogue.ENDOSCOPIC_FAMILIES}, set(v1_mapping.ENDOSCOPIC_FAMILIES))
        self.assertEqual(v1_values(catalogue.EM_FAMILIES), set(v1_lexicon.EM_PROCEDURES))
        self.assertEqual(v1_values(catalogue.EM_KINDS), set(v1_lexicon.EM_KINDS))
        self.assertEqual({SLUG[family] for family in catalogue.PROFILE_SUPPORTED},
                         {slug for slug, profile in v1_profiles.PROFILES.items() if profile.supported})

    def test_the_routing_ranges_and_carve_outs_equal_v1s(self):
        self.assertEqual(set(catalogue.CODE_RANGES), set(SessionKind))
        for slug, profile in v1_profiles.PROFILES.items():
            family = FAMILY_OF_SLUG[slug]
            with self.subTest(family=slug):
                self.assertEqual(tuple((str(low), str(high)) for low, high in catalogue.CODE_RANGES[family]),
                                 profile.code_ranges)
                self.assertEqual({str(code) for code in catalogue.EXCLUDED_CODES.get(family, ())},
                                 set(profile.excluded_codes))
        bounds = [bound for ranges in catalogue.CODE_RANGES.values() for pair in ranges for bound in pair]
        self.assertTrue(all(10000 <= bound <= 99999 for bound in bounds))  # each written as v1's five characters

    def test_the_catalogue_entries_support_levels_and_acts_equal_v1s(self):
        self.assertEqual({SLUG[family]: v1_value(level) for family, level in catalogue.FAMILY_SUPPORT.items()},
                         {slug: entry.support for slug, entry in v1_catalogue.CATALOGUE.items()})
        self.assertEqual({SLUG[family]: tuple(v1_kind(kind, family) for kind in acts)
                          for family, acts in catalogue.FAMILY_ACTS.items()},
                         {slug: tuple(entry.acts) for slug, entry in v1_catalogue.CATALOGUE.items()})

    def test_the_bundled_and_unsupported_kinds_equal_v1s_family_entries(self):
        """DECISIONS D191: BUNDLED_KINDS and UNSUPPORTED_KINDS are the Kind-valued parts of every v1 FamilyEntry's
        bundled and unsupported_acts, by value, family by family; what is left out is rule names (pinned here)."""
        rule_names = set()
        for field, table in (('bundled', catalogue.BUNDLED_KINDS), ('unsupported_acts', catalogue.UNSUPPORTED_KINDS)):
            self.assertEqual(tuple(table), tuple(catalogue.FAMILY_ACTS))  # keyed as FAMILY_ACTS: every catalogue entry
            for slug, entry in v1_catalogue.CATALOGUE.items():
                family = FAMILY_OF_SLUG[slug]
                kinds = {v1_kind(kind, family) for kind in Kind} - {''}  # v1's catalogue kinds in the family
                theirs = {item for item, _why in getattr(entry, field)}
                with self.subTest(field=field, family=slug):
                    self.assertEqual({v1_kind(kind, family) for kind in table[family]}, theirs & kinds)
                    self.assertTrue(all(isinstance(kind, Kind) for kind in table[family]))
                rule_names |= theirs - kinds
        self.assertEqual(rule_names,
                         {'em_routine', 'biopsy_of_removed_lesion', 'lift_injection', 'resection_technique'})

    def test_the_bundled_and_unsupported_kinds_are_those_the_repair_lists(self):
        """The arbiter triage's item 1e#1 (D191) lists both tables' members; the kinds no code of the family accounts
        for (family_codes_act) and a session of the family holds - D191's own cases for K2 - are among them."""
        common = {Kind.CLIP, Kind.CANNULATION}
        self.assertEqual({family: kinds for family, kinds in catalogue.BUNDLED_KINDS.items() if kinds}, {
            SessionKind.EGD: common, SessionKind.ENTEROSCOPY: common, SessionKind.COLONOSCOPY: common,
            SessionKind.FLEX_SIG: common, SessionKind.EUS: {Kind.BIOPSY},
            SessionKind.ERCP: {Kind.CANNULATION, Kind.INJECTION, Kind.CLIP}, SessionKind.REFLUX: {Kind.CAPSULE_STUDY}})
        self.assertEqual({family: kinds for family, kinds in catalogue.UNSUPPORTED_KINDS.items() if kinds}, {
            SessionKind.EGD: {Kind.ESD}, SessionKind.COLONOSCOPY: {Kind.ESD}, SessionKind.EUS: {Kind.DRAINAGE},
            SessionKind.ANORECTAL: {Kind.BALLOON_EXPULSION}})
        for family, kind in ((SessionKind.ERCP, Kind.CANNULATION), (SessionKind.COLONOSCOPY, Kind.CLIP),
                             (SessionKind.EGD, Kind.ESD)):
            with self.subTest(family=family, kind=kind):
                self.assertFalse(catalogue.family_codes_act(family, kind))
                self.assertIn(kind, catalogue.BUNDLED_KINDS[family] | catalogue.UNSUPPORTED_KINDS[family])

    def test_the_family_reach_equals_v1s_family_regions(self):
        """DECISIONS D192: K3's reach is studio.gi.services.FAMILY_REGIONS by value, over anatomy's Region; a family
        that is not in it (the EUS, the ERCP, every family that is no endoscopy) is not judged."""
        region = anatomy.Region
        reach = catalogue.FAMILY_REACH
        self.assertEqual({SLUG[family]: v1_values(regions) for family, regions in reach.items()},
                         {slug: set(regions) for slug, regions in v1_services.FAMILY_REGIONS.items()})
        self.assertEqual(dict(reach), {
            SessionKind.EGD: {region.ESOPHAGUS, region.STOMACH, region.DUODENUM},
            SessionKind.COLONOSCOPY: {region.COLON, region.RECTUM, region.ANUS, region.SMALL_BOWEL},
            SessionKind.FLEX_SIG: {region.COLON, region.RECTUM, region.ANUS},
            SessionKind.ENTEROSCOPY: {region.SMALL_BOWEL}})
        self.assertTrue(all(isinstance(found, region) for regions in reach.values() for found in regions))
        # 3a's pin (an EGD act at the sigmoid colon is out of reach), and the over-holds D192 records as fail-closed
        # residuals: an EGD biopsy at the ampulla (the biliary region), a push enteroscopy's gastric act
        self.assertNotIn(anatomy.region(Landmark.SIGMOID_COLON), reach[SessionKind.EGD])
        self.assertNotIn(anatomy.region(Landmark.AMPULLA), reach[SessionKind.EGD])
        self.assertNotIn(anatomy.region(Landmark.GASTRIC_ANTRUM), reach[SessionKind.ENTEROSCOPY])
        self.assertNotIn(SessionKind.EUS, reach)
        self.assertNotIn(SessionKind.ERCP, reach)

    def test_read_under_equals_v1s(self):
        self.assertEqual({(SLUG[family], v1_kind(kind, family)): (SLUG[rule[0]], v1_values(rule[1]))
                          for (family, kind), rule in catalogue.READ_UNDER.items()},
                         {key: (rule[0], set(rule[3])) for key, rule in v1_catalogue.READ_UNDER.items()})
        for family, kind, value in itertools.product(SessionKind, Kind, V1_LANDMARKS):
            mine = catalogue.read_under(family, kind, Landmark(value))
            theirs = v1_mapping.read_under(SLUG[family], v1_kind(kind, family), value)
            if (SLUG[mine] if mine is not None else '') != theirs:
                self.fail(f'read_under({family}, {kind}, {value}): {mine} != {theirs!r}')
        self.assertIs(catalogue.read_under(SessionKind.EUS, Kind.BIOPSY, Landmark.GASTRIC_ANTRUM), SessionKind.EGD)
        self.assertIsNone(catalogue.read_under(SessionKind.EUS, Kind.BIOPSY, Landmark.RECTUM))

    def test_the_anastomosis_families_and_route_b_tables_equal_v1s(self):
        self.assertEqual({v1_value(place): {SLUG[family] for family in families}
                          for place, families in catalogue.ANASTOMOSIS_FAMILIES.items()},
                         {place: set(families) for place, families in v1_mapping.ANASTOMOSIS_FAMILIES.items()})
        self.assertEqual({str(code): tuple(v1_value(kind) for kind in kinds)
                          for code, kinds in catalogue.UNRECONCILED_ACTS.items()}, dict(v1_catalogue.UNRECONCILED_ACTS))
        self.assertEqual({str(code): tuple(v1_value(region) for region in regions)
                          for code, regions in catalogue.UNRECONCILED_REGIONS.items()},
                         dict(v1_catalogue.UNRECONCILED_REGIONS))


# --- the boundary: NoWordLists, the rest of 5.7 measure 4, no v1 at runtime --------------------------------------------


def _source(name: str) -> str:
    return MODULES[name].read_text(encoding='utf-8')


def _strings_in_assignments(source: str) -> list:
    """Every string constant in a module-level assignment's value (stricter than NoWordLists: none at all)."""
    found = []
    for statement in ast.parse(source).body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            found += [node.value for node in ast.walk(statement.value)
                      if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    return found


class BoundaryTests(SimpleTestCase):
    def test_no_word_lists_and_the_rest_of_measure_4_hold(self):
        for name in MODULES:
            with self.subTest(module=name):
                self.assertEqual(measure_4(_source(name), engine=True), [])
                self.assertEqual(_strings_in_assignments(_source(name)), [])

    def test_each_rule_refuses_a_planted_control_in_these_modules(self):
        plants = {
            "\nWORDS = ('no', 'not')\n": 'a module-level word list',
            "\nPLACES = {'cecum': 'colon', 'rectum': 'rectum'}\n": 'a module-level word list',
            '\nimport re\n': 'imports re',
            '\nfrom studio.interpretation import mapping\n': 'imports studio.interpretation.mapping',
            '\nfrom studio.interpretation.contract import segment\n': 'imports a text module',
            '\ndef probe(fact):\n    return fact.text\n': 'reads .text',
            '\ndef probe(code):\n    return code.startswith("43")\n': 'calls .startswith()',
            '\ndef probe(code):\n    return "43" in code\n': 'tests membership against a string',
        }
        for name in MODULES:
            for plant, expected in plants.items():
                with self.subTest(module=name, plant=plant.strip()):
                    found = measure_4(_source(name) + plant, engine=True)
                    self.assertTrue(any(expected in finding for finding in found), found)
            with self.subTest(module=name, plant='a control'):
                self.assertEqual(measure_4(_source(name) + '\n# a comment\n', engine=True), [])
        self.assertEqual(_strings_in_assignments("A = ('x',)\nB = {1: 'y'}\n"), ['x', 'y'])

    def test_engine_imports_no_v1_module_and_nothing_of_gi_at_runtime(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.catalogue, studio.interpretation.engine.anatomy\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','),
                         ['studio', 'studio.interpretation', 'studio.interpretation.contract',
                          'studio.interpretation.contract.types', 'studio.interpretation.engine',
                          'studio.interpretation.engine.anatomy', 'studio.interpretation.engine.catalogue'])

    def test_the_new_enums_are_plain_unique_and_closed(self):
        defined = [value for module in (anatomy, catalogue) for value in vars(module).values()
                   if isinstance(value, type) and issubclass(value, enum.Enum) and value.__module__ == module.__name__]
        self.assertEqual({cls.__name__ for cls in defined},
                         {'Region', 'LinkRoute', 'NoRouteReason', 'SupportLevel', 'TechniqueClass', 'SiteClass',
                          'EusClass', 'EnteroscopyClass'})
        for cls in defined:
            with self.subTest(enum=cls.__name__):
                self.assertFalse(issubclass(cls, str))  # never a StrEnum: a member never equals a raw string
                self.assertEqual(len(cls.__members__), len(list(cls)))
                self.assertTrue(all(member.name == member.value.upper() for member in cls))

    def test_the_tables_cannot_be_changed_at_runtime(self):
        for table in (anatomy.REGION_OF, anatomy.CONTAINS, catalogue.CODES, catalogue.CODE_LINKS, catalogue.DEFINING,
                      catalogue.FAMILY_ACTS, catalogue.EUS_CLASS_REACH, catalogue.BUNDLED_KINDS,
                      catalogue.UNSUPPORTED_KINDS, catalogue.FAMILY_REACH):
            with self.subTest(table=type(table).__name__), self.assertRaises(TypeError):
                table[next(iter(table))] = None

    def test_no_file_of_the_step_cites_the_report_decisions_records(self):
        """DECISIONS D207: the builders' readings are recorded in DECISIONS (D207, and the D-number of each ruling),
        not in the report the harness refused; a citation of that report points nowhere."""
        report = 'REPORT' + '.md'  # written apart, so that this file's own source cites nothing
        for path in (*MODULES.values(), Path(__file__)):
            with self.subTest(file=path.name):
                self.assertNotIn(report, path.read_text(encoding='utf-8'))
        self.assertIn('DECISIONS D207 records the list', ' '.join((catalogue.__doc__ or '').split()))
