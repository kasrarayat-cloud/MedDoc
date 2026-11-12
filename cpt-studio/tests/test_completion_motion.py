"""The structure round (2026-11-08), U14, stance u14a: a reach continued past its first landmark, read as the segments of
one motion of the endoscope (detect._motion_parse, detect._motion_extent), by routing only, never by the request side.
Cycle 2 (the repair of the refuted cycle 1): the motion is read EXACTLY as the installed release reads its DIRECT-REACH
TWIN - the same document with the motion sentence's body, from its subject's head word on, replaced by "<subject> was
advanced to <the furthest landmark>." - and never more permissively.

1. One sentence carries the endoscope from the first landmark its moving verb reaches (the installed reach's own form)
   through later ones, segment by segment, to the end of the sentence. Its furthest landmark is the family's extent where
   the installed readers (and the findings statements, U19) read none, or only the motion's own first landmark's
   incomplete one - and only where the installed release, routing the direct twin, reads that same extent.
2. Anything else in the sentence makes it no motion, and the installed reading stands (the refuted continuation readers'
   counterexamples, a word before a preposition, an approximation, a next clause, a trailing phrase, an aside that stops
   or qualifies it, a service or an act named in it).
3. The motion's status is read at its own verb, at its subject's head word, at every place and landmark it names or passes
   and at its furthest landmark (any reading but the plain performed one keeps the installed reading), and its twin is
   routed: a lead that keeps the twin from its extent (another date, an interval, a question mark, a plan, a hearsay)
   keeps the long form from it, wherever in the sentence the lead stands.
4. A complete installed extent - a reach's or a findings statement's - is never replaced, deepened or made shallower, a
   withheld one stays withheld, and an installed incompleteness that another statement read stands. No exemption for a
   landmark of the family's own table: a denial of the ileocecal valve is a denial of the cecum.
Synthetic paraphrases of the shapes only."""
import time
from datetime import date

from django.test import SimpleTestCase

from studio.gi import detect
from tests.test_harness_engine import corti, proposal, run, span

DAY = date(2026, 10, 14)
HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Gastroenterology Procedure Report\n'
        'Date of service: 2026-10-14\n'
        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
UPPER = HEAD + 'Procedure: Upper endoscopy\n'
LOWER = HEAD + 'Procedure: Colonoscopy\n'
BIOPSY = 'Cold forceps biopsies were obtained from the gastric antrum.'
SNARE = 'A 6 mm polyp in the transverse colon was removed with a cold snare.'
QUIET = ('pass', 'not_applicable', 'not_verified', 'info')

# a long aside between the first landmark and the next segment (past the installed reach's 60 characters)
EGD_MOTION = ('The scope was then advanced into the stomach, which looked normal on forward view and in retroflexion, '
              'and through the pylorus to the second portion of the duodenum')
UES_MOTION = ('The gastroscope was introduced by mouth and advanced through the upper esophageal sphincter and down a normal '
              'esophagus to the gastroesophageal junction, where the Z-line lay at 39 cm above a small hiatal hernia, then '
              'on through the stomach and the pylorus to the third portion of the duodenum')
COL_LEAD = 'The colonoscope was advanced to the splenic flexure, which was normal on forward view and photographed, and then '
# the same with the furthest landmark more than CLAUSE_REACH (300) characters from a lead before the subject
FAR_UPPER = ('the gastroscope was introduced through the mouth and advanced through the upper esophageal sphincter and down a '
             'normal esophagus to the gastroesophageal junction, where a regular Z-line sat at 38 cm above a 2 cm sliding '
             'hiatal hernia with a small erosion on its upper edge, then on into the stomach, which held a small amount of '
             'clear fluid, and through the pylorus to the third portion of the duodenum.')
FAR_LOWER = ('the colonoscope was advanced to the splenic flexure, which showed several large diverticula and a few scattered '
             'small erosions in the surrounding mucosa that looked benign and were photographed in two views, and then '
             'through the transverse colon, which looked normal throughout its length, with a preserved vascular pattern '
             'and no masses or angioectasias in its folds, to the cecum.')


