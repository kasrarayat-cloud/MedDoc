"""Events and the catalogue (Gemini migration slice S03; design/contract.md 9.1-9.2; design/FINAL.md C3, C7, C8;
design/ADJUDICATION.md C-1 and C-6), TEXT-ONLY: mapping.REGION_OF pinned equal to studio.gi.services.REGION_OF through a
TEST-ONLY import (the module itself never imports gi.services); the service kinds pinned against the catalogue; every
catalogue kind reachable from an event; the umbrellas; the technique classes; the link routes (a), (b) and (d) - there is
no route (c): a code with no catalogue profile is never linked; map_events through normalize."""
from __future__ import annotations

import sys
from unittest import mock

from django.test import SimpleTestCase

from studio.gi import catalogue, profiles
from studio.interpretation import mapping, schema
from tests.test_interpretation_identity import a, act, normalized, snare, tg


def event(kind: str, *, family: str = 'gi.colonoscopy', purpose: str = 'not_stated', purpose_state: str = 'verified',
          technique: str = 'not_stated', technique_state: str = 'absent', landmark: str = 'not_stated',
          landmark_state: str = 'absent') -> dict:
    """An event in its stored shape, as far as the mapping reads it."""
    def record(value, state):
        return {'value': value, 'state': state, 'open': False, 'basis': 'stated' if state == 'verified' else 'absent'}
    return {'id': 'E1', 'family': family, 'kind': record(kind, 'verified'), 'purpose': record(purpose, purpose_state),
            'technique': record(technique, technique_state), 'target': record(landmark, landmark_state)}


class Regions(SimpleTestCase):
    """C8: REGION_OF is a copy of services.REGION_OF keyed by the schema's landmarks, pinned equal by this test-only
    import, so no gi.services code runs on the new path."""

    def test_every_landmark_has_a_region_entry_and_only_the_legacy_regions(self):
        from studio.gi import services  # test-only: the legacy table the copy is pinned to
        self.assertEqual(tuple(mapping.REGION_OF), schema.LANDMARKS)
        self.assertLessEqual(set(mapping.REGION_OF.values()) - {''}, set(services.REGION_OF.values()))

    def test_pinned_equal_to_services_region_of_by_name(self):
        from studio.gi import services
        alias = {'second portion of the duodenum': 'second_portion_duodenum'}
        compared = 0
        for name, legacy in services.REGION_OF.items():
            landmark = alias.get(name, name.replace(' ', '_'))
            if landmark in mapping.REGION_OF:
                compared += 1
                with self.subTest(name=name):
                    self.assertEqual(mapping.REGION_OF[landmark], legacy)
        self.assertEqual((len(services.REGION_OF), compared), (43, 39))  # all but antrum-and-body, 3 pancreas parts
        unnamed = {name for name in services.REGION_OF if alias.get(name, name.replace(' ', '_')) not in mapping.REGION_OF}
        self.assertEqual(unnamed, {'gastric antrum and body', 'pancreatic head', 'pancreatic body', 'pancreatic tail'})

    def test_pinned_equal_to_what_services_reads_in_each_landmarks_own_name(self):
        from studio.gi import services
        from studio.interpretation import lexicon
        for landmark in schema.LANDMARKS:
            forms = lexicon.LANDMARK_FORMS.get(landmark, ())
            legacy = next((region for _, region, pattern in services.ANATOMY if forms and pattern.search(forms[0])), '')
            with self.subTest(landmark=landmark, form=forms[:1]):
                self.assertEqual(mapping.REGION_OF[landmark], legacy)

    def test_in_regions_and_read_under(self):
        self.assertTrue(mapping.in_regions('anal_canal', catalogue.UNRECONCILED_REGIONS['46221']))
        self.assertFalse(mapping.in_regions('distal_esophagus', catalogue.UNRECONCILED_REGIONS['46221']))
        self.assertFalse(mapping.in_regions('anastomosis', ('colon',)))  # an altered place lies in no region
        self.assertEqual(mapping.read_under('gi.eus', 'biopsy', 'gastric_antrum'), 'gi.egd')
        self.assertEqual(mapping.read_under('gi.eus', 'biopsy', 'rectum'), '')
        self.assertEqual(mapping.read_under('gi.colonoscopy', 'biopsy', 'gastric_antrum'), '')


