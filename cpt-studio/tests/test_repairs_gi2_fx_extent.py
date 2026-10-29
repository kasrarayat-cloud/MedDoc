"""Session 7c8d38da, GI round 2, fix round (extent): the refutation lens "extent" found six regressions of the round's
extent repair (tests/test_repairs_gi2_extent.py) against the integrated head b8cc7b5b5. Each is narrowed toward the
installed reading (2b82889f): a statement that may be another occurrence's is held, never read as today's.
Synthetic data only; routing is a pure function (no database, no provider).

- EXT-R1 (studio/gi/sections.py): a narrative under a service's stand-alone heading inside an indication was released
  as today's report although today's report followed under a later heading of another kind ("Today:", "Examination",
  "Impression", "Results:" ...). A later heading whose section narrates an examination's course (cues.STARTED), or whose
  own label says today, now keeps the part held.
- EXT-R2 (sections.py): a released part ran over a plain line ("Comparison with the prior report", "Colonoscopy on
  2026-10-20") into a second narrative. A label-like line standing between two statements of what was done, or a
  landmark the part both reaches and denies (or that later text denies), now keeps the part held.
- EXT-R3 (sections.py): an intent clause after the performance statement left the indication and was lost. A part
  that states an intent anywhere is no longer released.
- EXT-R4 (studio/gi/detect.py): a reach to a depth was read as the extent although a deeper landmark of the same family
  was named before it ("Normal stomach and duodenum. The endoscope was then passed to 35 cm in the distal esophagus").
  A deeper landmark named anywhere in the family's text now makes the depth a waypoint.
- EXT-R5 (detect.py): a dated earlier reach to a depth escaped the time hold its plain twin gets, because the date stands
  further from the landmark. The depth itself must read as today's too; and a reach to a depth beyond a landmark the
  family's text says could not be passed is no extent.
- EXT-R6 (studio/gi/cues.py): adverbs saying the advance failed or fell short ("unsuccessfully", "ineffectively",
  "partially", "hardly") passed as auxiliaries. They are no longer auxiliaries; the failing ones are read by the denial
  twin.
- A3 (the lens's observation; sections.py): a procedure line naming an earlier occurrence ("Procedures: Colonoscopy 2019
  (tubular adenoma).", "prior colonoscopy", "Colonoscopy on 03/14/2024") declared that service as the report's own.

Every expectation below is the installed reading of the same input unless the test says otherwise."""
import unittest
from datetime import date

from studio.gi import sections
from studio.gi.detect import route
from tests.support import docgen

SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\n'
DAY = date(2026, 10, 20)
COLON_REPORT = ('Colonoscopy Report\nDate of procedure: 2026-10-20\n'
                'Place of service: Ambulatory surgery center (ASC), POS 24\n\n')
UPPER_REPORT = ('Upper Endoscopy Report\nDate of procedure: 2026-10-20\n'
                'Place of service: Ambulatory surgery center (ASC), POS 24\n\n')
BIDIRECTIONAL = ('Bidirectional Endoscopy Report\nDate of procedure: 2026-10-20\n'
                 'Place of service: Ambulatory surgery center (ASC), POS 24\n')
OFFICE = ('Gastroenterology Office Visit\nDate of service: 2026-10-20\nPlace of service: Office (POS 11)\n'
          'Visit type: Established patient.\n\n')
PRIOR = 'The colonoscope was advanced to the cecum and two adenomas were removed with a cold snare.'
HEPATIC = 'The colonoscope was advanced to the hepatic flexure, where looping stopped it. The cecum was not reached.'
STRICTURE = 'The colonoscope was advanced to the transverse colon, where a stricture stopped it. The cecum was not reached.'
EMR = 'The colonoscope was advanced to the cecum and a 25 mm polyp was removed by endoscopic mucosal resection.'
D2, TI = 'second part of duodenum', 'terminal ileum'