def extent(text, family):
    finding = next((f for f in detect.route(text, DAY).findings if f.family == family), None)
    return None if finding is None else next((f.value for f in finding.facts if f.name == 'extent'), None)


def upper(sentence, tail=''):
    return UPPER + sentence + ' ' + BIOPSY + '\n' + tail


def lower(sentence, tail=''):
    return LOWER + sentence + ' ' + SNARE + '\n' + tail


def flags(p):
    return sorted(c.id for c in p.checks if c.status not in QUIET and c.id != 'pfs.presence')


class OneMotionTests(SimpleTestCase):

    def test_a_motion_past_a_described_landmark_reaches_its_furthest_landmark(self):
        for text, family, expected in (
                (upper(EGD_MOTION + ', which was also normal.'), 'gi.egd', 'second part of duodenum'),
                (upper(EGD_MOTION + '.'), 'gi.egd', 'second part of duodenum'),
                (upper(UES_MOTION + '.'), 'gi.egd', 'third part of duodenum'),
                (lower(COL_LEAD + 'through the transverse colon to the cecum.'), 'gi.colonoscopy', 'cecum'),
                (lower(COL_LEAD + 'through the transverse colon and the ascending colon to the cecum, which showed no '
                                  'polyps.'), 'gi.colonoscopy', 'cecum'),
                (UPPER + 'Findings: ' + FAR_UPPER[0].upper() + FAR_UPPER[1:] + ' ' + BIOPSY + '\n', 'gi.egd',
                 'third part of duodenum')):
            with self.subTest(text=text[len(HEAD):]):
                self.assertEqual(extent(text, family), expected)

    def test_its_code_reads_ready_without_a_false_incompleteness(self):
        for text in (upper(EGD_MOTION + ', which was also normal.'), upper(UES_MOTION + '.')):
            with self.subTest(text=text[len(HEAD):]):
                result = run(text, corti(('43239', span(text, BIOPSY[:-1]))))
                found = proposal(result, '43239')
                self.assertEqual(found.status, 'ready')
                self.assertNotIn('service.incomplete', flags(found))
                self.assertNotIn('facts.required', flags(found))

    def test_the_installed_reading_is_kept_where_it_already_reads_a_complete_extent(self):
        # the short twin the installed reach reads itself, and a complete installed extent the motion never deepens
        self.assertEqual(extent(upper('The gastroscope was advanced into the stomach and through the pylorus to the second '
                                      'portion of the duodenum.'), 'gi.egd'), 'second part of duodenum')
        self.assertEqual(extent(upper('The scope was advanced through the pylorus, which was patent and round, into the '
                                      'duodenal bulb and the second portion of the duodenum, which were normal.'), 'gi.egd'),
                         'duodenal bulb')