class Kinds(SimpleTestCase):
    def test_service_kinds_are_the_catalogues(self):
        for family, kind in mapping.SERVICE_KIND.items():
            with self.subTest(family=family):
                self.assertEqual(catalogue.entry(family).kinds[0], kind)
        named = {family for family, entry in catalogue.CATALOGUE.items() if entry.kinds and entry.support == 'supported'}
        self.assertEqual(named, set(mapping.SERVICE_KIND))

    def test_an_examination_is_the_session(self):
        self.assertEqual(mapping.catalogue_kind(event('examination')), 'examination')
        self.assertEqual(mapping.catalogue_kind(event('examination', family='gi.eus')), 'eus_exam')
        self.assertEqual(mapping.role('eus_exam'), 'session')
        self.assertEqual(mapping.EXAMINATION_KINDS, frozenset({'examination', 'eus_exam'}))

    def test_a_verified_hemostasis_purpose_reads_a_clip_or_an_injection_as_bleeding_control(self):
        for kind in ('clip', 'injection'):
            with self.subTest(kind):
                self.assertEqual(mapping.catalogue_kind(event(kind, purpose='hemostasis')), 'bleeding_control')
                self.assertEqual(mapping.catalogue_kind(event(kind, purpose='hemostasis', purpose_state='unverified')),
                                 kind)
                self.assertEqual(mapping.catalogue_kind(event(kind, purpose='lift_for_resection')), kind)
        self.assertEqual(mapping.catalogue_kind(event('tattoo', purpose='hemostasis')), 'tattoo')

    def test_other_maps_to_none(self):
        self.assertEqual(mapping.catalogue_kind(event('other')), '')
        self.assertEqual(mapping.role(''), 'listed')

    def test_every_catalogue_kind_is_reachable_from_an_event(self):
        reached = set()
        for kind in schema.KINDS:
            for family in mapping.SERVICE_KIND:
                for purpose in ('not_stated', 'hemostasis'):
                    reached.add(mapping.catalogue_kind(event(kind, family=family, purpose=purpose)))
        reached.discard('')
        self.assertEqual(reached, set(mapping.CATALOGUE_KINDS))
        rules = {'biopsy_of_removed_lesion', 'lift_injection', 'resection_technique', 'em_routine'}  # rules, not acts
        named = {kind for profile in catalogue.CODES.values() for kind in profile.covers}
        for entry in catalogue.CATALOGUE.values():
            named |= set(entry.acts) | {kind for kind, _ in entry.bundled} | {kind for kind, _ in entry.unsupported_acts}
        named |= set(catalogue.NOT_REPORTED) | set(catalogue.UNSUPPORTED_ACTS)
        named |= {kind for kinds in catalogue.UNRECONCILED_ACTS.values() for kind in kinds}
        named |= {kind for (_, kind) in catalogue.READ_UNDER}
        self.assertEqual(named - rules - reached, set())

    def test_roles(self):
        self.assertEqual([mapping.role(kind) for kind in ('clip', 'cannulation', 'esd', 'snare', 'removal')],
                         ['not_reported', 'not_reported', 'unsupported', 'act', 'umbrella'])


class Umbrellas(SimpleTestCase):
    def test_the_removal_umbrella_is_reconciles_removal_kinds(self):
        from studio.validation import reconcile  # test-only: the legacy list the umbrella is copied from
        self.assertEqual(mapping.REMOVAL_MEMBERS, reconcile.REMOVAL_KINDS)

    def test_the_intervention_umbrella(self):
        members = set(mapping.INTERVENTION_MEMBERS)
        self.assertEqual(set(schema.KINDS) - members,
                         {'examination', 'em_visit', 'em_prolonged', 'moderate_sedation', 'intervention', 'other'})
        self.assertIn('removal', members)

    def test_covers(self):
        self.assertTrue(mapping.covers('snare', 'snare'))
        self.assertTrue(mapping.covers('tattoo', 'injection'))
        self.assertTrue(mapping.covers('injection', 'tattoo'))
        self.assertTrue(mapping.covers('removal', 'emr'))
        self.assertFalse(mapping.covers('snare', 'removal'))  # a member never covers its umbrella
        self.assertTrue(mapping.covers('intervention', 'biopsy'))
        self.assertFalse(mapping.covers('intervention', 'examination'))
        self.assertFalse(mapping.covers('intervention', 'em_visit'))
        self.assertFalse(mapping.covers('', ''))


