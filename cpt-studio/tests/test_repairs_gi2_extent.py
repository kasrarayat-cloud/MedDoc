"""Session 7c8d38da, GI round 2, extent: the routing extent of a service whose report is written under a stand-alone
service heading inside an indication (held-out ho-01), and of an examination stopped at a depth (held-out ho-03).
Synthetic data only; routing is a pure function (no database, no provider).

- R-A (studio/gi/sections.py): "Upper Endoscopy" / "Colonoscopy" on lines of their own are no headings, so the
  "Indications" section ran over both services' narratives, every statement there was held as an indication's, no
  landmark was reached and neither extent was read. A service's name standing alone now ends an indication that has
  said something of its own, in a report that names the service as its own on a procedure heading line above it, when
  the part it heads reports what was done, says no intent before it does, marks no clause as today's, and no
  procedure, findings or technique heading follows it. Everything else reads as installed.
- R-B1 (studio/gi/cues.py, detect.py): "The pediatric colonoscope was advanced to 28 cm from the anal verge in the
  sigmoid colon" was no reach. A reach to a depth then its landmark is one, only as the endoscope's own reach, its
  denial read first, and never where a deeper landmark the text does not deny is named after it (a waypoint whose onward
  reach no cue reads).
- R-B2 (studio/gi/detect.py): "Extent reached: sigmoid colon at 28 cm." was unread ("at", "28", "cm" are no extent
  tail words). A depth that opens a label's value is part of the value.

Every test below names the shape it pins; the controls are inputs whose reading must stay the installed one (most of
them inputs on which an earlier draft of this repair was refuted)."""
import time
import unittest
from datetime import date

from studio.gi import sections
from studio.gi.detect import route
from tests.support import docgen

SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\n'
DAY = date(2026, 10, 20)
BIDIRECTIONAL = ('Bidirectional Endoscopy Report\nDate of procedure: 2026-10-20\n'
                 'Place of service: Ambulatory surgery center (ASC), POS 24\n')
COLON_REPORT = ('Colonoscopy Report\nDate of procedure: 2026-10-20\n'
                'Place of service: Ambulatory surgery center (ASC), POS 24\n\n')
UPPER_REPORT = ('Upper Endoscopy Report\nDate of procedure: 2026-10-20\n'
                'Place of service: Ambulatory surgery center (ASC), POS 24\n\n')
OFFICE = 'Office Visit\nDate of service: 2026-10-20\nPlace of service: Office (POS 11)\nVisit type: Established patient.\n\n'
PROCEDURES = 'Procedures: Esophagogastroduodenoscopy with biopsies; colonoscopy with cold snare polypectomy.\n\n'
INDICATIONS = 'Indications\nIron deficiency anemia, referred for upper and lower endoscopic evaluation.\n\n'
EGD = ('The gastroscope was passed through the mouth and advanced to the second portion of the duodenum. Cold forceps '
       'biopsies were taken from the antrum.')
# The first sentence states no performance and is 88 characters long, so the PDF form puts it on a line of its own.
COLON = ('With the patient in the left lateral position, a digital rectal examination was normal. The adult colonoscope '
         'was advanced to the cecum, confirmed by the appendiceal orifice, and the terminal ileum was intubated. A 12 mm '
         'transverse colon polyp was removed with a cold snare.')
D2, TI = 'second part of duodenum', 'terminal ileum'


def report(*parts: str, procedures: str = PROCEDURES, head: str = BIDIRECTIONAL) -> str:
    return SYNTHETIC + head + procedures + INDICATIONS + '\n\n'.join(parts) + '\n\nImpression\nSee above.\n'


def forms(text: str) -> dict[str, str]:
    """The text, its DOCX paragraphs (no blank lines) and its PDF lines (wrapped at 90 characters)."""
    return {'text': text, 'docx': '\n'.join(line for line in text.split('\n') if line.strip()) + '\n',
            'pdf': '\n'.join(docgen._wrapped(text.rstrip('\n'), 90)) + '\n'}


