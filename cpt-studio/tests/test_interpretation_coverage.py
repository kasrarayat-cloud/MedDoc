"""Bundling, coverage and completeness over the event inventory (Gemini migration slice S08; design/FINAL.md 7.7 and 7.8,
as design/ADJUDICATION.md C-2, C-4 and C-5 amend them), SYNTHETIC: one test per bundling row of 7.7 (lift_injection by
part_of and C-5's structural arm and its unresolved identity, resection_technique, biopsy_of_removed_lesion with C-2's
common passage and its group lesion in separate passages, clip, cannulation, disjoint places); the sessions, reportable
events, the unresolved items (no_proposal, not_covered, unsupported, in_doubt) with their second-review marks, the office
visit beside a same-day procedure, coverage by a held code's candidates, completeness's wording pinned equal to
reconcile.completeness, and the event_coding record. Nothing is sent."""
from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import coverage, events
from studio.validation import engine, reconcile
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, anatomy_entry, asked, check, colonoscopy, exam,
                                              inventory, proposal, reached, removed, run)
from tests.test_interpretation_identity import a, act, les, sc, snare, tg

EMR_LINE = ('A submucosal injection of saline with methylene blue was given in the cecum, and the 20 mm flat polyp '
            'was resected by EMR en bloc.')
CECAL = les('L1', '20 mm flat polyp', 'P2', landmark='cecum', site_words='cecum', size_words='20 mm')


def emr(**changes) -> dict:
    return act('E2', 'P2', 'emr', 'EMR', status_words='was resected by EMR',
               target=tg('L1', 'cecum', '20 mm flat polyp', ['P2']), **changes)


def injection(target, **changes) -> dict:
    return act('E3', 'P2', 'injection', 'submucosal injection', status_words='was given', target=target, **changes)


class Bundling(SimpleTestCase):
    def lifted(self, target):
        inv, text = colonoscopy(injection(target), polyp=emr(), lesions=(CECAL,), lines={'P2': EMR_LINE})
        return inv, text, run(inv, text, [('45390', EMR_LINE), ('45381', EMR_LINE)])

    def test_c5_an_injection_at_the_resections_place_is_its_lift(self):
        """The refuter's C-5 scenario: no part_of, no lift purpose, no lesion - an injection in the cecum beside the
        cecal EMR is part of it, and 45381 is never READY beside 45390."""
        inv, text, result = self.lifted(tg('', 'cecum', 'in the cecum', ['P2']))
        self.assertEqual(proposal(result, '45390').status, 'ready')
        p = proposal(result, '45381')
        self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), coverage.COMMON['lift_injection'])
        self.assertEqual([item['event'] for item in result.completeness['bundled']], ['E3'])

    def test_c5_an_injection_with_no_place_joins_the_bundling_identity(self):
        inv, text, result = self.lifted(tg())
        p = proposal(result, '45381')
        self.assertEqual((asked(p), p.support['reason']), (['act_target'], events.BUNDLING_IDENTITY))
        self.assertIn('made to lift the lesion that was resected', p.clarifications[0].question)
        self.assertNotIn('E3', [item['events'][0] for item in result.completeness['unresolved_items']])

    def test_an_injection_at_a_disjoint_place_is_its_own_act(self):
        line = ('A submucosal injection of saline was given in the rectum, and the 20 mm flat polyp in the cecum was '
                'resected by EMR en bloc.')
        inv, text = colonoscopy(injection(tg('', 'rectum', 'in the rectum', ['P2'])), polyp=emr(), lesions=(CECAL,),
                                lines={'P2': line})
        result = run(inv, text, [('45390', line), ('45381', line)])
        self.assertEqual(proposal(result, '45381').status, 'ready')

    def test_a_tattoo_is_never_a_lift_by_place_alone(self):
        tattoo = act('E3', 'P2', 'tattoo', 'methylene blue', status_words='was given',
                     target=tg('', 'cecum', 'in the cecum', ['P2']), purpose=a('marking'))
        inv, text = colonoscopy(tattoo, polyp=emr(), lesions=(CECAL,), lines={'P2': EMR_LINE})
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')

    def test_resection_technique_on_the_same_verified_lesion(self):
        line = 'The 20 mm flat polyp in the cecum was resected by EMR using a hot snare.'
        technique = act('E3', 'P2', 'snare', 'hot snare', status_words='using a hot snare',
                        technique=a('hot_snare', 'hot snare', ['P2']),
                        target=tg('L1', 'cecum', '20 mm flat polyp in the cecum', ['P2']))
        inv, text = colonoscopy(technique, polyp=emr(), lesions=(CECAL,), lines={'P2': line})
        result = run(inv, text, [('45390', line), ('45385', line)])
        self.assertEqual(proposal(result, '45390').status, 'ready')
        p = proposal(result, '45385')
        self.assertEqual(p.support['reason'], events.BUNDLED)
        self.assertIn('the technique of that resection', check(p, 'service.status').detail)

    def biopsied(self, multiplicity: str, biopsy_line: str, snare_line: str = ''):
        lesion = les('L1', 'three 3 to 5 mm sessile polyps', 'P2', landmark='rectum', site_words='rectum',
                     size_words='3 to 5 mm', multiplicity=multiplicity)
        target = tg('L1', 'rectum', 'three 3 to 5 mm sessile polyps', ['P2'])
        lines = {'P2': biopsy_line} if not snare_line else {'P2': biopsy_line, 'P3': snare_line}
        biopsy = act('E3', 'P2', 'biopsy', 'biopsied', status_words='were biopsied', target=target)
        removal = snare('E2', 'P3' if snare_line else 'P2',
                        target=tg('L1', 'rectum', 'the polyps' if snare_line else 'three 3 to 5 mm sessile polyps',
                                  ['P3' if snare_line else 'P2']),
                        status_words='removed with a cold snare')
        inv, text = colonoscopy(biopsy, polyp=removal, lesions=(lesion,), lines=lines)
        return inv, text, run(inv, text, [('45380', biopsy_line), ('45385', snare_line or biopsy_line)])

    def test_biopsy_of_a_single_removed_lesion(self):
        line = 'In the rectum three 3 to 5 mm sessile polyps were biopsied and then removed with a cold snare.'
        inv, text, result = self.biopsied('single', line)
        self.assertEqual(proposal(result, '45380').support['reason'], events.BUNDLED)

    def test_c2_a_group_lesion_with_a_passage_in_common_is_bundled_whatever_its_multiplicity(self):
        line = 'In the rectum three 3 to 5 mm sessile polyps were biopsied and then removed with a cold snare.'
        inv, text, result = self.biopsied('group', line)
        p = proposal(result, '45380')
        self.assertEqual(p.support['reason'], events.BUNDLED)
        self.assertNotEqual(p.status, 'ready')

    def test_c2_a_group_lesion_in_separate_passages_asks_the_identity(self):
        inv, text, result = self.biopsied('group', 'In the rectum three 3 to 5 mm sessile polyps were biopsied.',
                                          'The polyps were removed with a cold snare.')
        p = proposal(result, '45380')
        self.assertEqual((asked(p), p.status), (['act_target'], 'needs_clarification'))
        self.assertIn('taken from the lesion that was removed', p.clarifications[0].question)

    def test_a_biopsy_of_a_distinct_lesion_is_its_own_act(self):
        lines = {'P3': 'A 4 mm polyp in the rectum was biopsied with cold forceps.'}
        rectal = les('L2', '4 mm polyp', 'P3', landmark='rectum', site_words='rectum', size_words='4 mm')
        biopsy = act('E3', 'P3', 'biopsy', 'biopsied', status_words='was biopsied',
                     technique=a('cold_forceps', 'cold forceps', ['P3']),
                     target=tg('L2', 'rectum', '4 mm polyp in the rectum', ['P3']))
        inv, text = colonoscopy(biopsy, lesions=(L1, rectal), lines=lines)
        result = run(inv, text, [('45385', POLYP), ('45380', lines['P3'])])
        self.assertEqual(proposal(result, '45380').status, 'ready')
        self.assertEqual(proposal(result, '45385').status, 'ready')

    def test_a_prophylactic_clip_is_never_separately_reported_and_a_hemostatic_one_is_bleeding_control(self):
        lines = {'P3': 'Two clips were placed to close the defect.'}
        clip = act('E3', 'P3', 'clip', 'clips', status_words='were placed', technique=a('clip', 'clips', ['P3']))
        inv, text = colonoscopy(clip, lines=lines)
        result = run(inv, text, [('45385', POLYP)])
        self.assertIn('E3', [item['event'] for item in result.completeness['bundled']])
        self.assertEqual(result.completeness['unresolved_items'], [])
        lines = {'P3': 'Two clips were placed for hemostasis of the oozing.'}
        clip = act('E3', 'P3', 'clip', 'clips', status_words='were placed', technique=a('clip', 'clips', ['P3']),
                   purpose=a('hemostasis', 'for hemostasis', ['P3']))
        inv, text = colonoscopy(clip, lines=lines)
        items = run(inv, text, [('45385', POLYP)]).completeness['unresolved_items']
        self.assertEqual([(item['act'], item['reason']) for item in items], [('bleeding_control', 'not_covered')])

    def test_cannulation_is_part_of_the_ercp(self):
        lines = {'P1': 'The duodenoscope was advanced to the second portion of the duodenum.',
                 'P2': 'The common bile duct was cannulated.',
                 'P3': 'A biliary sphincterotomy was performed.'}
        inv, text = inventory(lines, events=[
            exam(words='duodenoscope', procedure=a('ercp')),
            act('E2', 'P2', 'cannulation', 'cannulated', status_words='was cannulated', procedure=a('ercp'),
                target=tg('', 'common_bile_duct', 'common bile duct', ['P2'])),
            act('E3', 'P3', 'sphincterotomy', 'sphincterotomy', status_words='was performed', procedure=a('ercp'))])
        result = run(inv, text, [('43262', lines['P3'])])
        self.assertIn('E2', [item['event'] for item in result.completeness['bundled']])
        p = proposal(result, '43262')
        self.assertEqual(p.status, 'ready')  # the cannulation fact is read from the cannulation event
        self.assertIn('common bile duct cannulated', check(p, 'facts.required').detail)