class Techniques(SimpleTestCase):
    def test_the_technique_classes_read_a_verified_device_only(self):
        self.assertEqual(mapping.code_technique(event('dilation', technique='balloon', technique_state='verified')),
                         catalogue.BALLOON)
        self.assertEqual(mapping.code_technique(event('dilation', technique='wire_bougie', technique_state='verified')),
                         catalogue.WIRE_BOUGIE)
        self.assertEqual(mapping.code_technique(event('dilation', technique='bougie', technique_state='verified')),
                         'bougie')
        self.assertEqual(mapping.code_technique(event('dilation', technique='balloon', technique_state='unverified')),
                         '')
        self.assertEqual(mapping.code_technique(event('snare', technique='cold_snare', technique_state='verified')), '')
        self.assertEqual(set(mapping.TECHNIQUE_CLASS.values()) - {'bougie'},
                         {profile.technique for profile in catalogue.CODES.values() if profile.technique})

    def test_technique_dependence(self):
        self.assertTrue(mapping.technique_dependent('gi.egd', 'dilation'))
        self.assertTrue(mapping.technique_dependent('', 'dilation'))
        self.assertFalse(mapping.technique_dependent('gi.colonoscopy', 'snare'))


class CodeLinks(SimpleTestCase):
    def test_route_a_for_every_profiled_code(self):
        for code, profile in catalogue.CODES.items():
            link = mapping.code_link(code)
            with self.subTest(code=code):
                self.assertEqual((link.route, link.family, link.reason), ('catalogue', profile.family, ''))
                self.assertEqual(link.technique, profile.technique)
                self.assertEqual(link.includes, profile.includes)
                self.assertFalse(set(link.acts) & mapping.EXAMINATION_KINDS)

    def test_c1_the_examination_is_the_session_of_an_eus_code(self):
        link = mapping.code_link('43242')
        self.assertEqual((link.kinds, link.session, link.acts), (('eus_exam', 'fna'), 'eus_exam', ('fna',)))
        link = mapping.code_link('43259')
        self.assertEqual((link.kinds, link.session, link.acts), (('eus_exam',), 'eus_exam', ()))

    def test_a_base_code_and_an_office_visit(self):
        link = mapping.code_link('45378')
        self.assertEqual((link.kinds, link.session, link.acts, link.base), (('examination',), 'examination', (), True))
        link = mapping.code_link('99213')
        self.assertEqual((link.kinds, link.session, link.acts, link.base), (('em_visit',), '', ('em_visit',), True))
        self.assertEqual(mapping.code_link('99417').kinds, ('em_prolonged',))

    def test_route_b_an_unreconciled_act(self):
        link = mapping.code_link('46221')
        self.assertEqual((link.route, link.kinds, link.regions), ('unreconciled', ('band_ligation',), ('rectum', 'anus')))
        self.assertEqual(link.family, 'gi.other')

    def test_c6_route_d_and_no_route_c(self):
        self.assertEqual(mapping.ROUTES, ('catalogue', 'unreconciled', 'none'))
        for code in ('45305', '46600', '91200', '99999', '12345', 'abcde'):  # gi.other, gi.unsupported, not a code
            link = mapping.code_link(code)
            with self.subTest(code=code):
                self.assertEqual((link.route, link.reason, link.kinds, link.linked), ('none', 'unprofiled', (), False))
        self.assertEqual(mapping.code_link('45305').family, profiles.family_for_code('45305'))

    def test_route_d_for_a_profile_of_another_family(self):
        with mock.patch.dict(catalogue.CODES, {'45380': catalogue._c('gi.egd', ('biopsy',))}):
            link = mapping.code_link('45380')
        self.assertEqual((link.route, link.reason), ('none', 'family_mismatch'))

    def test_the_support_the_engine_reads(self):
        self.assertEqual((mapping.code_link('99152').supported, mapping.code_link('99152').support),
                         (False, 'recognised'))
        self.assertEqual((mapping.code_link('45385').supported, mapping.code_link('45385').support),
                         (True, 'supported'))

    def test_candidates(self):
        colonoscopy_snare = event('snare')
        removal = event('removal')
        self.assertTrue(mapping.candidate(mapping.code_link('45385'), colonoscopy_snare))
        self.assertTrue(mapping.candidate(mapping.code_link('45385'), removal))  # an umbrella covering the kind
        self.assertFalse(mapping.candidate(mapping.code_link('43251'), colonoscopy_snare))  # another family
        self.assertTrue(mapping.candidate(mapping.code_link('45381'), event('tattoo')))
        self.assertTrue(mapping.candidate(mapping.code_link('45378'), event('examination')))
        banding = event('band_ligation', landmark='rectum', landmark_state='verified')
        self.assertTrue(mapping.candidate(mapping.code_link('46221'), banding))
        self.assertFalse(mapping.candidate(mapping.code_link('46221'),
                                           event('band_ligation', landmark='rectum', landmark_state='unverified')))
        self.assertFalse(mapping.candidate(mapping.code_link('46221'),
                                           event('band_ligation', family='gi.egd', landmark='distal_esophagus',
                                                 landmark_state='verified')))
        self.assertFalse(mapping.candidate(mapping.code_link('45305'), event('examination', family='gi.other')))

    def test_included(self):
        egd = event('examination', family='gi.egd')
        self.assertTrue(mapping.included('43242', egd))
        self.assertFalse(mapping.included('45342', egd))
        self.assertFalse(mapping.included('43242', event('biopsy', family='gi.egd')))


