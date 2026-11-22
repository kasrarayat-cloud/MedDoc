"""Owner direction 2026-11-22 (D390): "make sure Fable covers every code ... I don't want to miss any". Nothing in CPT
Studio may drop a code Fable writes: a code written the way the CPT book prints an add-on ("+22614") is that code,
wherever the answer names it - a code line, a missed code, a review, the checker's correction, a question's target and
a section marker. Everything else stays as FIX-SPEC-2 section 2 decided: white space, lower case or a code joined to a
modifier make the answer unreadable rather than altered or guessed (tests/test_answer_fields.py). Plumbing only: it
decides no code (D358). Synthetic answers only; nothing reaches the network."""
from django.test import SimpleTestCase

from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r


def texts(found, key):
    return [item['text'] for item in found.get(key, [])]


class WrittenCodeTests(SimpleTestCase):
    def test_a_code_is_read_the_way_a_coder_reads_it(self):
        cases = {'+22614': '22614', '+63048': '63048', '+0075T': '0075T', '+L1832': 'L1832', '22614': '22614'}
        for written, read in cases.items():
            with self.subTest(written=written):
                self.assertEqual(result._written_code(written), read)
        # not of the code shape once read: returned as written, never guessed
        for kept in (' 22614 ', 'g0453', '+ 22614', '+22614 ', '22614-62', '+22614-62', 'L2', '++22614', '+2261', '',
                     'spine fusion'):
            with self.subTest(kept=kept):
                self.assertEqual(result._written_code(kept), kept)
        self.assertIsNone(result._written_code(None))

    def test_an_add_on_written_with_its_plus_is_a_code_line_not_a_failed_round(self):
        answer = f.reader_message(f.reader_result([f.code('22612'), f.code('+22614', units=2), f.code('+22840')]))
        lines = result.combine(result.read_reader(answer), result.read_checker(f.message(
            [f.text_block(f.fenced(f.checker_result([r.review('L1', '22612'), r.review('L2', '+22614'),
                                                     r.review('L3', '22840 ')])))])))['codes']
        self.assertEqual([(line['line'], line['code'], line['units']) for line in lines],
                         [('L1', '22612', 1), ('L2', '22614', 2), ('L3', '22840', 1)])
        # the reviews written with the same marks still match their lines: nothing is sent to manual review for it
        self.assertEqual([line['status'] for line in lines], ['ready', 'ready', 'ready'])

    def test_a_code_joined_to_a_modifier_still_fails_the_round_rather_than_being_guessed(self):
        with self.assertRaises(result.Unreadable):
            result.combine(result.read_reader(f.reader_message(f.reader_result([f.code('22614-62')]))),
                           result.read_checker(f.message([f.text_block(f.fenced(f.checker_result([])))])))

    def test_a_section_marker_with_the_plus_files_its_citations_under_its_line(self):
        reader = f.message([
            f.text_block('LINE L1 22612\n'),
            f.text_block('Fusion at L4-L5.', [f.page_cite('posterolateral arthrodesis L4-L5', 1)]),
            f.text_block('\n\nLINE L2 +22614\n'),
            f.text_block('A second level.', [f.page_cite('extended to L5-S1', 1)]),
            f.text_block('\nEND'),
            f.text_block(f.fenced(f.reader_result([f.code('22612'), f.code('+22614')])))])
        found = result.citations(reader, None)
        self.assertEqual((texts(found, 'L1'), texts(found, 'L2')),
                         (['posterolateral arthrodesis L4-L5'], ['extended to L5-S1']))