ADJUNCT_LINES = {'P2': 'The 20 mm flat polyp in the cecum was resected by EMR.',
                 'P3': 'The margins of the resection defect were treated with snare-tip soft coagulation.'}


def adjunct(**changes):
    """(inventory, text, lines) of a colonoscopy whose cecal EMR (E2) has an ablation (E3) verifiably part_of it - note8
    r1's snare-tip soft coagulation - unless ``changes`` say otherwise."""
    options = {'technique': a('electrocautery', 'snare-tip soft coagulation', ['P3']), 'part_of': 'E2', **changes}
    ablation = act('E3', 'P3', 'ablation', 'snare-tip soft coagulation', status_words='were treated', **options)
    inv, text = colonoscopy(ablation, polyp=emr(), lesions=(CECAL,), lines=ADJUNCT_LINES)
    return inv, text, ADJUNCT_LINES


def standalone_ablation(landmark: str, words: str):
    """(inventory, text, line) of a colonoscopy whose cecal EMR (E2) is beside an argon plasma coagulation (E3) of two
    angioectasias at ``landmark``, named by ``words``: no lesion, no part_of."""
    line = f'Two angioectasias in the {words} were treated with argon plasma coagulation.'
    inv, text = colonoscopy(act('E3', 'P3', 'ablation', 'argon plasma coagulation', status_words='were treated',
                                technique=a('argon_plasma', 'argon plasma coagulation', ['P3']),
                                target=tg('', landmark, words, ['P3'])),
                            polyp=emr(), lesions=(CECAL,), lines={'P2': ADJUNCT_LINES['P2'], 'P3': line})
    return inv, text, line


