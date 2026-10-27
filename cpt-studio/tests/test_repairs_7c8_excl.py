"""Repair round 7c8, cluster EXCL: what the round's skeptic demonstrated against the ec5 EXCL repairs. A code for an act
the document states done today is never EXCLUDED by a misreading (must-fix class 4, owner decision 2026-10-27): an
exclusion needs both readers to read the same not-done status for the act, from its own clause; anything less holds.

Each text is a fresh synthetic paraphrase written for the case under test (fictional patients only); the expected
readings are written here, outside the reader. None of them is a sentence the reader matches by its exact wording.
"""
from datetime import date

from django.test import SimpleTestCase

from tests.test_repairs_ec5_excl import (COLON_BASE, COLONOSCOPY, EGD, EGD_BASE, HEAD, assessed, proposal, statuses,
                                         unresolved)


def _not_excluded(test, text, code, quote, day=date(2026, 10, 14)):
    result = assessed(text, [(code, quote)], day)
    test.assertNotEqual(proposal(result, code).bucket, 'excluded', f'{code} excluded on {quote!r}')
    return proposal(result, code)


class TodayAcrossAnOwnTimeCutTests(SimpleTestCase):
    """sk:1 (a regression of 06eb17aa8, negtime-4): the cut that gives a coordinated predicate its own time ("... and will
    be sent to pathology today") also took the sentence's TODAY word away from the act before it, so a manner or
    attributive plan or history word in the act's own clause ("as recommended", "seen previously", "as planned") dated
    it, and its code was newly excluded. The cut separates a coordinated predicate's time, plan and cancel words - never
    the sentence's TODAY word: whether the sentence says today is read over the coordinated predicates together."""

    CASES = (
        (EGD, 'Biopsies were taken as recommended and will be sent to pathology today.', 'biopsy', '43239', EGD_BASE),
        (COLONOSCOPY, 'The polyp seen previously was removed with a cold snare and will be sent to pathology today.',
         'snare', '45385', COLON_BASE),
        (EGD, 'A 10 mm gastric polyp was removed with a hot snare as planned and the patient will be discharged today.',
         'snare', '43251', EGD_BASE),
        (EGD, 'Biopsies were obtained as previously recommended and the specimens will be sent to pathology this '
              'session.', 'biopsy', '43239', EGD_BASE),
    )

    def test_the_act_reads_done_and_its_code_is_never_excluded(self):
        for template, line, kind, code, base in self.CASES:
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['performed'])
                _not_excluded(self, text, code, line)
                # with the base code alone the act done today is visible again (it had been hidden as planned)
                self.assertIn((kind, 'not_covered'), unresolved(assessed(text, [base])))

    def test_the_service_itself_is_never_dated_by_the_cut(self):
        sentence = 'Upper endoscopy was performed as recommended and biopsies will be sent to pathology today.'
        text = HEAD + 'Date of service: 10/14/2026\n' + sentence + '\n'
        for code in ('43235', '43239'):
            with self.subTest(code=code):
                _not_excluded(self, text, code, sentence)
        sentence = 'The colonoscope was advanced to the cecum as planned and the patient will be discharged today.'
        text = HEAD + 'Date of service: 10/14/2026\n' + sentence + '\n'
        _not_excluded(self, text, '45378', sentence)

    def test_controls_the_cut_still_keeps_another_predicates_words_off_the_act(self):
        for template, line, kind, status in (
                # no TODAY word: the coordinated predicate's plan or cancel word still never dates the act before it
                (EGD, 'Cold forceps biopsies were obtained from the antrum and will be sent to pathology.', 'biopsy',
                 'performed'),
                (EGD, 'Biopsies were obtained and dilation was deferred today.', 'biopsy', 'performed'),
                (COLONOSCOPY, 'Biopsies were taken from the cecum and polypectomy was deferred today.', 'snare',
                 'cancelled'),
                # a TODAY word never overrules the act's own denial or its own date
                (EGD, 'Biopsies were not obtained and will be taken today.', 'biopsy', 'negated'),
                (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare on 09/03/2026 and will be reviewed '
                              'today.', 'snare', 'historical'),
                # without a TODAY word the act's own plan word still dates it
                (EGD, 'Biopsies will be obtained and will be sent to pathology.', 'biopsy', 'planned')):
            with self.subTest(line=line, kind=kind):
                self.assertEqual(statuses(template.format(x=line), kind), [status])


