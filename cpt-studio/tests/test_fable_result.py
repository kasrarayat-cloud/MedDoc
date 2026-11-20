"""studio.fable.result (BUILD-SPEC 4.4-4.6): the final JSON, shape-only validation, the combination of the two reads and
the citations per code. Synthetic answers only."""
from django.test import SimpleTestCase

from studio.fable import result
from tests.support import coding as f


class ParseTests(SimpleTestCase):
    def test_the_last_json_fence_that_parses_wins(self):
        text = 'analysis ```json\n{"a": 1}\n``` more ```json\n{"a": 2}\n``` and ```json\n{broken\n```'
        self.assertEqual(result.last_json(text), {'a': 2})

    def test_without_a_fence_the_widest_brace_span_is_read(self):
        self.assertEqual(result.last_json('The result: {"codes": [{"code": "45380"}]} done.'),
                         {'codes': [{'code': '45380'}]})

    def test_nothing_parseable_is_none(self):
        self.assertIsNone(result.last_json('no json here {not json}'))
        self.assertIsNone(result.last_json(''))

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
        written = f.reader_result([f.code('45385', units='1', modifiers='59')])
        self.assertEqual(result.read_reader(f.reader_message(written)), written)


class CombineTests(SimpleTestCase):
    def combine(self, codes, reviews, missed=(), reader_questions=(), checker_questions=(), problems=()):
        reader = f.reader_result(codes, questions=reader_questions, problems=problems)
        checker = f.checker_result(reviews, missed=missed, questions=checker_questions)
        return result.combine(reader, checker)

    def test_an_agreed_code_keeps_the_readers_status(self):
        for status in ('ready', 'needs_answer', 'not_supported'):
            with self.subTest(status=status):
                combined = self.combine([f.code('45385', status)], [f.review('45385', 'agree')])
                self.assertEqual(combined['codes'][0]['status'], status)
                self.assertEqual(combined['codes'][0]['listed_status'], status)
                self.assertIs(combined['codes'][0]['second_check']['agrees'], True)

    def test_a_disagreement_or_no_review_makes_needs_review_with_both_reasons(self):
        combined = self.combine([f.code('45385', reason='Reader reason.'), f.code('45380')],
                                [f.review('45385', 'disagree', reason='Checker reason.')])
        disagreed, unreviewed = combined['codes']
        self.assertEqual(disagreed['status'], 'needs_review')
        self.assertEqual(disagreed['reason'], 'Reader reason.')
        self.assertEqual(disagreed['second_check']['reason'], 'Checker reason.')
        self.assertIs(disagreed['second_check']['agrees'], False)
        self.assertEqual(unreviewed['status'], 'needs_review')
        self.assertIsNone(unreviewed['second_check']['agrees'])

    def test_a_verdict_other_than_exactly_agree_is_not_agreement(self):
        for verdict in ('Agree', 'agrees', None, 1):
            with self.subTest(verdict=verdict):
                item = {**f.review('45385'), 'verdict': verdict}
                self.assertEqual(self.combine([f.code('45385')], [item])['codes'][0]['status'], 'needs_review')

    def test_a_code_reviewed_twice_agrees_only_when_every_review_agrees(self):
        both = self.combine([f.code('45385')], [f.review('45385'), f.review('45385', 'disagree', reason='No.')])
        self.assertEqual(both['codes'][0]['status'], 'needs_review')
        self.assertEqual(both['codes'][0]['second_check']['reason'], 'No.')
        agreed = self.combine([f.code('45385')], [f.review('45385'), f.review('45385')])
        self.assertEqual(agreed['codes'][0]['status'], 'ready')

    def test_missed_codes_are_added_as_needs_review(self):
        missed = {'code': '45380', 'units': 1, 'modifiers': ['59'], 'status': 'ready', 'reason': 'Biopsy taken.',
                  'evidence': [], 'question': None}
        combined = self.combine([f.code('45385')], [f.review('45385')], missed=[missed])
        added = combined['codes'][1]
        self.assertEqual((added['code'], added['status'], added['listed_by'], added['listed_status']),
                         ('45380', 'needs_review', 'checker', 'ready'))
        self.assertEqual(added['modifiers'], ['59'])
        self.assertIsNone(added['second_check'])

    def test_a_field_of_the_wrong_type_is_dropped_never_corrected(self):
        item = {**f.code('45385'), 'units': '2', 'modifiers': ['59', 7], 'reason': ['x'], 'question': 3,
                'evidence': [{'quote': 'ok', 'page': 'one'}, {'quote': 5}, 'text']}
        shown = self.combine([item], [f.review('45385')])['codes'][0]
        self.assertEqual((shown['units'], shown['modifiers'], shown['reason'], shown['question']),
                         (None, None, None, None))
        self.assertEqual(shown['evidence'], [{'quote': 'ok', 'page': None}])
        self.assertEqual(shown['code'], '45385')

    def test_questions_are_both_lists_with_folded_duplicates_shown_once(self):
        combined = self.combine(
            [f.code('45385')], [f.review('45385')],
            reader_questions=[{'question': 'Was the  polyp\nremoved whole?', 'affects': ['45385']}, 'not an object'],
            checker_questions=[{'question': 'Was the polyp removed whole?', 'affects': ['45380']},
                               {'question': 'Which payer applies?', 'affects': None}])
        self.assertEqual(combined['questions'], [
            {'id': 'q1', 'text': 'Was the  polyp\nremoved whole?', 'codes': ['45385', '45380'], 'source': 'reader'},
            {'id': 'q2', 'text': 'Which payer applies?', 'codes': [], 'source': 'checker'}])

    def test_problems_are_the_readers_documentation_problems(self):
        combined = self.combine([f.code('45385')], [f.review('45385')], problems=['No signature.', 4])
        self.assertEqual(combined['problems'], ['No signature.'])

    def test_the_listing_the_checker_is_given(self):
        reader = f.reader_result([f.code('45385', modifiers=['PT'], question=None)])
        self.assertEqual(result.listing(reader), [{'code': '45385', 'units': 1, 'modifiers': ['PT'],
                                                   'status': 'ready', 'question': None}])


