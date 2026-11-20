"""studio.fable.result (BUILD-SPEC 4.4-4.6; the fix pass, FIX-SPEC sections 1-3): the final JSON, shape-only validation,
the code lines, the combination of the two reads and the citations per line. Synthetic answers only. The findings'
own cases are in tests/test_answer_shape.py, test_line_identity.py, test_citation_sections.py and
test_round_questions.py."""
from django.test import SimpleTestCase

from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r


class ParseTests(SimpleTestCase):
    def test_only_the_last_fenced_block_is_read(self):
        broken = 'analysis\n```json\n{"a": 1}\n```\nmore\n```json\n{"a": 2}\n```\nand\n```json\n{broken\n```'
        self.assertIsNone(result.last_json(broken))
        self.assertEqual(result.last_json('```json\n{"a": 1}\n```\nthen\n```json\n{"a": 2}\n```'), {'a': 2})
        # a fence opens and closes only on a line of its own (markdown): ``` inside a line is text, never a fence
        self.assertEqual(result.last_json('Use ```json``` blocks.\n```json\n{"a": 3}\n```'), {'a': 3})

    def test_without_a_fence_the_widest_brace_span_is_read(self):
        self.assertEqual(result.last_json('The result: {"codes": [{"code": "45380"}]} done.'),
                         {'codes': [{'code': '45380'}]})

    def test_nothing_parseable_is_none(self):
        self.assertIsNone(result.last_json('no json here {not json}'))
        self.assertIsNone(result.last_json(''))
        self.assertIsNone(result.last_json('```json\n' + '[' * 100_000 + '\n```'))  # too deep for the parser

    def test_the_text_blocks_are_joined_in_order_and_other_blocks_skipped(self):
        message = f.message([{'type': 'thinking', 'thinking': '', 'signature': 'x'}, f.text_block('one '),
                             {'type': 'fallback', 'from': {'model': 'a'}, 'to': {'model': 'b'}}, f.text_block('two')])
        self.assertEqual(result.message_text(message), 'one two')

    def test_a_reader_answer_without_a_json_object_is_unreadable(self):
        for text in ('no json at all', '```json\n[1, 2]\n```', '```json\n{"document_kind": "x"}\n```'):
            with self.subTest(text=text), self.assertRaises(result.Unreadable):
                result.read_reader(f.message([f.text_block(text)]))

    def test_a_code_that_is_not_a_string_or_a_status_outside_the_three_is_unreadable(self):
        for bad in ({'code': 45380, 'status': 'ready'}, {'code': '  ', 'status': 'ready'},
                    {'code': '45380', 'status': 'Ready'}, {'code': '45380'}, 'not an object'):
            with self.subTest(bad=bad), self.assertRaises(result.Unreadable):
                result.read_reader(f.message([f.text_block(f.fenced(f.reader_result([bad])))]))

    def test_the_checker_needs_a_list_of_reviews_and_named_missed_codes(self):
        for bad in ({'missed_codes': []}, {'reviews': {}, 'missed_codes': []},
                    {'reviews': [], 'missed_codes': {'code': '45380'}}, {'reviews': [], 'missed_codes': [{'units': 1}]}):
            with self.subTest(bad=bad), self.assertRaises(result.Unreadable):
                result.read_checker(f.message([f.text_block(f.fenced(bad))]))

    def test_the_parsed_result_is_kept_as_written(self):
        written = f.reader_result([f.code('45385', units='1', modifiers=[59])])
        self.assertEqual(result.read_reader(f.reader_message(written)), written)
        checker = f.checker_result([r.review('L1', '45385', 'agree')], missed=[r.missed('45378', modifiers=[59])])
        self.assertEqual(result.read_checker(f.checker_message(checker)), checker)


