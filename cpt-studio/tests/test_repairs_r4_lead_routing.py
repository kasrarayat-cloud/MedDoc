"""Round 4 routing repairs made by the lead: hold-only readings for cancellations, deferrals and plan-today passages,
and the bounded clause lookups behind two quadratic paths.

Each test reproduces a confirmed round-4 finding from its exact input and pins the controls. Every change only holds
(uncertain, with a non-silent cue): nothing here newly excludes or releases. Synthetic text only; pure functions.
"""
import time
import unittest

from studio.gi import detect
from tests.test_repairs_r3_time import VISIT, plan_office
from tests.test_repairs_status_r2_routing import HEADER, clarified, family, read, run_engine

EUS_LINE = 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.'
INDICATION = 'Indication: Pancreatic head mass on CT.'


def eus_note(*lines):
    return HEADER + '\n'.join(lines) + '\n'


class Release4PlanTodayOutranksOtherMentionsTests(unittest.TestCase):
    """release:4: the PLAN_TODAY hold was lost as soon as the family had another plan, history or negated mention."""

    SENTENCE = 'EGD this morning revealed a Schatzki ring, dilated to 18 mm.'

    def test_a_second_mention_does_not_release_the_visit(self):
        for extra in ('Prior EGD in 2023 was normal.', 'Repeat EGD if dysphagia recurs.', 'No prior EGD.'):
            text = plan_office(self.SENTENCE + ' ' + extra)
            with self.subTest(extra=extra):
                self.assertEqual(family(text, 'gi.egd'), 'uncertain')
                proposals, _ = run_engine(text, [('99214', VISIT)])
                self.assertEqual(proposals['99214'].status, 'needs_clarification')
                self.assertIn('separate_em', clarified(proposals['99214']))

    def test_a_plan_with_no_today_still_plans(self):
        text = plan_office('Repeat EGD in one year.')
        self.assertEqual(family(text, 'gi.egd'), 'planned')


class Routing6CancellationReaderTests(unittest.TestCase):
    """routing:6 and release:8: the cancellation reader stopped at a sentence naming the same service, read only below
    the procedure line, and missed a typed 'Procedure performed: No'."""

    def held(self, text, line=EUS_LINE):
        status, cues = read(text, line)
        self.assertNotEqual(status, 'performed', cues)
        proposals, _ = run_engine(text, [('43242', line)])
        self.assertNotEqual(proposals['43242'].status, 'ready')
        self.assertNotEqual(proposals['43242'].bucket, 'excluded')  # held, never excluded by these readers

    def test_a_status_line_after_a_sentence_naming_the_same_service(self):
        self.held(eus_note(EUS_LINE, INDICATION, 'Consent: The risks and benefits of EUS were discussed with the '
                                                  'patient.', 'Procedure status: Cancelled - the patient had eaten '
                                                              'breakfast.'))

    def test_a_status_line_above_the_procedure_line(self):
        self.held(eus_note('Procedure status: Cancelled - the patient had eaten breakfast.', EUS_LINE, INDICATION))
        self.held(eus_note(INDICATION, 'Procedure status: Cancelled - the patient had eaten breakfast.', EUS_LINE))

    def test_a_typed_answer_that_it_was_not_performed(self):
        for answer in ('Procedure performed: No (patient refused).', 'Procedure performed? no', 'Exam completed: N'):
            with self.subTest(answer=answer):
                self.held(eus_note(EUS_LINE, INDICATION, answer, 'Plan: Reschedule next week.'))

    def test_controls_stay_performed(self):
        for lines in ((EUS_LINE, INDICATION, 'Procedure status: Completed.'),
                      (EUS_LINE, INDICATION, 'Procedure performed: Yes.'),
                      (EUS_LINE, INDICATION, 'Consent: The risks and benefits of EUS were discussed with the patient.'),
                      ('Procedure status: Completed.', EUS_LINE, INDICATION)):
            text = eus_note(*lines)
            with self.subTest(lines=lines):
                self.assertEqual(read(text, EUS_LINE)[0], 'performed')
                proposals, _ = run_engine(text, [('43242', EUS_LINE)])
                self.assertEqual(proposals['43242'].status, 'ready', clarified(proposals['43242']))

    def test_another_familys_sentence_still_ends_the_reading(self):
        text = eus_note(EUS_LINE, INDICATION, 'EGD was performed first.', 'Status: Cancelled.')
        self.assertEqual(read(text, EUS_LINE)[0], 'performed')


