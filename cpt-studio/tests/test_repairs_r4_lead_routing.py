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


ADDENDUM = '\n\nADDENDUM (revision 2, added 2026-10-22 10:00 UTC)\n'
NO_EXTENT = (HEADER + 'Procedure: Colonoscopy\nIndication: Positive FIT.\nFindings: A 6 mm sigmoid polyp was removed with '
             'a cold snare.\nPlan: Repeat colonoscopy in 5 years.\n')
POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


def extent(text):
    return next((f.value for f in family_facts(text, 'gi.colonoscopy') if f.name == 'extent'), None)


def family_facts(text, slug):
    return detect.route(text, None).finding(slug).facts


class ExtentLabelTests(unittest.TestCase):
    """routing:2, release:3 and routing:9: an extent label's value was read as the extent reached in any 'other'
    section, with an aim or a denial after the landmark."""

    def test_an_addendum_answer_still_clears_the_extent(self):
        for answer in ('Furthest extent reached: cecum.', 'Extent: cecum', 'Extent reached: cecum.',
                       'Extent reached: cecum, with photodocumentation of the appendiceal orifice.'):
            with self.subTest(answer=answer):
                self.assertEqual(extent(NO_EXTENT + ADDENDUM + answer + '\n'), 'cecum')

    def test_an_answer_with_an_aim_or_a_denial_is_not_the_extent_reached(self):
        for answer in ('Extent: cecum (intended; not reached).', 'Extent: cecum (intended), splenic flexure (reached).',
                       'Extent: cecum was the goal.'):
            with self.subTest(answer=answer):
                self.assertNotEqual(extent(NO_EXTENT + ADDENDUM + answer + '\n'), 'cecum')

    def test_another_facilitys_record_never_supplies_todays_extent(self):
        for heading, line in (('Outside records:', 'Colonoscopy at another facility in 2021. Extent: cecum.'),
                              ('Outside colonoscopy report:', 'Extent reached: cecum.'),
                              ('Referral information:', 'Furthest extent reached: cecum.'),
                              ('Records reviewed:', 'Extent: cecum.'), ('Last colonoscopy:', 'Extent: cecum.'),
                              ('Comparison:', 'Extent reached: cecum.')):
            text = (HEADER + 'Procedure: Colonoscopy\nIndication: Surveillance of adenomatous polyps.\nFindings: The '
                    'colonoscope was advanced to the splenic flexure. A 6 mm polyp in the sigmoid colon was removed '
                    'with a cold snare.\n' + heading + '\n' + line + '\nImpression: Sigmoid polyp, removed.\nPlan: CT '
                    'colonography to complete the evaluation.\n')
            with self.subTest(heading=heading):
                self.assertNotEqual(extent(text), 'cecum')
                self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')

    def test_an_aim_after_the_landmark_in_a_findings_label(self):
        for line in ('Extent: cecum (intended).', 'Extent: cecum (goal), hepatic flexure (reached).',
                     'Extent: cecum was the goal.'):
            text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the hepatic flexure. A '
                    '5 mm sigmoid polyp was removed with a cold snare.\n' + line + '\nImpression: Sigmoid polyp '
                    'removed.\n')
            with self.subTest(line=line):
                self.assertEqual(extent(text), 'incomplete: hepatic flexure')
                self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')
                proposals, _ = run_engine(text, [('45385', POLYP.replace('6 mm', '5 mm'))])
                checks = {c.id: c.status for c in proposals['45385'].checks}
                self.assertEqual(checks.get('service.incomplete'), 'warn')  # routed to review, never completed

    def test_another_facilitys_depth_never_supplies_a_flexible_sigmoidoscopys(self):
        text = (HEADER + 'Procedure: Flexible sigmoidoscopy with biopsy.\nFindings: A biopsy was taken from the '
                'rectum.\nOutside records:\nDepth of insertion: 60 cm.\n')
        facts = {f.name: f.value for f in family_facts(text, 'gi.flex_sig')}
        self.assertIsNone(facts.get('extent'))


class Routing7QualifiedMonthTests(unittest.TestCase):
    """routing:7: a part of the service month ('at the end of October' for an October 21 date of service) was read as
    the date of service, and a time hold on one line did not contradict the procedure line."""

    def test_a_qualified_month_holds(self):
        for tail in ('at the end of October.', 'in early October.', 'at the beginning of October.'):
            text = eus_note('Procedure: EUS with fine-needle biopsy of the pancreatic head mass ' + tail, INDICATION)
            with self.subTest(tail=tail):
                self.assertEqual(family(text, 'gi.eus'), 'uncertain')
                proposals, _ = run_engine(text, [('43242', text.split('\n')[2])])
                self.assertNotEqual(proposals['43242'].status, 'ready')

    def test_a_time_hold_on_another_line_contradicts_the_procedure_line(self):
        text = eus_note('Procedure: EUS', INDICATION, 'Technique: EUS with fine-needle biopsy of the pancreatic head '
                                                    'mass next Tuesday under MAC.')
        self.assertEqual(family(text, 'gi.eus'), 'uncertain')
        proposals, _ = run_engine(text, [('43259', 'Procedure: EUS')])
        self.assertNotEqual(proposals['43259'].status, 'ready')

    def test_the_month_itself_and_its_day_stay_today(self):
        for tail in ('in October.', 'on October 21.'):
            text = eus_note('Procedure: EUS with fine-needle biopsy of the pancreatic head mass ' + tail, INDICATION)
            with self.subTest(tail=tail):
                self.assertEqual(family(text, 'gi.eus'), 'performed')


def office(visit):
    return (HEADER + 'Place of service: Office (POS 11)\n' + visit + '\nChief complaint: GI symptoms.\nAssessment: '
            'Stable.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')


class Routing4And5AnotherServicesTimeTests(unittest.TestCase):
    """routing:4 and routing:5: another service's time made a visit statement, or today's colonoscopy line, read
    historical, so the E/M or 45385 was excluded."""

    def test_a_visit_to_discuss_a_past_procedure_is_never_excluded(self):
        for visit in ('Follow-up office visit to discuss the EGD performed last week.',
                      'Established patient office visit to review the colonoscopy done last week.',
                      'Office visit to review her colonoscopy from 2 weeks ago.',
                      'Follow-up office visit to discuss the EGD performed last month.'):
            text = office(visit)
            with self.subTest(visit=visit):
                proposals, _ = run_engine(text, [('99214', visit)])
                self.assertNotEqual(proposals['99214'].bucket, 'excluded', proposals['99214'].exclusion_reason)

    def test_another_services_time_never_excludes_todays_colonoscopy(self):
        findings = 'Findings: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n'
        for line in ('Colonoscopy with cold snare polypectomy for iron deficiency anemia after a normal EGD performed '
                     'last week.', 'Colonoscopy with cold snare polypectomy for a polyp seen on a flexible '
                     'sigmoidoscopy at an outside hospital.'):
            text = HEADER + 'Procedure: ' + line + '\n' + findings
            with self.subTest(line=line):
                proposals, _ = run_engine(text, [('45385', 'Procedure: ' + line)])
                self.assertNotEqual(proposals['45385'].bucket, 'excluded', proposals['45385'].exclusion_reason)

    def test_a_services_own_time_still_dates_it(self):
        for text, slug in ((HEADER + 'History: EGD was performed last month at an outside hospital.\n', 'gi.egd'),
                           (HEADER + 'Indication: She underwent EGD last year.\n', 'gi.egd')):
            with self.subTest(text=text):
                self.assertEqual(family(text, slug), 'historical')
