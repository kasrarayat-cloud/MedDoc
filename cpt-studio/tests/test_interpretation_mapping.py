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

    def test_d27_the_defining_kinds_computed_from_the_catalogue(self):
        """DECISIONS D27: D(C) is C's covers less every kind another code of its family covers alone, kept where it is
        non-empty and smaller than the covers - computed at import, pinned here. Every other code is unaffected."""
        fna = ('fna',)
        self.assertEqual(dict(mapping.DEFINING), {
            '43265': ('lithotripsy',), '44365': ('hot_biopsy',), '49440': ('peg',),
            '43232': fna, '43238': fna, '43242': fna, '44407': fna, '45342': fna, '45392': fna,
            '43240': ('drainage',), '43253': ('injection',)})
        for code in catalogue.CODES:
            with self.subTest(code=code):
                link = mapping.code_link(code)
                self.assertEqual(link.defining, mapping.DEFINING.get(code, ()))
                if link.defining and set(link.kinds) & mapping.EXAMINATION_KINDS:
                    self.assertEqual(link.acts, link.defining)  # C-1's groups of an EUS code are already its D(C)
        self.assertTrue(mapping.candidate(mapping.code_link('43265'), event('lithotripsy', family='gi.ercp')))
        self.assertFalse(mapping.candidate(mapping.code_link('43265'), event('stone_extraction', family='gi.ercp')))
        self.assertTrue(mapping.candidate(mapping.code_link('43264'), event('stone_extraction', family='gi.ercp')))
        # the rule over a catalogue of other shapes: every kind of its own, or every kind another code's alone
        mine = catalogue._c('gi.ercp', ('lithotripsy', 'cholangioscopy'))
        with mock.patch.dict(catalogue.CODES, {'99001': mine, '99002': catalogue._c('gi.ercp', ('lithotripsy',)),
                                               '99003': catalogue._c('gi.ercp', ('cholangioscopy', 'stent_removal'))}):
            self.assertEqual(mapping._defining('99001', mine), ())  # cholangioscopy (43273) and lithotripsy (99002)
            self.assertEqual(mapping._defining('99003', catalogue.CODES['99003']), ('stent_removal',))
        self.assertEqual(mapping._defining('43264', catalogue.CODES['43264']), ())

    def test_d28_the_examination_classes_and_the_reach_a_full_one_needs(self):
        self.assertEqual({code: mapping.examination_class(code) for code in catalogue.CODES
                          if mapping.examination_class(code)},
                         {'43231': 'limited', '43232': 'limited', '43237': 'limited', '43238': 'limited',
                          '43242': 'full', '43259': 'full',
                          # D43: the lower-tract EUS codes, which the catalogue gives no class
                          '45341': 'sigmoidoscopic', '45342': 'sigmoidoscopic', '45391': 'colonoscopic',
                          '45392': 'colonoscopic', '44406': 'stoma', '44407': 'stoma'})
        self.assertEqual(mapping.FULL_REACH, {'duodenum', 'duodenal_bulb', 'second_portion_duodenum', 'ampulla',
                                              'jejunum'})
        # short of the duodenum: the tract before it - D29's esophageal class and the stomach's half of its gastric one
        self.assertEqual(mapping.SHORT_OF_DUODENUM, mapping.SITE_CLASSES[mapping.ESOPHAGEAL]
                         | (mapping.SITE_CLASSES[mapping.GASTRIC_DUODENAL] - {'duodenum', 'duodenal_bulb',
                                                                              'second_portion_duodenum'}))
        self.assertEqual(dict(mapping.CLASS_REACH), {'full': mapping.FULL_REACH, 'limited': mapping.SHORT_OF_DUODENUM,
                                                     'sigmoidoscopic': mapping.SIGMOIDOSCOPIC_REACH,
                                                     'colonoscopic': mapping.COLONOSCOPIC_REACH,
                                                     'stoma': mapping.STOMA_REACH})
        self.assertFalse(mapping.FULL_REACH & mapping.SHORT_OF_DUODENUM)
        self.assertFalse(mapping.SIGMOIDOSCOPIC_REACH & mapping.COLONOSCOPIC_REACH)
        # D43: the splenic flexure is the boundary, so it fits neither lower class; no lower class holds an upper place
        self.assertNotIn('splenic_flexure', mapping.SIGMOIDOSCOPIC_REACH | mapping.COLONOSCOPIC_REACH)
        self.assertFalse((mapping.SIGMOIDOSCOPIC_REACH | mapping.COLONOSCOPIC_REACH | mapping.STOMA_REACH)
                         & (mapping.FULL_REACH | mapping.SHORT_OF_DUODENUM))
        for reach in mapping.CLASS_REACH.values():
            self.assertLessEqual(reach, set(schema.LANDMARKS))

    def test_d29_the_site_specific_dilation_codes(self):
        """DECISIONS D29: the table lives here (never in studio.gi), names only the catalogue's EGD-family dilation
        codes, and every other dilation code of the catalogue (the colon's, the enteroscopy's, the ERCP's) is not in
        it. The classes are D29's landmark lists, exactly."""
        self.assertEqual(dict(mapping.DILATION_SITES), {
            '43213': 'esophageal', '43214': 'esophageal', '43220': 'esophageal', '43226': 'esophageal',
            '43233': 'esophageal', '43248': 'esophageal', '43249': 'esophageal', '43245': 'gastric_duodenal'})
        for code in mapping.DILATION_SITES:
            self.assertEqual((catalogue.CODES[code].family, catalogue.CODES[code].covers), ('gi.egd', ('dilation',)))
        self.assertEqual({code for code, profile in catalogue.CODES.items() if 'dilation' in profile.covers}
                         - set(mapping.DILATION_SITES), {'44381', '45386', '44405', '45340', '43277'})
        self.assertEqual(mapping.SITE_CLASSES[mapping.ESOPHAGEAL],
                         {'esophagus', 'proximal_esophagus', 'mid_esophagus', 'distal_esophagus',
                          'gastroesophageal_junction'})
        self.assertEqual(mapping.SITE_CLASSES[mapping.GASTRIC_DUODENAL],
                         {'stomach', 'gastric_cardia', 'gastric_fundus', 'gastric_body', 'gastric_antrum', 'pylorus',
                          'duodenum', 'duodenal_bulb', 'second_portion_duodenum'})
        for landmarks in mapping.SITE_CLASSES.values():
            self.assertLessEqual(landmarks, set(schema.LANDMARKS))