def forms(text: str) -> dict[str, str]:
    """The text, its DOCX paragraphs (no blank lines) and its PDF lines (wrapped at 90 characters)."""
    return {'text': text, 'docx': '\n'.join(line for line in text.split('\n') if line.strip()) + '\n',
            'pdf': '\n'.join(docgen._wrapped(text.rstrip('\n'), 90)) + '\n'}


def finding(text: str, family: str):
    return route(text, DAY).finding(family)


def facts(text: str, family: str = 'gi.colonoscopy') -> dict:
    found = finding(text, family)
    return {} if found is None else {item.name: item.value for item in found.facts}


def extent(text: str, family: str = 'gi.colonoscopy'):
    return facts(text, family).get('extent')


def interventions(text: str, family: str = 'gi.colonoscopy') -> str:
    return facts(text, family).get('interventions') or ''


def colon_report(indication: str, *parts: str) -> str:
    return (SYNTHETIC + COLON_REPORT + 'Procedures: Colonoscopy.\n\nIndications\n' + indication + '\n\nColonoscopy\n'
            + '\n'.join(parts) + '\n')


def procedure(sentence: str, head: str = COLON_REPORT) -> str:
    return SYNTHETIC + head + 'Procedure\n' + sentence + '\n'


class TodaysReportUnderALaterHeadingTests(unittest.TestCase):
    """EXT-R1: today's report under a later heading of a kind other than procedure, findings or technique."""

    HEADINGS = ('Examination', 'Exam:', 'Today:', 'Current examination:', 'Report:', 'Narrative:', 'Course:',
                'Endoscopic description:', 'Colonoscopy narrative:', 'Procedure summary:', 'Results:', 'Summary',
                'Impression')
    INDICATIONS = ('Surveillance. The previous report is reproduced below.',
                   'Surveillance after adenomas removed in 2023 (report below).', 'Surveillance after adenomas.')

    def text(self, heading: str, indication: str, narrative: str = HEPATIC) -> str:
        return (colon_report(indication, PRIOR) + '\n' + heading + '\n' + narrative
                + '\n\nPlan\nRepeat with a pediatric colonoscope.\n')

    def test_every_later_heading_keeps_the_earlier_narrative_held(self):
        for heading in self.HEADINGS:
            for indication in self.INDICATIONS:
                for form, variant in forms(self.text(heading, indication)).items():
                    with self.subTest(heading=heading, indication=indication[:20], form=form):
                        self.assertEqual(extent(variant), 'incomplete: hepatic flexure')
                        self.assertNotIn('cold snare', interventions(variant))

    def test_a_today_heading_over_a_narrative_that_names_no_course(self):
        # the heading's own label says today; its section says nothing of the instrument's course
        text = self.text('Today:', 'Surveillance after adenomas.',
                         'Looping stopped the examination at the hepatic flexure; the cecum was not reached.')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertNotEqual(extent(variant), 'cecum')
                self.assertNotIn('cold snare', interventions(variant))

    def test_a_later_section_that_denies_the_parts_landmark(self):
        # no course statement after the part, but a later section says the landmark the part reaches was not reached
        text = self.text('Comment:', 'Surveillance after adenomas.',
                         'Looping stopped the examination; the cecum was not reached.')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))
                self.assertNotIn('cold snare', interventions(variant))

    def test_a_later_course_alone(self):
        # no denial and no today's heading after the part: only the later section's course says it is another account
        for heading in ('Examination', 'Results:', 'Impression'):
            text = self.text(heading, 'Surveillance after adenomas.',
                             'The colonoscope was advanced to the hepatic flexure, where looping stopped it.')
            for form, variant in forms(text).items():
                with self.subTest(heading=heading, form=form):
                    self.assertEqual(extent(variant), 'incomplete: hepatic flexure')
                    self.assertNotIn('cold snare', interventions(variant))

    def test_a_later_act_outside_a_summary(self):
        # no course, denial or today's heading: a later section that is no summary reports an act of its own
        for heading in ('Results:', 'Examination', 'Report:', 'Comment:'):
            text = self.text(heading, 'Surveillance after adenomas.', 'One adenoma was removed with a hot snare.')
            for form, variant in forms(text).items():
                with self.subTest(heading=heading, form=form):
                    self.assertIsNone(extent(variant))
                    self.assertNotIn('cold snare', interventions(variant))

    def test_a_later_summary_or_statement_keeps_the_part_read(self):
        # an impression or assessment restates the outcome; "None." and "tolerated the procedure" state no act
        for heading, body in (('Impression', 'Two adenomas were removed.'), ('Assessment', 'Two adenomas were removed.'),
                              ('Complications', 'None. Estimated blood loss minimal.'),
                              ('Disposition', 'The patient tolerated the procedure well.')):
            text = self.text(heading, 'Surveillance after adenomas.', body)
            for form, variant in forms(text).items():
                with self.subTest(heading=heading, form=form):
                    self.assertEqual(extent(variant), 'cecum')
                    self.assertIn('cold snare', interventions(variant))

    def test_a_today_heading_alone(self):
        # neither a course nor a denial after the part: only the heading's own "Today" says the part is another time's
        text = self.text('Today:', 'Surveillance after adenomas.', 'Looping stopped the examination at the hepatic flexure.')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))
                self.assertNotIn('cold snare', interventions(variant))

    def test_a_size_under_a_later_heading_is_no_course(self):
        # "of 2 cm" is a size, not the instrument's course: the part stays read (the round's gain)
        text = colon_report('Positive FIT.', 'The colonoscope was advanced to the cecum and a 20 mm polyp was removed with '
                            'a cold snare.') + '\nImpression\nA polyp of 2 cm was removed.\n'
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant), 'cecum')
                self.assertIn('cold snare', interventions(variant))