class ProceduralAdjuncts(SimpleTestCase):
    """DECISIONS D30 (note8 r1: 45388 READY on the snare-tip soft coagulation Gemini verified as part_of the EMR): an
    ablation or a bleeding control verifiably part_of a current performed removal, or on that removal's verified
    lesion, is bundled into it, so a code supported only by such acts takes R5's "part of another documented act" hold.
    A standalone ablation, an act part_of nothing, and an act beside a removal of another encounter are unaffected."""

    def test_an_ablation_part_of_the_resection_is_bundled_and_its_code_held(self):
        inv, text, lines = adjunct()
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), coverage.PROCEDURAL_ADJUNCT)
        result = run(inv, text, [('45390', lines['P2']), ('45388', lines['P3'])])
        self.assertEqual(proposal(result, '45390').status, 'ready')
        p = proposal(result, '45388')
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['performed_status'], events.BUNDLED))
        self.assertIn('which is part of another documented act: ' + coverage.PROCEDURAL_ADJUNCT,
                      check(p, 'service.status').detail)
        self.assertIn('Was a separate ablation performed on the date of service?', p.clarifications[0].question)
        self.assertEqual([(item['event'], item['why']) for item in result.completeness['bundled']],
                         [('E3', coverage.PROCEDURAL_ADJUNCT)])

    def test_a_bleeding_control_on_the_removed_lesion_is_bundled_by_the_lesion_alone(self):
        line = 'Oozing from the polypectomy site of the 6 mm sessile polyp was controlled with a clip for hemostasis.'
        clip = act('E3', 'P3', 'clip', 'clip', status_words='was controlled', technique=a('clip', 'clip', ['P3']),
                   purpose=a('hemostasis', 'for hemostasis', ['P3']), target=tg('L1', 'sigmoid_colon',
                                                                               '6 mm sessile polyp', ['P3']))
        inv, text = colonoscopy(clip, lines={'P3': line})
        reading = events.Reading.of(inv)
        self.assertEqual((reading.events['E3']['catalogue_kind'], reading.events['E3']['part_of']['value']),
                         ('bleeding_control', ''))
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), coverage.PROCEDURAL_ADJUNCT)
        result = run(inv, text, [('45385', POLYP), ('45382', line)])
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assertEqual(proposal(result, '45382').support['reason'], events.BUNDLED)

    def test_a_standalone_ablation_stays_its_codes(self):
        # DECISIONS D58: in the transverse colon, three steps from the cecum on the tract - the same ablation in the
        # ascending colon, one step from the resection, is asked (test_d58_a_standalone_ablation_one_step_from_...)
        inv, text, line = standalone_ablation('transverse_colon', 'transverse colon')
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
        result = run(inv, text, [('45390', ADJUNCT_LINES['P2']), ('45388', line)])
        self.assertEqual([proposal(result, code).status for code in ('45390', '45388')], ['ready', 'ready'])

    def test_an_adjunct_of_a_removal_of_another_encounter_is_its_own_act(self):
        lines = {'P2': 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare in 2024.',
                 'P3': 'The scar was treated with argon plasma coagulation.'}
        earlier = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P2']),
                        time=a('earlier_encounter', 'in 2024', ['P2']))
        ablation = act('E3', 'P3', 'ablation', 'argon plasma coagulation', status_words='was treated', part_of='E2',
                       technique=a('argon_plasma', 'argon plasma coagulation', ['P3']))
        inv, text = colonoscopy(ablation, polyp=earlier, lines=lines)
        reading = events.Reading.of(inv)
        self.assertEqual((reading.events['E3']['part_of']['value'], coverage.bundled_reason(reading,
                                                                                            reading.events['E3'])),
                         ('E2', ''))
        self.assertEqual(proposal(run(inv, text, [('45388', lines['P3'])]), '45388').status, 'ready')

    def test_a_biopsy_part_of_nothing_is_unaffected(self):
        lines = {'P3': 'Cold forceps biopsies were taken from the transverse colon.'}
        biopsy = act('E3', 'P3', 'biopsy', 'biopsies', status_words='were taken',
                     technique=a('cold_forceps', 'Cold forceps', ['P3']),
                     target=tg('', 'transverse_colon', 'transverse colon', ['P3']))
        inv, text = colonoscopy(biopsy, lines=lines)
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
        result = run(inv, text, [('45385', POLYP), ('45380', lines['P3'])])
        self.assertEqual([proposal(result, code).status for code in ('45385', '45380')], ['ready', 'ready'])