class NegationListEndsAtANewClauseTests(SimpleTestCase):
    """sk:5 (negtime-6, claimed fixed by 6fd66f2b3): a negation's list still reached a new clause after a comma, "and",
    "so" or "as" ("There was no bleeding and biopsies were taken", "No active bleeding, two hemoclips were placed"), so
    both readers read the act denied and its code was excluded. A negation covers what it lists; an act named after a
    clause boundary as the subject of its own predicate (an auxiliary and a participle right after it) is outside the
    list and reads by that predicate - unless a negation of its own governs it."""

    def test_an_act_with_its_own_predicate_after_the_list_is_outside_it(self):
        for template, line, kind, code in (
                (EGD, 'There was no bleeding and biopsies were taken from the antrum.', 'biopsy', '43239'),
                (EGD, 'No active bleeding, two hemoclips were placed prophylactically on the visible vessel.', 'clip',
                 '43255'),
                (EGD, 'There was no active bleeding, so two hemoclips were placed prophylactically on the visible '
                      'vessel.', 'clip', '43255'),
                (EGD, 'No bleeding occurred as the biopsies were obtained from the antrum.', 'biopsy', '43239'),
                (EGD, 'No complications, biopsies were obtained from the antrum.', 'biopsy', '43239'),
                (COLONOSCOPY, 'Without complication, biopsies were taken from the ascending colon.', 'biopsy',
                 '45380'),
                (COLONOSCOPY, 'No polyps in the left colon, a 6 mm cecal polyp was removed with a cold snare.', 'snare',
                 '45385')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['performed'])
                _not_excluded(self, text, code, line)

    def test_controls_the_negations_own_list_still_denies(self):
        for template, line, kind in (
                (COLONOSCOPY, 'No biopsy, polypectomy or tattoo was performed.', 'snare'),
                (COLONOSCOPY, 'No biopsy, polypectomy, or tattoo was performed.', 'tattoo'),
                (COLONOSCOPY, 'No biopsies or polypectomy were performed.', 'snare'),
                (EGD, 'There were no biopsies taken since the mucosa was normal.', 'biopsy'),
                (EGD, 'There was no bleeding, and no biopsies were taken.', 'biopsy'),
                (EGD, 'No ulcers, so no biopsies were obtained.', 'biopsy'),
                (EGD, 'Without bleeding, perforation or a clip being placed.', 'clip'),
                (EGD, 'No biopsies were taken after the dilation.', 'biopsy')):
            with self.subTest(line=line):
                self.assertEqual(statuses(template.format(x=line), kind), ['negated'])


class AnotherPredicatesTimeTests(SimpleTestCase):
    """sk:2 (negtime-4, claimed fixed by 06eb17aa8): the cut gave a coordinated predicate its own time only in two
    wordings ("and" with a subject and "will", or "and" with one to four words, an auxiliary and a plan or cancel
    participle), so a relative "which will", an absolute "with ... recommended", a verbless "and dilation deferred",
    "and are scheduled", "and we plan", "and results should be available next week" and "and H. pylori treatment will"
    still dated the act the sentence states done, and its code was excluded. After an act predicate stated done, a
    coordinated, relative or absolute predicate with a plan, future or cancel word of its own is its own clause."""

    CASES = (
        (EGD, 'Cold forceps biopsies were obtained from the antrum, which will be sent to pathology.', 'biopsy', '43239'),
        (EGD, 'Biopsies were taken from the antrum and results should be available next week.', 'biopsy', '43239'),
        (EGD, 'Biopsies of the distal esophageal stricture were obtained and dilation deferred until pathology '
              'returns.', 'biopsy', '43239'),
        (EGD, 'Cold forceps biopsies were obtained from the antrum and are scheduled for pathology review.', 'biopsy',
         '43239'),
        (EGD, 'Cold forceps biopsies were obtained from the antrum and we plan to review the results at the next '
              'visit.', 'biopsy', '43239'),
        (EGD, 'Biopsies were taken from the antrum and H. pylori treatment will depend on pathology.', 'biopsy',
         '43239'),
        (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare with repeat colonoscopy recommended in 3 '
                      'years.', 'snare', '45385'),
        (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare, repeat colonoscopy planned in 3 years.',
         'snare', '45385'),
    )

    def test_the_act_reads_by_its_own_predicate_and_is_never_excluded(self):
        for template, line, kind, code in self.CASES:
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['performed'])
                _not_excluded(self, text, code, line)

    def test_controls_an_acts_own_plan_or_cancel_word_still_dates_it(self):
        for template, line, kind, status in (
                (EGD, 'Biopsies will be obtained, which will be sent to pathology.', 'biopsy', 'planned'),
                (EGD, 'Biopsies were deferred and will be taken at the next EGD.', 'biopsy', 'cancelled'),
                (COLONOSCOPY, 'Polypectomy is planned with a cold snare at the next colonoscopy.', 'snare', 'planned'),
                (COLONOSCOPY, 'Cold snare polypectomy will be performed, with biopsies recommended.', 'snare',
                 'planned'),
                (COLONOSCOPY, 'A polyp was seen and will be removed with a cold snare at the next colonoscopy.', 'snare',
                 'planned'),
                # the act in the coordinated predicate reads by that predicate's own time
                (EGD, 'The esophagus was dilated with a 15 mm balloon, and biopsies will be taken at the next EGD.',
                 'biopsy', 'planned')):
            with self.subTest(line=line, kind=kind):
                self.assertEqual(statuses(template.format(x=line), kind), [status])