def facts(text: str, family: str) -> dict:
    found = route(text, DAY).finding(family)
    return {} if found is None else {item.name: item.value for item in found.facts}


def extent(text: str, family: str = 'gi.colonoscopy'):
    return facts(text, family).get('extent')


class ServiceHeadingEndsAnIndicationTests(unittest.TestCase):
    """R-A: the ho-01 shape, and the spellings of a service heading."""

    def test_each_service_part_is_read_in_every_form(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\n' + COLON)
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant, 'gi.egd'), D2)
                self.assertEqual(extent(variant), TI)
                if form != 'pdf':  # the PDF wrap cuts "cold" / "snare", which no tree reads across a line (installed too)
                    self.assertIn('cold snare', facts(variant, 'gi.colonoscopy').get('interventions', ''))

    def test_the_indication_ends_at_the_service_heading(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\n' + COLON)
        found = [(s.kind, s.label) for s in sections.layout(text).sections]
        self.assertIn(('indication', 'indications'), found)
        self.assertIn(('other', 'upper endoscopy'), found)
        self.assertIn(('other', 'colonoscopy'), found)
        part = next(s for s in sections.layout(text).sections if s.label == 'colonoscopy')
        self.assertTrue(text[part.start:part.end].startswith('Colonoscopy\nWith the patient'))

    def test_heading_spellings(self):
        for egd, colon in [('UPPER ENDOSCOPY', 'COLONOSCOPY'), ('Esophagogastroduodenoscopy (EGD)', 'Colonoscopy'),
                           ('**Upper Endoscopy**', '**Colonoscopy**'), ('## Upper Endoscopy', '## Colonoscopy')]:
            text = report(egd + '\n' + EGD, colon + '\n' + COLON)
            with self.subTest(egd=egd):
                self.assertEqual(extent(text, 'gi.egd'), D2)
                self.assertEqual(extent(text), TI)

    def test_a_report_title_names_its_service(self):
        text = SYNTHETIC + COLON_REPORT + 'Indications\nPositive FIT.\n\nColonoscopy\n' + COLON + '\n'
        self.assertEqual(extent(text), TI)

    def test_an_indication_answered_on_its_own_line(self):
        text = SYNTHETIC + COLON_REPORT + 'Indication: positive FIT.\nColonoscopy\n' + COLON + '\n'
        self.assertEqual(extent(text), TI)

    def test_a_today_word_under_a_later_heading_stops_nothing(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\n' + COLON).replace(
            'Impression\nSee above.', 'Impression\nBoth procedures were completed today.')
        self.assertEqual(extent(text, 'gi.egd'), D2)
        self.assertEqual(extent(text), TI)


class ServiceHeadingControlsTests(unittest.TestCase):
    """R-A controls: where a stand-alone service name must leave the indication as installed."""

    def test_a_report_that_names_neither_service_as_its_own(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\n' + COLON, procedures='\n')
        self.assertIsNone(extent(text, 'gi.egd'))
        self.assertIsNone(extent(text))

    def test_an_office_reason_for_visit_over_a_pasted_report(self):
        text = (SYNTHETIC + OFFICE + 'Reason for visit\nFollow-up after upper endoscopy.\nEGD\nThe gastroscope was advanced '
                'to the second portion of the duodenum. Biopsies showed eosinophilic esophagitis.\n\nAssessment and plan\n'
                'Start topical steroid.\n')
        self.assertIsNone(extent(text, 'gi.egd'))
        self.assertNotIn('interventions', facts(text, 'gi.egd'))

    def test_an_undeclared_service_part_goes_back_to_the_indication(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\n' + COLON,
                      procedures='Procedures: Upper endoscopy with biopsies.\n\n', head=UPPER_REPORT)
        self.assertEqual(extent(text, 'gi.egd'), D2)
        self.assertIsNone(extent(text))

    def test_an_intent_under_the_heading_stays_the_indications(self):
        text = (SYNTHETIC + COLON_REPORT + 'Indications\nAverage-risk patient, age 52, no prior colonoscopy.\nColonoscopy\n'
                'Screening.\nThe colonoscope was advanced to the cecum and the terminal ileum was intubated.\n')
        self.assertEqual(facts(text, 'gi.colonoscopy').get('intent'), 'screening')
        self.assertIsNone(extent(text))

    def test_an_indication_organised_by_service_sub_headings(self):
        text = (SYNTHETIC + COLON_REPORT + 'Indications\nColonoscopy\nScreening, average risk.\n\nThe colonoscope was '
                'advanced to the cecum. No polyps.\n')
        self.assertEqual(facts(text, 'gi.colonoscopy').get('intent'), 'screening')
        self.assertIsNone(extent(text))

    def test_an_indication_that_opens_with_a_service_sub_heading(self):
        # what its sub-headings head is the indication's, a past procedure's narrative too
        text = (SYNTHETIC + COLON_REPORT + 'Indications\nColonoscopy\nThe colonoscope was advanced to the cecum and two '
                'adenomas were removed.\nEGD\nDysphagia.\n')
        self.assertIsNone(extent(text))

    def test_an_undated_prior_report_before_the_procedure_section(self):
        text = (SYNTHETIC + COLON_REPORT + 'Indications\nSurveillance.\nColonoscopy\nThe colonoscope was advanced to the cecum '
                'and two adenomas were removed.\n\nProcedure\nThe colonoscope was advanced to the hepatic flexure, where '
                'looping stopped it. The cecum was not reached.\n')
        self.assertEqual(extent(text), 'incomplete: hepatic flexure')

    def test_a_part_that_marks_its_todays_statements(self):
        text = (SYNTHETIC + COLON_REPORT + 'Indications\nSurveillance.\nColonoscopy\nThe colonoscope was advanced to the cecum '
                'and two adenomas were removed.\nToday the colonoscope was advanced to the transverse colon. The cecum was '
                'not reached.\n')
        self.assertEqual(extent(text), 'incomplete: transverse colon')

    def test_a_today_marked_second_part_keeps_the_first_part_read(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\nThe colonoscope was advanced to the cecum and two adenomas '
                      'were removed.\nToday the colonoscope was advanced to the transverse colon. The cecum was not reached.')
        self.assertEqual(extent(text, 'gi.egd'), D2)
        self.assertEqual(extent(text), 'incomplete: transverse colon')

    def test_a_findings_heading_after_the_service_heading(self):
        text = report('Upper Endoscopy\n' + EGD, 'Colonoscopy\n' + COLON).replace('Impression\nSee above.',
                                                                                    'Findings: one polyp.')
        self.assertIsNone(extent(text, 'gi.egd'))
        self.assertIsNone(extent(text))

    def test_lines_that_are_no_service_heading(self):
        for line in ('1. Colonoscopy', '- Colonoscopy', 'Colonoscopy (not performed)', 'Colonoscopy with biopsy',
                     'EGD and Colonoscopy'):
            text = report(line + '\n' + COLON)
            with self.subTest(line=line):
                self.assertIsNone(extent(text))

    def test_a_service_line_that_continues_the_line_before(self):
        text = (SYNTHETIC + COLON_REPORT + 'Indications\nIron deficiency anemia, referred for an upper endoscopy and a\n'
                'colonoscopy\nafter a positive FIT.\nThe colonoscope was advanced to the cecum.\n')
        self.assertIsNone(extent(text))

    def test_plan_and_history_items_keep_their_section(self):
        planned = (SYNTHETIC + OFFICE + 'History of present illness\nIron deficiency anemia.\n\nPlan\nColonoscopy\nThe '
                   'colonoscope will be advanced to the cecum with biopsies as needed.\n')
        self.assertIsNone(extent(planned))
        prior = (SYNTHETIC + COLON_REPORT + 'Prior procedures\nColonoscopy\nThe colonoscope was advanced to the cecum and two '
                 'adenomas were removed.\n\nProcedure\nThe colonoscope was advanced to the transverse colon, where a '
                 'stricture stopped it. The cecum was not reached.\n')
        self.assertEqual(extent(prior), 'incomplete: transverse colon')


class ReachToADepthTests(unittest.TestCase):
    """R-B1: the ho-03 shape and its relatives."""

    def test_the_stricture_report_in_every_form(self):
        text = (SYNTHETIC + COLON_REPORT + 'Procedure\nThe pediatric colonoscope was advanced to 28 cm from the anal verge in '
                'the sigmoid colon, where a circumferential stricture was found. The colonoscope could not be passed through '
                'the stricture.\n')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant), 'incomplete: sigmoid colon')

    def test_depth_reaches_that_stop_there(self):
        cases = {
            'The colonoscope could only be advanced to 40 cm in the descending colon because of a fixed angulation.':
                'incomplete: descending colon',
            'The colonoscope was advanced to 25 cm in the sigmoid colon, but the patient became hypoxic and the '
            'examination was aborted.': 'incomplete: sigmoid colon',
            'We advanced the pediatric colonoscope to 28 cm, in the sigmoid colon, where a stricture stopped it.':
                'incomplete: sigmoid colon',
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence[:40]):
                self.assertEqual(extent(SYNTHETIC + COLON_REPORT + 'Procedure\n' + sentence + '\n'), expected)

    def test_an_upper_depth_reach(self):
        text = (SYNTHETIC + UPPER_REPORT + 'Procedure\nThe gastroscope was advanced to 38 cm from the incisors in the distal '
                'esophagus, where a tight stricture prevented further passage. The stomach and duodenum were not '
                'examined.\n')
        self.assertEqual(extent(text, 'gi.egd'), 'incomplete: esophagus')

    def test_controls(self):
        none = [
            # a waypoint whose onward reach no cue reads (the guard): no extent, as installed
            'The colonoscope was passed to 20 cm in the sigmoid colon where a polyp was found, and then to the cecum.',
            'The colonoscope was advanced to 30 cm in the sigmoid colon. Beyond this point, the examination continued to '
            'the cecum without difficulty.',
            # denied, planned, hedged
            'The colonoscope was not advanced to 40 cm in the descending colon because the preparation was poor.',
            'Unable to advance the colonoscope to 25 cm in the sigmoid colon; the examination was aborted.',
            'The colonoscope will be advanced to 40 cm in the descending colon at the next session.',
            'The colonoscope was possibly advanced to 28 cm in the sigmoid colon.',
            # a reach that is no endoscope's
            'Colonoscopy was performed. A guidewire was advanced to 28 cm in the sigmoid colon.',
        ]
        for sentence in none:
            with self.subTest(sentence=sentence[:50]):
                self.assertIsNone(extent(SYNTHETIC + COLON_REPORT + 'Procedure\n' + sentence + '\n'))
        kept = {
            'The colonoscope was advanced to the cecum. A 6 mm polyp at 28 cm in the sigmoid colon was removed with a '
            'cold snare.': 'cecum',
            'The colonoscope was advanced to the cecum. On withdrawal the scope was at 28 cm in the sigmoid colon where a '
            'polyp was removed.': 'cecum',
            'The colonoscope was inserted to 15 cm in the rectum and advanced to the cecum.': 'cecum',
        }
        for sentence, expected in kept.items():
            with self.subTest(sentence=sentence[:50]):
                self.assertEqual(extent(SYNTHETIC + COLON_REPORT + 'Procedure\n' + sentence + '\n'), expected)
        history = (SYNTHETIC + COLON_REPORT + 'History\nAt the prior colonoscopy the scope was advanced only to 28 cm in the '
                   'sigmoid colon.\n\nProcedure\nThe colonoscope was advanced to the cecum and the terminal ileum was '
                   'intubated.\n')
        self.assertEqual(extent(history), TI)

    def test_a_denied_reach_to_a_depth_is_blocked(self):
        # installed: the denied clause's "into the" / "at the level of the" read as a reach (the denial read first now)
        aborted = ('The colonoscope was inserted into the rectum. It could not be advanced to 30 cm, into the sigmoid colon, '
                   'and the examination was aborted.')
        self.assertEqual(extent(SYNTHETIC + COLON_REPORT + 'Procedure\n' + aborted + '\n'), 'incomplete: rectum')
        short = ('The colonoscope was advanced to the descending colon. It could not be advanced to 60 cm at the level of '
                 'the transverse colon. The cecum was not reached.')
        self.assertEqual(extent(SYNTHETIC + COLON_REPORT + 'Procedure\n' + short + '\n'), 'incomplete: descending colon')

    def test_an_accessorys_depth_is_no_extent(self):
        text = (SYNTHETIC + UPPER_REPORT + 'Procedure\nUpper endoscopy was performed. Normal duodenum. A balloon was advanced '
                'to 35 cm in the distal esophagus and the stricture was dilated to 15 mm.\n')
        self.assertIsNone(extent(text, 'gi.egd'))

    def test_each_service_keeps_its_own_landmark(self):
        text = (SYNTHETIC + BIDIRECTIONAL + '\nProcedure\nUpper endoscopy: the gastroscope was advanced to 38 cm from the '
                'incisors in the distal esophagus, where a tight stricture prevented further passage.\nColonoscopy: the '
                'colonoscope was advanced to the cecum, confirmed by the appendiceal orifice.\n')
        self.assertEqual(extent(text, 'gi.egd'), 'incomplete: esophagus')
        self.assertEqual(extent(text), 'cecum')