class APartThatRunsOverAnotherAccountTests(unittest.TestCase):
    """EXT-R2: a part that runs over a plain line into a second account of the examination."""

    LINES = ('Comparison with the prior report', 'Prior colonoscopy for comparison', 'Previous report (2021)',
             'For reference, the 2021 report', 'Earlier examination')

    def test_a_label_line_between_two_accounts(self):
        for line in self.LINES:
            text = colon_report('Surveillance after a large polyp.', STRICTURE, line, EMR) + \
                '\nImpression\nStricture in the transverse colon.\n'
            for form, variant in forms(text).items():
                with self.subTest(line=line, form=form):
                    self.assertIsNone(extent(variant))
                    self.assertNotIn('EMR', interventions(variant))

    def test_a_dated_service_line_between_two_accounts(self):
        text = colon_report('Surveillance after adenomas.', PRIOR, 'Colonoscopy on 2026-10-20', HEPATIC)
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))
                self.assertNotIn('cold snare', interventions(variant))

    def test_a_landmark_the_part_both_denies_and_reaches(self):
        # no line between the two accounts: the part says the cecum was not reached, then that it was
        text = colon_report('Surveillance after a large polyp.', STRICTURE + ' ' + EMR) + \
            '\nImpression\nStricture in the transverse colon.\n'
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))
                self.assertNotIn('EMR', interventions(variant))

    def test_a_landmark_reached_then_denied_in_the_part(self):
        text = colon_report('Surveillance.', 'In 2023 the colonoscope was advanced to the cecum and two adenomas were '
                            'removed.', 'Now the colonoscope was advanced to the transverse colon. The cecum was not '
                            'reached.') + '\nImpression\nIncomplete.\n'
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))

    def test_a_denial_wrapped_over_two_lines(self):
        # the PDF form writes "The cecum was not" / "reached." on two lines: read as the other forms are
        text = colon_report('Surveillance.', 'Previously the colonoscope was advanced to the cecum and two adenomas were '
                            'removed.', 'At this procedure the colonoscope was advanced to the transverse colon. The cecum '
                            'was not reached.') + '\nImpression\nIncomplete.\n'
        self.assertIn('was not\nreached', forms(text)['pdf'])
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))

    def test_a_label_line_between_two_accounts_that_agree(self):
        # no landmark both reached and denied: only the line between the two accounts holds the part
        text = colon_report('Surveillance after a large polyp.', 'The colonoscope was advanced to the transverse colon, '
                            'where a stricture stopped it.', 'Comparison with the prior report', 'The colonoscope was '
                            'advanced to the ascending colon and a 25 mm polyp was removed by endoscopic mucosal '
                            'resection.') + '\nImpression\nStricture in the transverse colon.\n'
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))
                self.assertNotIn('EMR', interventions(variant))

    def test_two_parts_of_one_service(self):
        text = colon_report('Surveillance after adenomas.', PRIOR, 'Colonoscopy', 'The colonoscope was advanced to the '
                            'hepatic flexure, where looping stopped it.') + '\nImpression\nIncomplete examination.\n'
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))
                self.assertNotIn('cold snare', interventions(variant))