class DateNotTheActsOwnTests(SimpleTestCase):
    """sk:3 (negtime-7, claimed fixed by 28dcc0e7f): dates that are not the act's own still excluded it as historical - a
    clock time after "at approximately", a date in a parenthesis that labels another event ("(barium swallow
    09/22/2026)", "(CT 09/22/2026)"), another event's date after a later word that is no clause of its own ("held since
    <date>": the last opener had won), a birth date after "b.", and a bare year beside "today". A date dates an act only as
    its own time: these hold the act (or leave it performed), never exclude it."""

    def test_a_date_that_is_not_the_acts_own_never_excludes_it(self):
        for template, line, kind, code in (
                (EGD, 'Today two hemoclips were placed on the visible vessel at approximately 2015.', 'clip', '43255'),
                (EGD, 'Hemostasis was achieved with two hemoclips at approximately 2015.', 'bleeding_control', '43255'),
                (EGD, 'Today two hemoclips were placed on the visible vessel around 2015.', 'clip', '43255'),
                (EGD, 'The distal esophageal stricture (barium swallow 09/22/2026) was dilated with a 15 mm '
                      'through-the-scope balloon.', 'dilation', '43249'),
                (COLONOSCOPY, 'The polyp (CT 09/22/2026) was removed with a cold snare.', 'snare', '45385'),
                (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare, apixaban held since 10/12/2026.',
                 'snare', '45385'),
                (COLONOSCOPY, 'Alex Synthetic (b. 03/04/1961) underwent cold snare polypectomy of a 6 mm sigmoid polyp.',
                 'snare', '45385')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertIn(statuses(text, kind), (['performed'], ['uncertain']))
                _not_excluded(self, text, code, line)
        # a birth date is no act's time at all, in a parenthesis or not: the act reads by its own predicate
        for line in ('Alex Synthetic (b. 03/04/1961) underwent cold snare polypectomy of a 6 mm sigmoid polyp.',
                     'Alex Synthetic, b. 03/04/1961, underwent cold snare polypectomy of a 6 mm sigmoid polyp.'):
            with self.subTest(line=line):
                text = COLONOSCOPY.format(x=line)
                self.assertEqual(statuses(text, 'snare'), ['performed'])
                _not_excluded(self, text, '45385', line)

    def test_controls_the_acts_own_date_still_dates_it(self):
        for line, status in (
                ('A 6 mm sigmoid polyp was removed with a cold snare on 09/03/2026.', 'historical'),
                ('A 6 mm sigmoid polyp was removed with a cold snare (09/03/2026).', 'historical'),
                ('A 6 mm sigmoid polyp was removed with a cold snare (on 09/03/2026).', 'historical'),
                ('In 2015 a 6 mm sigmoid polyp was removed with a cold snare.', 'historical'),
                ('A 6 mm sigmoid polyp will be removed with a cold snare on 11/20/2026.', 'planned'),
                ('Polypectomy with a cold snare is scheduled for 11/20/2026.', 'planned')):
            with self.subTest(line=line):
                self.assertEqual(statuses(COLONOSCOPY.format(x=line), 'snare'), [status])


class TimeOfAnotherNounTests(SimpleTestCase):
    """sk:4 (negtime-5, claimed fixed by 77847adf7): a time word or a date that describes another noun still dated the act -
    in an "of" phrase on a site ("the site of prior polypectomy"), leading the clause on a participle ("Previously
    tattooed polyp"), inside a relative clause ("the polyp that was previously biopsied"), as a dated noun ("The 2023
    EMR scar") or in the occasion another participle tells of ("the ulcer seen on the prior EGD"). Each is that noun's
    or that event's time: the act's own time is in doubt, so its code is held, never excluded."""

    CASES = (
        (COLONOSCOPY, 'Biopsies were obtained from the site of prior polypectomy in the ascending colon.', 'biopsy',
         '45380'),
        (COLONOSCOPY, 'Previously tattooed polyp in the ascending colon was removed with a hot snare.', 'snare', '45385'),
        (COLONOSCOPY, 'The polyp that was previously biopsied was removed with a hot snare.', 'snare', '45385'),
        (COLONOSCOPY, 'The 2023 EMR scar in the ascending colon was biopsied with cold forceps.', 'biopsy', '45380'),
        (EGD, 'The ulcer seen on the prior EGD was biopsied with cold forceps.', 'biopsy', '43239'),
    )

    def test_the_act_is_held_never_excluded(self):
        for template, line, kind, code in self.CASES:
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['uncertain'])
                held = _not_excluded(self, text, code, line)
                self.assertEqual((held.bucket, held.status), ('selected', 'needs_clarification'))

    def test_controls_the_words_own_act_or_an_occasion_still_dates(self):
        for template, line, kind, status in (
                # the time word's own act, inside the phrase it describes
                (COLONOSCOPY, 'The polyp that was previously biopsied was removed with a hot snare.', 'biopsy',
                 'historical'),
                (COLONOSCOPY, 'Previously tattooed polyp in the ascending colon was removed with a hot snare.', 'tattoo',
                 'historical'),
                (COLONOSCOPY, 'Biopsies were obtained from the site of prior polypectomy in the ascending colon.',
                 'snare', 'historical'),
                (COLONOSCOPY, 'The 2023 EMR scar in the ascending colon was biopsied with cold forceps.', 'emr',
                 'historical'),
                # an occasion, a sentence adverb, an adjective on the act's own noun, or the main predicate's own time
                (COLONOSCOPY, 'Biopsies were taken at the 2023 colonoscopy.', 'biopsy', 'historical'),
                (COLONOSCOPY, 'Previously, polyps were removed with a cold snare.', 'snare', 'historical'),
                (COLONOSCOPY, 'Prior polyps were removed with a cold snare.', 'snare', 'historical'),
                (COLONOSCOPY, 'A polyp seen on CT will be removed with a cold snare at the next colonoscopy.', 'snare',
                 'planned'),
                (COLONOSCOPY, 'The polyp that was seen will be removed with a cold snare at the next colonoscopy.',
                 'snare', 'planned')):
            with self.subTest(line=line, kind=kind):
                self.assertEqual(statuses(template.format(x=line), kind), [status])