def anatomy(words: str, *, landmark: str = 'anastomosis', state: str = 'verified', structure: str = 'altered',
            opened: bool = False) -> dict:
    """An encounter.anatomy entry in its stored shape, as far as anastomosis_place reads it."""
    return {'value': landmark, 'anatomy': structure, 'state': state, 'open': opened,
            'words': {'start': 0, 'end': len(words), 'text': words} if words else None}


def targeted(landmark: str, words: str, state: str = 'verified') -> dict:
    """An event whose target is ``landmark`` with its own ``words``."""
    item = event('dilation', landmark=landmark, landmark_state=state)
    item['target']['words'] = {'start': 0, 'end': len(words), 'text': words} if words else None
    return item


class AnastomosisPlace(SimpleTestCase):
    """DECISIONS D34: the place the encounter's one anastomosis takes, from its anatomy entry's own type words, and the
    landmark the comparisons and D29 read for a target at it."""
    ILEOCOLONIC = anatomy('stapled side-to-side ileocolonic anastomosis')

    def test_each_type_gives_its_place(self):
        cases = {'stapled side-to-side ileocolonic anastomosis': 'right_colon', 'ileocolic anastomosis': 'right_colon',
                 'colorectal anastomosis at 20 cm': 'rectum', 'coloanal anastomosis': 'rectum',
                 'ileorectal anastomosis': 'rectum', 'gastrojejunal anastomosis': 'stomach',
                 'esophagojejunal anastomosis': 'esophagus', 'esophagogastric anastomosis': 'esophagus'}
        for words, place in cases.items():
            with self.subTest(words):
                self.assertEqual(mapping.anastomosis_place({'anatomy': [anatomy(words)]}), place)
        others = [anatomy('native cecum', landmark='cecum', structure='absent'), anatomy('end ileostomy',
                                                                                       landmark='stoma')]
        self.assertEqual(mapping.anastomosis_place({'anatomy': others + [self.ILEOCOLONIC]}), 'right_colon')

    def test_what_establishes_no_place(self):
        cases = {
            'no anatomy': {'anatomy': []},
            'no anatomy list': {},
            'two anastomoses': {'anatomy': [self.ILEOCOLONIC, anatomy('colorectal anastomosis')]},
            'the same type twice': {'anatomy': [self.ILEOCOLONIC, anatomy('ileocolonic anastomosis')]},
            'an unverified second one': {'anatomy': [self.ILEOCOLONIC, anatomy('end colostomy', state='unverified')]},
            'unverified': {'anatomy': [anatomy('ileocolonic anastomosis', state='unverified')]},
            'opened': {'anatomy': [anatomy('ileocolonic anastomosis', opened=True)]},
            'absent': {'anatomy': [anatomy('ileocolonic anastomosis', structure='absent')]},
            'no words': {'anatomy': [anatomy('')]},
            'no type word': {'anatomy': [anatomy('the anastomotic stricture')]},
            'a type word not before the noun': {'anatomy': [anatomy('ileocolonic side-to-side anastomosis')]},
            'an unknown type': {'anatomy': [anatomy('colocolonic anastomosis')]},
            'a pouch': {'anatomy': [anatomy('ileal pouch-anal anastomosis')]},
            'two types': {'anatomy': [anatomy('ileocolonic and colorectal anastomoses')]},
            'another type elsewhere in the words': {'anatomy': [anatomy(
                'right hemicolectomy for colorectal cancer with an ileocolonic anastomosis')]},
            'several of one type': {'anatomy': [anatomy('two ileocolonic anastomoses')]},
        }
        for name, encounter in cases.items():
            with self.subTest(name):
                self.assertEqual(mapping.anastomosis_place(encounter), '')

    def test_the_landmark_the_comparisons_read(self):
        compared = mapping.compared_landmark
        self.assertEqual(compared(targeted('anastomosis', 'anastomotic narrowing'), 'right_colon'), 'right_colon')
        self.assertEqual(compared(targeted('anastomosis', 'the ileocolonic anastomosis'), 'right_colon'), 'right_colon')
        self.assertEqual(compared(targeted('anastomosis', 'anastomotic narrowing'), ''), 'anastomosis')
        self.assertEqual(compared(targeted('descending_colon', 'descending colon'), 'right_colon'), 'descending_colon')
        self.assertEqual(compared(targeted('anastomosis', 'anastomotic narrowing', 'unverified'), 'right_colon'), '')
        self.assertEqual(compared(targeted('not_stated', ''), 'right_colon'), '')
        # an act of a family that does not reach the place is not at that anastomosis: the ambiguity is kept
        upper = dict(targeted('anastomosis', 'anastomotic stricture'), family='gi.egd')
        self.assertEqual((compared(upper, 'right_colon'), compared(upper, 'stomach'), compared(upper, 'esophagus')),
                         ('anastomosis', 'stomach', 'esophagus'))
        for family in ('gi.other', ''):
            with self.subTest(family=family):
                self.assertEqual(compared(dict(targeted('anastomosis', 'anastomotic stricture'), family=family),
                                          'right_colon'), 'anastomosis')
        self.assertEqual({place: sorted(families) for place, families in mapping.ANASTOMOSIS_FAMILIES.items()}, {
            'esophagus': ['gi.egd', 'gi.enteroscopy', 'gi.ercp', 'gi.eus'],
            'stomach': ['gi.egd', 'gi.enteroscopy', 'gi.ercp', 'gi.eus'],
            'right_colon': ['gi.colonoscopy', 'gi.flex_sig'], 'rectum': ['gi.colonoscopy', 'gi.flex_sig']})
        # the target's own words name another type, or several anastomoses: the ambiguity is kept
        self.assertEqual(compared(targeted('anastomosis', 'colorectal anastomotic stricture'), 'right_colon'),
                         'anastomosis')
        self.assertEqual(compared(targeted('anastomosis', 'the anastomoses'), 'right_colon'), 'anastomosis')
        # never the target's value, its region or its label
        item = targeted('anastomosis', 'anastomotic narrowing')
        self.assertEqual((mapping.target_landmark(item), mapping.key(item)['region']), ('anastomosis', ''))


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
