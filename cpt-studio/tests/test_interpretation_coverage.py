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
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, asked, check, colonoscopy, exam, inventory,
                                              proposal, reached, removed, run)
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