class NoMotionTests(SimpleTestCase):
    """Every case below reads as installed: the sentence is no motion, or its furthest landmark fails a guard."""

    def assertNotReached(self, text, family, landmark):
        self.assertNotEqual(extent(text, family), landmark, text[len(HEAD):])

    def test_the_walk_rounds_refuted_counterexamples(self):
        # a segment named after a later mention (the walk round's refutation, acts 1), and a verb-less segment past the
        # first landmark (cycle 1, the competing design's refutation): no step of the motion's own verb
        for sentence in ('The colonoscope was advanced to the transverse colon, leaving the colon beyond the transverse '
                         'colon to the cecum unexamined.',
                         'The colonoscope was advanced to the transverse colon, leaving the colon beyond the transverse '
                         'colon to the cecum.',
                         'The colonoscope was advanced to the descending colon, leaving the colon beyond the splenic '
                         'flexure to the cecum, which was out of reach.',
                         'The colonoscope was advanced to the hepatic flexure, which was sharply angulated, and the colon '
                         'beyond the hepatic flexure to the cecum remained unexamined.',
                         'The colonoscope was advanced to the hepatic flexure, which was sharply angulated, and colon beyond '
                         'the hepatic flexure to the cecum remained unexamined.',
                         'The colonoscope was advanced to the splenic flexure, which was fixed by adhesions, and the colon '
                         'from the splenic flexure to the cecum was inaccessible.'):
            with self.subTest(sentence):
                self.assertNotReached(lower(sentence), 'gi.colonoscopy', 'cecum')
        self.assertNotReached(upper('The gastroscope was advanced into the stomach, which contained a large bezoar, and the '
                                    'duodenum from the pylorus to the second portion of the duodenum was inaccessible.'),
                              'gi.egd', 'second part of duodenum')

    def test_a_reach_unsaid_after_the_motion(self):
        # the walk round's refutation (acts 2): a next clause, a trailing phrase or a trailing aside that unsays it
        for tail in (', but this could not be confirmed.', ', although cecal landmarks could not be identified.',
                     ', but we were unable to do so.', ', possibly.', ', which could not be confirmed.',
                     ', which remained unexamined.', ', which was inaccessible.', ', which was not reached.',
                     ' unexamined.', ' only partially.', ' at the repeat examination.', '; the cecum was not seen.',
                     ', which was reached on 10/02/2026.'):
            with self.subTest(tail):
                self.assertNotReached(lower(COL_LEAD + 'through the transverse colon to the cecum' + tail),
                                      'gi.colonoscopy', 'cecum')

    def test_any_word_before_a_preposition_or_the_furthest_place(self):
        # the walk round's refutation (closures 1): an approximation or a hedge as the route
        for word in ('nearly', 'almost', 'close', 'partway', 'halfway', 'near', 'probably', 'likely', 'apparently',
                     'possibly'):
            with self.subTest(word):
                self.assertNotReached(upper('The gastroscope was advanced into the stomach, which was normal on forward '
                                            'view and on retroflexion, and then through the pylorus %s to the second '
                                            'portion of the duodenum.' % word), 'gi.egd', 'second part of duodenum')
                self.assertNotReached(lower(COL_LEAD + 'through the transverse colon %s to the cecum.' % word),
                                      'gi.colonoscopy', 'cecum')
        for before in ('nearly the', 'almost', 'near', 'approximately', 'just short of the', 'within 5 cm of the',
                       'the region of the'):
            with self.subTest(before):
                self.assertNotReached(lower(COL_LEAD + 'through the transverse colon to %s cecum.' % before),
                                      'gi.colonoscopy', 'cecum')
        for word in ('toward the', 'short of the', 'in an attempt to reach the', 'but not to the', 'but never into the'):
            with self.subTest(word):
                self.assertNotReached(lower(COL_LEAD + 'through the transverse colon %s cecum.' % word),
                                      'gi.colonoscopy', 'cecum')

    def test_an_aside_that_stops_or_qualifies_the_motion(self):
        # the walk round's refutation (closures 1: an aside word outside the negation list), the installed
        # incompleteness reader's own reasons for stopping short, and a date in the aside
        for aside in ('where further advancement was impossible', 'where it was impossible to proceed',
                      'where the lumen was completely obstructed', 'where we stopped', 'which was impassable',
                      'which was markedly redundant and looping despite abdominal pressure',
                      'where the procedure was terminated', 'where further passage failed', 'where the exam was aborted',
                      'which was the limit of the examination', 'where the colonoscope looped repeatedly',
                      'which was possibly the hepatic flexure', 'which was unclear', 'which was dilated in 2023',
                      'where the patient became hypoxic', 'which was biopsied on 10/02/2026'):
            with self.subTest(aside):
                self.assertNotReached(lower('The colonoscope was advanced to the splenic flexure, %s, and then through '
                                            'the transverse colon to the cecum.' % aside), 'gi.colonoscopy', 'cecum')

    def test_a_service_or_an_act_in_the_motion(self):
        # the twin would drop it: the motion's own words name no act of the shared tables and no service
        for aside in ('where a polyp was removed with a cold snare', 'where a clip was placed',
                      'where biopsies were taken', 'which was tattooed', 'where the EGD findings were reviewed'):
            with self.subTest(aside):
                self.assertNotReached(lower('The colonoscope was advanced to the splenic flexure, %s, and then through '
                                            'the transverse colon to the cecum.' % aside), 'gi.colonoscopy', 'cecum')

    def test_a_denied_finding_in_an_aside_is_plain(self):
        self.assertEqual(extent(lower('The colonoscope was advanced to the splenic flexure, which showed no blood or '
                                      'masses, and then through the transverse colon to the cecum.'), 'gi.colonoscopy'),
                         'cecum')

    def test_an_accessory_another_time_a_plan_or_a_doubted_opening(self):
        for sentence in ('A guidewire was advanced into the stomach, which was normal on forward view and on retroflexion, '
                         'and through the pylorus to the second portion of the duodenum.',
                         'The balloon catheter was passed into the stomach, which was normal on forward view and on '
                         'retroflexion, and through the pylorus to the second portion of the duodenum.',
                         'At her prior EGD, the scope was advanced into the stomach, which was normal on forward view and '
                         'on retroflexion, and through the pylorus to the second portion of the duodenum.',
                         'In 2023 the scope was advanced into the stomach, which was normal on forward view and on '
                         'retroflexion, and through the pylorus to the second portion of the duodenum.',
                         'The scope will be advanced into the stomach, which should be empty, and through the pylorus to '
                         'the second portion of the duodenum.',
                         'If tolerated, the scope would be advanced into the stomach, which was full of food, and through '
                         'the pylorus to the second portion of the duodenum.',
                         'The scope was not advanced into the stomach, which was full of food, or through the pylorus to '
                         'the second portion of the duodenum.',
                         'The scope was partially advanced into the stomach, which was normal on forward view and on '
                         'retroflexion, and through the pylorus to the second portion of the duodenum.',
                         'Usually the scope is advanced into the stomach, which is normal on forward view and on '
                         'retroflexion, and through the pylorus to the second portion of the duodenum.'):
            with self.subTest(sentence):
                self.assertNotReached(upper(sentence), 'gi.egd', 'second part of duodenum')
        # a prior examination pasted into the procedure section, under a line naming it
        self.assertNotReached(upper('Retained food in the stomach.\nPrior exam 3/2024\n' + EGD_MOTION + '.'), 'gi.egd',
                              'second part of duodenum')

    def test_another_time_place_agent_or_source_in_its_sentence(self):
        # the labelled paragraph reader's hold signals (structure._signals); "by mouth" is the route, no agent
        for lead in ('Per the outside report, the', 'In 2023 the', 'At Mercy Hospital the', 'According to the referring '
                     'physician, the', 'During her prior admission the', 'Last year the', 'Two years ago the'):
            with self.subTest(lead):
                self.assertNotReached(upper(lead + UES_MOTION[len('The'):] + '.'), 'gi.egd', 'third part of duodenum')
        self.assertNotReached(upper('The scope was advanced by Dr. Other into the stomach, which was normal on forward '
                                    'view and on retroflexion, and through the pylorus to the second portion of the '
                                    'duodenum.'), 'gi.egd', 'second part of duodenum')
        self.assertEqual(extent(upper(UES_MOTION.replace('by mouth', 'through the mouth') + '.'), 'gi.egd'),
                         'third part of duodenum')

    def test_the_opening_doubted_or_failed(self):
        for lead in ('The scope was advanced with no success into', 'The scope was advanced without success into',
                     'The scope was advanced to no avail into', 'The scope was advanced no further than into',
                     'The scope was partially advanced into', 'The scope was advanced in an attempt to get into'):
            with self.subTest(lead):
                self.assertNotReached(upper(lead + ' the stomach, which was normal on forward view and on retroflexion, '
                                            'and through the pylorus to the second portion of the duodenum.'),
                                      'gi.egd', 'second part of duodenum')
        # a denied difficulty is plain (the installed negation reader's own exception)
        self.assertEqual(extent(upper('The gastroscope was advanced without difficulty into the stomach, which was normal '
                                      'on forward view and on retroflexion, and through the pylorus to the second portion '
                                      'of the duodenum.'), 'gi.egd'), 'second part of duodenum')

    def test_the_mover_is_the_endoscope_named_as_the_subject(self):
        # an accessory moved through the scope, a device of no listed name, a scope an accessory word names, and a verb
        # whose subject is no instrument word: no mover the twin could stand for (cycle 1, release finding 4)
        for lead in ('A guidewire was passed through the gastroscope into', 'The biopsy forceps was advanced through the '
                     'scope into', 'A nasojejunal tube was passed alongside the gastroscope into',
                     'The wire was passed through the scope and advanced into', 'A Jagwire was passed through the scope '
                     'into', 'A cytology brush was passed through the scope into', 'A hemoclip applicator was advanced '
                     'through the scope into', 'The capsule endoscope was then advanced into',
                     'We advanced the gastroscope into', 'It was then advanced into'):
            with self.subTest(lead):
                self.assertNotReached(upper(lead + ' the stomach, which was normal on forward view and on retroflexion, '
                                            'and through the pylorus to the second portion of the duodenum.'),
                                      'gi.egd', 'second part of duodenum')

    def test_the_movers_own_predicate_doubted(self):
        # the words between the subject and the motion's verb, which the twin drops: a modal, the present tense, an
        # infinitive or a negator of the mover's own predicate governs the coordinated motion verb
        tail = (' through the upper esophageal sphincter and down a normal esophagus to the gastroesophageal junction, '
                'where the Z-line lay at 39 cm above a small hiatal hernia, then on through the stomach and the pylorus to '
                'the third portion of the duodenum.')
        for predicate in ('would be introduced by mouth and advanced', 'should be introduced and then advanced',
                          'is introduced by mouth and advanced', 'was to be introduced by mouth and advanced',
                          'will be introduced by mouth and advanced', 'could not be introduced by mouth and advanced',
                          'was introduced and would then be advanced', 'was reportedly introduced and advanced'):
            with self.subTest(predicate):
                self.assertNotReached(upper('The gastroscope ' + predicate + tail), 'gi.egd', 'third part of duodenum')
        self.assertEqual(extent(upper('The gastroscope had been introduced by mouth and advanced' + tail), 'gi.egd'),
                         'third part of duodenum')

    def test_a_doubt_a_stop_a_shorter_label_or_a_denial_in_the_familys_text(self):
        motion = EGD_MOTION + '.'
        for tail in ('Exam limited to the stomach.', 'We stopped in the stomach.', 'The examination was aborted.',
                     'The second portion of the duodenum was not examined.', 'Unable to advance beyond the bulb.'):
            with self.subTest(tail):
                self.assertNotReached(upper(motion, tail + '\n'), 'gi.egd', 'second part of duodenum')
        self.assertNotReached(upper('Extent of exam: stomach.\n' + motion), 'gi.egd', 'second part of duodenum')
        for tail in ('The cecum could not be reached.', 'Cecum not reached; the exam ended at the splenic flexure.',
                     'The procedure was aborted because of discomfort.', 'The examination was incomplete.'):
            with self.subTest(tail):
                self.assertNotReached(lower(COL_LEAD + 'through the transverse colon to the cecum.', tail + '\n'),
                                      'gi.colonoscopy', 'cecum')

    def test_a_stop_statement_keeps_the_installed_incomplete_reading(self):
        # the installed reading of the same report, never a new hold
        text = upper(EGD_MOTION + '.', 'We stopped in the stomach.\n')
        self.assertEqual(extent(text, 'gi.egd'), 'incomplete: stomach')

    def test_never_a_new_incompleteness_and_never_a_flexible_sigmoidoscopy(self):
        # a motion whose furthest landmark lies short of the depth called for reads as installed
        self.assertNotEqual(extent(lower('The colonoscope was advanced to the rectum, which was normal on retroflexion '
                                         'and photographed, and then through the sigmoid colon to the descending colon.'),
                                   'gi.colonoscopy'), 'incomplete: descending colon')
        text = (HEAD + 'Procedure: Flexible sigmoidoscopy\nThe sigmoidoscope was advanced to the sigmoid colon, which was '
                'angulated and tortuous with many diverticula, and then through the descending colon to the splenic '
                'flexure. Biopsies of the sigmoid colon were taken with cold forceps.\n')
        self.assertNotEqual(extent(text, 'gi.flex_sig'), 'splenic flexure')