class DocumentationStampLabelTests(SimpleTestCase):
    """sk:6 (negtime-10, claimed fixed by 842698be0): a documentation stamp outside STAMP_LABEL's closed list still dated
    the act an addendum adds ("Addendum <date>:", "Late entry <date>:", "(entered <date>)", "(updated <date>)",
    "(corrected <date>)", "(note revised <date>)", "signed by Dr. <name> on <date>"), so 43239 was excluded as planned. A
    date stamping when the text was written - a documentation word, optionally its author ("by <name>") and "on", right
    before the date - is no act's time: the act reads by its own words, or is held, never excluded."""

    LINES = ('Addendum 10/16/2026: cold forceps biopsies were also taken from the duodenum.',
             'Late entry 10/16/2026: cold forceps biopsies were also taken from the duodenum.',
             'Cold forceps biopsies were also taken from the duodenum (entered 10/16/2026).',
             'Cold forceps biopsies were also taken from the duodenum (updated 10/16/2026).',
             'Cold forceps biopsies were also taken from the duodenum (corrected 10/16/2026).',
             'Cold forceps biopsies were also taken from the duodenum (note revised 10/16/2026).',
             'Cold forceps biopsies were also taken from the duodenum, signed by Dr. Ramos on 10/16/2026.',
             'Cold forceps biopsies were also taken from the duodenum, electronically signed by Alex Q. Synthetic, MD '
             'on 10/16/2026.',
             'Addendum (10/16/2026): cold forceps biopsies were also taken from the duodenum.')

    def test_a_stamp_never_dates_the_act(self):
        for line in self.LINES:
            with self.subTest(line=line):
                text = EGD.format(x=line)
                self.assertIn(statuses(text, 'biopsy'), (['performed'], ['uncertain']))
                _not_excluded(self, text, '43239', line)
        for line in self.LINES[:2] + self.LINES[6:]:
            with self.subTest(line=line):
                self.assertEqual(statuses(EGD.format(x=line), 'biopsy'), ['performed'])

    def test_controls_a_date_that_is_no_stamp_still_dates_the_act(self):
        for line, status in (('Cold forceps biopsies were taken from the duodenum on 10/16/2026.', 'planned'),
                             ('On 09/03/2026 cold forceps biopsies were taken from the duodenum.', 'historical'),
                             ('Cold forceps biopsies of the duodenum were entered in the plan for 11/20/2026.',
                              'planned')):
            with self.subTest(line=line):
                self.assertEqual(statuses(EGD.format(x=line), 'biopsy'), [status])
