"""GI round 4, package PS: the shared helpers in studio/gi/sections.py (head_lines_end, procedure_report_head,
around_procedure_title, under_another_occurrence, beyond_heading_reach). New functions only; nothing calls them yet, so
their expected delta is NONE (tests/test_gi4_freeze.py and tests/test_gi4_replay.py prove it). Each helper only ever
holds: these tests pin what makes it say True, what never does, and that its work is bounded. Every case is synthetic.

Each of ops/gi4/mutants.py's 'ps-*' mutants is killed here (H6): a test below fails when that guard is removed.
"""
import time

from django.test import SimpleTestCase

from ops.gi4 import regression
from studio.gi import sections

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
FILL = ''.join(f'Line {i} of the outside summary lists medications and allergies in detail.\n' for i in range(8))


class HeadLinesEndTests(SimpleTestCase):
    def test_counts_only_non_empty_lines(self):
        text = 'first\n\n   \n\t\nsecond\nthird\n'
        self.assertEqual(text[:sections.head_lines_end(text, 2)], 'first\n\n   \n\t\nsecond')
        self.assertEqual(sections.head_lines_end(text, 1), len('first'))

    def test_fewer_lines_than_asked_ends_at_the_last_non_empty_line(self):
        self.assertEqual(sections.head_lines_end('a\nb\n\n\n', 12), len('a\nb'))
        self.assertEqual(sections.head_lines_end('', 12), 0)
        self.assertEqual(sections.head_lines_end('\n \n\t\n', 3), 0)

    def test_a_whitespace_only_line_never_counts(self):  # kills ps-head-lines-blank
        text = 'title\n' + ' \n' * 20 + 'own field\n'
        self.assertEqual(text[:sections.head_lines_end(text, 2)].split('\n')[-1], 'own field')


class ProcedureReportHeadTests(SimpleTestCase):
    def test_the_regression_reports_have_their_own_head_fields(self):
        docs = regression.load_fixtures()
        for doc_id in ('h4-02', 'h4-03', 'h4-04', 'h4-05', 'h4-06', 'h2-10'):
            self.assertTrue(sections.procedure_report_head(docs[doc_id]['text']), doc_id)
        self.assertFalse(sections.procedure_report_head(docs['h4-01']['text']))  # an office visit: no such field

    def test_a_field_naming_who_performed_it_or_a_sedation_line(self):
        for line in ('Endoscopist: Synthetic MD', 'Proceduralist: Synthetic MD', 'Operator: Synthetic MD',
                     'Performing physician: Synthetic MD', 'Colonoscopist: Synthetic MD', 'Gastroenterologist: X',
                     'Attending physician: Synthetic MD', 'Sedation: propofol', 'Monitored anesthesia care',
                     'Given by a CRNA (fictional)', 'Midazolam 2 mg'):
            self.assertTrue(sections.procedure_report_head(B + 'Report\n' + line + '\n'), line)

    def test_records_reviews_letters_and_handouts_have_none(self):
        for title in ('GI Records Review', 'Clinic Correspondence', 'Patient Education Handout'):
            text = B + title + '\nDate of service: 10/20/2026\n\nSummary of outside records\n' + FILL
            self.assertFalse(sections.procedure_report_head(text), title)
        self.assertFalse(sections.procedure_report_head(B + 'Report\nThe attending reviewed the film: normal.\n'))

    def test_only_the_head_is_read(self):  # kills ps-procedure-head-reach
        text = B + 'GI Records Review\n' + FILL + 'More outside text.\n' * 3 + 'Copied block\nSedation: propofol by a CRNA\n'
        self.assertGreater(text.count('\n'), sections.PROCEDURE_HEAD_LINES)
        self.assertFalse(sections.procedure_report_head(text))
        self.assertTrue(sections.procedure_report_head(text, lines=40))


class AroundProcedureTitleTests(SimpleTestCase):
    def test_notes_written_around_a_procedure(self):
        for title in ('Pre-procedure telephone call', 'Endoscopy booking', 'Colonoscopy scheduling', 'Pre-op note',
                      'Preoperative assessment', 'Phone call with patient', 'Colonoscopy preparation instructions',
                      'Procedure consent', 'Patient Education Handout', 'Clinic Correspondence',
                      'Letter to the referring physician', 'GI Records Review', 'Outside records review',
                      '## Telephone Encounter ##', 'Education:'):
            self.assertTrue(sections.around_procedure_title(B + title + '\nDay of procedure: 11/04/2026\n'), title)

    def test_the_regression_documents_are_none(self):
        for doc_id, doc in regression.load_fixtures().items():
            self.assertFalse(sections.around_procedure_title(doc['text']), doc_id)

    def test_a_field_with_a_value_is_no_title(self):  # kills ps-around-title-field
        self.assertFalse(sections.around_procedure_title(B + 'Colonoscopy Report\nPhone: 555-0100\n'))
        self.assertFalse(sections.around_procedure_title(B + 'Colonoscopy Report\nConsent: signed\n'))

    def test_a_sentence_is_no_title(self):  # kills ps-around-title-sentence
        self.assertFalse(sections.around_procedure_title(B + 'Colonoscopy Report\nCall placed on 10/30/2026.\n'))
        self.assertFalse(sections.around_procedure_title(B + 'Colonoscopy Report\nConsent was signed, risks given;\n'))

    def test_only_the_title_block_is_read(self):
        text = B + 'Colonoscopy Report\nHensley (fictional)\nPOS 24\nPatient: X\nDOB: 1959-06-02\nIndication\n' \
                   'Procedure consent\n'
        self.assertFalse(sections.around_procedure_title(text))
        self.assertTrue(sections.around_procedure_title(text, lines=8))
        self.assertFalse(sections.around_procedure_title(B + 'Colonoscopy Report\n' + 'a ' * 300 + 'telephone\n'))