class MapEvents(SimpleTestCase):
    def test_every_event_gets_its_mapping_fields_through_normalize(self):
        lines = {'P1': 'The colonoscope was advanced to the cecum.',
                 'P2': 'A 6 mm polyp in the rectum was removed with a cold snare.',
                 'P3': 'A clip was placed to treat bleeding at the site.',
                 'P4': 'The stricture was dilated with a balloon.', 'P5': 'Something else was noted.'}
        inventory = normalized(lines, events=[
            act('E0', 'P1', 'examination', 'colonoscope', status_words='was advanced to the cecum'),
            snare(passage='P2', target=tg('', 'rectum', 'rectum', ['P2'])),
            act('E2', 'P3', 'clip', 'clip', status_words='was placed', purpose=a('hemostasis', 'to treat bleeding',
                                                                                 ['P3'])),
            act('E3', 'P4', 'dilation', 'dilated', status_words='was dilated',
                technique=a('balloon', 'balloon', ['P4'])),
            act('E4', 'P5', 'other', 'Something else', status_words='was noted')])
        fields = {item['id']: (item['catalogue_kind'], item['code_technique'], item['key'])
                  for item in inventory.events['events']}
        self.assertEqual(fields['E0'], ('examination', '', {
            'family': 'gi.colonoscopy', 'catalogue_kind': 'examination', 'service': 'colonoscopy', 'technique': '',
            'region': '', 'role': 'session', 'members': []}))
        self.assertEqual(fields['E1'][0], 'snare')
        self.assertEqual(fields['E1'][2]['region'], 'rectum')
        self.assertEqual(fields['E2'][0], 'bleeding_control')
        self.assertEqual(fields['E3'][:2], ('dilation', 'balloon'))
        self.assertEqual(fields['E4'][0], '')
        self.assertEqual(fields['E4'][2]['role'], 'listed')


if __name__ == '__main__':  # pragma: no cover
    sys.exit('Run with manage.py test.')