class Coverage(SimpleTestCase):
    def test_a_reportable_act_no_code_covers_is_not_covered_and_marked_for_the_second_review(self):
        lines = {'P3': 'Cold forceps biopsies were taken from the transverse colon.'}
        biopsy = act('E3', 'P3', 'biopsy', 'biopsies', status_words='were taken',
                     technique=a('cold_forceps', 'Cold forceps', ['P3']),
                     target=tg('', 'transverse_colon', 'transverse colon', ['P3']))
        inv, text = colonoscopy(biopsy, lines=lines)
        result = run(inv, text, [('45385', POLYP)])
        items = result.completeness['unresolved_items']
        self.assertEqual([(item['act'], item['reason'], item['second_review'], item['events']) for item in items],
                         [('biopsy', 'not_covered', True, ['E3'])])
        self.assertEqual(items[0]['evidence'][0]['text'], lines['P3'])
        self.assertEqual(result.completeness['state'], 'incomplete')
        self.assertEqual(check_of(result, 'services.unresolved').status, 'warn')

    def test_a_session_with_no_code_is_no_proposal(self):
        lines = {'P0b': 'EGD: the gastroscope was advanced to the duodenum.', 'P1': 'Colonoscopy: ' + COLONOSCOPE,
                 'P2': POLYP}
        inv, text = inventory(lines, lesions=[L1], events=[
            exam('E0', 'P0b', words='gastroscope', procedure=a('egd', 'EGD', ['P0b'])),
            exam(procedure=a('colonoscopy', 'Colonoscopy', ['P1'])),
            removed(procedure=a('colonoscopy', 'polyp', ['P2']))], reach=[reached()])
        result = run(inv, text, [('45385', POLYP)])
        items = result.completeness['unresolved_items']
        self.assertEqual([(item['service'], item['reason'], item['second_review']) for item in items],
                         [('gi.egd', 'no_proposal', True)])
        self.assertEqual(items[0]['label'], 'upper endoscopy (documented as performed) has no supported proposal')

    def test_an_office_visit_beside_a_same_day_procedure_is_not_listed_not_unresolved(self):
        lines = {'P0b': 'Office visit: established patient seen today for anemia.', 'P1': COLONOSCOPE, 'P2': POLYP}
        visit = act('E0', 'P0b', 'em_visit', 'Office visit', status_words='seen today',
                    procedure=a('office_em', 'Office visit', ['P0b']))
        inv, text = inventory(lines, lesions=[L1], events=[visit, exam(procedure=a('colonoscopy', 'colonoscope',
                                                                                 ['P1'])),
                                                          removed(procedure=a('colonoscopy', 'polyp', ['P2']))],
                              reach=[reached()])
        result = run(inv, text, [('45385', POLYP)])
        self.assertEqual(result.completeness['unresolved_items'], [])
        self.assertEqual([item['service'] for item in result.completeness['not_listed']], ['gi.office_em'])
        self.assertIn('beside a procedure done or possibly done the same day', result.completeness['statement'])

    def test_an_unsupported_act_is_listed_as_such(self):
        lines = {'P3': 'An endoscopic submucosal dissection of the 30 mm rectal lesion was performed.'}
        esd = act('E3', 'P3', 'esd', 'endoscopic submucosal dissection', status_words='was performed')
        inv, text = colonoscopy(esd, lines=lines)
        items = run(inv, text, [('45385', POLYP)]).completeness['unresolved_items']
        self.assertEqual([(item['act'], item['reason']) for item in items], [('esd', 'unsupported')])

    def test_an_act_in_doubt_no_code_depends_on_is_in_doubt_with_a_service_question(self):
        lines = {'P3': 'It is unclear whether biopsies were taken from the transverse colon.'}
        doubt = act('E3', 'P3', 'biopsy', 'biopsies', status='uncertain', status_words='It is unclear whether')
        inv, text = colonoscopy(doubt, lines=lines)
        result = run(inv, text, [('45385', POLYP)])
        items = result.completeness['unresolved_items']
        self.assertEqual([(item['act'], item['reason'], item['second_review']) for item in items],
                         [('biopsy', 'in_doubt', False)])
        self.assertEqual([(spec.scope, spec.fact) for spec in result.clarifications],
                         [('service', 'performed_status')])
        self.assertEqual(result.completeness['state'], 'incomplete')

    def test_a_held_codes_candidate_is_covered(self):
        inv, text = colonoscopy(polyp=removed(performer=a('unknown')))
        result = run(inv, text, [('45385', POLYP)])
        self.assertEqual(proposal(result, '45385').status, 'needs_clarification')
        self.assertEqual(result.completeness['unresolved_items'], [])
        self.assertIn("CPT Studio's reading left 1 attribute unverified that a decision read",
                      result.completeness['reasons'])

    def test_complete_pending_review(self):
        inv, text = colonoscopy()
        result = run(inv, text, [('45385', POLYP)])
        self.assertEqual(result.completeness['state'], 'complete_pending_review')
        self.assertEqual(result.completeness['covered'], {'gi.colonoscopy': ['45385']})
        self.assertEqual(result.completeness['inventory_problems'],
                         ['This assessment was made by a later release from an event inventory; this release does not '
                          're-read it.'])

    def test_c4_an_egd_within_an_upper_eus_is_included(self):
        lines = {'P1': 'A standard gastroscope was advanced to the second portion of the duodenum.',
                 'P2': 'A linear echoendoscope was then introduced; the pancreatic head mass was sampled with a 22-gauge '
                       'needle.'}
        inv, text = inventory(lines, events=[
            exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
            exam('E2', 'P2', words='echoendoscope', status_words='was then introduced',
                 procedure=a('eus', 'echoendoscope', ['P2'])),
            act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'echoendoscope', ['P2']),
                technique=a('needle', '22-gauge needle', ['P2']), target=tg('', 'pancreas', 'pancreatic head', ['P2']))],
            reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])
        sessions_ = coverage.sessions(events.Reading.of(inv))
        self.assertEqual(sessions_['gi.egd'].part_of, 'gi.eus')
        result = run(inv, text, [('43242', lines['P2'])])
        self.assertEqual(result.completeness['included_by'], {'gi.egd': ['43242']})
        self.assertNotIn('gi.egd', [item['service'] for item in result.completeness['unresolved_items']])

    def test_two_examinations_of_one_family_leave_its_session_unresolved(self):
        lines = {'P3': 'The colonoscope was reinserted to the splenic flexure.'}
        inv, text = colonoscopy(exam('E3', 'P3', status_words='was reinserted'), lines=lines)
        session = coverage.sessions(events.Reading.of(inv))['gi.colonoscopy']
        self.assertEqual((session.event, session.unresolved, session.examinations), ('', True, ('E1', 'E3')))


def check_of(result, cid):
    return next(item for item in result.encounter_checks if item.id == cid)