class AnIntentInThePartTests(unittest.TestCase):
    """EXT-R3: a part that states an intent stays the indication's, where the intent reader reads it."""

    def test_an_intent_after_the_performance_statement(self):
        cases = {
            'This was a screening examination.': 'screening',
            'Screening.': 'screening',
            'Indication for the examination: surveillance.': 'surveillance',
        }
        for clause, intent in cases.items():
            text = (SYNTHETIC + COLON_REPORT + 'Procedures: Colonoscopy with cold snare polypectomy.\n\nIndications\nAge 55, '
                    'no symptoms, no prior colonoscopy.\n\nColonoscopy\nThe colonoscope was advanced to the cecum. A 6 mm '
                    'polyp was removed with a cold snare. ' + clause + '\n\nImpression\nOne polyp removed.\n')
            for form, variant in forms(text).items():
                with self.subTest(clause=clause, form=form):
                    self.assertEqual(facts(variant).get('intent'), intent)
                    self.assertIn('cold snare', interventions(variant))

    def test_an_intent_on_a_line_after_the_narrative(self):
        for tail in (' This was a screening examination.', '\nScreening.'):
            text = (SYNTHETIC + COLON_REPORT + 'Procedures: Colonoscopy.\n\nIndications\nAge 55, no symptoms.\n\n'
                    'Colonoscopy\nThe colonoscope was advanced to the cecum and the terminal ileum was intubated.' + tail
                    + '\n\nImpression\nNormal.\n')
            for form, variant in forms(text).items():
                with self.subTest(tail=tail, form=form):
                    self.assertEqual(facts(variant).get('intent'), 'screening')


class ADeeperLandmarkNamedFirstTests(unittest.TestCase):
    """EXT-R4: a deeper landmark the family's text names before the reach to a depth makes the depth a waypoint."""

    def test_the_depth_after_an_examined_duodenum_is_no_extent(self):
        cases = [
            'Esophagogastroduodenoscopy was performed for variceal screening. Normal stomach and duodenum. The endoscope '
            'was then passed to 35 cm in the distal esophagus and four bands were placed on large varices.',
            'Upper endoscopy was performed. Normal duodenum and stomach. The gastroscope was advanced to 38 cm from the '
            'incisors in the distal esophagus to mark the site for the pH capsule.',
            'Upper endoscopy was performed with a normal duodenum. The pH capsule was attached and the delivery scope was '
            'advanced to 32 cm in the distal esophagus.',
        ]
        for sentence in cases:
            for form, variant in forms(procedure(sentence, UPPER_REPORT)).items():
                with self.subTest(sentence=sentence[:40], form=form):
                    found = finding(variant, 'gi.egd')
                    self.assertEqual(found.status, 'performed')
                    self.assertIsNone(extent(variant, 'gi.egd'))

    def test_a_withdrawal_depth_after_the_cecum(self):
        text = procedure('The colonoscope was advanced to the cecum. On withdrawal the colonoscope was then passed to 30 cm '
                         'in the sigmoid colon, where a polyp was removed with a cold snare.')
        self.assertEqual(extent(text), 'cecum')