class UnderAnotherOccurrenceTests(SimpleTestCase):
    def test_the_nearest_heading_like_line_names_another_record(self):  # kills ps-under-occurrence-head
        text = B + 'Outside records reviewed\nThe colonoscope reached the cecum.\n'
        self.assertTrue(sections.under_another_occurrence(text, text.index('The colonoscope')))
        text = B + 'Index Examination\nThe colonoscope reached the cecum; a polyp was removed.\n'
        self.assertTrue(sections.under_another_occurrence(text, text.index('a polyp')))

    def test_its_own_line_before_the_position(self):
        text = B + 'Findings\nOutside report: the colonoscope reached the cecum.\n'
        self.assertTrue(sections.under_another_occurrence(text, text.index('the colonoscope')))

    def test_todays_heading_or_a_sentence_says_nothing(self):
        text = B + 'Findings\nThe colonoscope reached the cecum.\n'
        self.assertFalse(sections.under_another_occurrence(text, text.index('The colonoscope')))
        text = B + 'The prior report was reviewed.\nThe colonoscope reached the cecum.\n'
        self.assertFalse(sections.under_another_occurrence(text, text.index('The colonoscope')))

    def test_its_reach_is_bounded(self):
        text = B + 'Outside records reviewed\n' + 'x' * 700 + '\nThe colonoscope reached the cecum.\n'
        self.assertFalse(sections.under_another_occurrence(text, text.index('The colonoscope')))
        text = B + 'Outside records reviewed\nThe colonoscope reached the cecum.\n'
        self.assertFalse(sections.under_another_occurrence(text, text.index('The colonoscope'),
                                                           lo=text.index('The colonoscope')))


class BeyondHeadingReachTests(SimpleTestCase):
    H405 = (B + 'Pancreatic Endosonography\nService date: 2026-10-15\n\nPrior Studies\nEarlier EUS: 2025-04-09.\n\n'
            'Question to Answer\nIs the nodule tissue or mucin?\n\nScope Passage and Views\nA linear echoendoscope was '
            'introduced by mouth.\n')

    def test_an_unread_heading_like_line_between_heading_and_passage(self):  # kills ps-beyond-reach-heading-like
        lay = sections.layout(self.H405)
        pos = self.H405.index('A linear echoendoscope')
        self.assertEqual(lay.section_at(pos).kind, 'history')  # the installed layout: a runaway history section
        self.assertTrue(sections.beyond_heading_reach(self.H405, lay, pos))

    def test_a_passage_its_heading_reaches(self):
        lay = sections.layout(self.H405)
        self.assertFalse(sections.beyond_heading_reach(self.H405, lay, self.H405.index('Earlier EUS')))
        text = B + 'Findings\nThe surgeon recommended\nthe colonoscope reached the cecum.\n'
        lay = sections.layout(text)
        self.assertFalse(sections.beyond_heading_reach(text, lay, text.index('the colonoscope')))

    def test_text_before_the_first_heading(self):
        text = B + 'The colonoscope reached the cecum.\n'
        self.assertFalse(sections.beyond_heading_reach(text, sections.layout(text), text.index('The colonoscope')))

    def test_a_heading_beyond_reach_fails_closed(self):  # kills ps-beyond-reach-fail-closed
        text = B + 'Prior Studies\n' + ('a sentence of plain history text that ends here.\n' * 500) + 'The end.\n'
        self.assertGreater(len(text), sections.HEADING_REACH_CHARS)
        self.assertTrue(sections.beyond_heading_reach(text, sections.layout(text), text.index('The end.')))


class BoundedWorkTests(SimpleTestCase):
    def test_each_helper_reads_a_bounded_part_of_a_long_text(self):
        texts = ('x' * 400_000, '\n' * 400_000 + 'title\n', 'Telephone ' * 40_000 + '\n',
                 B + 'Prior Studies\n' + 'Some Heading Line\nA line.\n' * 20_000)
        for text in texts:
            t0 = time.perf_counter()
            sections.head_lines_end(text, 12)
            sections.procedure_report_head(text)
            sections.around_procedure_title(text)
            sections.under_another_occurrence(text, len(text) - 1)
            self.assertLess(time.perf_counter() - t0, 2.0)
        text = texts[-1]
        lay = sections.layout(text)
        t0 = time.perf_counter()
        self.assertTrue(sections.beyond_heading_reach(text, lay, len(text) - 2))
        self.assertLess(time.perf_counter() - t0, 1.0)