class CycleOneFindingTests(SimpleTestCase):
    """Pins of the cycle-1 findings repaired in cycle 2 (design-r2/cycle1/u14a.json; briefs/u14-c2-repair.md), each with
    the reading the installed release gives the long form (and, where the brief asks it, its direct twin)."""

    def test_a_lead_beyond_the_station_window_keeps_the_installed_reading(self):
        # release finding 1 (both designs): a lead that governs the verb and lies more than 300 characters before the
        # furthest landmark; the direct twin with the same lead is held on the installed release, and so is the long form
        # (the controls: with no lead both sentences read their furthest landmark)
        self.assertEqual(extent(UPPER + 'Findings: ' + FAR_UPPER[0].upper() + FAR_UPPER[1:] + ' ' + BIOPSY + '\n',
                                'gi.egd'), 'third part of duodenum')
        self.assertEqual(extent(LOWER + 'Findings: ' + FAR_LOWER[0].upper() + FAR_LOWER[1:] + ' ' + SNARE + '\n',
                                'gi.colonoscopy'), 'cecum')
        for lead in ('On 09/30 ', '6 mos later, ', '3 wks later, ', 'Over the holidays, ', 'At her convenience, ', '(?) ',
                     'Tomorrow ', 'Consider that '):
            with self.subTest(lead):
                self.assertIsNone(extent(UPPER + 'Findings: ' + lead + FAR_UPPER + ' Today, cold forceps biopsies were '
                                         'obtained from the distal esophagus.\n', 'gi.egd'))
                self.assertIsNone(extent(LOWER + 'Findings: ' + lead + FAR_LOWER + ' Today, a 6 mm polyp in the transverse '
                                         'colon was removed with a cold snare.\n', 'gi.colonoscopy'))
        for opening in ('was advanced (?) to', 'was advanced on 09/30 to'):
            with self.subTest(opening):
                self.assertIsNone(extent(LOWER + 'Findings: The colonoscope ' + opening + FAR_LOWER.split(
                    'was advanced to', 1)[1] + ' Today, a 6 mm polyp in the transverse colon was removed with a cold '
                    'snare.\n', 'gi.colonoscopy'))

    def test_today_inside_the_opening_does_not_lift_a_lead_the_twin_reads(self):
        # the twin drops the body from the subject on: its lead governs it, whatever words the long opening adds
        today = FAR_UPPER.replace('was introduced through', 'was introduced today through')
        # (the control: with no lead the same sentence reads its furthest landmark)
        self.assertEqual(extent(UPPER + 'Findings: ' + today[0].upper() + today[1:] + ' ' + BIOPSY + '\n', 'gi.egd'),
                         'third part of duodenum')
        for lead in ('On 09/30 ', 'Two years ago, ', 'Last year '):
            with self.subTest(lead):
                self.assertIsNone(extent(UPPER + 'Findings: ' + lead + today + ' ' + BIOPSY + '\n', 'gi.egd'))

    def test_a_short_reach_today_then_an_earlier_long_course(self):
        # release finding 1 (the competing design's variant): today's reach stands, the earlier course is no motion
        text = (UPPER + 'Today the gastroscope was advanced to the stomach. ' + BIOPSY + '\nTwo years ago, at another '
                'hospital and under general anesthesia, ' + FAR_UPPER + '\n')
        self.assertEqual(extent(text, 'gi.egd'), 'incomplete: stomach')

    def test_a_denial_of_the_cecums_own_landmark_is_a_denial_of_the_cecum(self):
        # release finding 3 / regress finding 3: no exemption for a landmark of the family's own extent table
        motion = ('The colonoscope was inserted through the anus and advanced gently through the anal canal and along a '
                  'tortuous sigmoid colon to the descending colon, where scattered diverticula were seen, then on through '
                  'the splenic flexure and the transverse colon to the cecum.')
        for tail in ('The ileocecal valve could not be reached.', 'The ileocecal valve was not reached.',
                     'We were unable to reach the ileocecal valve.', 'The ileocecal valve was not visualized.',
                     'The ileocecal valve could not be reached because of looping.',
                     'The ileocecal valve could not be traversed.'):
            with self.subTest(tail):
                text = lower(motion, tail + '\n')
                self.assertNotEqual(extent(text, 'gi.colonoscopy'), 'cecum')
                result = run(text, corti(('45385', span(text, SNARE[:-1]))))
                self.assertIn('service.incomplete', flags(proposal(result, '45385')))
                self.assertNotEqual(extent(lower(COL_LEAD + 'through the transverse colon to the cecum.', tail + '\n'),
                                           'gi.colonoscopy'), 'cecum')

    def test_a_sub_acts_denial_keeps_the_installed_reading(self):
        # cycle 1 exempted these; cycle 2 reads them as the installed release reads the long form (fail closed)
        motion = COL_LEAD + 'through the transverse colon to the cecum.'
        for tail in ('The terminal ileum could not be intubated.', 'The terminal ileum was not intubated.'):
            with self.subTest(tail):
                self.assertEqual(extent(lower(motion, tail + '\n'), 'gi.colonoscopy'),
                                 'incomplete: splenic flexure')

    def test_a_deeper_findings_statement_is_never_made_shallower(self):
        # regress finding 2: the installed findings-stated reach (U19) reads the third portion; the motion to the second
        # never replaces it
        motion = UES_MOTION.replace('third portion', 'second portion') + '.'
        for statement in ('Duodenum: the bulb and third portion were normal.', 'Duodenum: bulb and third portion normal.'):
            with self.subTest(statement):
                self.assertEqual(extent(upper(motion, statement + '\n'), 'gi.egd'), 'third part of duodenum')

    def test_an_incompleteness_another_statement_reads_stands(self):
        # the competing design's regress finding 2, adopted as a narrowing: an installed 'incomplete: X' is opened only
        # where X is one of this motion's own landmarks in its own clause
        motion = ('The colonoscope was advanced to the transverse colon, which was long and redundant with scattered small '
                  'diverticula along its whole length, and then to the cecum.')
        self.assertEqual(extent(lower(motion, 'Colonoscopy to hepatic flexure.\n'), 'gi.colonoscopy'),
                         'incomplete: hepatic flexure')
        self.assertEqual(extent(upper(UES_MOTION + '.', 'EGD to antrum.\n'), 'gi.egd'), 'incomplete: stomach')
        # its own first segment's incompleteness is the one the motion opens (the walk round's finding 3 shape)
        self.assertEqual(extent(lower(motion), 'gi.colonoscopy'), 'cecum')

    def test_a_lead_holding_an_aside_is_not_read(self):
        # the twin keeps the lead as written, so a lead with an aside set off in it (which an aside-free twin drops) is
        # never read: its own words may say today where the lead says another day
        for lead in ('On 09/30, which was a Tuesday, ', 'Today, which was her birthday, ', 'In the ED (overnight) ',
                     'At 10:15, when the room was free, '):
            with self.subTest(lead):
                self.assertNotEqual(extent(UPPER + 'Findings: ' + lead + FAR_UPPER + ' ' + BIOPSY + '\n', 'gi.egd'),
                                    'third part of duodenum')

    def test_a_lead_aside_set_off_by_dashes_or_commas_is_not_read(self):
        # integration (2026-11-08, u14a2 release 0): an aside set off by a dash, a spaced hyphen or commas is an aside
        # too. 'On 09/30 — unlike today — <the far course>' was read to the third portion (the verbatim-lead twin
        # inherits an installed blind spot: the aside's today word outranks the lead's date), where the aside-free twin
        # 'On 09/30 the gastroscope was advanced to ...' holds; any set-off punctuation in the lead now keeps the
        # installed reading
        for lead in ('On 09/30 — unlike today — ', 'On 09/30 – unlike today – ', 'On 09/30 - unlike today - ',
                     'On 09/30, unlike today, ', 'On 09/30, in contrast to today, ', 'Over the holidays; unlike today: '):
            with self.subTest(lead):
                self.assertNotEqual(extent(UPPER + 'Findings: ' + lead + FAR_UPPER + ' ' + BIOPSY + '\n', 'gi.egd'),
                                    'third part of duodenum')
        # the plain lead-free course is still read (the member shape)
        self.assertEqual(extent(UPPER + 'Findings: ' + FAR_UPPER[0].upper() + FAR_UPPER[1:] + ' ' + BIOPSY + '\n',
                                'gi.egd'), 'third part of duodenum')


