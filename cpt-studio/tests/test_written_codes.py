"""Owner direction 2026-11-22 (D390): "make sure Fable covers every code ... I don't want to miss any". Nothing in CPT
Studio may drop a code Fable writes: a code line written the way the CPT book prints an add-on or a resequenced code ("+22614",
"#+22853") is that code, in a reader code, a missed code and a section marker; a review, the checker's correction and a
question's target are read as main reads them, so stored rounds show what they showed (refutation N1-1-1). Everything else stays as FIX-SPEC-2 section 2 decided: white space, lower case or a code joined to a
modifier make the answer unreadable rather than altered or guessed (tests/test_answer_fields.py). Plumbing only: it
decides no code (D358). Synthetic answers only; nothing reaches the network."""
from django.test import SimpleTestCase

from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r


def texts(found, key):
    return [item['text'] for item in found.get(key, [])]


class WrittenCodeTests(SimpleTestCase):
    def test_a_code_lines_code_is_read_with_the_books_marks_set_aside(self):
        cases = {'+22614': '22614', '#22853': '22853', '+#22853': '22853', '#+22853': '22853', '+63048': '63048',
                 '+0075T': '0075T', '+L1832': 'L1832', '22614': '22614'}
        for written, read in cases.items():
            with self.subTest(written=written):
                self.assertEqual(result._written_code(written), read)
        # not of the code shape once the marks are set aside: returned as written, never guessed
        for kept in (' 22614 ', 'g0453', '+ 22614', '+22614 ', ' +22614', '22614-62', '+22614-62', 'L2', '++22614',
                     '##22853', '+#+22853', '+2261', '', 'spine fusion'):
            with self.subTest(kept=kept):
                self.assertEqual(result._written_code(kept), kept)
        self.assertIsNone(result._written_code(None))

    def test_an_add_on_written_with_its_mark_is_a_code_line_not_a_failed_round(self):
        answer = f.reader_message(f.reader_result([f.code('22612'), f.code('+22614', units=2), f.code('#+22853')]))
        checker = f.message([f.text_block(f.fenced(f.checker_result([r.review('L1', '22612'), r.review('L2', '22614'),
                                                                       r.review('L3', '22853')])))])
        lines = result.combine(result.read_reader(answer), result.read_checker(checker))['codes']
        self.assertEqual([(line['line'], line['code'], line['units'], line['status']) for line in lines],
                         [('L1', '22612', 1, 'ready'), ('L2', '22614', 2, 'ready'), ('L3', '22853', 1, 'ready')])
        missed = result.read_checker(f.message([f.text_block(f.fenced(f.checker_result(
            [r.review('L1', '22612')], missed=[r.missed('+22614')])))]))
        self.assertEqual([line['code'] for line in result.combine(result.read_reader(f.reader_message(
            f.reader_result([f.code('22612')]))), missed)['codes']], ['22612', '22614'])

    def test_a_review_is_read_as_main_reads_it_so_stored_rounds_show_what_they_showed(self):
        # refutation N1-1-1: a stored round is read again whenever a page shows it, so a review keeps the reading it
        # was stored under - a review written "+99153" stays a review that names no line's code, its note shown
        reader = f.reader_result([f.code('43239'), f.code('99153')])
        checker = f.checker_result([r.review('L1', '43239'), r.review('L2', '+99153', 'disagree',
                                                                       reason='Sedation lasted 20 minutes.')])
        lines = result.combine(reader, checker)['codes']
        self.assertEqual([line['status'] for line in lines], ['ready', 'needs_review'])
        unmatched = result.unmatched_reviews(lines, checker)
        self.assertEqual([(item['number'], item['review']['code'], item['reaches']) for item in unmatched],
                         [(2, '+99153', ['L2'])])

    def test_a_code_joined_to_a_modifier_still_fails_the_round_rather_than_being_guessed(self):
        with self.assertRaises(result.Unreadable):
            result.combine(result.read_reader(f.reader_message(f.reader_result([f.code('22614-62')]))),
                           result.read_checker(f.message([f.text_block(f.fenced(f.checker_result([])))])))

    def test_a_section_marker_with_the_books_marks_files_its_citations_under_its_line(self):
        reader = f.message([
            f.text_block('LINE L1 22612\n'),
            f.text_block('Fusion at L4-L5.', [f.page_cite('posterolateral arthrodesis L4-L5', 1)]),
            f.text_block('\n\nLINE L2 +22614\n'),
            f.text_block('A second level.', [f.page_cite('extended to L5-S1', 1)]),
            f.text_block('\n\nLINE L3 #+22853\n'),
            f.text_block('A cage.', [f.page_cite('interbody cage at L4-L5', 1)]),
            f.text_block('\nEND'),
            f.text_block(f.fenced(f.reader_result([f.code('22612'), f.code('+22614'), f.code('#+22853')])))])
        found = result.citations(reader, None)
        self.assertEqual((texts(found, 'L1'), texts(found, 'L2'), texts(found, 'L3')),
                         (['posterolateral arthrodesis L4-L5'], ['extended to L5-S1'], ['interbody cage at L4-L5']))