class CombineTests(SimpleTestCase):
    def combine(self, codes, reviews, missed=(), reader_questions=(), checker_questions=(), problems=()):
        reader = f.reader_result(codes, questions=reader_questions, problems=problems)
        checker = f.checker_result(reviews, missed=missed, questions=checker_questions)
        return result.combine(reader, checker)

    def test_an_agreed_code_keeps_the_readers_status(self):
        for status in ('ready', 'needs_answer', 'not_supported'):
            with self.subTest(status=status):
                combined = self.combine([f.code('45385', status, question='Q?')], [r.review('L1', '45385', 'agree')])
                row = combined['codes'][0]
                self.assertEqual((row['line'], row['status'], row['listed_status']), ('L1', status, status))
                self.assertIs(row['second_check']['agrees'], True)
                self.assertEqual((row['second_check']['reviews'], row['second_check']['unmatched'],
                                  row['second_check']['unplaced']), (1, 0, 0))

    def test_a_disagreement_or_no_review_makes_needs_review_with_both_reasons(self):
        combined = self.combine([f.code('45385', reason='Reader reason.'), f.code('45380')],
                                [r.review('L1', '45385', 'disagree', reason='Checker reason.')])
        disagreed, unreviewed = combined['codes']
        self.assertEqual(disagreed['status'], 'needs_review')
        self.assertEqual(disagreed['reason'], 'Reader reason.')
        self.assertEqual(disagreed['second_check']['reason'], 'Checker reason.')
        self.assertIs(disagreed['second_check']['agrees'], False)
        self.assertEqual(unreviewed['status'], 'needs_review')
        self.assertIsNone(unreviewed['second_check']['agrees'])
        self.assertEqual(unreviewed['second_check']['reviews'], 0)

    def test_a_verdict_other_than_exactly_agree_is_not_agreement(self):
        for verdict in ('Agree', 'agrees', None, 1):
            with self.subTest(verdict=verdict):
                item = {**r.review('L1', '45385'), 'verdict': verdict}
                self.assertEqual(self.combine([f.code('45385')], [item])['codes'][0]['status'], 'needs_review')

    def test_a_line_reviewed_twice_agrees_only_when_every_review_agrees(self):
        both = self.combine([f.code('45385')], [r.review('L1', '45385'), r.review('L1', '45385', 'disagree',
                                                                                  reason='No.')])
        self.assertEqual(both['codes'][0]['status'], 'needs_review')
        self.assertEqual(both['codes'][0]['second_check']['reason'], 'No.')
        agreed = self.combine([f.code('45385')], [r.review('L1', '45385'), r.review(' l1 ', ' 45385 ')])
        self.assertEqual(agreed['codes'][0]['status'], 'ready')
        self.assertEqual(agreed['codes'][0]['second_check']['reviews'], 2)

    def test_an_unmatched_review_is_counted_on_the_lines_it_reaches(self):
        combined = self.combine([f.code('45385'), f.code('45380')],
                                [r.review('L1', '45385'), r.review('L2', '45380'), f.review('45385', 'disagree')])
        first, second = combined['codes']
        self.assertEqual((first['status'], first['second_check']['agrees'], first['second_check']['unmatched']),
                         ('needs_review', True, 1))
        self.assertEqual((second['status'], second['second_check']['unmatched']), ('ready', 0))
        self.assertEqual({first['second_check']['unplaced'], second['second_check']['unplaced']}, {0})
        # a review naming an unknown line and a code no line holds: the code cannot tell which line it is about, so
        # every line goes to a human (FIX-SPEC-2 section 3)
        placed_nowhere = self.combine([f.code('45385'), f.code('45380')],
                                      [r.review('L1', '45385'), r.review('L2', '45380'),
                                       r.review('L7', '99999', 'disagree')])['codes']
        self.assertEqual([(row['status'], row['second_check']['unmatched'], row['second_check']['unplaced'])
                          for row in placed_nowhere], [('needs_review', 0, 1), ('needs_review', 0, 1)])

    def test_missed_codes_are_added_as_needs_review_lines(self):
        missed = {'code': '45380', 'units': 1, 'modifiers': ['59'], 'status': 'ready', 'reason': 'Biopsy taken.',
                  'evidence': [], 'question': None}
        combined = self.combine([f.code('45385')], [r.review('L1', '45385')], missed=[missed])
        added = combined['codes'][1]
        self.assertEqual((added['line'], added['code'], added['status'], added['listed_by'], added['listed_status']),
                         ('M1', '45380', 'needs_review', 'checker', 'ready'))
        self.assertEqual(added['modifiers'], ['59'])
        self.assertIsNone(added['second_check'])

    def test_a_field_is_read_in_its_shape_and_an_integer_modifier_is_its_string(self):
        item = {**f.code('45385'), 'units': '2', 'modifiers': ['59', 7], 'reason': ['x', 'y'], 'question': None,
                'evidence': [{'quote': 'ok', 'page': 'one'}, {'quote': 5}, 'text']}
        shown = self.combine([item], [r.review('L1', '45385')])['codes'][0]
        self.assertEqual((shown['units'], shown['modifiers'], shown['reason'], shown['question']),
                         (2, ['59', '7'], 'x y', None))
        self.assertEqual(shown['evidence'], [{'quote': 'ok', 'page': None}])
        self.assertEqual(shown['code'], '45385')
        for units in (-1, 1.0, True, '2.0'):  # any other shape cannot be read (FIX-SPEC-2 section 2)
            with self.subTest(units=units), self.assertRaises(result.Unreadable):
                self.combine([{**f.code('45385'), 'units': units}], [r.review('L1', '45385')])
        # zero is a value, shown as written: the reader writes it for a code it does not support
        zero = self.combine([{**f.code('45385', 'not_supported'), 'units': 0}], [r.review('L1', '45385')])['codes'][0]
        self.assertEqual(zero['units'], 0)

    def test_questions_are_both_lists_with_folded_duplicates_shown_once(self):
        combined = self.combine(
            [f.code('45385')], [r.review('L1', '45385')],
            reader_questions=[{'question': 'Was the  polyp\nremoved whole?', 'affects': ['45385']}, '  '],
            checker_questions=[{'question': 'WAS the polyp removed whole?', 'affects': ['45380']},
                               {'question': 'Which payer applies?', 'affects': None}])
        self.assertEqual(combined['questions'], [
            {'id': 'q1', 'text': 'Was the  polyp\nremoved whole?', 'lines': ['L1'], 'codes': ['45385'],
             'source': 'reader'},
            {'id': 'q2', 'text': 'Which payer applies?', 'lines': [], 'codes': [], 'source': 'checker'}])

    def test_problems_are_the_readers_documentation_problems(self):
        combined = self.combine([f.code('45385')], [r.review('L1', '45385')], problems=['No signature.', 4])
        self.assertEqual(combined['problems'], ['No signature.', '4'])

    def test_the_listing_the_checker_is_given(self):
        reader = f.reader_result([f.code('45385', modifiers=['PT'], question=None)])
        self.assertEqual(result.listing(reader), [{'line': 'L1', 'code': '45385', 'units': 1, 'modifiers': ['PT'],
                                                   'status': 'ready', 'question': None}])


