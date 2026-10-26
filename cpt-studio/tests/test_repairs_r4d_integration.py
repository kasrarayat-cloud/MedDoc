"""Round 4d integration (lead): what the round-4d verifiers confirmed and the repairs left open, fixed on the integrated
head.

- BOXES3's verifier, new problem 6 (low): on a row that pairs both ways, one reading giving an item a checked box and the
  other none read it checked ("Biopsy: ☒ Cold snare polypectomy" under "Procedures performed today:"), releasing round
  4c's performed-today hold against the strict rows.
- New problem 2 (medium): ordinary lines above the separately identifiable E/M statement refused it ("Allergies
  confirmed: none.", "Consent: patient agrees.").
- New problems 3 and 4 (medium): a done-question about a prior procedure ("Prior colonoscopy performed? No"), or one
  whose noun ran across a sentence end ("Colonoscopy to the cecum. Biopsy done? No"), held today's procedure.
- New problem 7 (low): one box before a sentence over 1,000 characters was held, with a cue saying its boxes "cannot be
  paired in exactly one way" - a row nobody tried to pair.
Every older tree read these inputs as the fixes now do. Round 6 sections:4 (the office visit's E/M held beside a line
under an answered plan label) is NOT fixed here: routing's hold of such a line records only its layout cue, so validation
cannot tell "Upper endoscopy with dilation." from "Upper endoscopy with dilation today." - releasing both would drop the
same-day question for the second. It stays a known limit (ACCURACY-RESIDUALS.md). Synthetic data only.
"""
import unittest

from studio.gi import detect
from tests.test_repairs_r4d_boxes3 import ATTEST_NOTE, HEAD, family, outcome, read, separate_em_fact

COLONOSCOPY = HEAD + ('Procedure: Colonoscopy\nIndication: Average-risk screening.\n{line}\nFindings: The colonoscope was '
                      'advanced to the cecum. A 6 mm sigmoid polyp was seen and removed with a cold snare.\n'
                      'Impression: Sigmoid polyp.\n')
EGD = HEAD + ('Procedure: EGD\nIndication: Dyspepsia.\n{line}\nFindings: The gastroscope was advanced to the second part '
              'of the duodenum. Biopsies were taken from the antrum.\nImpression: Gastritis.\n')
EUS = HEAD + 'Procedure: EUS with fine-needle aspiration of the pancreatic head mass\n{line}\n'


class OneReadingAloneIsNoCheckedBoxTests(unittest.TestCase):
    NOTE = HEAD + ('Procedure: Colonoscopy\nIndication: Screening.\nProcedures performed today:\n{row}\n'
                   'Findings: The colonoscope was advanced to the cecum.\n')

    def test_an_item_label_row_with_one_box_holds_both_items(self):
        for row in ('Biopsy: ☒ Cold snare polypectomy', 'Biopsy: [x] Cold snare polypectomy',
                    'Biopsy:\t☒ Cold snare polypectomy', 'Biopsy:  ☒ Cold snare polypectomy'):
            text = self.NOTE.format(row=row)
            with self.subTest(row=row):
                self.assertEqual(read(text, 'Biopsy')[0], 'uncertain')
                self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'uncertain')
                self.assertEqual(outcome(text, '45380', 'Biopsy'), 'held')

    def test_controls_a_box_that_only_one_way_can_govern_is_read(self):
        for row, phrase, status in (('☒ Biopsy', 'Biopsy', 'performed'),
                                     ('Biopsy | ☒', 'Biopsy', 'performed'),
                                     ('☐ Biopsy', 'Biopsy', 'negated')):
            with self.subTest(row=row):
                self.assertEqual(read(self.NOTE.format(row=row), phrase)[0], status)


