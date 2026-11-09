"""The seven trial cases, the owner's classes and the slips (Gemini migration slice S08; design/FINAL.md 7.12 and 5.6),
as SYNTHETIC inventories asserted as STRUCTURE: which event supports which code, which relation decides and why, what is
held, excluded or left for completeness - never a list of expected codes for a real document. Each case is a synthetic
document of the case's shape, written here (no sealed set, no trial document, no recorded response is read). The four
slips run through the engine from slice S03's synthetic slip fixtures (tests/fixtures/interpretation/synthetic), each
beside its correct twin: contained means the slip changes no decision a twin would not make.

| case | decided by | expected structure |
|---|---|---|
| D1 (Note #8) | time DIFFERENT (a verified 2024 literal): INDEPENDENT | the dilation event supports; no relation holds |
| D2 | technique DIFFERENT; kind DIFFERENT; target DIFFERENT by distinctness | independent x3 |
| D3 | part_of gives lift_injection; clip NOT_REPORTED; the tattoo denial on another target | EMR supports; the |
|  |  | cut-edge coagulation stays a reportable event no code covers |
| D4 | sites disjoint, so no bundling identity | biopsy supports |
| D5 | purpose is not time; target DIFFERENT | tattoo supports |
| D6 / v6 | reach guard plus permission | extent verified from the scope's own reach |
| v1 | distinct by literal; single-target denial on L2 | snare on L1 and biopsy on L2 support; modifier review offered |
| v2 | technique DIFFERENT | snare supports |
| v3 | time DIFFERENT | dilation supports |
| v4 | CONTRADICTION (an extension statement at the current encounter) | held with the conflict question |
| v5 | broad current denial | a removal code citing the scar is EXCLUDED, reinstatable; the biopsy of the scar supports |
| E5, E13, E15, the v5 truncations | table 5.6 | contained |
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events, relations
from tests.test_interpretation_events import (COLONOSCOPE, asked, check, exam, inventory, proposal, reached, run)
from tests.test_interpretation_identity import a, act, les, sc, snare, tg
from tests.test_interpretation_slips import fixture, inventory_of


def relation_types(inv, event: str) -> list:
    return sorted((item['type'], item['reason']) for item in inv.events['relations'] if item['event'] == event)


def acts_of(p) -> list:
    return [item['id'] for item in p.support['acts']]


def colonoscopy_case(lines: dict, *more, lesions=(), **options):
    base = {'P1': COLONOSCOPE, **lines}
    return inventory(base, events=[exam(), *more], lesions=list(lesions), reach=[reached()], **options)


DILATED = 'The anastomotic stricture was dilated today to 15 mm with a through-the-scope balloon.'


def dilation(eid='E2', passage='P2'):
    return act(eid, passage, 'dilation', 'dilated', status_words='was dilated',
               technique=a('balloon', 'through-the-scope balloon', [passage]),
               target=tg('', 'anastomosis', 'anastomotic stricture', [passage]))


class TrialCases(SimpleTestCase):
    def test_d1_a_historical_denial_beside_todays_dilation(self):
        lines = {'P2': DILATED, 'P3': 'No dilation was carried out in 2024.'}
        historical = act('E3', 'P3', 'dilation', 'dilation', status='not_performed',
                         status_words='No dilation was carried out', time=a('earlier_encounter', 'in 2024', ['P3']),
                         scope=sc('all_of_kind', 'No', ['P3']))
        inv, text = colonoscopy_case(lines, dilation(), historical)
        self.assertEqual(relation_types(inv, 'E2'), [('independent', 'another_time')])
        p = proposal(run(inv, text, [('45386', DILATED)]), '45386')
        self.assertEqual((p.status, acts_of(p)), ('ready', ['E2']))

    def test_d2_three_denials_each_independent(self):
        lines = {'P2': 'A 7 mm polyp in the ascending colon was removed with a cold snare.',
                 'P3': 'No hot snare was used on this polyp.', 'P4': 'It was not removed by EMR.',
                 'P5': 'A 12 mm lesion at the splenic flexure was seen; it was not removed.'}
        l1 = les('L1', '7 mm polyp', 'P2', landmark='ascending_colon', site_words='ascending colon', size_words='7 mm')
        l2 = les('L2', '12 mm lesion', 'P5', landmark='splenic_flexure', site_words='splenic flexure',
                 size_words='12 mm')
        removal = snare('E2', 'P2', target=tg('L1', 'ascending_colon', '7 mm polyp in the ascending colon', ['P2']))
        hot = act('E3', 'P3', 'snare', 'hot snare', status='not_performed', status_words='No hot snare was used',
                  technique=a('hot_snare', 'hot snare', ['P3']), scope=sc('single_target', 'this polyp', ['P3']),
                  target=tg('L1', 'ascending_colon', 'this polyp', ['P3']))
        emr = act('E4', 'P4', 'emr', 'EMR', status='not_performed', status_words='was not removed by EMR',
                  scope=sc('single_target', 'It', ['P4']), target=tg('L1', 'ascending_colon', 'It', ['P4']))
        other = act('E5', 'P5', 'removal', 'removed', status='not_performed', status_words='it was not removed',
                    scope=sc('single_target', 'it', ['P5']),
                    target=tg('L2', 'splenic_flexure', '12 mm lesion at the splenic flexure', ['P5']))
        inv, text = colonoscopy_case(lines, removal, hot, emr, other, lesions=(l1, l2))
        self.assertEqual(relation_types(inv, 'E2'), [('independent', 'another_lesion'),
                                                     ('independent', 'another_technique')])  # the EMR denial: no pair
        self.assertEqual(proposal(run(inv, text, [('45385', lines['P2'])]), '45385').status, 'ready')

    def test_d3_the_emr_with_its_lift_its_clips_and_an_uncoded_coagulation(self):
        lines = {'P2': 'A 25 mm flat lesion in the cecum was lifted with a submucosal injection and removed by EMR.',
                 'P3': 'Three clips were placed to close the defect.',
                 'P4': 'The cut edge was coagulated with argon plasma.',
                 'P5': 'No tattoo was placed for the rectal polyp.'}
        l1 = les('L1', '25 mm flat lesion', 'P2', landmark='cecum', site_words='cecum', size_words='25 mm')
        l2 = les('L2', 'rectal polyp', 'P5', landmark='rectum', site_words='rectal')
        emr = act('E2', 'P2', 'emr', 'EMR', status_words='removed by EMR',
                  target=tg('L1', 'cecum', '25 mm flat lesion in the cecum', ['P2']))
        lift = act('E3', 'P2', 'injection', 'submucosal injection', status_words='lifted with a submucosal injection',
                   part_of='E2', target=tg('L1', 'cecum', '25 mm flat lesion in the cecum', ['P2']))
        clips = act('E4', 'P3', 'clip', 'clips', status_words='were placed', technique=a('clip', 'clips', ['P3']))
        coagulation = act('E5', 'P4', 'ablation', 'coagulated', status_words='was coagulated',
                          technique=a('argon_plasma', 'argon plasma', ['P4']))
        tattoo = act('E6', 'P5', 'tattoo', 'tattoo', status='not_performed', status_words='No tattoo was placed',
                     scope=sc('single_target', 'the rectal polyp', ['P5']),
                     target=tg('L2', 'rectum', 'the rectal polyp', ['P5']))
        inv, text = colonoscopy_case(lines, emr, lift, clips, coagulation, tattoo, lesions=(l1, l2))
        result = run(inv, text, [('45390', lines['P2'])])
        p = proposal(result, '45390')
        self.assertEqual((p.status, acts_of(p)), ('ready', ['E2']))
        self.assertEqual(sorted(item['event'] for item in result.completeness['bundled']), ['E3', 'E4'])
        self.assertEqual([(item['act'], item['reason']) for item in result.completeness['unresolved_items']],
                         [('ablation', 'not_covered')])
        self.assertEqual(result.completeness['state'], 'incomplete')
        self.assertEqual(relation_types(inv, 'E3'), [('independent', 'another_lesion'), ('step', 'lift_injection')])

    def test_d4_four_biopsies_at_four_disjoint_sites(self):
        lines = {'P2': 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.',
                 'P3': 'Cold forceps biopsies were taken from the cecum, the transverse colon and the rectum.'}
        l1 = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                 size_words='6 mm')
        removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon',
                                              ['P2']))
        biopsies = [act(f'E{3 + index}', 'P3', 'biopsy', 'biopsies', status_words='were taken',
                        technique=a('cold_forceps', 'Cold forceps', ['P3']), target=tg('', site, words, ['P3']))
                    for index, (site, words) in enumerate((('cecum', 'cecum'), ('transverse_colon', 'transverse colon'),
                                                           ('rectum', 'rectum')))]
        inv, text = colonoscopy_case(lines, removal, *biopsies, lesions=(l1,))
        self.assertFalse([item for item in inv.events['relations'] if item['type'] == relations.BUNDLING])
        result = run(inv, text, [('45380', lines['P3']), ('45385', lines['P2'])])
        p = proposal(result, '45380')
        self.assertEqual((p.status, acts_of(p)), ('ready', ['E3', 'E4', 'E5']))

    def test_d5_a_tattoo_for_future_localization(self):
        lines = {'P2': 'A tattoo was placed distal to the lesion in the descending colon for future localization.',
                 'P3': 'No tattoo was placed in the bed of the ascending colon lesion.'}
        tattoo = act('E2', 'P2', 'tattoo', 'tattoo', status_words='was placed',
                     purpose=a('marking', 'for future localization', ['P2']),
                     target=tg('', 'descending_colon', 'descending colon', ['P2']))
        denial = act('E3', 'P3', 'tattoo', 'tattoo', status='not_performed', status_words='No tattoo was placed',
                     scope=sc('single_target', 'the bed', ['P3']),
                     target=tg('', 'ascending_colon', 'ascending colon', ['P3']))
        inv, text = colonoscopy_case(lines, tattoo, denial)
        self.assertEqual(events.Reading.of(inv).events['E2']['time']['value'], 'current_encounter')  # purpose is not time
        self.assertEqual(relation_types(inv, 'E2'), [('independent', 'another_site')])
        self.assertEqual(proposal(run(inv, text, [('45381', lines['P2'])]), '45381').status, 'ready')

    def test_d6_the_extent_from_the_scopes_own_reach_never_the_guidewires(self):
        lines = {'P1': 'The colonoscope was advanced to the neo-terminal ileum.',
                 'P2': 'A guidewire was then passed into the terminal ileum.'}
        reaches = [{'event': 'E1', 'landmark': 'terminal_ileum', 'words': 'A guidewire was then passed into the terminal '
                                                                          'ileum', 'passages': ['P2'],
                    'completion': a('not_stated')},
                   {'event': 'E1', 'landmark': 'neo_terminal_ileum', 'words': 'neo-terminal ileum', 'passages': ['P1'],
                    'completion': a('not_stated')}]
        inv, text = inventory(lines, events=[exam()], reach=list(reversed(reaches)))
        p = proposal(run(inv, text, [('45378', lines['P1'])]), '45378')
        self.assertEqual(p.status, 'ready')
        self.assertIn('extent reached = neo terminal ileum', check(p, 'facts.required').detail)
        # the guidewire's reach given first: guarded (device_reach), so the extent is asked - never the guidewire's ileum
        inv, text = inventory(lines, events=[exam()], reach=reaches)
        p = proposal(run(inv, text, [('45378', lines['P1'])]), '45378')
        self.assertEqual(asked(p), ['extent'])
        self.assertNotIn('terminal ileum', check(p, 'facts.required').detail)


class OwnerClasses(SimpleTestCase):
    def test_v1_two_lesions_at_one_site(self):
        lines = {'P2': 'In the sigmoid colon a 6 mm polyp at 25 cm was removed with a cold snare.',
                 'P3': 'In the sigmoid colon a 3 mm polyp at 30 cm was biopsied with cold forceps; it was not removed.'}
        l1 = les('L1', '6 mm polyp at 25 cm', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                 size_words='6 mm')
        l2 = les('L2', '3 mm polyp at 30 cm', 'P3', landmark='sigmoid_colon', site_words='sigmoid colon',
                 size_words='3 mm')
        removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm polyp at 25 cm', ['P2']))
        biopsy = act('E3', 'P3', 'biopsy', 'biopsied', status_words='was biopsied',
                     technique=a('cold_forceps', 'cold forceps', ['P3']),
                     target=tg('L2', 'sigmoid_colon', '3 mm polyp at 30 cm', ['P3']))
        denial = act('E4', 'P3', 'removal', 'removed', status='not_performed', status_words='it was not removed',
                     scope=sc('single_target', 'it', ['P3']), target=tg('L2', 'sigmoid_colon', 'it', ['P3']))
        inv, text = colonoscopy_case(lines, removal, biopsy, denial, lesions=(l1, l2))
        self.assertEqual(inv.events['lesions'][0]['distinct_from'], ['L2'])  # by the distance literals
        self.assertEqual(relation_types(inv, 'E2'), [('independent', 'another_lesion')])
        result = run(inv, text, [('45385', lines['P2']), ('45380', lines['P3'])])
        snared, biopsied = proposal(result, '45385'), proposal(result, '45380')
        self.assertEqual((snared.status, acts_of(snared), biopsied.status, acts_of(biopsied)),
                         ('ready', ['E2'], 'ready', ['E3']))
        self.assertTrue(any(text_.startswith('Separate lesions are documented')
                            for text_ in snared.modifier_considerations))

    def test_v2_technique_denials(self):
        lines = {'P2': 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.',
                 'P3': 'No hot snare was used.'}
        l1 = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                 size_words='6 mm')
        removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon',
                                              ['P2']))
        hot = act('E3', 'P3', 'snare', 'hot snare', status='not_performed', status_words='No hot snare was used',
                  technique=a('hot_snare', 'hot snare', ['P3']), scope=sc('all_of_kind', 'No', ['P3']))
        inv, text = colonoscopy_case(lines, removal, hot, lesions=(l1,))
        self.assertEqual(relation_types(inv, 'E2'), [('independent', 'another_technique')])
        self.assertEqual(proposal(run(inv, text, [('45385', lines['P2'])]), '45385').status, 'ready')

    def test_v3_not_dilated_in_2024_dilated_today(self):
        lines = {'P2': 'In 2024 the stricture was not dilated.', 'P3': DILATED}
        historical = act('E3', 'P2', 'dilation', 'dilated', status='not_performed', status_words='was not dilated',
                         time=a('earlier_encounter', 'In 2024', ['P2']), scope=sc('single_target', 'the stricture', ['P2']),
                         target=tg('', 'anastomosis', 'stricture', ['P2']))
        inv, text = colonoscopy_case(lines, dilation('E2', 'P3'), historical)
        self.assertEqual(relation_types(inv, 'E2'), [('independent', 'another_time')])
        self.assertEqual(proposal(run(inv, text, [('45386', DILATED)]), '45386').status, 'ready')

    def test_v4_an_extension_to_this_encounter_is_a_genuine_contradiction(self):
        lines = {'P2': DILATED, 'P3': 'No dilation was carried out in 2024.', 'P4': 'This time as well.'}
        historical = act('E3', 'P3', 'dilation', 'dilation', status='not_performed',
                         status_words='No dilation was carried out', time=a('earlier_encounter', 'in 2024', ['P3']),
                         scope=sc('all_of_kind', 'No', ['P3']))
        extension = act('E4', 'P3', 'dilation', 'dilation', status='not_performed',
                        status_words='No dilation was carried out', scope=sc('all_of_kind', 'No', ['P3']),
                        time=a('current_encounter', 'This time as well', ['P4']))
        extension['kind']['passages'] = ['P3', 'P4']
        extension['status']['passages'] = ['P3', 'P4']
        inv, text = colonoscopy_case(lines, dilation(), historical, extension)
        self.assertIn(('contradiction', 'same_act'), relation_types(inv, 'E2'))
        p = proposal(run(inv, text, [('45386', DILATED)]), '45386')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['conflict:dilation']))
        self.assertIn('No dilation was carried out in 2024.', [span['text'] for span in p.support['source']])


class SlipsContained(SimpleTestCase):
    """FINAL 5.6, through the engine: each slip fixture beside its twin."""

    def assessed(self, name: str, codes):
        record = fixture(name)
        inv = inventory_of(name)
        return inv, run(inv, record['text'], codes)

    def test_e5_a_historical_examinations_reach_never_makes_the_extent(self):
        line = 'Procedure: The colonoscope was advanced to the terminal ileum, which appeared normal.'
        _, alone = self.assessed('s1-e5-earlier-reach-alone', [('45378', line)])
        self.assertEqual(asked(proposal(alone, '45378')), ['extent'])  # the 2024 reach neither satisfies nor blocks
        for name in ('s1-e5-earlier-reach-beside-current', 's1-e5-mislabelled-current-with-its-time-words',
                     's1-twin-current-reach'):
            with self.subTest(fixture=name):
                _, result = self.assessed(name, [('45378', line)])
                p = proposal(result, '45378')
                self.assertEqual((p.status, acts_of(p)), ('ready', ['E2']))
                self.assertIn('extent reached = terminal ileum', check(p, 'facts.required').detail)

    def test_e13_the_digital_examination_is_no_session(self):
        line = 'The colonoscope was then advanced to the cecum.'
        for name in ('s3-e13-reach-on-a-digital-examination', 's3-twin-colonoscopy-reach'):
            with self.subTest(fixture=name):
                inv, result = self.assessed(name, [('45378', line)])
                p = proposal(result, '45378')
                self.assertEqual((p.status, acts_of(p)), ('ready', ['E2']))
                self.assertEqual(result.completeness['event_coding']['sessions']['gi.colonoscopy']['event'], 'E2')

    def test_e15_the_biopsy_is_unaffected_unless_its_link_is_unresolved(self):
        biopsy = 'Cold forceps biopsies were taken from an inflamed portion of the anastomotic rim.'
        removal = 'A 5 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        for name in ('s2-twin-correct-targets', 's2a-merged-target-words'):
            with self.subTest(fixture=name):
                _, result = self.assessed(name, [('45380', biopsy), ('45385', removal)])
                self.assertEqual([proposal(result, code).status for code in ('45380', '45385')], ['ready', 'ready'])
                self.assertFalse(any(text_.startswith('Separate lesions') for text_ in
                                     proposal(result, '45380').modifier_considerations))
        _, held = self.assessed('s2c-erosion-words-from-their-sentence', [('45380', biopsy), ('45385', removal)])
        self.assertEqual((asked(proposal(held, '45380')), proposal(held, '45385').status), (['act_target'], 'ready'))
        _, no_tie = self.assessed('s2b-link-to-the-erosions', [('45380', biopsy), ('45385', removal)])
        self.assertNotEqual(proposal(no_tie, '45380').status, 'excluded')

    def test_v5_the_scar_the_outside_hospital_and_the_broad_denial_cut_or_whole(self):
        scar = 'Cold forceps biopsies were taken from the transverse colon polypectomy scar'
        decisions = []
        for name in ('s4-twin-whole-strings', 's4-v5-cut-strings'):
            _, result = self.assessed(name, [('45380', scar), ('45385', scar)])
            removal, biopsy = proposal(result, '45385'), proposal(result, '45380')
            self.assertEqual((removal.bucket, removal.reinstatable, removal.support['exclusion']['cover'],
                              removal.support['exclusion']['basis']), ('excluded', True, 'broad', 'literal'))
            self.assertEqual((biopsy.status, acts_of(biopsy)), ('ready', ['E3']))
            decisions.append([(p.key, p.code, p.bucket, p.status, [c.id for c in p.checks],
                               [spec.fact for spec in p.clarifications]) for p in result.proposals])
        self.assertEqual(decisions[0], decisions[1])  # the cut strings change no decision (D7: another interpretation's
        # anchors are its own words, so a decision on one never carries to the other through the fingerprint)