class Record(SimpleTestCase):
    def test_the_event_coding_record(self):
        inv, text = colonoscopy()
        coding = run(inv, text, [('45378', COLONOSCOPE), ('45385', POLYP)]).completeness['event_coding']
        self.assertEqual(coding['version'], 'cpt-studio-events@1')
        session = coding['sessions']['gi.colonoscopy']
        self.assertEqual((session['event'], session['label'], session['part_of']), ('E1', 'colonoscopy', ''))
        self.assertEqual([item['event'] for item in session['reportable']], ['E2'])
        self.assertEqual(coding['codes'], {'sel:0': {'session': 'gi.colonoscopy', 'events': ['E1'], 'lesions': []},
                                           'sel:1': {'session': 'gi.colonoscopy', 'events': ['E2'],
                                                     'lesions': ['L1']}})
        self.assertEqual(coding['lesions']['L1']['landmark'], 'sigmoid_colon')

    def test_the_second_review_mark_stops_at_the_checked_count(self):
        self.assertEqual(coverage.SECOND_REVIEW_CHECKED, engine.SECOND_REVIEW_CHECKED)
        items = [{'reason': 'not_covered', 'label': str(index)} for index in range(66)]
        marks = [item['second_review'] for item in coverage.unresolved_record(items)]
        self.assertEqual((marks.count(True), marks[63], marks[64]), (64, True, False))

    def test_completeness_is_worded_as_reconcile_words_it(self):
        """reconcile.completeness pinned: the same reasons for equivalent inputs (the added unverified-attribute reason
        aside)."""
        session = coverage.Session(id='gi.office_em', family='gi.office_em', kind='office_em',
                                   label='office / outpatient visit', done=True)
        procedure = coverage.Session(id='gi.colonoscopy', family='gi.colonoscopy', kind='colonoscopy',
                                     label='colonoscopy', done=True)
        cov = coverage.Coverage(unresolved=[{'label': 'x'}, {'label': 'y'}], not_listed=[session], unestablished=1)
        mine = coverage.completeness(cov, {'a': procedure, 'b': session}, open_questions=3, provider_ok=False,
                                     conflicts=2)
        legacy_services = [SimpleNamespace(status='performed', family='gi.colonoscopy', kind='colonoscopy'),
                           SimpleNamespace(status='performed', family='gi.office_em', kind='office_em')]
        inventory_ = SimpleNamespace(services=legacy_services, conflicts=[1, 2], problems=[])
        legacy = reconcile.completeness(inventory_, [1, 2], 3, False, unestablished=1, not_listed=[legacy_services[1]])
        self.assertEqual(mine, legacy)
        clean = coverage.completeness(coverage.Coverage(), {'a': procedure}, open_questions=0, provider_ok=True,
                                      conflicts=0)
        self.assertEqual(clean, reconcile.completeness(SimpleNamespace(services=legacy_services[:1], conflicts=[],
                                                                       problems=[]), [], 0, True))
        self.assertEqual(coverage.uncounted_label(session), reconcile.uncounted_label(legacy_services[1]))

    def test_the_bundled_reasons_are_the_catalogues(self):
        self.assertEqual(coverage.COMMON, dict(catalogue.COMMON_BUNDLED))


ERCP_STENT_LINES = {'P1': 'The duodenoscope was advanced to the major papilla.',
                    'P2': 'Deep biliary cannulation was achieved with a sphincterotome and a guidewire.',
                    'P3': 'A biliary sphincterotomy was performed with blended current.',
                    'P4': 'A 10 Fr by 7 cm plastic biliary stent was placed in the common bile duct with good drainage.',
                    'P5': 'A 5 Fr pancreatic stent was placed in the pancreatic duct.',
                    'P6': 'A papillotomy was performed.',
                    'P7': 'The distal common bile duct stricture was dilated with a 6 mm balloon.',
                    'P8': 'The existing biliary stent was removed and exchanged for a new 10 Fr stent in the common bile '
                          'duct.',
                    'P9': 'Stones were extracted from the bile duct with an extraction balloon.',
                    'PA': 'A pancreatic duct stent will be placed at the next ERCP.'}
ERCP_EXAM = exam(words='duodenoscope', procedure=a('ercp'))
ERCP_CANNULATION = act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
                       target=tg('', 'bile_duct', 'biliary', ['P2']))