class CitationTests(SimpleTestCase):
    READER = f.reader_result([f.code('45385'), f.code('45380'), f.code('0001U')])

    def test_citations_follow_the_line_and_review_sections(self):
        reader = f.message([
            f.text_block('Overview of the note.', [f.page_cite('SYNTHETIC PROCEDURE NOTE', 1)]),
            f.text_block('\nLINE L1 45385\n'),
            f.text_block('Snare removal.', [f.page_cite('removed by cold snare', 2)]),
            f.text_block('\n### LINE L2 45380\n'), f.text_block('Biopsy taken.', [f.page_cite('biopsy', 3)]),
            f.text_block(f.fenced(self.READER))])
        checker = f.message([f.text_block('REVIEW L1 45385\n'), f.text_block('Agreed.', [f.char_cite('cold snare', 10)]),
                             f.text_block(f.fenced(f.checker_result([r.review('L1', '45385')])))])
        found = result.citations(reader, checker)
        self.assertEqual(found['_document'], [{'text': 'SYNTHETIC PROCEDURE NOTE', 'page': 1, 'source': 'reader'}])
        self.assertEqual(found['L1'], [{'text': 'removed by cold snare', 'page': 2, 'source': 'reader'},
                                       {'text': 'cold snare', 'page': None, 'source': 'checker'}])
        self.assertEqual(found['L2'], [{'text': 'biopsy', 'page': 3, 'source': 'reader'}])

    def test_markers_are_case_sensitive_whole_lines(self):
        reader = f.message([f.text_block('Code: 45385\nText.', [f.page_cite('x', 1)]),
                            f.text_block('\nLINE L3 0001U\n'), f.text_block('Lab.', [f.page_cite('y', 2)]),
                            f.text_block('\nline L1 45385\n'), f.text_block('Text.', [f.page_cite('z', 3)]),
                            f.text_block(f.fenced(self.READER))])
        found = result.citations(reader, None)
        self.assertEqual({key: [item['text'] for item in items] for key, items in found.items()},
                         {'_document': ['x', 'z'], 'L3': ['y']})

    def test_a_checker_marker_in_the_reader_answer_starts_no_section(self):
        reader = f.message([f.text_block('REVIEW L1 45385\nText.', [f.page_cite('x', 1)]),
                            f.text_block(f.fenced(self.READER))])
        self.assertEqual(result.citations(reader, f.message([])), {'_document': [
            {'text': 'x', 'page': 1, 'source': 'reader'}]})

    def test_an_answer_whose_final_json_cannot_be_read_files_nothing_under_a_line(self):
        reader = f.message([f.text_block('LINE L1 45385\nText.', [f.page_cite('x', 1)])])
        self.assertEqual(result.citations(reader, None), {'_document': [{'text': 'x', 'page': 1, 'source': 'reader'}]})

    def test_malformed_citations_are_skipped(self):
        reader = f.message([f.text_block('LINE L1 45385\n'),
                            f.text_block('Text.', [{'type': 'page_location'}, 'x',
                                                   {**f.page_cite('q', 1), 'start_page_number': '1'}]),
                            f.text_block(f.fenced(self.READER))])
        self.assertEqual(result.citations(reader, None), {'L1': [{'text': 'q', 'page': None, 'source': 'reader'}]})
