"""Completion repair (owner directive 2026-11-06; HARNESS.md "Completion repair (2026-11-06)"), builder A: act frames
in the documented-service reader. Each rule is pinned by minimal positive and negative pairs, its refuter sentences,
and an equivalent wording in another layout or GI family. Real engine and readers, no provider or database calls.
Synthetic documents only (the retained cases appear through paraphrases of their structure, as the earlier repairs'
tests do).

- U6, placement never overwrites outcome: an act on a Procedure line is promoted to performed only where its own clause
  states no outcome (services._outcome_in_doubt).
- U13, coordinated anatomy: "the right and left colon" reads both sites (services._anatomy_in).
"""
from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi import services as gi_services
from tests.test_harness_engine import DAY, code, corti, proposal, read, run, span

COLON_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
              'Endoscopy Report\n'
              'Date of service: 2026-10-14\n'
              'Endoscopist: Test Endoscopist, MD\n'
              'Indication: Chronic diarrhea.\n')
FAILED_SNARE = ('Hot snare polypectomy of a 14 mm polyp in the sigmoid colon was attempted, but the polypectomy was '
                'unsuccessful because of poor positioning; the polyp was left in place.')
FAILED_DILATION = ('Balloon dilation of a distal esophageal stricture was attempted, but the dilation was unsuccessful '
                   'because of poor positioning.')


def inventory(text, day=DAY):
    return gi_services.build(text, service_date=day, routing=detect.route(text, day))


def acts_of(text, family, kind):
    svc = next(s for s in inventory(text).services if s.family == family)
    return [(a.status, a.cues) for a in svc.acts if a.kind == kind]


def outcome(text, value, quote, *primary):
    """(Corti's bucket/status, a participant's bucket/status) for ``value`` on ``quote``."""
    base = [(c, span(text, q)) for c, q in primary]
    by_corti = proposal(run(text, corti(*base, (value, span(text, quote)))), value)
    by_astra = proposal(run(text, corti(*base), [read('astra', [code(text, value, quote)])]), value)
    return (by_corti.bucket, by_corti.status), (by_astra.bucket, by_astra.status)