BILIARY_SPHINCTEROTOMY = act('E3', 'P3', 'sphincterotomy', 'sphincterotomy', status_words='was performed',
                             procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P3']))
PAPILLOTOMY = act('E3', 'P6', 'sphincterotomy', 'papillotomy', status_words='was performed', procedure=a('ercp'),
                  target=tg('', 'ampulla', 'papillotomy', ['P6']))
UNPLACED_SPHINCTEROTOMY = act('E3', 'P6', 'sphincterotomy', 'papillotomy', status_words='was performed',
                              procedure=a('ercp'))
BILIARY_STENT = act('E4', 'P4', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                    technique=a('stent', 'plastic biliary stent', ['P4']),
                    target=tg('', 'common_bile_duct', 'common bile duct', ['P4']))
PANCREATIC_STENT = act('E4', 'P5', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                       technique=a('stent', 'pancreatic stent', ['P5']),
                       target=tg('', 'pancreatic_duct', 'pancreatic duct', ['P5']))
PLANNED_STENT = act('E4', 'PA', 'stent', 'pancreatic duct stent', status='planned', status_words='will be placed',
                    procedure=a('ercp'), time=a('future', 'at the next ERCP', ['PA']),
                    target=tg('', 'pancreatic_duct', 'pancreatic duct', ['PA']))
DUCT_DILATION = act('E3', 'P7', 'dilation', 'dilated', status_words='was dilated', procedure=a('ercp'),
                    technique=a('balloon', 'balloon', ['P7']), target=tg('', 'common_bile_duct', 'common bile duct',
                                                                         ['P7']))
STENT_EXCHANGE = act('E4', 'P8', 'stent_exchange', 'exchanged', status_words='was removed and exchanged',
                     procedure=a('ercp'), technique=a('stent', '10 Fr stent', ['P8']),
                     target=tg('', 'common_bile_duct', 'common bile duct', ['P8']))
STONE_EXTRACTION = act('E4', 'P9', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
                       technique=a('extraction_balloon', 'extraction balloon', ['P9']),
                       target=tg('', 'bile_duct', 'bile duct', ['P9']))


def ercp_with(*acts):
    lines = {pid: ERCP_STENT_LINES[pid] for pid in ['P1', 'P2'] + [item['status']['passages'][0] for item in acts]}
    return inventory(lines, events=[ERCP_EXAM, ERCP_CANNULATION, *acts])


class StentIncluded(SimpleTestCase):
    """DECISIONS D45 (the S17 refutation, finding 10): an ERCP stent placement or exchange code includes "sphincterotomy,
    when performed" and pre- and post-dilation (43274, 43276), so a sphincterotomy or a dilation beside a current
    performed stent act of its duct at the same ERCP is part of it - R5's "part of another documented act" hold, never
    READY alone. Both ducts verified and different keep it a separate service; a duct verified on neither act, or the
    ampulla (it opens on both ducts), never sets the two apart."""

    def assert_held_as_part_of_the_stent(self, result, code):
        p = proposal(result, code)
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['performed_status'], events.BUNDLED))
        self.assertIn('which is part of another documented act: ' + coverage.STENT_INCLUDED,
                      check(p, 'service.status').detail)

    def test_a_sphincterotomy_of_the_stented_duct_is_part_of_the_stent(self):
        inv, text = ercp_with(BILIARY_SPHINCTEROTOMY, BILIARY_STENT)
        reading = events.Reading.of(inv)
        self.assertEqual((coverage.duct_side(reading.events['E3']), coverage.duct_side(reading.events['E4'])),
                         ('biliary', 'biliary'))
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), coverage.STENT_INCLUDED)
        result = run(inv, text, [('43262', ERCP_STENT_LINES['P3']), ('43274', ERCP_STENT_LINES['P4'])])
        self.assert_held_as_part_of_the_stent(result, '43262')
        self.assertEqual(proposal(result, '43274').status, 'ready')
        self.assertIn('E3', [item['event'] for item in result.completeness['bundled']])

    def test_the_stent_code_alone_leaves_no_act_open(self):
        inv, text = ercp_with(BILIARY_SPHINCTEROTOMY, BILIARY_STENT)
        result = run(inv, text, [('43274', ERCP_STENT_LINES['P4'])])
        self.assertEqual(proposal(result, '43274').status, 'ready')
        self.assertEqual(result.completeness['unresolved_items'], [])

    def test_a_sphincterotomy_of_the_other_duct_is_a_separate_service(self):
        inv, text = ercp_with(BILIARY_SPHINCTEROTOMY, PANCREATIC_STENT)
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
        result = run(inv, text, [('43262', ERCP_STENT_LINES['P3']), ('43274', ERCP_STENT_LINES['P5'])])
        self.assertEqual({code: proposal(result, code).status for code in ('43262', '43274')},
                         {'43262': 'ready', '43274': 'ready'})

    def test_a_duct_not_established_never_sets_the_two_apart(self):
        for name, sphincterotomy in (('the ampulla', PAPILLOTOMY), ('no target', UNPLACED_SPHINCTEROTOMY)):
            inv, text = ercp_with(sphincterotomy, PANCREATIC_STENT)
            reading = events.Reading.of(inv)
            with self.subTest(sphincterotomy=name):
                self.assertEqual(coverage.duct_side(reading.events['E3']), '')
                self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), coverage.STENT_INCLUDED)
                result = run(inv, text, [('43262', ERCP_STENT_LINES['P6']), ('43274', ERCP_STENT_LINES['P5'])])
                self.assert_held_as_part_of_the_stent(result, '43262')

    def test_a_dilation_of_the_stented_duct_and_a_stent_exchange(self):
        inv, text = ercp_with(DUCT_DILATION, BILIARY_STENT)
        result = run(inv, text, [('43277', ERCP_STENT_LINES['P7']), ('43274', ERCP_STENT_LINES['P4'])])
        self.assert_held_as_part_of_the_stent(result, '43277')
        inv, text = ercp_with(BILIARY_SPHINCTEROTOMY, STENT_EXCHANGE)
        result = run(inv, text, [('43262', ERCP_STENT_LINES['P3']), ('43276', ERCP_STENT_LINES['P8'])])
        self.assert_held_as_part_of_the_stent(result, '43262')
        self.assertEqual(proposal(result, '43276').status, 'ready')

    def test_no_stent_act_of_this_ercp_leaves_the_sphincterotomy_alone(self):
        for name, other, code, line in (('a stone extraction', STONE_EXTRACTION, '43264', 'P9'),
                                        ('a planned stent', PLANNED_STENT, '', 'PA')):
            inv, text = ercp_with(BILIARY_SPHINCTEROTOMY, other)
            reading = events.Reading.of(inv)
            with self.subTest(beside=name):
                self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
                codes = [('43262', ERCP_STENT_LINES['P3'])] + ([(code, ERCP_STENT_LINES[line])] if code else [])
                self.assertEqual(proposal(run(inv, text, codes), '43262').status, 'ready')


HEMOCLIPS = 'Immediate oozing from the polypectomy site was controlled with two hemoclips for hemostasis.'
DIVERTICULUM = 'A bleeding diverticulum in the ascending colon was controlled with two hemoclips for hemostasis.'
# DECISIONS D58: the S17 round-2 refutation's finding 5, its inputs
RS_POLYP = 'A 12 mm sessile polyp at the rectosigmoid junction was removed with a hot snare.'
RS_CLIP = ('Immediate oozing from the polypectomy site in the distal sigmoid colon was controlled with two hemoclips '
           'for hemostasis.')
HF_POLYP = 'A 12 mm sessile polyp at the hepatic flexure was removed with a hot snare.'
HF_CLIP = ('Immediate oozing from the polypectomy site in the proximal transverse colon was controlled with two '
           'hemoclips for hemostasis.')


def hemoclips(line: str = HEMOCLIPS, **changes) -> dict:
    """A bleeding control (E3): two clips whose hemostasis purpose is verified, in its own line (P3)."""
    options = {'technique': a('clip', 'hemoclips', ['P3']), 'purpose': a('hemostasis', 'for hemostasis', ['P3']),
               **changes}
    return act('E3', 'P3', 'clip', 'hemoclips', status_words='was controlled', **options)


def hot_snared(clip: dict, clip_line: str, polyp_line: str = RS_POLYP, landmark: str = 'rectosigmoid',
               site_words: str = 'rectosigmoid junction', **options):
    """(inventory, text, result) of a colonoscopy to the cecum (E1) whose 12 mm polyp L1 at ``landmark`` is removed
    with a hot snare (E2, ``polyp_line``), beside ``clip`` (``clip_line``, P3); Corti proposes 45385 and 45382."""
    lesion = les('L1', '12 mm sessile polyp', 'P2', landmark=landmark, site_words=site_words, size_words='12 mm')
    removal = snare('E2', 'P2', technique=a('hot_snare', 'hot snare', ['P2']),
                    status_words='was removed with a hot snare',
                    target=tg('L1', landmark, polyp_line[2:polyp_line.index(' was removed')], ['P2']))
    lines = {'P2': polyp_line, 'P3': clip_line, **options.pop('lines', {})}
    inv, text = colonoscopy(clip, polyp=removal, lesions=(lesion,), lines=lines, **options)
    return inv, text, run(inv, text, [('45385', polyp_line), ('45382', clip_line)])