class ADatedOrShorterReachToADepthTests(unittest.TestCase):
    """EXT-R5: a reach to a depth that the text dates to an earlier occurrence, or that lies beyond a landmark the text
    says could not be passed, is no extent."""

    def test_a_dated_reach_to_a_depth(self):
        for sentence in ('The colonoscope was inserted into the rectum and could not pass the rectosigmoid. In 2024 the '
                         'colonoscope was advanced to 60 cm in the transverse colon.',
                         'The colonoscope was inserted into the rectum and could not pass the rectosigmoid. In 2024 the '
                         'colonoscope was advanced to the transverse colon.'):
            for form, variant in forms(procedure(sentence)).items():
                with self.subTest(sentence=sentence[-50:], form=form):
                    self.assertEqual(extent(variant), 'incomplete: rectum')

    def test_a_dated_reach_with_no_denial_beside_it(self):
        # the depth's own reading holds it where no shallower denial does
        text = procedure('The colonoscope was inserted into the rectum. In 2024 the colonoscope was advanced to 60 cm in '
                         'the transverse colon.')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertIsNone(extent(variant))

    def test_an_earlier_occasion_named_before_the_reach(self):
        # no time cue within a date's reach of the depth or the landmark: the reach's clause names the earlier occasion
        for opening in ('At the previous attempt the colonoscope was advanced',
                        'At the previous examination the colonoscope was advanced',
                        'In 2024 the pediatric variable-stiffness colonoscope was carefully advanced',
                        'Last year the pediatric variable-stiffness colonoscope was carefully advanced'):
            text = procedure('The colonoscope was inserted into the rectum. ' + opening + ' to 60 cm in the transverse '
                             'colon.')
            for form, variant in forms(text).items():
                with self.subTest(opening=opening[:30], form=form):
                    self.assertIsNone(extent(variant))

    def test_a_reach_whose_clause_is_the_days(self):
        # the day's own date, a manoeuvre, or a second scope past the first one's stop: the reach stays read
        cases = {
            'On 2026-10-20 the colonoscope was advanced to 40 cm in the descending colon, where a stricture stopped it.':
                'incomplete: descending colon',
            'With abdominal pressure the colonoscope was advanced to 40 cm in the descending colon, where a stricture '
            'stopped it.': 'incomplete: descending colon',
            'The colonoscope could not be passed beyond the sigmoid colon with the adult scope; the pediatric colonoscope '
            'was advanced to 60 cm in the transverse colon, where a mass stopped it.': 'incomplete: transverse colon',
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence[:40]):
                self.assertEqual(extent(procedure(sentence)), expected)

    def test_a_reach_beyond_a_landmark_that_could_not_be_passed(self):
        text = procedure('The colonoscope was inserted into the rectum. At the previous attempt the colonoscope was '
                         'advanced to 60 cm in the transverse colon. Today it could not pass the rectosigmoid.')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant), 'incomplete: rectum')
        # no word, date or time cue names another occasion: only the stop says the reach is not this examination's
        unmarked = {
            'The colonoscope was inserted into the rectum and could not pass the rectosigmoid. The colonoscope was then '
            'advanced to 60 cm in the transverse colon.': 'incomplete: rectum',
            'The colonoscope could not be advanced into the sigmoid colon. The colonoscope was advanced to 60 cm in the '
            'transverse colon, where a mass stopped it.': None,
        }
        for sentence, expected in unmarked.items():
            for form, variant in forms(procedure(sentence)).items():
                with self.subTest(sentence=sentence[:40], form=form):
                    self.assertEqual(extent(variant), expected)