class PlacementNeverOverwritesOutcomeTests(SimpleTestCase):
    """U6 (D|RT-f1, D|RT-f3, D|ARCH-D3a): a failed attempt sharing the Procedure line had been promoted to a performed
    act ('performed: listed on the procedure line'), so a code citing it was READY. The listing places the act; the
    clause's own outcome decides it."""

    def test_a_failed_attempt_on_the_procedure_line_is_not_performed(self):
        text = (COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum. The appendiceal orifice '
                'was identified. ' + FAILED_SNARE + '\n')
        readings = acts_of(text, 'gi.colonoscopy', 'snare')
        self.assertTrue(readings)
        self.assertNotIn('performed', [status for status, _ in readings])
        self.assertTrue(all('performed: listed on the procedure line' not in cues for _, cues in readings))
        for label, (bucket, status) in zip(('corti', 'astra'), outcome(text, '45385', FAILED_SNARE)):
            with self.subTest(label):
                self.assertNotEqual(status, 'ready')

    def test_the_same_attempt_on_its_own_line_reads_the_same(self):
        on_line = (COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum. ' + FAILED_SNARE + '\n')
        own_line = (COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\n' + FAILED_SNARE
                    + '\n')
        self.assertEqual([status for status, _ in acts_of(on_line, 'gi.colonoscopy', 'snare')],
                         [status for status, _ in acts_of(own_line, 'gi.colonoscopy', 'snare')])
        self.assertEqual(outcome(on_line, '45385', FAILED_SNARE), outcome(own_line, '45385', FAILED_SNARE))

    def test_an_egd_dilation_attempt_on_the_procedure_line(self):
        text = (COLON_HEAD + 'Procedure: EGD. The gastroscope was advanced to the second portion of the duodenum. '
                + FAILED_DILATION + '\n')
        self.assertNotIn('performed', [status for status, _ in acts_of(text, 'gi.egd', 'dilation')])
        for label, (bucket, status) in zip(('corti', 'astra'), outcome(text, '43249', FAILED_DILATION)):
            with self.subTest(label):
                self.assertNotEqual(status, 'ready')

    def test_a_hedge_or_an_open_question_on_the_procedure_line_is_not_promoted(self):
        for sentence in ('Hot snare polypectomy of the sigmoid polyp was possibly performed.',
                         'It is unknown whether hot snare polypectomy of the sigmoid polyp was performed.'):
            with self.subTest(sentence):
                text = COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum. ' + sentence + '\n'
                self.assertNotIn('performed', [status for status, _ in acts_of(text, 'gi.colonoscopy', 'snare')])

    def test_a_labelled_procedures_line_with_its_attempt(self):
        line = 'Procedures performed: Colonoscopy; hot snare polypectomy attempted, unsuccessful.'
        text = COLON_HEAD + line + '\nThe colonoscope was advanced to the cecum.\n'
        self.assertNotIn('performed', [status for status, _ in acts_of(text, 'gi.colonoscopy', 'snare')])

    def test_a_bare_listing_is_still_placed_as_performed(self):
        # the control: a listing with no outcome of its own stands in for the performance statement, as before
        listing = 'Colonoscopy with cold snare polypectomy'
        text = (COLON_HEAD + 'Procedure: ' + listing + '\nThe colonoscope was advanced to the cecum. A 6 mm polyp was '
                'seen in the sigmoid colon.\n')
        self.assertIn('performed', [status for status, _ in acts_of(text, 'gi.colonoscopy', 'snare')])
        self.assertEqual(outcome(text, '45385', listing)[0], ('selected', 'ready'))

    def test_the_failure_is_one_shared_test(self):
        self.assertTrue(gi_services._outcome_in_doubt(('uncertain: attempted',)))
        self.assertTrue(gi_services._outcome_in_doubt(('uncertain: unsuccessful',)))
        self.assertTrue(gi_services._outcome_in_doubt((gi_services.CONDITION_CUE,)))
        self.assertFalse(gi_services._outcome_in_doubt(('uncertain: named without an act predicate',)))
        self.assertFalse(gi_services._outcome_in_doubt(('uncertain: no performance statement',)))


class CoordinatedAnatomyTests(SimpleTestCase):
    """U13: "from the right and left colon" had read the descending colon only (the left colon) - the coordinated
    modifier shares the site's head."""

    @staticmethod
    def sites(sentence):
        return [name for name, _, _, _ in gi_services._anatomy_in(sentence, 0, len(sentence))]

    def test_a_shared_head_reads_both_sites(self):
        cases = {
            'Random cold forceps biopsies were obtained from the right and left colon.': ['ascending colon',
                                                                                         'descending colon'],
            'Biopsies were obtained from the left and right colon.': ['descending colon', 'ascending colon'],
            'Biopsies were obtained from the proximal and distal esophagus.': ['proximal esophagus', 'distal esophagus'],
            'Biopsies were obtained from the mid and distal esophagus.': ['mid esophagus', 'distal esophagus'],
            'Biopsies were obtained from the upper or lower esophagus.': ['proximal esophagus', 'distal esophagus'],
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence):
                self.assertEqual(self.sites(sentence), expected)

    def test_a_coordination_of_whole_sites_adds_nothing(self):
        cases = {
            'Biopsies of the stomach and duodenal bulb.': ['stomach', 'duodenal bulb'],
            'Biopsies of the cecum and ascending colon.': ['cecum', 'ascending colon'],
            'Biopsies from the sigmoid and descending colon.': ['sigmoid colon', 'descending colon'],
            'Biopsies of the antrum and body.': ['gastric antrum and body'],
            'Biopsies from the left colon.': ['descending colon'],
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence):
                self.assertEqual(self.sites(sentence), expected)

    def test_the_act_carries_both_sites(self):
        biopsy = 'Random cold forceps biopsies were obtained from the right and left colon to evaluate for microscopic colitis.'
        text = (COLON_HEAD + 'Procedure: The colonoscope was advanced to the terminal ileum.\n' + biopsy + '\n')
        svc = next(s for s in inventory(text).services if s.family == 'gi.colonoscopy')
        act = next(a for a in svc.acts if a.kind == 'biopsy')
        self.assertEqual(act.anatomy, ('ascending colon', 'descending colon'))