class OnlyTheAttestationItselfRefusesFromAboveTests(unittest.TestCase):
    ORDINARY = ('Allergies confirmed: none.', 'Consent: patient agrees.', 'Diagnosis not confirmed.',
                'Patient agrees with plan - no questions.', 'Medications reviewed and confirmed.', 'Notes: Agree',
                'The patient acknowledges the risks of banding.', 'Plan confirmed with the patient: no changes.')
    REFUSING = ('☐ Separate E/M attestation:', '☐ Attested', 'Attested: ☐', '[ ] Attested',
                'Attested | [ ]', 'Separate E/M attested: No', 'Attestation: pending', 'E/M attestation: Not attested',
                'Notes: Not attested', 'Attestation: I do not attest to a separate service today.', 'Unattested',
                'Modifier 25 not appended', 'I cannot confirm a separately identifiable service today.',
                'I cannot confirm that a separate service was provided.',
                '☐ Confirmed', '☐ Patient agrees')

    def test_an_ordinary_line_above_the_statement_leaves_it_attesting(self):
        for line in self.ORDINARY:
            with self.subTest(line=line):
                self.assertEqual(separate_em_fact(ATTEST_NOTE.format(above=line + '\n', under='')), 'documented')

    def test_controls_a_line_about_the_attestation_or_its_box_still_refuses_it(self):
        for line in self.REFUSING:
            with self.subTest(line=line):
                self.assertIsNone(separate_em_fact(ATTEST_NOTE.format(above=line + '\n', under='')))


class ADoneQuestionAboutAnotherTimeTests(unittest.TestCase):
    def test_a_question_about_a_prior_procedure_never_holds_todays(self):
        for template, line, slug in (
                (COLONOSCOPY, 'Prior colonoscopy performed? No', 'gi.colonoscopy'),
                (COLONOSCOPY, 'Previous colonoscopy done? No', 'gi.colonoscopy'),
                (COLONOSCOPY, 'Any prior colonoscopy performed? No', 'gi.colonoscopy'),
                (COLONOSCOPY, 'Last colonoscopy completed? No', 'gi.colonoscopy'),
                (EGD, 'Prior EGD performed? No', 'gi.egd')):
            with self.subTest(line=line):
                self.assertEqual(family(template.format(line=line), slug), 'performed')

    def test_a_question_never_reaches_back_across_a_sentence_end(self):
        for template, line, slug in (
                (COLONOSCOPY, 'Colonoscopy to the cecum. Biopsy done? No', 'gi.colonoscopy'),
                (COLONOSCOPY, 'Colonoscopy to the cecum; biopsy performed? No', 'gi.colonoscopy'),
                (EGD, 'EGD with biopsies of the antrum. Dilation performed? No', 'gi.egd')):
            with self.subTest(line=line):
                self.assertEqual(family(template.format(line=line), slug), 'performed')

    def test_controls_todays_service_answered_no_is_still_held(self):
        for template, line, slug in ((COLONOSCOPY, 'Colonoscopy performed? No', 'gi.colonoscopy'),
                                     (EGD, 'EGD performed? No', 'gi.egd'),
                                     (EUS, 'Was the EUS performed today? No', 'gi.eus'),
                                     (EUS, 'Was the EUS with FNA performed today? No', 'gi.eus')):
            with self.subTest(line=line):
                self.assertEqual(family(template.format(line=line), slug), 'uncertain')


def long_sentence(chars):
    parts, n = [], 0
    segments = ('ascending colon', 'transverse colon', 'descending colon', 'sigmoid colon', 'rectum', 'hepatic flexure')
    while len(', '.join(parts)) < chars:
        parts.append(f'a {3 + n % 7} mm sessile polyp in the {segments[n % len(segments)]} removed en bloc and retrieved')
        n += 1
    return ', '.join(parts)


class OneBoxOnALongRowTests(unittest.TestCase):
    BASE = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n{row}\n'

    def test_one_checked_box_before_a_long_sentence_is_read(self):
        for chars in (900, 1200, 4000):
            text = self.BASE.format(row='☒ Cold snare polypectomy, with ' + long_sentence(chars) + '.')
            with self.subTest(chars=len(text)):
                self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'performed')
                self.assertEqual(outcome(text, '45385', 'Cold snare polypectomy'), 'ready')

    def test_controls_two_boxes_on_a_long_row_are_held_and_the_cue_says_why(self):
        # one row: no sentence end between the two boxes (a period would start the second box's own row)
        text = self.BASE.format(row='☒ Cold snare polypectomy with ' + long_sentence(1200) + ' ☐ Biopsy')
        status, cues = read(text, 'Cold snare polypectomy')[:2]
        self.assertEqual(status, 'uncertain')
        held = [c for c in cues if c.startswith('uncertain: the check boxes on the line ')]
        self.assertTrue(held, cues)
        self.assertIn('are not paired with its entries (the row is too long', held[0])
        self.assertNotIn('in exactly one way', held[0])


if __name__ == '__main__':
    unittest.main()