class TwinTests(SimpleTestCase):

    def test_the_twin_is_routed_with_no_motion_and_at_most_once_per_document(self):
        text = upper(UES_MOTION + '.')
        an = detect._analysis.__wrapped__(text, DAY)[0]
        self.assertFalse(detect._MOTION_OFF.get())
        asked, answer = an.memo[('motion-twin',)]
        self.assertEqual(asked[0], 'gi.egd')
        self.assertTrue(answer)

    def test_a_motion_only_extent_is_no_evidence_of_the_procedure(self):
        text = upper(UES_MOTION + '.')
        an = detect._analysis.__wrapped__(text, DAY)[0]
        self.assertTrue(an.memo.get((detect.MOTION_ONLY_EXTENT, 'gi.egd')))
        # an installed incompleteness the motion opens was already a reach: no mark
        an = detect._analysis.__wrapped__(upper(EGD_MOTION + '.'), DAY)[0]
        self.assertIsNone(an.memo.get((detect.MOTION_ONLY_EXTENT, 'gi.egd')))


class MotionCostTests(SimpleTestCase):

    def test_each_aside_is_read_once(self):
        # cycle 1, regress finding 1 (cost): an aside's words were read again at every comma of its window; now once
        # per aside, whatever the commas and the joins inside it
        calls = []
        original = detect._motion_aside_plain

        def counting(an, start, end):
            calls.append((start, end))
            return original(an, start, end)
        sentence = ('The colonoscope was advanced to the rectum' + (', which showed no polyps' + ', to x' * 8
                                                                     + ', to the colon') * 6 + ', which advanced.')
        detect._motion_aside_plain = counting
        try:
            detect._analysis.__wrapped__(LOWER + sentence + ' ' + SNARE + '\n', DAY)  # never a cached reading
        finally:
            detect._motion_aside_plain = original
        self.assertTrue(calls)
        self.assertEqual(len(calls), len({start for start, _ in calls}))  # one reading per aside
        self.assertLessEqual(len(calls), sentence.count(', which'))

    def test_a_long_text_of_motions_routes_in_bounded_time(self):
        unit = (UES_MOTION + '. ')
        for size in (detect._MOTION_TEXT - 2_000, 120_000):
            with self.subTest(size):
                text = UPPER + (unit * (size // len(unit) + 1))[:size] + '\n'
                started = time.monotonic()
                detect.route(text, DAY)
                self.assertLess(time.monotonic() - started, 10.0)
        # a clause past the bound is no motion, and a document past its bound keeps the installed reading
        self.assertGreater(detect._MOTION_CLAUSE, 600)
        text = UPPER + (unit * (detect._MOTION_TEXT // len(unit) + 2)) + '\n'
        self.assertIsNone(extent(text, 'gi.egd'))
