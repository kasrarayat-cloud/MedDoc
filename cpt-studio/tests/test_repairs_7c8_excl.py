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