class AdjunctBesideARemoval(SimpleTestCase):
    """DECISIONS D41 (the S17 refutation, finding 6): beside a current performed removal of its session, an ablation or a
    bleeding control that D30 does not bundle - no verified part_of, no lesion, at compatible or unknown places - is
    asked (act_target, the procedural_adjunct bundling identity), never READY alone. Verified places that are not
    compatible, two distinct verified lesions, or a verified part_of naming another act set it apart.

    DECISIONS D58 (the S17 round-2 refutation, finding 5) narrows what sets it apart: places only when they are
    verifiably apart - both on one of the tract's chains, neither compatible nor ADJACENT (one step apart); a place on
    no chain (a region, an anastomosis, even one D34 places) never - and a part_of only when it names an ACT, never the
    examination (the session, ADJUDICATION C-1) or an umbrella."""

    def assert_asked(self, result, code):
        p = proposal(result, code)
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['act_target'], events.BUNDLING_IDENTITY))
        self.assertIn('done as part of the removal', p.clarifications[0].question)

    def test_a_bleeding_control_naming_nothing_beside_a_polypectomy_is_asked(self):
        inv, text = colonoscopy(hemoclips(), lines={'P3': HEMOCLIPS})
        reading = events.Reading.of(inv)
        self.assertEqual((reading.events['E3']['catalogue_kind'], reading.events['E3']['part_of']['value'],
                          coverage.bundled_reason(reading, reading.events['E3'])), ('bleeding_control', '', ''))
        self.assertEqual(coverage.bundling_doubt(reading, reading.events['E3'])['reason'], 'procedural_adjunct')
        result = run(inv, text, [('45385', POLYP), ('45382', HEMOCLIPS)])
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assert_asked(result, '45382')

    def test_an_ablation_of_the_resection_margins_with_no_part_of_is_asked(self):
        inv, text, lines = adjunct(part_of='')
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
        result = run(inv, text, [('45390', lines['P2']), ('45388', lines['P3'])])
        self.assertEqual(proposal(result, '45390').status, 'ready')
        self.assert_asked(result, '45388')

    def test_a_bleeding_control_at_another_verified_place_is_its_own_act(self):
        inv, text = colonoscopy(hemoclips(DIVERTICULUM, target=tg('', 'ascending_colon', 'ascending colon', ['P3'])),
                                lines={'P3': DIVERTICULUM})
        reading = events.Reading.of(inv)
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
        result = run(inv, text, [('45385', POLYP), ('45382', DIVERTICULUM)])
        self.assertEqual([proposal(result, code).status for code in ('45385', '45382')], ['ready', 'ready'])

    def test_a_verified_part_of_another_act_sets_it_apart(self):
        biopsy_line = 'Cold forceps biopsies were taken from the sigmoid colon.'
        clip_line = 'The biopsy site oozing was controlled with two hemoclips for hemostasis.'
        biopsy = act('E4', 'P4', 'biopsy', 'biopsies', status_words='were taken',
                     technique=a('cold_forceps', 'Cold forceps', ['P4']),
                     target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P4']))
        inv, text = colonoscopy(hemoclips(clip_line, part_of='E4'), biopsy, lines={'P3': clip_line, 'P4': biopsy_line})
        reading = events.Reading.of(inv)
        self.assertEqual(reading.events['E3']['part_of']['value'], 'E4')
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))

    # --- DECISIONS D58 ------------------------------------------------------------------------------------------------

    def assert_places(self, inv, removal: set, clip: set):
        reading = events.Reading.of(inv)
        self.assertEqual((reading.context.places(reading.events['E2']), reading.context.places(reading.events['E3'])),
                         (frozenset(removal), frozenset(clip)))
        doubt = coverage.bundling_doubt(reading, reading.events['E3']) or {}
        self.assertEqual(doubt.get('reason'), 'procedural_adjunct')

    def test_d58_a_clip_in_the_distal_sigmoid_beside_a_rectosigmoid_polypectomy_is_asked(self):
        """Finding 5, variant 1: the clip's line says 'the polypectomy site', and its place - the sigmoid colon - is one
        step from the rectosigmoid on the tract. Adjacent places never set the adjunct apart (it was READY)."""
        clip = hemoclips(RS_CLIP, target=tg('', 'sigmoid_colon', 'polypectomy site in the distal sigmoid colon',
                                            ['P3']))
        inv, text, result = hot_snared(clip, RS_CLIP)
        self.assert_places(inv, {'rectosigmoid'}, {'sigmoid_colon'})
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assert_asked(result, '45382')

    def test_d58_a_clip_in_the_proximal_transverse_beside_a_hepatic_flexure_polypectomy_is_asked(self):
        """Finding 5, variant 2: the transverse colon is one step from the hepatic flexure (it was READY)."""
        clip = hemoclips(HF_CLIP, target=tg('', 'transverse_colon', 'polypectomy site in the proximal transverse colon',
                                            ['P3']))
        inv, text, result = hot_snared(clip, HF_CLIP, HF_POLYP, 'hepatic_flexure', 'hepatic flexure')
        self.assert_places(inv, {'hepatic_flexure'}, {'transverse_colon'})
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assert_asked(result, '45382')

    def test_d58_a_part_of_naming_the_examination_sets_nothing_apart(self):
        """Finding 5, variant 3: the examination is the session, never an act (ADJUDICATION C-1), and normalize
        verifies a part_of only as naming an event that exists - so a part_of naming the colonoscopy sets the clip apart
        from nothing (it was READY). On the D41 control's line, and on the claim's own line with no place given."""
        for line in (HEMOCLIPS, RS_CLIP):
            with self.subTest(line=line):
                inv, text, result = hot_snared(hemoclips(line, part_of='E1'), line)
                reading = events.Reading.of(inv)
                self.assertEqual((reading.events['E3']['part_of']['value'], reading.events['E3']['part_of']['state'],
                                  reading.events['E1']['catalogue_kind'], reading.events['E1']['kind']['state']),
                                 ('E1', 'verified', 'examination', 'verified'))
                doubt = coverage.bundling_doubt(reading, reading.events['E3']) or {}
                self.assertEqual(doubt.get('reason'), 'procedural_adjunct')
                self.assertEqual(proposal(result, '45385').status, 'ready')
                self.assert_asked(result, '45382')

    def test_d58_a_standalone_ablation_one_step_from_the_resection_is_asked(self):
        """D58's cost, pinned: D30's standalone-ablation control - two angioectasias in the ascending colon treated with
        argon plasma coagulation, naming no lesion, beside a cecal EMR - was READY because the ascending colon is not
        compatible with the cecum. It is one step from it on the tract, so the ablation is asked (act_target)."""
        inv, text, line = standalone_ablation('ascending_colon', 'ascending colon')
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
        self.assert_places(inv, {'cecum'}, {'ascending_colon'})
        result = run(inv, text, [('45390', ADJUNCT_LINES['P2']), ('45388', line)])
        self.assertEqual(proposal(result, '45390').status, 'ready')
        self.assert_asked(result, '45388')

    def test_d58_an_adjunct_at_an_anastomosis_is_never_set_apart_by_its_place(self):
        """A place on no chain never sets the adjunct apart (fail-closed): an anastomosis beside the sigmoid colon, and
        an anastomosis that D34 places at the rectum (the encounter's one colorectal anastomosis) beside the descending
        colon, three steps away - that place is the anatomy entry's, not the clip's own words'. Both were READY."""
        line = 'Oozing at the colorectal anastomosis was controlled with two hemoclips for hemostasis.'
        clip = hemoclips(line, target=tg('', 'anastomosis', 'colorectal anastomosis', ['P3']))
        inv, text = colonoscopy(clip, lines={'P3': line})
        self.assert_places(inv, {'sigmoid_colon'}, {'anastomosis'})
        self.assert_asked(run(inv, text, [('45385', POLYP), ('45382', line)]), '45382')
        polyp = 'A 12 mm sessile polyp in the descending colon was removed with a hot snare.'
        inv, text, result = hot_snared(clip, line, polyp, 'descending_colon', 'descending colon',
                                       lines={'G3': 'History: low anterior resection with a colorectal anastomosis.'},
                                       anatomy=[anatomy_entry('colorectal anastomosis')])
        self.assert_places(inv, {'descending_colon'}, {'rectum'})
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assert_asked(result, '45382')

    def test_d58_control_places_two_steps_apart_set_the_adjunct_apart(self):
        """The control D58 keeps: a bleeding diverticulum in the descending colon, two steps from the rectosigmoid, is
        its own act, READY beside the polypectomy (D41's ascending-colon control is five steps from the sigmoid)."""
        line = 'A bleeding diverticulum in the descending colon was controlled with two hemoclips for hemostasis.'
        inv, text, result = hot_snared(hemoclips(line, target=tg('', 'descending_colon', 'descending colon', ['P3'])),
                                       line)
        reading = events.Reading.of(inv)
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
        self.assertEqual([proposal(result, code).status for code in ('45385', '45382')], ['ready', 'ready'])


