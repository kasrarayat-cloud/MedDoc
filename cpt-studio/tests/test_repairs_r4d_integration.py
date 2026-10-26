"""Round 4d integration (lead): what the round-4d verifiers confirmed and the repairs left open, fixed on the integrated
head.

- BOXES3's verifier, new problem 6 (low): on a row that pairs both ways, a checked box that only one reading gives an
  item lifted round 4c's performed-today hold ("Biopsy: ☒ Cold snare polypectomy" under "Procedures performed
  today:"). Only that hold now asks for a box every reading gives the item; elsewhere the row reads as every tree read
  it (a two-column PDF form's "Biopsy: ☒ <the next column's sentence>" stays ready: round 4 extraction:0's pin).
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
import re
import unittest

from studio.gi import detect
from tests.test_repairs_r4d_boxes3 import ATTEST_NOTE, HEAD, D, family, outcome, read, separate_em_fact

COLONOSCOPY = HEAD + ('Procedure: Colonoscopy\nIndication: Average-risk screening.\n{line}\nFindings: The colonoscope was '
                      'advanced to the cecum. A 6 mm sigmoid polyp was seen and removed with a cold snare.\n'
                      'Impression: Sigmoid polyp.\n')
EGD = HEAD + ('Procedure: EGD\nIndication: Dyspepsia.\n{line}\nFindings: The gastroscope was advanced to the second part '
              'of the duodenum. Biopsies were taken from the antrum.\nImpression: Gastritis.\n')
EUS = HEAD + 'Procedure: EUS with fine-needle aspiration of the pancreatic head mass\n{line}\n'


class OneReadingAloneIsNoCheckedBoxTests(unittest.TestCase):
    NOTE = HEAD + ('Procedure: Colonoscopy\nIndication: Screening.\nProcedures performed today:\n{row}\n'
                   'Findings: The colonoscope was advanced to the cecum.\n')

    def test_under_a_performed_today_label_one_reading_alone_lifts_no_hold(self):
        for row in ('Biopsy: ☒ Cold snare polypectomy', 'Biopsy: [x] Cold snare polypectomy',
                    'Biopsy:\t☒ Cold snare polypectomy', 'Biopsy:  ☒ Cold snare polypectomy'):
            text = self.NOTE.format(row=row)
            with self.subTest(row=row):
                self.assertEqual(read(text, 'Biopsy')[0], 'uncertain')
                self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'uncertain')
                self.assertEqual(outcome(text, '45380', 'Biopsy'), 'held')

    def test_outside_that_label_the_row_reads_as_every_tree_read_it(self):
        text = HEAD + ('Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp '
                       'was seen.\nBiopsy: \u2612 Cold snare polypectomy\n')
        self.assertEqual(read(text, 'Biopsy')[0], 'performed')
        self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'performed')

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


# --- a list member's tail: the next service name after spaces and commas is read without masking to the window's end -

from unittest import mock  # noqa: E402

from studio.gi import cues  # noqa: E402

LEADS = ('', ' ', ',', ', ', ' ,', ',,', '\t, ', ' , ,  ')
# Continuations that each tail reader accepts at a tail's start (the positive control below proves every reader
# matches one of them when no service token stands before it).
TAILS = (' was not performed', ' not performed', ' were not.', ': not performed', ' (not performed)', ', declined',
         ' was declined', ' was incomplete', ' attempted', ' - partial', ' if needed', ' ?', ' pending', ': pending',
         ' was discussed', ' may be needed', ' may have been performed', ' of the cecum may have been taken',
         ' would be done', ' possibly performed', ': unsure', ' related', '-related', ' complications', ' findings',
         ' were not performed', ' n/a', ' none', ' no')
READERS = ([(f'NEGATED_POST {label}', p) for label, p in cues.NEGATED_POST]
           + [(f'INCOMPLETE_POST {label}', p) for label, p in cues.INCOMPLETE_POST]
           + [(f'UNCERTAIN_POST {label}', p) for label, p in cues.UNCERTAIN_POST]
           + [('NEGATION_HEAD_AFTER', cues.NEGATION_HEAD_AFTER)])


class ListTailTests(unittest.TestCase):
    def test_every_tail_reader_fails_on_a_tail_that_opens_with_the_next_service(self):
        for label, reader in READERS:
            with self.subTest(reader=label):
                self.assertTrue(any(reader.match(tail) for tail in TAILS), f'no continuation exercises {label}')
                for lead in LEADS:
                    for tail in TAILS + ('',):
                        self.assertIsNone(reader.match(lead + detect.LIST_TAIL + tail), (lead, tail))
                        self.assertIsNone(reader.match(lead + detect.LIST_TAIL.rstrip() + tail), (lead, tail))
        for lead in LEADS:  # what the fast path stands in for: a tail that opens like this, whatever follows
            self.assertIsNotNone(re.fullmatch(r'[\s,]*' + re.escape(detect.LIST_TAIL.strip()) + r'\b.*',
                                              lead + detect.LIST_TAIL + 'was not performed'))

    def readings(self, text):
        detect._analysis.cache_clear()
        an = detect._analysis(text, D)[0]
        routed = detect._route(an)
        spans = [detect.status_for_span(text, s, e, D)[:2] for s, e in an.lay.sentences if e > s]
        return [(f.family, f.status, tuple(m.status for m in f.mentions)) for f in routed.findings], spans

    def test_the_readings_are_those_the_whole_masked_tail_gives(self):
        texts = [HEAD + 'Procedure: Colonoscopy\nFindings: ' + body + '\n' for body in (
            'EUS, EGD were not performed.', 'EUS, EGD, colonoscopy pending.', 'No EUS, EGD complications were seen.',
            'EUS, EGD and ERCP may have been performed.', 'EUS, EGD were declined.', 'EUS,, EGD, ERCP - not performed',
            'EGD, EUS (not performed), colonoscopy.', 'EUS, EGD was incomplete.', 'EUS, EGD if needed.',
            'EUS, ' * 300 + 'EGD were not performed.', 'Colonoscopy, EGD, EUS; ERCP was cancelled.')]
        slow = detect._masked
        for text in texts:
            with self.subTest(text=text[len(HEAD):][:60]):
                fast = self.readings(text)
                with mock.patch.object(detect, '_masked_post', lambda an, me, ce: slow(an, me, ce)):
                    whole = self.readings(text)
                self.assertEqual(fast, whole)

    def test_controls_a_tail_that_says_something_is_still_read(self):
        # the equivalence above compares the two paths; these pin what the tails themselves say
        for body, phrase, status in (('EUS, EGD were not performed.', 'EUS', 'negated'),
                                     ('EUS, EGD were not performed.', 'EGD', 'negated'),
                                     ('EUS, EGD, colonoscopy pending.', 'colonoscopy', 'uncertain'),
                                     ('EUS, EGD, colonoscopy pending.', 'EUS', 'uncertain'),
                                     ('EUS, EGD was incomplete.', 'EGD', 'incomplete')):
            text = HEAD + 'Procedure: Colonoscopy\nFindings: ' + body + '\n'
            with self.subTest(body=body, phrase=phrase):
                start = text.index(phrase, text.index('Findings: '))
                self.assertEqual(detect.status_for_span(text, start, start + len(phrase), D)[0], status)

    def test_a_list_member_tail_is_not_masked_to_the_windows_end(self):
        text = HEAD + 'Findings: ' + 'EUS, ' * 400 + 'done.\n'
        counts = {}
        for name, patch in (('fast', None), ('whole', lambda an, me, ce: original(an, me, ce))):
            original = detect._masked
            calls = []

            def counting(an, start, end):
                calls.append(1)
                return original(an, start, end)
            patches = [mock.patch.object(detect, '_masked', counting)]
            if patch is not None:
                patches.append(mock.patch.object(detect, '_masked_post', lambda an, me, ce: counting(an, me, ce)))
            detect._analysis.cache_clear()
            with patches[0]:
                if len(patches) > 1:
                    with patches[1]:
                        detect.route(text, D)
                else:
                    detect.route(text, D)
            counts[name] = len(calls)
        self.assertLess(counts['fast'] * 3, counts['whole'], counts)