class Release9DenyingHeadingTests(unittest.TestCase):
    """release:9: lines under a verbless denying heading ('Cancelled procedures:') read silent."""

    def test_the_cancelled_line_is_held(self):
        for heading in ('Cancelled procedures:', 'Procedures cancelled:'):
            text = (HEADER + 'Procedures performed: EGD with biopsy.\nIndication: Dysphagia.\nFindings: The endoscope '
                    'was advanced to the second part of the duodenum. Mild esophagitis; biopsies were taken.\n'
                    + heading + '\nEGD with balloon dilation.\nPlan: PPI twice daily.\n')
            with self.subTest(heading=heading):
                status, cues = read(text, 'EGD with balloon dilation.')
                self.assertEqual(status, 'uncertain', cues)
                self.assertTrue(any('a label that denies performance' in c for c in cues), cues)
                proposals, _ = run_engine(text, [('43239', 'Procedures performed: EGD with biopsy.'),
                                                 ('43249', 'EGD with balloon dilation.')])
                self.assertNotEqual(proposals['43249'].status, 'ready')


class Release10DeferralTests(unittest.TestCase):
    """release:10: 'we decided to defer EUS' under Impression read silent, so the procedure line decided."""

    def test_a_deferral_holds_the_procedure(self):
        text = (HEADER + 'Procedure: Upper EUS\nIndication: 2.5 cm pancreatic cyst.\nImpression: Because of her recent '
                'anticoagulation we decided to defer EUS of the pancreatic cyst.\nPlan: Hold apixaban; return in 2 '
                'weeks.\n')
        self.assertEqual(family(text, 'gi.eus'), 'uncertain')
        proposals, _ = run_engine(text, [('43259', 'Procedure: Upper EUS')])
        self.assertNotEqual(proposals['43259'].status, 'ready')

    def test_an_ordinary_impression_stays_silent(self):
        text = (HEADER + 'Procedure: Upper EUS\nIndication: 2.5 cm pancreatic cyst.\nImpression: EUS showed a 2.5 cm '
                'unilocular cyst.\n')
        self.assertEqual(family(text, 'gi.eus'), 'performed')


class BoundedClauseLookupTests(unittest.TestCase):
    """routing:10 and routing:14: per-mention clause lists made two paths quadratic. The bounded lookups return
    exactly the same clauses."""

    def test_the_bounded_lookups_equal_the_slices(self):
        text = HEADER + 'Procedure: EGD; ' + '; '.join(f'clause {n}' for n in range(60)) + '.\n'
        an, _ = detect._analysis(text, None)
        clauses = an.lay.clauses
        points = sorted({c[0] for c in clauses} | {c[1] for c in clauses} | {0, len(text)})
        for s in points[::3]:
            for e in points[::5]:
                for limit in (1, 3):
                    self.assertEqual(detect._first_clauses_in(an, s, e, limit), detect._clauses_in(an, s, e)[:limit])
                    self.assertEqual(detect._last_clauses_in(an, s, e, limit), detect._clauses_in(an, s, e)[-limit:])

    def test_long_semicolon_chains_route_in_bounded_time(self):
        for text in (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum'
                     + '; cecum' * 8000 + '.\n', HEADER + 'Procedure: EGD' + '; EGD' * 8000 + '.\n'):
            start = time.perf_counter()
            detect.route(text, None)
            self.assertLess(time.perf_counter() - start, 20)  # 3.9 s and 14.9 s before (quadratic growth)