class PossiblyCurrent(SimpleTestCase):
    """DECISIONS D62 (D54's review): a current time left unverified is a doubt about the event's own code, never an
    absence for the rules that hold OTHER codes by it - a session's examinations, the removal a biopsy is bundled into.
    A current time whose own words place the event on another occasion (a differing date, D35's marker) is evidence,
    and keeps the event out."""

    ASIDE = 'These were the findings at her index colonoscopy: a 12 mm sessile polyp in the ascending colon was removed.'

    def aside_session(self, time_words):
        lines = {'P1': COLONOSCOPE, 'P5': self.ASIDE}
        aside_exam = exam('E3', 'P5', words='index colonoscopy', status_words='were the findings',
                          time=a('current_encounter', time_words, ['P5']))
        removal = snare('E2', 'P5', status_words='was removed', technique=a('not_stated'),
                        target=tg('', 'ascending_colon', 'ascending colon', ['P5']))
        return inventory(lines, events=[exam(), aside_exam, removal], reach=[reached()])

    def test_an_aside_examination_with_unanchored_words_leaves_todays_session_unresolved(self):
        inv, text = self.aside_session('These were the findings at her index colonoscopy')
        reading = events.Reading.of(inv)
        self.assertEqual(reading.events['E3']['time']['reasons'], ['current_unanchored'])
        session = coverage.sessions(reading)['gi.colonoscopy']
        self.assertEqual((session.event, session.unresolved, session.examinations), ('', True, ('E1', 'E3')))
        p = proposal(run(inv, text, [('45385', self.ASIDE)]), '45385')
        self.assertEqual(p.status, 'needs_clarification')  # never READY on the index colonoscopy's removal

    def test_an_examination_its_own_date_places_elsewhere_never_takes_the_session(self):
        inv, text = self.aside_session('at her index colonoscopy on 01/14/2024')
        reading = events.Reading.of(inv)
        self.assertIn('date_mismatch', reading.events['E3']['time']['reasons'])
        session = coverage.sessions(reading)['gi.colonoscopy']
        self.assertEqual((session.event, session.unresolved), ('E1', False))

    def test_a_removal_with_an_unanchored_time_still_holds_the_biopsy_of_the_lesion_it_removed(self):
        line = 'During this colonoscopy, a 6 mm sessile polyp in the sigmoid colon was biopsied and then removed with a ' \
               'cold snare.'
        lesion = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                     size_words='6 mm')
        biopsy = act('E3', 'P2', 'biopsy', 'biopsied', status_words='was biopsied',
                     technique=a('not_stated'),
                     target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P2']))
        for time_words, removal_held in (('During this colonoscopy', True), ('', False)):
            removal = snare('E2', 'P2', status_words='removed with a cold snare',
                            target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P2']),
                            time=a('current_encounter', time_words, ['P2']) if time_words else a('current_encounter'))
            inv, text = inventory({'P1': COLONOSCOPE, 'P2': line}, events=[exam(), removal, biopsy], lesions=[lesion],
                                  reach=[reached()])
            result = run(inv, text, [('45380', line), ('45385', line)])
            with self.subTest(time_words=time_words):
                self.assertEqual(proposal(result, '45380').support['reason'], events.BUNDLED)  # held, never READY
                self.assertEqual(proposal(result, '45380').status, 'needs_clarification')
                self.assertEqual(proposal(result, '45385').status == 'ready', not removal_held)