class AFailingAdverbTests(unittest.TestCase):
    """EXT-R6: an adverb saying the advance failed or fell short is no auxiliary of a reach to a depth."""

    def test_a_failed_advance_is_no_reach(self):
        cases = {
            'The colonoscope was unsuccessfully advanced to 30 cm in the sigmoid colon because of a fixed angulation; the '
            'rectum was examined.': 'incomplete: rectum',
            'The colonoscope was inserted into the rectum. The pediatric colonoscope was unsuccessfully advanced to 30 cm '
            'in the sigmoid colon; a fixed angulation prevented passage.': None,
            'The colonoscope was inserted into the rectum. The colonoscope was ineffectively advanced to 30 cm in the '
            'sigmoid colon owing to looping, and the examination ended.': None,
        }
        for sentence, expected in cases.items():
            for form, variant in forms(procedure(sentence)).items():
                with self.subTest(sentence=sentence[:60], form=form):
                    self.assertEqual(extent(variant), expected)

    def test_an_advance_that_fell_short_is_held(self):
        for adverb in ('partially', 'incompletely', 'hardly', 'barely', 'nearly', 'scarcely', 'inadequately'):
            text = procedure(f'The colonoscope was {adverb} advanced to 30 cm in the sigmoid colon and the examination was '
                             'terminated.')
            with self.subTest(adverb=adverb):
                self.assertIsNone(extent(text))

    def test_other_adverbs_still_read_the_reach(self):
        for adverb in ('successfully', 'carefully', 'repeatedly', 'only', 'then gently'):
            text = procedure(f'The colonoscope was {adverb} advanced to 30 cm in the sigmoid colon, where a stricture '
                             'stopped it.')
            with self.subTest(adverb=adverb):
                self.assertEqual(extent(text), 'incomplete: sigmoid colon')

    def test_the_active_form(self):
        failed = procedure('We unsuccessfully advanced the colonoscope to 30 cm in the sigmoid colon because of a fixed '
                           'angulation.')
        self.assertIsNone(extent(failed))
        plain = procedure('We advanced the colonoscope to 30 cm in the sigmoid colon, where a stricture stopped it.')
        self.assertEqual(extent(plain), 'incomplete: sigmoid colon')


class AProcedureLineNamingAnotherOccurrenceTests(unittest.TestCase):
    """The lens's A3 observation: a procedure line that names an earlier occurrence declares no service of today's."""

    def test_an_office_note_over_a_pasted_report(self):
        for line in ('Procedures: Colonoscopy 2019 (tubular adenoma).', 'Procedures: prior colonoscopy with polypectomy.',
                     'Procedure: Colonoscopy on 03/14/2024 by Dr. Synthetic.'):
            text = (SYNTHETIC + OFFICE + line + '\n\nReason for visit\nFollow-up of iron deficiency anemia; her colonoscopy '
                    'report is pasted below.\nColonoscopy\nThe colonoscope was advanced to the cecum. A 6 mm polyp was '
                    'removed with a cold snare.\n\nAssessment and plan\nContinue iron.\n')
            with self.subTest(line=line):
                self.assertIsNone(extent(text))
                self.assertNotIn('cold snare', interventions(text))

    def test_one_service_dated_and_one_todays(self):
        text = (SYNTHETIC + UPPER_REPORT + 'Procedures: Upper endoscopy with biopsies; colonoscopy (2024).\n\nIndications\n'
                'Dysphagia. Her colonoscopy is summarized below.\nColonoscopy\nThe colonoscope was advanced to the cecum. '
                'Three adenomas were removed with a cold snare.\nUpper Endoscopy\nThe gastroscope was advanced to the second '
                'portion of the duodenum. Biopsies were taken.\n\nImpression\nSee above.\n')
        self.assertEqual(extent(text, 'gi.egd'), D2)
        self.assertIsNone(extent(text))
        self.assertNotIn('cold snare', interventions(text))