class CitationTests(SimpleTestCase):
    def test_citations_follow_the_code_and_review_sections(self):
        reader = f.message([
            f.text_block('Overview of the note.', [f.page_cite('SYNTHETIC PROCEDURE NOTE', 1)]),
            f.text_block('\nCODE 45385\n'),
            f.text_block('Snare removal.', [f.page_cite('removed by cold snare', 2)]),
            f.text_block('\n### CODE 45380 (biopsy)\nBiopsy taken.', [f.page_cite('biopsy', 3)]),
            f.text_block(f.fenced(f.reader_result([])))])
        checker = f.message([f.text_block('**REVIEW 45385**\nAgreed.', [f.char_cite('cold snare', 10)])])
        found = result.citations(reader, checker)
        self.assertEqual(found['_document'], [{'text': 'SYNTHETIC PROCEDURE NOTE', 'page': 1, 'source': 'reader'}])
        self.assertEqual(found['45385'], [{'text': 'removed by cold snare', 'page': 2, 'source': 'reader'},
                                          {'text': 'cold snare', 'page': None, 'source': 'checker'}])
        self.assertEqual(found['45380'], [{'text': 'biopsy', 'page': 3, 'source': 'reader'}])

    def test_a_colon_or_another_case_still_starts_a_section(self):
        reader = f.message([f.text_block('Code: 45385\nText.', [f.page_cite('x', 1)]),
                            f.text_block('\nCODE 0001U\n', [f.page_cite('y', 2)])])
        self.assertEqual(set(result.citations(reader, None)), {'45385', '0001U'})

    def test_a_checker_line_in_the_reader_answer_starts_no_section(self):
        reader = f.message([f.text_block('REVIEW 45385\nText.', [f.page_cite('x', 1)])])
        self.assertEqual(result.citations(reader, f.message([])), {'_document': [
            {'text': 'x', 'page': 1, 'source': 'reader'}]})

    def test_malformed_citations_are_skipped(self):
        reader = f.message([f.text_block('CODE 45385\n', [{'type': 'page_location'}, 'x',
                                                           {**f.page_cite('q', 1), 'start_page_number': '1'}])])
        self.assertEqual(result.citations(reader, None), {'45385': [{'text': 'q', 'page': None, 'source': 'reader'}]})