class DepthInALabelValueTests(unittest.TestCase):
    """R-B2: ho-03's extent label, and labels whose value must stay unread."""

    def label(self, value: str, before: str = 'A stricture stopped the colonoscope.') -> str:
        return SYNTHETIC + COLON_REPORT + 'Procedure\n' + before + '\n' + value + '\n'

    def test_a_depth_that_opens_the_value(self):
        cases = {'Extent reached: sigmoid colon at 28 cm. The cecum was not reached.': 'incomplete: sigmoid colon',
                 'Extent: descending colon (35 cm). The cecum was not reached.': 'incomplete: descending colon',
                 'Extent: sigmoid colon, 28 cm from the anal verge. The cecum was not reached.': 'incomplete: sigmoid colon',
                 'Extent: sigmoid colon at 28 cm; the cecum could not be reached.': 'incomplete: sigmoid colon',
                 'Extent: sigmoid colon at 28 cm | Prep quality: Good\nThe cecum was not reached.': 'incomplete: sigmoid colon'}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(extent(self.label(value)), expected)

    def test_values_that_stay_unread(self):
        # an aim, a reason after the depth, and a depth after another landmark: read as installed
        aim = self.label('Extent: cecum at 80 cm (intended). The cecum was not reached.',
                         'The colonoscope was advanced to the sigmoid colon, where a stricture stopped it.')
        self.assertEqual(extent(aim), 'incomplete: sigmoid colon')
        self.assertIsNone(extent(self.label('Extent: sigmoid colon at 28 cm (stricture). The cecum was not reached.')))
        self.assertIsNone(extent(self.label('Extent: transverse colon at 60 cm and cecum at 85 cm.',
                                            'The examination was difficult.')))


class CostTests(unittest.TestCase):
    """The repair reads each part under a service heading once, and each depth reach against one sorted list."""

    def test_many_service_lines_in_one_indication(self):
        lines = ''.join('Colonoscopy\nScreening.\nThe colonoscope was advanced to the cecum today.\n' for _ in range(3000))
        text = SYNTHETIC + COLON_REPORT + 'Indications\nPositive FIT.\n' + lines
        started = time.perf_counter()
        sections.layout(text)
        self.assertLess(time.perf_counter() - started, 20.0)

    def test_many_depth_reaches(self):
        reaches = ' '.join('The colonoscope was advanced to 28 cm in the sigmoid colon.' for _ in range(2000))
        text = SYNTHETIC + COLON_REPORT + 'Procedure\n' + reaches + ' The descending colon was normal.\n'
        started = time.perf_counter()
        route(text, DAY)
        self.assertLess(time.perf_counter() - started, 60.0)


if __name__ == '__main__':
    unittest.main()