class TheRoundsGainsStayTests(unittest.TestCase):
    """What the round's extent repair reads and the narrowing keeps: ho-01's shape with its nursing checklist and
    later sections, ho-03's stricture, and a part whose plan-like sentence is the indication's business."""

    HO01 = (SYNTHETIC + BIDIRECTIONAL + 'Procedures: Esophagogastroduodenoscopy with biopsies; colonoscopy with cold snare '
            'polypectomy, biopsies of a separate lesion and submucosal tattoo.\nIndications\nIron deficiency anemia, '
            'referred for upper and lower endoscopic evaluation.\nConsent and Preparation\nThe risks were explained, and '
            'written consent was obtained.\nUpper Endoscopy\nThe gastroscope was passed through the mouth under direct '
            'vision and advanced to the second portion of the duodenum. The esophagus was normal. Cold forceps biopsies '
            'were taken from the antrum.\nColonoscopy\nThe adult colonoscope was advanced to the cecum, confirmed by the '
            'appendiceal orifice, and the terminal ileum was intubated for 5 cm and was normal. Insertion time 7 minutes.\n'
            '1. Transverse colon: a 12 mm sessile polyp was removed en bloc with a cold snare.\n2. Sigmoid colon at 24 cm: '
            'a 25 mm lesion. It was not resected. Cold forceps biopsies were taken from its edge.\nNursing Intraprocedure '
            'Checklist\nEntries recorded by the procedure nurse at 14:52:\nChecklist item | Nursing entry\nSnare polypectomy '
            '| Yes, transverse colon\nTattoo or marking agent injected | No - none used\nImpression\n1. Normal duodenum.\n'
            '2. 12 mm transverse colon polyp, removed with a cold snare.\nComplications\nNone.\nPlan\nThe surveillance '
            'interval will be set after pathology.\n')

    def test_ho01_shape_in_every_form(self):
        for form, variant in forms(self.HO01).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant, 'gi.egd'), D2)
                self.assertEqual(extent(variant), TI)

    def test_ho03_stricture(self):
        text = (SYNTHETIC + COLON_REPORT + 'Indication\nThin stools. She was scheduled for a total colonoscopy.\n\nProcedure\n'
                'The pediatric colonoscope was advanced to 28 cm from the anal verge in the sigmoid colon, where a '
                'circumferential stricture was found. The colonoscope could not be passed through the stricture. The rectum '
                'and distal sigmoid colon were otherwise normal on withdrawal.\nExtent reached: sigmoid colon at 28 cm. The '
                'cecum was not reached and the colon above the stricture was not examined.\n')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant), 'incomplete: sigmoid colon')

    def test_two_services_each_read(self):
        text = (SYNTHETIC + BIDIRECTIONAL + 'Procedures: EGD; colonoscopy.\n\nIndications\nAnemia.\nUpper Endoscopy\nThe '
                'gastroscope was advanced to the second portion of the duodenum.\nColonoscopy\nThe colonoscope was advanced '
                'to the cecum.\n\nImpression\nNormal.\n')
        for form, variant in forms(text).items():
            with self.subTest(form=form):
                self.assertEqual(extent(variant, 'gi.egd'), D2)
                self.assertEqual(extent(variant), 'cecum')

    def test_a_part_with_a_plan_like_sentence(self):
        text = colon_report('Positive FIT.', 'The colonoscope was advanced to the cecum. Repeat colonoscopy will be needed '
                            'if the preparation is inadequate.') + '\nImpression\nNormal.\n'
        self.assertEqual(extent(text), 'cecum')

    def test_the_part_ends_where_it_ended(self):
        # the narrowing decides only whether a part is released; where a released part ends is unchanged
        text = self.HO01
        part = next(s for s in sections.layout(text).sections if s.label == 'colonoscopy')
        self.assertTrue(text[part.start:part.end].rstrip().endswith('No - none used'))


if __name__ == '__main__':
    unittest.main()
