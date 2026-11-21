"""Each question once, for every document (D370, D372). The reader writes each question once, in its top-level list,
with an id (Q1, Q2..), and a code names the questions it depends on in question_ids; the checker is given the reader's
questions with their ids, refers to them, and writes only its new ones (C1, C2..). The site merges by id - and by
today's exact-text merge, never by reading what a question means (D358) - shows each question once naming every line it
affects, and never loses one: today's shape reads exactly as today, a mixed answer additively, a duplicate id stays
separate questions, an id naming no question carries no text (the operator console lists it), and a needs_answer line
no question names still gets one a member can answer. Synthetic answers only; nothing reaches the network."""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from studio import decisions, models, state
from studio.fable import prompts, result
from tests.support import coding as f
from tests.support import operator as ops
from tests.support import questions as q
from tests.support import rounds as r

Round = models.CodingRound


def combine(reader, checker):
    """The combination of the two answers, each read first as the coding stage reads it."""
    result.read_reader(f.reader_message(reader))
    result.read_checker(f.checker_message(checker))
    return result.combine(reader, checker)


def combined(codes, reviews, *, missed=(), reader_questions=(), checker_questions=()):
    return combine(f.reader_result(codes, questions=reader_questions),
                   f.checker_result(reviews, missed=missed, questions=checker_questions))


def asked(out):
    """The round's questions: (text, lines, codes, source) each, in order."""
    return [(item['text'], item['lines'], item['codes'], item['source']) for item in out['questions']]


def shown(out):
    """{line: (the question its row shows, the question its second check shows)}."""
    return {row['line']: (row['question'], (row['second_check'] or {}).get('question')) for row in out['codes']}


class NewShapeTests(SimpleTestCase):
    def test_a_question_many_codes_depend_on_is_shown_once_naming_every_line_that_names_it(self):
        # its affects names no line: the lines naming its id are the lines it affects
        out = combined([q.coded('20610', 'needs_answer', ids=['Q1'], modifiers=['RT']),
                        q.coded('20610', 'needs_answer', ids=['Q1'], modifiers=['LT'])],
                       [q.reviewed('L1', '20610', ids=['Q1'], status='needs_answer'),
                        q.reviewed('L2', '20610', ids=['Q1'], status='needs_answer')],
                       reader_questions=[q.asked('Q1', 'Which knee was injected?')])
        self.assertEqual(asked(out), [('Which knee was injected?', ['L1', 'L2'], ['20610'], 'reader')])
        self.assertEqual([row['status'] for row in out['codes']], ['needs_answer', 'needs_answer'])
        self.assertEqual(shown(out), {'L1': ('Which knee was injected?', 'Which knee was injected?'),
                                      'L2': ('Which knee was injected?', 'Which knee was injected?')})

    def test_affects_names_lines_by_their_label_and_by_their_code(self):
        out = combined([q.coded('20610', modifiers=['RT']), q.coded('20610', modifiers=['LT']), q.coded('45380')],
                       [q.reviewed('L1', '20610'), q.reviewed('L2', '20610'), q.reviewed('L3', '45380')],
                       reader_questions=[q.asked('Q1', 'Which knee was injected?', ['20610']),
                                         q.asked('Q2', 'Was the biopsy from a separate site?', ['L3', ' l1 '])])
        self.assertEqual(asked(out), [('Which knee was injected?', ['L1', 'L2'], ['20610'], 'reader'),
                                      ('Was the biopsy from a separate site?', ['L1', 'L3'], ['20610', '45380'],
                                       'reader')])

    def test_a_code_row_shows_the_text_of_each_question_it_names_one_per_line(self):
        out = combined([q.coded('45380', 'needs_answer', ids=['Q2', 'Q1', 'Q2'])],
                       [q.reviewed('L1', '45380', ids=['Q1'], status='needs_answer')],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?'), q.asked('Q2', 'Which site?')])
        self.assertEqual(shown(out), {'L1': ('Which site?\nWas a biopsy taken?', 'Was a biopsy taken?')})
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                                      ('Which site?', ['L1'], ['45380'], 'reader')])

    def test_the_stored_questions_keep_todays_fields_and_ids_in_order(self):
        out = combine(q.READER, q.CHECKER)
        self.assertEqual([set(item) for item in out['questions']], [{'id', 'text', 'lines', 'codes', 'source'}] * 2)
        self.assertEqual([item['id'] for item in out['questions']], ['q1', 'q2'])
        self.assertEqual(set(out), {'codes', 'questions', 'problems'})
        # nothing the combination reads for itself is stored on a row or its second check
        for row in out['codes']:
            self.assertNotIn('refs', row)
            self.assertNotIn('asked', row)
            self.assertNotIn('refs', row['second_check'])

    def test_the_case_in_the_new_shape_asks_its_two_questions_once(self):
        out = combine(q.READER, q.CHECKER)
        self.assertEqual([(row['line'], row['code'], row['status']) for row in out['codes']],
                         [('L1', '45380', 'needs_answer'), ('L2', '45378', 'needs_review'),
                          ('L3', '99152', 'not_supported')])
        self.assertEqual(asked(out), [(q.BIOPSY, ['L1', 'L2'], ['45380', '45378'], 'reader'),
                                      (q.DATE, ['L1', 'L2'], ['45380', '45378'], 'reader')])
        both = f'{q.BIOPSY}\n{q.DATE}'
        self.assertEqual(shown(out), {'L1': (both, both), 'L2': (both, q.BIOPSY), 'L3': (None, None)})
        self.assertEqual(out['problems'], [q.PROBLEM])

    def test_the_case_names_both_lines_even_when_affects_does_not(self):
        reader = {**q.READER, 'questions': [q.asked('Q1', q.BIOPSY, ['L1']), q.asked('Q2', q.DATE)]}
        self.assertEqual(asked(combine(reader, q.CHECKER)),
                         [(q.BIOPSY, ['L1', 'L2'], ['45380', '45378'], 'reader'),
                          (q.DATE, ['L1', 'L2'], ['45380', '45378'], 'reader')])

    def test_the_case_as_it_was_stored_still_shows_its_five_questions(self):
        # today's shape reads as today: the code never judges two wordings to be one question (D358)
        out = combine(q.TODAYS_READER, q.TODAYS_CHECKER)
        self.assertEqual(asked(out), [(q.BIOPSY, ['L1', 'L2'], ['45380', '45378'], 'reader'),
                                      (q.DATE, ['L1', 'L2'], ['45380', '45378'], 'reader'),
                                      (q.DATE_BY_CHECKER, ['L1', 'L2'], ['45380', '45378'], 'checker'),
                                      (q.BIOPSY_ON_L1, ['L1'], ['45380'], 'reader'),
                                      (q.BIOPSY_ON_L2, ['L2'], ['45378'], 'reader')])

    def test_a_question_the_checker_writes_again_in_other_words_is_shown_as_written(self):
        checker = {**q.CHECKER, 'questions': [q.asked('C1', q.DATE_BY_CHECKER, ['L1', 'L2'])]}
        self.assertEqual([text for text, *_ in asked(combine(q.READER, checker))],
                         [q.BIOPSY, q.DATE, q.DATE_BY_CHECKER])


class CheckerReferenceTests(SimpleTestCase):
    def test_a_review_and_a_missed_code_reuse_the_readers_ids_and_its_new_questions_follow(self):
        out = combined([q.coded('45385'), q.coded('45380', 'needs_answer', ids=['Q1'])],
                       [q.reviewed('L1', '45385', 'disagree', ids=['Q1']),
                        q.reviewed('L2', '45380', ids=['Q1'], status='needs_answer')],
                       missed=[q.added('45378', 'needs_answer', ids=['Q1', 'C1'])],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?', ['L2'])],
                       checker_questions=[q.asked('C1', 'Was the cecum reached?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1', 'L2', 'M1'], ['45385', '45380', '45378'],
                                       'reader'),
                                      ('Was the cecum reached?', ['M1'], ['45378'], 'checker')])
        self.assertEqual(shown(out), {'L1': (None, 'Was a biopsy taken?'),
                                      'L2': ('Was a biopsy taken?', 'Was a biopsy taken?'),
                                      'M1': ('Was a biopsy taken?\nWas the cecum reached?', None)})

    def test_a_review_that_belongs_to_no_line_names_the_lines_it_reaches(self):
        out = combined([q.coded('45385'), q.coded('45380'), q.coded('45378')],
                       [q.reviewed('L1', '45385'), q.reviewed('L2', '45380'), q.reviewed('L3', '45378'),
                        q.reviewed('L1', '45378', 'disagree', ids=['C1']),  # names L1, carries L3's code
                        q.reviewed('L9', '99999', 'disagree', ids=['C2'])],  # placed nowhere: names no line
                       checker_questions=[q.asked('C1', 'Which polyp was removed?'), q.asked('C2', 'Which payer?')])
        self.assertEqual(asked(out), [('Which polyp was removed?', ['L1', 'L3'], ['45385', '45378'], 'checker'),
                                      ('Which payer?', [], [], 'checker')])

    def test_a_reader_line_names_only_the_readers_questions(self):
        # the reader was never shown the checker's questions: its C1 names none of them
        out = combined([q.coded('45385', ids=['C1'])], [q.reviewed('L1', '45385')],
                       checker_questions=[q.asked('C1', 'Which payer?')])
        self.assertEqual(asked(out), [('Which payer?', [], [], 'checker')])
        self.assertEqual(shown(out), {'L1': (None, None)})
        self.assertEqual(result.dangling_references(f.reader_result([q.coded('45385', ids=['C1'])]),
                                                    f.checker_result([], questions=[q.asked('C1', 'Which payer?')])),
                         [{'item': 'L1', 'code': '45385', 'reference': 'C1'}])


class IdReadingTests(SimpleTestCase):
    def test_a_single_id_written_where_a_list_is_expected_reads_as_a_list_of_one(self):
        out = combined([{**q.coded('45380', 'needs_answer'), 'question_ids': 'Q1'}],
                       [{**q.reviewed('L1', '45380', status='needs_answer'), 'question_ids': 'Q1'}],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1'], ['45380'], 'reader')])
        self.assertEqual(shown(out), {'L1': ('Was a biopsy taken?', 'Was a biopsy taken?')})

    def test_ids_compare_case_insensitively(self):
        out = combined([q.coded('45380', ids=['Q1']), q.coded('45385', ids=[' q2 '])],
                       [q.reviewed('L1', '45380'), q.reviewed('L2', '45385')],
                       reader_questions=[q.asked(' q1 ', 'Was a biopsy taken?'), q.asked('Q2', 'Which site?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                                      ('Which site?', ['L2'], ['45385'], 'reader')])

    def test_an_integer_id_reads_as_its_decimal_string(self):
        out = combined([q.coded('45380', ids=[1]), q.coded('45385', ids=['2'])],
                       [q.reviewed('L1', '45380'), q.reviewed('L2', '45385')],
                       reader_questions=[q.asked('1', 'Was a biopsy taken?'), q.asked(2, 'Which site?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                                      ('Which site?', ['L2'], ['45385'], 'reader')])

    def test_no_shape_of_an_id_or_a_reference_makes_the_answer_unreadable(self):
        # today's answers have no such field: an Unreadable round costs a paid read and fails the member's document
        for value in ({'id': 'Q1'}, 1.5, True, [['Q1']], [{'id': 'Q1'}], ['Q1', 7.0], False):
            with self.subTest(value=value):
                reader = f.reader_result([{**q.coded('45380'), 'question_ids': value}],
                                         questions=[{**q.asked('Q1', 'Was a biopsy taken?'), 'id': value}])
                checker = f.checker_result([{**q.reviewed('L1', '45380'), 'question_ids': value}],
                                           missed=[{**q.added('45378'), 'question_ids': value}])
                out = combine(reader, checker)
                self.assertEqual([text for text, *_ in asked(out)], ['Was a biopsy taken?'])  # the question is kept
                # the question's id is no id, so nothing names it: each id is listed, then each item that is no id
                items = value if isinstance(value, list) else [value]
                listed = [item for item in items if isinstance(item, str)] + [
                    item for item in items if not isinstance(item, str)]
                self.assertEqual(result.dangling_references(reader, checker),
                                 [{'item': where, 'code': code, 'reference': item} for where, code in
                                  (('L1', '45380'), ('review 1', '45380'), ('M1', '45378')) for item in listed])

    def test_a_blank_or_null_reference_names_nothing(self):
        reader = f.reader_result([q.coded('45380', ids=['', None, '  '])])
        checker = f.checker_result([{**q.reviewed('L1', '45380'), 'question_ids': None}])
        self.assertEqual(asked(combine(reader, checker)), [])
        self.assertEqual(result.dangling_references(reader, checker), [])


class DuplicateIdTests(SimpleTestCase):
    def test_a_duplicate_id_stays_two_questions_and_every_reference_reaches_both(self):
        out = combined([q.coded('45380', 'needs_answer', ids=['Q1']), q.coded('45385')],
                       [q.reviewed('L1', '45380', status='needs_answer'), q.reviewed('L2', '45385', ids=['Q1'])],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?'), q.asked('Q1', 'Which site?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1', 'L2'], ['45380', '45385'], 'reader'),
                                      ('Which site?', ['L1', 'L2'], ['45380', '45385'], 'reader')])
        self.assertEqual(shown(out)['L1'], ('Was a biopsy taken?\nWhich site?', None))

    def test_one_id_in_both_lists_is_two_questions_and_names_what_its_author_was_shown(self):
        out = combined([q.coded('45380', ids=['Q1']), q.coded('45385')],
                       [q.reviewed('L1', '45380'), q.reviewed('L2', '45385', ids=['q1'])],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?')],
                       checker_questions=[q.asked('Q1', 'Which site?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1', 'L2'], ['45380', '45385'], 'reader'),
                                      ('Which site?', ['L2'], ['45385'], 'checker')])

    def test_two_ids_with_one_text_are_one_question_as_today(self):
        out = combined([q.coded('45380', ids=['Q1']), q.coded('45385')],
                       [q.reviewed('L1', '45380'), q.reviewed('L2', '45385', ids=['C1'])],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?')],
                       checker_questions=[q.asked('C1', 'was a  BIOPSY taken?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1', 'L2'], ['45380', '45385'], 'reader')])


class DanglingReferenceTests(SimpleTestCase):
    def test_an_id_that_names_no_question_carries_no_text_and_is_listed_for_the_operator(self):
        reader = f.reader_result([q.coded('45385', ids=['Q9', 'Q1'])], questions=[q.asked('Q1', 'Which site?')])
        checker = f.checker_result([q.reviewed('L1', '45385', ids=['C4'])], missed=[q.added('45378', ids=['Q1', 'Q7'])])
        out = combine(reader, checker)
        self.assertEqual(asked(out), [('Which site?', ['L1', 'M1'], ['45385', '45378'], 'reader')])
        self.assertEqual(shown(out), {'L1': ('Which site?', None), 'M1': ('Which site?', None)})
        self.assertEqual(result.dangling_references(reader, checker),
                         [{'item': 'L1', 'code': '45385', 'reference': 'Q9'},
                          {'item': 'review 1', 'code': '45385', 'reference': 'C4'},
                          {'item': 'M1', 'code': '45378', 'reference': 'Q7'}])

    def test_a_needs_answer_line_no_question_names_still_gets_one_the_member_can_answer(self):
        silent = combined([q.coded('45380', 'needs_answer', ids=['Q9'])],
                          [q.reviewed('L1', '45380', ids=['Q8'], status='needs_answer')])
        self.assertEqual(asked(silent), [(result.UNASKED_QUESTION.format(code='45380'), ['L1'], ['45380'], 'studio')])
        own = combined([q.coded('45380', 'needs_answer', ids=['Q9'])],
                       [{**q.reviewed('L1', '45380', ids=['Q8'], status='needs_answer'), 'question': 'Which site?'}])
        self.assertEqual(asked(own), [('Which site?', ['L1'], ['45380'], 'checker')])

    def test_a_blank_question_is_no_question_an_id_can_name(self):
        out = combined([q.coded('45380', 'needs_answer', ids=['Q1'])],
                       [q.reviewed('L1', '45380', status='needs_answer')],
                       reader_questions=[q.asked('Q1', '   ')])
        self.assertEqual(asked(out), [(result.UNASKED_QUESTION.format(code='45380'), ['L1'], ['45380'], 'studio')])

    def test_what_the_agreeing_reviews_wrote_on_themselves_is_asked_as_today(self):
        # a question names the line only by an id: the agreeing review's own question is still asked, as today's
        # reading asks it - the worst case is today's behaviour, never a lost question - and CPT Studio's own question
        # is not, since a question names the line
        reader = f.reader_result([q.coded('45380', 'needs_answer', ids=['Q1'])],
                                 questions=[q.asked('Q1', 'Was a biopsy taken?')])
        review = q.reviewed('L1', '45380', status='needs_answer')
        self.assertEqual(asked(combine(reader, f.checker_result([{**review, 'question': 'Which site?'}]))),
                         [('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                          ('Which site?', ['L1'], ['45380'], 'checker')])
        self.assertEqual(asked(combine(reader, f.checker_result([review]))),
                         [('Was a biopsy taken?', ['L1'], ['45380'], 'reader')])


class TodaysShapeTests(SimpleTestCase):
    def test_todays_shape_reads_exactly_as_today(self):
        out = combine(r.READER, r.CHECKER)
        self.assertEqual(asked(out), [
            ('Was a biopsy taken from a separate site?', ['L2'], ['45380'], 'reader'),
            ('Which site was biopsied during the upper endoscopy?', ['L3'], ['43239'], 'checker')])
        self.assertEqual(shown(out), {'L1': (None, None), 'L2': ('Was a biopsy taken from a separate site?', None),
                                      'L3': (None, None), 'L4': (None, None), 'M1': (None, None)})
        line_texts = combine(f.reader_result([f.code('20610', 'needs_answer', question=['Which knee?', 'Which day?'])]),
                             f.checker_result([r.review('L1', '20610', status='needs_answer', question='Which knee?')]))
        self.assertEqual(shown(line_texts), {'L1': ('Which knee?\nWhich day?', 'Which knee?')})

    def test_ids_on_todays_questions_change_nothing_when_nothing_names_them(self):
        plain = combine(r.READER, r.CHECKER)
        numbered = {**r.READER, 'questions': [{**item, 'id': f'Q{n}'} for n, item in
                                              enumerate(r.READER['questions'], start=1)]}
        self.assertEqual(combine(numbered, r.CHECKER), plain)


class MixedShapeTests(SimpleTestCase):
    def test_a_line_with_its_own_question_and_ids_asks_both(self):
        out = combined([{**q.coded('20610', 'needs_answer', ids=['Q1']), 'question': 'Which knee?'}],
                       [q.reviewed('L1', '20610', status='needs_answer')],
                       reader_questions=[q.asked('Q1', 'Was ultrasound guidance used?')])
        self.assertEqual(asked(out), [('Was ultrasound guidance used?', ['L1'], ['20610'], 'reader'),
                                      ('Which knee?', ['L1'], ['20610'], 'reader')])
        self.assertEqual(shown(out)['L1'], ('Which knee?\nWas ultrasound guidance used?', None))

    def test_a_line_text_that_is_a_listed_questions_text_is_shown_once(self):
        out = combined([{**q.coded('20610', 'needs_answer', ids=['Q1']), 'question': 'was ultrasound  GUIDANCE used?'}],
                       [q.reviewed('L1', '20610', status='needs_answer')],
                       reader_questions=[q.asked('Q1', 'Was ultrasound guidance used?')])
        self.assertEqual(asked(out), [('Was ultrasound guidance used?', ['L1'], ['20610'], 'reader')])
        self.assertEqual(shown(out)['L1'], ('was ultrasound  GUIDANCE used?', None))

    def test_top_level_questions_with_and_without_ids_are_read_together(self):
        out = combined([q.coded('45380', 'needs_answer', ids=['Q1'])],
                       [q.reviewed('L1', '45380', status='needs_answer')],
                       reader_questions=['Which payer applies?', q.asked('Q1', 'Was a biopsy taken?'),
                                         {'question': 'Which site?', 'affects': ['45380']}])
        self.assertEqual(asked(out), [('Which payer applies?', [], [], 'reader'),
                                      ('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                                      ('Which site?', ['L1'], ['45380'], 'reader')])


class InstructionTests(SimpleTestCase):
    def test_both_instructions_ask_for_each_question_once_with_an_id(self):
        reader, checker = prompts.READER_SYSTEM, prompts.CHECKER_SYSTEM
        for text in ('"question_ids": ["the id of a question this code depends on"]',
                     '"questions": [{"id": "Q1", "question": "plain question", "affects": ["L1"]}]',
                     'Write every question once, in "questions", with an id: Q1 for the first question',
                     'A question that more than one code depends on is written once, and its "affects" names every '
                     'line it concerns', 'an empty list when it depends on none',
                     'Never repeat a question on a code, and never write two questions that ask the same thing.'):
            with self.subTest(reader=text):
                self.assertIn(text, reader)
        for text in ('"question_ids": ["the id of a question this line depends on"]', '"question_ids": []}',
                     '"questions": [{"id": "C1", "question": "plain question", "affects": ["L1"]}]',
                     'The first coder\'s questions are given with their ids (Q1, Q2, and so on)',
                     'Never write again, in any words, a question the coding review already asked; refer to its id '
                     'instead.', 'Write each new question once, in "questions", with an id: C1 for the first new '
                     'question'):
            with self.subTest(checker=text):
                self.assertIn(text, checker)
        for system in (reader, checker):
            self.assertNotIn('"question": "the question to ask, or null"', system)
            self.assertNotIn('"question": "or null"', system)
            self.assertIn('The ids are for the JSON only: never write one in a question or a reason.', system)

    def test_the_checkers_user_text_carries_the_readers_questions_with_their_ids(self):
        reader = f.reader_result([q.coded('45380', 'needs_answer', ids=['Q1', 'Q2']),
                                  {**q.coded('45378'), 'question_ids': 'Q1'}],
                                 questions=[q.asked('Q1', 'Was a biopsy taken?', ['L1', 'L2']),
                                            q.asked('Q2', 'Which date of service is right?', ['L1'])])
        text = prompts.checker_instruction({'service_date': '2026-11-13', 'insurance': 'commercial'},
                                           result.listing(result.read_reader(f.reader_message(reader))))
        lines_part, rest = text.split("\n\nThe first coder's questions (JSON):\n")
        questions_part, context = rest.split('\n\nInformation from the practice', 1)
        self.assertEqual(json.loads(lines_part.removeprefix("The first coder's list for this document (JSON):\n")), [
            {'line': 'L1', 'code': '45380', 'units': 1, 'modifiers': [], 'status': 'needs_answer',
             'question_ids': ['Q1', 'Q2']},
            {'line': 'L2', 'code': '45378', 'units': 1, 'modifiers': [], 'status': 'ready', 'question_ids': ['Q1']}])
        self.assertEqual(json.loads(questions_part), [
            {'id': 'Q1', 'question': 'Was a biopsy taken?', 'affects': ['L1', 'L2']},
            {'id': 'Q2', 'question': 'Which date of service is right?', 'affects': ['L1']}])
        self.assertTrue(context.endswith('date of service: 2026-11-13; insurance: commercial or other.\n\n'
                                         'Check it against the document.'))

    def test_a_reader_answer_in_todays_shape_still_shows_the_checker_what_it_asked(self):
        reader = f.reader_result([f.code('45380', 'needs_answer', question='Was a biopsy taken?')],
                                 questions=[{'question': 'Which site?', 'affects': ['45380']}, 'Which payer?'])
        self.assertEqual(result.listing(reader), {
            'lines': [{'line': 'L1', 'code': '45380', 'units': 1, 'modifiers': [], 'status': 'needs_answer',
                       'question_ids': [], 'question': 'Was a biopsy taken?'}],
            'questions': [{'id': None, 'question': 'Which site?', 'affects': ['45380']},
                          {'id': None, 'question': 'Which payer?', 'affects': []}]})


class QuestionIdPipelineTests(r.CustomerCase, TestCase):
    def test_a_round_in_the_new_shape_asks_each_question_once_and_one_answer_covers_its_lines(self):
        enc = self.started(service_date=q.SERVICE_DATE, insurance=q.INSURANCE)
        reader_msg, checker_msg = q.case_messages()
        fake = self.use(f.FakeCoder(reader=f.succeeded(reader_msg), checker=f.succeeded(checker_msg)))
        self.run_next()
        checker_text = fake.calls[1][1].params['messages'][0]['content'][1]['text']
        self.assertIn("The first coder's questions (JSON):\n" + json.dumps(
            [{'id': 'Q1', 'question': q.BIOPSY, 'affects': ['L1', 'L2']},
             {'id': 'Q2', 'question': q.DATE, 'affects': ['L1', 'L2']}], indent=1), checker_text)
        self.assertIn('"question_ids": [\n   "Q1",\n   "Q2"\n  ]', checker_text)
        client = self.client_for(self.reviewer)
        payload = client.get(f'/api/encounters/{enc.pk}').json()
        self.assertEqual(payload['state'], 'awaiting_answer')
        self.assertEqual([(item['text'], item['lines'], item['codes']) for item in payload['questions']],
                         [(q.BIOPSY, ['L1', 'L2'], ['45380', '45378']), (q.DATE, ['L1', 'L2'], ['45380', '45378'])])
        self.assertEqual([(code['line'], code['question']) for code in payload['codes']],
                         [('L1', f'{q.BIOPSY}\n{q.DATE}'), ('L2', f'{q.BIOPSY}\n{q.DATE}'), ('L3', None)])
        response = client.post(f'/api/encounters/{enc.pk}/answers', data=json.dumps(
            {'answers': [{'question_id': payload['questions'][0]['id'], 'text': 'No biopsy was taken.'}]}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        round2 = state.latest_round(enc)
        self.assertEqual((round2.number, round2.trigger), (2, Round.ANSWERS))
        self.assertEqual(round2.context['answers'], [{'question': q.BIOPSY, 'answer': 'No biopsy was taken.'}])
        self.assertEqual(list(models.CodingAnswer.objects.filter(encounter=enc).values_list('question', 'answer')),
                         [(q.BIOPSY, 'No biopsy was taken.')])

    def test_the_operator_console_lists_each_id_that_names_no_question(self):
        enc = self.started()
        reader = f.reader_result([q.coded('45385', ids=['Q9'])], questions=[q.asked('Q1', 'Which site?')])
        self.code_round(enc, reader=reader, checker=f.checker_result([q.reviewed('L1', '45385', ids=[{'id': 'Q1'}])]))
        page = ops.client(f.user('platform-operator')).get(f'/ops/encounters/{enc.pk}').content.decode('utf-8')
        self.assertIn('<h3>Question ids that name no question</h3>', page)
        self.assertIn('<li>L1 <span class="mono">45385</span> names <span class="mono">&quot;Q9&quot;</span></li>',
                      page)
        self.assertIn('<li>review 1 <span class="mono">45385</span> names <span class="mono">{&quot;id&quot;: '
                      '&quot;Q1&quot;}</span></li>', page)
        clean = self.started(title='Synthetic note whose ids all name questions')
        self.code_round(clean, reader=q.READER, checker=q.CHECKER)
        page = ops.client(f.user('platform-operator-2')).get(f'/ops/encounters/{clean.pk}').content.decode('utf-8')
        self.assertNotIn('Question ids that name no question', page)
        self.assertIn(q.BIOPSY, page)


class SharedQuestionFixtureTests(r.CustomerCase, TestCase):
    """The customer fixture of one question for two lines (tests/fixtures/customer/encounter-shared-question.json, which
    the page's node tests and ops/dev_preview_server.cjs read) is what the server builds for the case in the new shape:
    its codes as the page reads them, its questions (ids aside: the server's are the round's own), its notes."""

    def test_the_fixture_is_what_the_server_builds_for_the_case(self):
        enc = self.started(title='Synthetic colonoscopy, one question for two lines', service_date=q.SERVICE_DATE,
                           insurance=q.INSURANCE)
        reader_msg, checker_msg = q.case_messages()
        self.code_round(enc, reader_msg=reader_msg, checker_msg=checker_msg)
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        fixture = json.loads((Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'customer' /
                              'encounter-shared-question.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['codes'], fixture['codes'])
        self.assertEqual([{key: value for key, value in item.items() if key != 'id'} for item in payload['questions']],
                         [{key: value for key, value in item.items() if key != 'id'} for item in fixture['questions']])
        for key in ('title', 'state', 'state_label', 'context', 'notes', 'readiness', 'answers', 'permissions'):
            with self.subTest(key=key):
                self.assertEqual(payload[key], fixture[key])
        self.assertEqual(len(fixture['questions']), 2)


# --- round 2 (the lead's decisions on the refutation of the first build) ---------------------------------------------

SPECIMEN = 'Did a specimen from the gastric antrum go to pathology?'
SNARE = 'Was the second polyp removed with a snare or with forceps?'
SITE = 'Which part of the colon was the polyp in?'
TISSUE = 'Was any tissue sampled during the scope?'
# the console's sentence under the ids both answers defined (G1 of round 3: true whether their definitions stayed two
# questions or merged into one)
SHARED_SENTENCE = ("Each reference the checker made to one of these ids reaches every question that carries it in "
                   "either answer, which is one question where their texts are the same; a reader line's reference "
                   "reaches the reader's only.")


class QuestionObjectTests(SimpleTestCase):
    """F1: an object with a string "question" that is not blank is question text wherever an item writes it - its
    "question" or inside its question_ids - and is never lost; with an id it defines that id among its author's
    questions."""

    def test_a_question_object_in_question_ids_is_asked_and_shown_on_its_line(self):
        reader = f.reader_result([q.coded('43239', 'needs_answer', ids=[{'id': 'Q1', 'question': SPECIMEN}])])
        checker = f.checker_result([q.reviewed('L1', '43239', status='needs_answer')],
                                   missed=[q.added('43251', 'needs_answer', ids=[{'id': 'C1', 'question': SNARE}]),
                                           q.added('43235', ids=[{'question': SITE}])])  # one without an id
        out = combine(reader, checker)
        self.assertEqual(asked(out), [(SPECIMEN, ['L1'], ['43239'], 'reader'), (SNARE, ['M1'], ['43251'], 'checker'),
                                      (SITE, ['M2'], ['43235'], 'checker')])
        self.assertEqual(shown(out), {'L1': (SPECIMEN, None), 'M1': (SNARE, None), 'M2': (SITE, None)})
        self.assertEqual(result.dangling_references(reader, checker), [])

    def test_a_question_object_a_review_writes_behaves_as_its_question_does(self):
        # without an id: shown on its second check and asked only by the fallback, as the same object in "question" is
        inline = combined([q.coded('45385')], [q.reviewed('L1', '45385', 'disagree', ids=[{'question': SITE}])])
        field = combined([q.coded('45385')], [{**q.reviewed('L1', '45385', 'disagree'), 'question': {'question': SITE}}])
        self.assertEqual(inline, field)
        self.assertEqual((asked(inline), shown(inline)), ([], {'L1': (None, SITE)}))
        # with an id it is one of the checker's questions: asked, naming the line the review is about, and reached by
        # a reference to its id
        defined = combined([q.coded('45385')],
                           [q.reviewed('L1', '45385', 'disagree', ids=[{'id': 'C1', 'question': SITE}])],
                           missed=[q.added('45378', ids=['c1'])])
        self.assertEqual(asked(defined), [(SITE, ['L1', 'M1'], ['45385', '45378'], 'checker')])
        self.assertEqual(shown(defined), {'L1': (None, SITE), 'M1': (SITE, None)})

    def test_an_id_on_a_question_object_defines_it_among_its_authors_questions(self):
        # the reader's: a line's own question object, named by another line's id
        reader = f.reader_result([{**q.coded('45380', 'needs_answer'), 'question': {'id': 'Q1', 'question': TISSUE}},
                                  q.coded('45378', 'needs_answer', ids=['Q1'])])
        checker = f.checker_result([q.reviewed('L1', '45380', status='needs_answer'),
                                    q.reviewed('L2', '45378', status='needs_answer')])
        out = combine(reader, checker)
        self.assertEqual(asked(out), [(TISSUE, ['L1', 'L2'], ['45380', '45378'], 'reader')])
        self.assertEqual(shown(out), {'L1': (TISSUE, None), 'L2': (TISSUE, None)})
        self.assertEqual(result.dangling_references(reader, checker), [])
        # the checker's: a missed code's question object, named by a review
        reader = f.reader_result([q.coded('45380', 'needs_answer', ids=['Q1'])],
                                 questions=[q.asked('Q1', 'Was a biopsy taken?', ['L1'])])
        checker = f.checker_result([q.reviewed('L1', '45380', ids=['Q1', 'C1'], status='needs_answer')],
                                   missed=[{**q.added('45385', 'needs_answer'), 'question': {'id': 'C1', 'question': SNARE}}])
        out = combine(reader, checker)
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                                      (SNARE, ['L1', 'M1'], ['45380', '45385'], 'checker')])
        self.assertEqual(shown(out), {'L1': ('Was a biopsy taken?', f'Was a biopsy taken?\n{SNARE}'), 'M1': (SNARE, None)})
        self.assertEqual(result.dangling_references(reader, checker), [])

    def test_a_checker_reference_reaches_the_readers_question_object_and_its_own(self):
        reader = f.reader_result([q.coded('45380', 'needs_answer', ids=[{'id': 'Q1', 'question': 'Was a biopsy taken?'}]),
                                  q.coded('45385', ids=['C1'])])  # the reader was never shown the checker's questions
        checker = f.checker_result([q.reviewed('L1', '45380', ids=['Q1'], status='needs_answer'),
                                    q.reviewed('L2', '45385')],
                                   missed=[q.added('45378', ids=['Q1', 'C1']),
                                           q.added('45384', ids=[{'id': 'C1', 'question': SITE}])])
        out = combine(reader, checker)
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1', 'M1'], ['45380', '45378'], 'reader'),
                                      (SITE, ['M1', 'M2'], ['45378', '45384'], 'checker')])
        self.assertEqual(shown(out)['M1'], (f'Was a biopsy taken?\n{SITE}', None))
        self.assertEqual(result.dangling_references(reader, checker), [{'item': 'L2', 'code': '45385', 'reference': 'C1'}])

    def test_an_id_a_top_level_question_also_carries_gives_two_questions_and_a_reference_reaches_both(self):
        out = combined([q.coded('45380', 'needs_answer', ids=[{'id': 'Q1', 'question': 'Was a biopsy taken?'}]),
                        q.coded('45385', ids=['q1'])],
                       [q.reviewed('L1', '45380', status='needs_answer'), q.reviewed('L2', '45385')],
                       reader_questions=[q.asked('Q1', 'Which site?')])
        self.assertEqual(asked(out), [('Which site?', ['L1', 'L2'], ['45380', '45385'], 'reader'),
                                      ('Was a biopsy taken?', ['L1', 'L2'], ['45380', '45385'], 'reader')])
        self.assertEqual(shown(out), {'L1': ('Was a biopsy taken?\nWhich site?', None),
                                      'L2': ('Which site?\nWas a biopsy taken?', None)})

    def test_a_question_objects_text_is_merged_with_the_same_text_as_today(self):
        out = combined([q.coded('45380', 'needs_answer', ids=[{'id': 'Q2', 'question': 'was a BIOPSY  taken?'}]),
                        q.coded('45385', ids=['Q2'])],
                       [q.reviewed('L1', '45380', status='needs_answer'), q.reviewed('L2', '45385')],
                       reader_questions=[q.asked('Q1', 'Was a biopsy taken?')])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1', 'L2'], ['45380', '45385'], 'reader')])
        self.assertEqual(shown(out), {'L1': ('was a BIOPSY  taken?', None), 'L2': ('Was a biopsy taken?', None)})
        # a row shows a text once: a question object repeating the line's own question text is not shown again
        twice = combined([{**q.coded('20610', 'needs_answer', ids=[{'question': 'which  KNEE?'}]),
                           'question': 'Which knee?'}], [q.reviewed('L1', '20610', status='needs_answer')])
        self.assertEqual((asked(twice), shown(twice)), ([('Which knee?', ['L1'], ['20610'], 'reader')],
                                                        {'L1': ('Which knee?', None)}))

    def test_the_rounds_order_is_unchanged_and_the_questions_reviews_define_come_before_the_fallback(self):
        reader = f.reader_result([{**q.coded('45380', 'needs_answer', ids=[{'id': 'Q2', 'question': 'Inline on L1?'}]),
                                   'question': 'Field on L1?'}, q.coded('45385', 'needs_answer')],
                                 questions=[q.asked('Q1', 'Reader list?')])
        checker = f.checker_result([q.reviewed('L1', '45380', ids=[{'id': 'C2', 'question': 'Defined by a review?'}],
                                               status='needs_answer'),
                                    {**q.reviewed('L2', '45385', status='needs_answer'), 'question': 'Fallback?'}],
                                   missed=[q.added('45378', ids=[{'id': 'C3', 'question': 'Inline on M1?'}])],
                                   questions=[q.asked('C1', 'Checker list?')])
        self.assertEqual(asked(combine(reader, checker)), [
            ('Reader list?', [], [], 'reader'), ('Checker list?', [], [], 'checker'),
            ('Field on L1?', ['L1'], ['45380'], 'reader'), ('Inline on L1?', ['L1'], ['45380'], 'reader'),
            ('Inline on M1?', ['M1'], ['45378'], 'checker'), ('Defined by a review?', ['L1'], ['45380'], 'checker'),
            ('Fallback?', ['L2'], ['45385'], 'checker')])

    def test_an_object_without_a_question_text_stays_an_unread_item_for_the_operator(self):
        unread = [{'id': 'Q1'}, {'id': 'Q2', 'question': 5}, {'id': 'Q3', 'question': ' \ufeff\u3000'}, {'text': 'Q?'}]
        reader = f.reader_result([q.coded('45380', 'needs_answer', ids=unread), q.coded('45385', ids=['Q3'])])
        checker = f.checker_result([q.reviewed('L1', '45380', status='needs_answer'), q.reviewed('L2', '45385')])
        out = combine(reader, checker)
        # none defines an id or carries text: the needs_answer line gets CPT Studio's own question
        self.assertEqual(asked(out), [(result.UNASKED_QUESTION.format(code='45380'), ['L1'], ['45380'], 'studio')])
        self.assertEqual(result.dangling_references(reader, checker),
                         [{'item': 'L1', 'code': '45380', 'reference': value} for value in unread]
                         + [{'item': 'L2', 'code': '45385', 'reference': 'Q3'}])

    def test_a_needs_answer_line_named_only_by_a_question_object_keeps_the_fallback_floor(self):
        # origin/main never reads question_ids, so it asks the agreeing review's own question here: so does this
        out = combined([q.coded('45380', 'needs_answer', ids=[{'id': 'Q1', 'question': 'Was a biopsy taken?'}])],
                       [{**q.reviewed('L1', '45380', status='needs_answer'), 'question': 'Which site?'}])
        self.assertEqual(asked(out), [('Was a biopsy taken?', ['L1'], ['45380'], 'reader'),
                                      ('Which site?', ['L1'], ['45380'], 'checker')])

    def test_the_checkers_user_text_lists_the_readers_question_objects(self):
        reader = f.reader_result(
            [{**q.coded('45380', 'needs_answer'), 'question': {'id': 'Q1', 'question': 'Was a biopsy taken?'}},
             q.coded('45378', 'needs_answer', ids=['Q1', {'id': 'Q2', 'question': 'Which date is right?'},
                                                   {'question': SITE}]),
             q.coded('99152', 'not_supported', ids=[{'id': 'q1', 'question': 'was a biopsy TAKEN?'}])],
            questions=[q.asked('Q9', 'Which payer applies?', ['L2'])])
        listed = result.listing(result.read_reader(f.reader_message(reader)))
        self.assertEqual([(line['line'], line['question_ids'], line.get('question')) for line in listed['lines']],
                         [('L1', ['Q1'], None), ('L2', ['Q1', 'Q2'], SITE), ('L3', ['q1'], None)])
        self.assertEqual(listed['questions'], [
            {'id': 'Q9', 'question': 'Which payer applies?', 'affects': ['L2']},
            {'id': 'Q1', 'question': 'Was a biopsy taken?', 'affects': ['L1', 'L3']},  # one id, one text: listed once
            {'id': 'Q2', 'question': 'Which date is right?', 'affects': ['L2']}])
        text = prompts.checker_instruction({}, listed)
        self.assertIn("The first coder's questions (JSON):\n" + json.dumps(listed['questions'], indent=1), text)


class BlankQuestionTests(SimpleTestCase):
    """F2: one test of a blank question; every text the customer page's JavaScript trim() empties is blank to it."""
    POINTS = json.loads((Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'blank-question-characters.json')
                        .read_text(encoding='utf-8'))['code_points']

    def test_every_code_point_javascript_trim_removes_is_blank_to_the_server(self):
        # ECMAScript's String.prototype.trim() removes WhiteSpace - TAB, VT, FF, SP, NBSP, ZWNBSP (U+FEFF) and every
        # Zs - and LineTerminator - LF, CR, LS (U+2028), PS (U+2029)
        named = [0x0009, 0x000B, 0x000C, 0x0020, 0x00A0, 0xFEFF, 0x000A, 0x000D, 0x2028, 0x2029]
        zs = [point for point in range(sys.maxunicode + 1) if unicodedata.category(chr(point)) == 'Zs']
        removed = sorted({*named, *zs})
        self.assertEqual(len(zs), 17)
        self.assertEqual([f'{point:04X}' for point in removed], self.POINTS)  # the list the page's own test reads
        for point in removed:
            with self.subTest(code_point=f'U+{point:04X}'):
                for text in (chr(point), chr(point) * 3, f' {chr(point)}\n', f'\ufeff{chr(point)}\ufeff'):
                    self.assertTrue(result.blank_question(text), repr(text))
        self.assertTrue(result.blank_question(''.join(map(chr, removed))))
        self.assertTrue(result.blank_question(''))
        # U+FEFF is the only one of them Python's str.strip() keeps: the reason the one test removes it too
        self.assertEqual([point for point in removed if chr(point).strip()], [0xFEFF])
        for text in ('\ufeffWas a biopsy taken?', '?', '\u200b', '\u180e', 'x\ufeff'):
            with self.subTest(text=text):
                self.assertFalse(result.blank_question(text))

    def test_the_server_also_calls_blank_five_code_points_the_page_keeps(self):
        # the converse does not hold (D378): str.strip() also removes U+001C..U+001F and U+0085, which trim() keeps, so
        # a question made only of them is blank here and shown by the page, as API.md and ARCHITECTURE.md say
        page = {int(point, 16) for point in self.POINTS}
        server = {point for point in range(sys.maxunicode + 1)
                  if not 0xD800 <= point <= 0xDFFF and result.blank_question(chr(point))}
        self.assertLessEqual(page, server)
        self.assertEqual(sorted(server - page), [0x1C, 0x1D, 0x1E, 0x1F, 0x85])

    def test_a_question_made_only_of_them_is_no_question_wherever_it_is_written(self):
        unasked = (result.UNASKED_QUESTION.format(code='20610'), ['L1'], ['20610'], 'studio')
        listed = combined([q.coded('20610', 'needs_answer', ids=['Q1'])],
                          [q.reviewed('L1', '20610', status='needs_answer')],
                          reader_questions=[q.asked('Q1', '\ufeff'), '\u3000\ufeff\u2028'])
        self.assertEqual(asked(listed), [unasked])
        own = combined([{**q.coded('20610', 'needs_answer'), 'question': ['\ufeff', ' \ufeff\n']}],
                       [{**q.reviewed('L1', '20610', status='needs_answer'), 'question': {'question': '\ufeff\u2029'}}])
        self.assertEqual((asked(own), shown(own)), ([unasked], {'L1': (None, None)}))
        self.assertEqual(result._question_text(['\ufeff', 'Which knee?', '\u2028']), 'Which knee?')
        self.assertIsNone(result._question_text(['\ufeff\u00a0']))


    def test_an_id_blank_to_the_one_test_is_no_id(self):
        # an id is read with the same test: U+FEFF alone names nothing, and a question carrying it as its id has none
        reader = f.reader_result([q.coded('20610', ids=['\ufeff', ' \ufeff '])], questions=[q.asked('\ufeff', 'Which knee?')])
        checker = f.checker_result([q.reviewed('L1', '20610', ids=['\ufeff'])])
        self.assertEqual(asked(combine(reader, checker)), [('Which knee?', [], [], 'reader')])
        self.assertEqual(result.dangling_references(reader, checker), [])
        self.assertEqual(result.listing(reader)['questions'], [{'id': None, 'question': 'Which knee?', 'affects': []}])


class BlankQuestionPageTests(r.CustomerCase, TestCase):
    def test_a_needs_answer_line_whose_only_question_is_blank_gets_the_fallback_a_member_can_answer(self):
        # the server side of the page check: U+FEFF alone is blank to the page, so it is blank to the server too
        enc = self.started()
        reader = f.reader_result([q.coded('20610', 'needs_answer', ids=['Q1'])], questions=[q.asked('Q1', '\ufeff')])
        self.code_round(enc, reader=reader, checker=f.checker_result([q.reviewed('L1', '20610', status='needs_answer')]))
        client = self.client_for(self.reviewer)
        payload = client.get(f'/api/encounters/{enc.pk}').json()
        unasked = result.UNASKED_QUESTION.format(code='20610')
        self.assertEqual(payload['state'], 'awaiting_answer')
        self.assertEqual([(item['text'], item['lines'], item['codes']) for item in payload['questions']],
                         [(unasked, ['L1'], ['20610'])])
        self.assertEqual([(code['line'], code['status'], code['question']) for code in payload['codes']],
                         [('L1', 'needs_answer', None)])
        response = client.post(f'/api/encounters/{enc.pk}/answers', data=json.dumps(
            {'answers': [{'question_id': payload['questions'][0]['id'], 'text': 'The right knee.'}]}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(state.latest_round(enc).context['answers'], [{'question': unasked, 'answer': 'The right knee.'}])

    def test_a_stored_question_or_row_question_that_is_blank_is_never_served(self):
        enc = self.encounter()
        round_ = r.write_round(enc, codes=[r.row('45380', 'needs_answer', question='\ufeff \u2028'),
                                           r.row('45385', 'needs_answer', question='Which site?')],
                               questions=[{'id': 'q1', 'text': '\u3000\ufeff', 'lines': ['L1'], 'codes': ['45380'],
                                           'source': 'reader'},
                                          {'id': 'q2', 'text': 'Which site?', 'lines': ['L1', 'L2'],
                                           'codes': ['45380', '45385'], 'source': 'reader'}])
        self.assertEqual([item['id'] for _, item in decisions.round_questions(round_)], ['q2'])
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        self.assertEqual([item['text'] for item in payload['questions']], ['Which site?'])
        self.assertEqual([code['question'] for code in payload['codes']], [None, 'Which site?'])


class InstructionPinTests(SimpleTestCase):
    """F4 and G3: the instructions are origin/main d7c6a77dc's (tests/fixtures/instructions-d7c6a77dc.json, taken with
    git show from its studio/fable/prompts.py) with only the question parts changed. The sentence checks (F4) make a
    readable failure: the sentences removed and added are exactly the pinned ones, and every other sentence is
    identical and in the same order. The whole-text check (G3 of the D370 round 3) is exact: the fixture's text rebuilt
    - each removed sentence replaced in its own place, between its own separators, by its pinned replacement (or by
    nothing), and each pinned new paragraph inserted at its pinned place - equals the module's text, so a pinned line
    or sentence moved among the unchanged ones, or a paragraph break or a space changed anywhere, fails it. The prompt
    values the change must not touch are pinned too."""
    maxDiff = None  # a failing whole-text check shows the whole difference
    ORIGIN = json.loads((Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'instructions-d7c6a77dc.json')
                        .read_text(encoding='utf-8'))
    READER_REMOVED = [
        '      "question": "the question to ask, or null"',
        '  "questions": [{"question": "plain question", "affects": ["code"]}]',
        '"needs_answer": the code depends on a fact the document does not settle; the question says what.']
    READER_ADDED = [
        '      "question_ids": ["the id of a question this code depends on"]',
        '  "questions": [{"id": "Q1", "question": "plain question", "affects": ["L1"]}]',
        'Questions.',
        'Write every question once, in "questions", with an id: Q1 for the first question, Q2 for the second, and so '
        'on.',
        'A question that more than one code depends on is written once, and its "affects" names every line it '
        'concerns (L1 for the first code of your list, L2 for the second, and so on).',
        'Each code gives the ids of the questions it depends on in "question_ids", an empty list when it depends on '
        'none.',
        'Never repeat a question on a code, and never write two questions that ask the same thing.',
        'The ids are for the JSON only: never write one in a question or a reason.',
        '"needs_answer": the code depends on a fact the document does not settle; the questions its "question_ids" '
        'name say what.']
    CHECKER_REMOVED = [
        '      "question": "the question to ask, or null"',
        '    {"code": "CPT code", "units": 1, "modifiers": [], "status": "ready | needs_answer", "reason": "...", '
        '"evidence": [{"quote": "...", "page": 1}], "question": "or null"}',
        '  "questions": [{"question": "plain question", "affects": ["code"]}]']
    CHECKER_ADDED = [
        '      "question_ids": ["the id of a question this line depends on"]',
        '    {"code": "CPT code", "units": 1, "modifiers": [], "status": "ready | needs_answer", "reason": "...", '
        '"evidence": [{"quote": "...", "page": 1}], "question_ids": []}',
        '  "questions": [{"id": "C1", "question": "plain question", "affects": ["L1"]}]',
        'Questions.',
        "The first coder's questions are given with their ids (Q1, Q2, and so on), and each of its lines names the ids "
        "of the questions it depends on.",
        'Never write again, in any words, a question the coding review already asked; refer to its id instead.',
        'Write each new question once, in "questions", with an id: C1 for the first new question, C2 for the second, '
        'and so on; its "affects" names every line it concerns (L1, L2 and so on for the first coder\'s lines, M1, M2 '
        'and so on for your missed codes).',
        'Each review and each missed code gives the ids of the questions its code depends on in "question_ids", the '
        'coding review\'s or your own, an empty list when it depends on none.',
        'The ids are for the JSON only: never write one in a question or a reason.']
    # G3: what the whole-text check rebuilds the fixture with. Each removed sentence with what replaces it in its own
    # place (None: nothing); each new paragraph - its sentences, joined by one space - with the opening words of the
    # fixture's paragraph it goes before (None: after the last one).
    READER_REPLACED = [(READER_REMOVED[0], READER_ADDED[0]), (READER_REMOVED[1], READER_ADDED[1]),
                       (READER_REMOVED[2], READER_ADDED[-1])]
    READER_INSERTED = [(READER_ADDED[2:-1], 'Status meanings.')]
    CHECKER_REPLACED = list(zip(CHECKER_REMOVED, CHECKER_ADDED[:3]))
    CHECKER_INSERTED = [(CHECKER_ADDED[3:], None)]
    SEPARATOR = re.compile(r'(\n|(?<=[.?!]) +)')

    @classmethod
    def pieces(cls, text):
        """The pin's one splitter, lossless: an instruction cut at every line break, and after every '.', '?' or '!'
        that one or more spaces follow - its sentences at the even places, the separators between them (a line break,
        or those spaces) at the odd places - so that the pieces joined are the text. A line of the JSON shape holds no
        such sentence end, so each of its lines is one sentence; a blank line (a paragraph break) is an empty piece."""
        return cls.SEPARATOR.split(text)

    @classmethod
    def sentences(cls, text):
        """The sentences of an instruction: its pieces without the separators and the empty ones. Every sentence keeps
        its text exactly, its indentation included."""
        return [part for part in cls.pieces(text)[::2] if part.strip()]

    def rebuilt(self, text, replaced, inserted):
        """``text`` rebuilt (G3): each removed sentence replaced, in its own place and between its own separators, by
        its pinned replacement - or, for None, taken out with the spaces before it (with the separator after it when it
        opens its line) - then each new paragraph, its sentences joined by one space, inserted before the paragraph that
        opens with the pinned words, or after the last one (None). A removed sentence that is not in the text exactly
        once, or pinned words no one paragraph opens with, fails the test. (A whole paragraph taken out is not one
        sentence: it would need a pin of its own.)"""
        pieces = self.pieces(text)
        for old, new in replaced:
            places = [index for index in range(0, len(pieces), 2) if pieces[index] == old]
            self.assertEqual(len(places), 1, f'a removed sentence is not in the text exactly once: {old!r}')
            index = places[0]
            if new is not None:
                pieces[index] = new
            elif index + 1 < len(pieces) and (index == 0 or pieces[index - 1] == '\n'):
                del pieces[index:index + 2]
            else:
                del pieces[max(index - 1, 0):index + 1]
        paragraphs = ''.join(pieces).split('\n\n')
        for sentences, before in inserted:
            places = [len(paragraphs)] if before is None else [
                index for index, paragraph in enumerate(paragraphs) if paragraph.startswith(before)]
            self.assertEqual(len(places), 1, f'no one paragraph opens with {before!r}')
            paragraphs.insert(places[0], ' '.join(sentences))
        return '\n\n'.join(paragraphs)

    def assert_rebuilt(self, name, removed, added, replaced, inserted):
        # the rebuild uses exactly the pinned sentences: every removed one once, every added one once
        self.assertEqual([old for old, _ in replaced], removed)
        self.assertCountEqual([new for _, new in replaced if new is not None]
                              + [sentence for sentences, _ in inserted for sentence in sentences], added)
        self.assertEqual(self.rebuilt(self.ORIGIN[name], replaced, inserted), getattr(prompts, name))

    def assert_only_question_parts_changed(self, name, removed, added):
        old, new = self.sentences(self.ORIGIN[name]), self.sentences(getattr(prompts, name))
        self.assertEqual([sentence for sentence in old if sentence not in new], removed)
        self.assertEqual([sentence for sentence in new if sentence not in old], added)
        # every other sentence: identical, as often, and in the same order
        self.assertEqual([sentence for sentence in old if sentence in new],
                         [sentence for sentence in new if sentence in old])

    def test_the_readers_instruction_changes_only_in_its_question_parts(self):
        self.assert_only_question_parts_changed('READER_SYSTEM', self.READER_REMOVED, self.READER_ADDED)

    def test_the_checkers_instruction_changes_only_in_its_question_parts(self):
        self.assert_only_question_parts_changed('CHECKER_SYSTEM', self.CHECKER_REMOVED, self.CHECKER_ADDED)

    def test_the_readers_instruction_is_the_fixture_rebuilt_with_its_question_parts(self):
        self.assert_rebuilt('READER_SYSTEM', self.READER_REMOVED, self.READER_ADDED, self.READER_REPLACED,
                            self.READER_INSERTED)

    def test_the_checkers_instruction_is_the_fixture_rebuilt_with_its_question_parts(self):
        self.assert_rebuilt('CHECKER_SYSTEM', self.CHECKER_REMOVED, self.CHECKER_ADDED, self.CHECKER_REPLACED,
                            self.CHECKER_INSERTED)

    def test_the_rebuild_keeps_every_separator_where_it_was(self):
        # on a synthetic text: a replacement keeps the separators around it; a sentence taken out goes with the spaces
        # before it, or - when it opens its line - with the separator after it; a new paragraph goes before the one
        # opening with its pinned words, or after the last one
        text = 'One. Two.  Three?\n  "shape": 1,\n  "line": 2\n\nLast one! End.'
        self.assertEqual(self.rebuilt(text, [('Two.', 'Deux.'), ('  "shape": 1,', None), ('End.', None)],
                                      [(['New.', 'Again.'], 'Last one!'), (['Tail.'], None)]),
                         'One. Deux.  Three?\n  "line": 2\n\nNew. Again.\n\nLast one!\n\nTail.')
        self.assertEqual(self.rebuilt(text, [('One.', None), ('  "line": 2', None)], []),
                         'Two.  Three?\n  "shape": 1,\n\nLast one! End.')
        with self.assertRaises(self.failureException):  # a removed sentence must be in the text exactly once
            self.rebuilt(text + ' One.', [('One.', 'Uno.')], [])
        with self.assertRaises(self.failureException):  # and a new paragraph's place must be one paragraph
            self.rebuilt(text, [], [(['New.'], 'Nowhere.')])

    def test_the_splitter_keeps_every_sentence_of_the_text(self):
        for name in ('READER_SYSTEM', 'CHECKER_SYSTEM'):
            for text in (self.ORIGIN[name], getattr(prompts, name)):
                with self.subTest(name=name):
                    pieces = self.pieces(text)
                    self.assertEqual(''.join(pieces), text)  # lossless: every separator is kept, in its place
                    self.assertTrue(all(part == '\n' or (part and not part.strip(' ')) for part in pieces[1::2]))
                    kept = self.sentences(text)
                    self.assertEqual(kept, [part for line in text.split('\n')  # the F4 splitter's cut, unchanged
                                            for part in re.split(r'(?<=[.?!]) +', line) if part.strip()])
                    self.assertEqual(''.join(kept), re.sub(r'(?<=[.?!]) +|\n', '', text))
                    self.assertGreater(len(kept), 35)

    def test_the_other_prompt_values_are_unchanged(self):
        self.assertEqual(self.ORIGIN['source'], 'git show d7c6a77dc:cpt-studio/studio/fable/prompts.py')
        for name, value in self.ORIGIN['values'].items():
            with self.subTest(name=name):
                self.assertEqual(getattr(prompts, name), value)
        for item in self.ORIGIN['contexts']:
            with self.subTest(context=item['context']):
                self.assertEqual(prompts.practice_context(item['context']), item['practice_context'])
                self.assertEqual(prompts.reader_instruction(item['context']), item['reader_instruction'])
        # the checker's user text: origin/main's, with the reader's questions inserted after its lines
        pinned, asked_ = self.ORIGIN['checker_instruction'], [q.asked('Q1', 'Was a biopsy taken?', ['L1'])]
        lines = json.dumps(pinned['lines'], indent=1)
        expected = pinned['text'].replace(f'{lines}\n\n', f"{lines}\n\nThe first coder's questions (JSON):\n"
                                                          f'{json.dumps(asked_, indent=1)}\n\n', 1)
        self.assertNotEqual(expected, pinned['text'])
        self.assertEqual(prompts.checker_instruction(pinned['context'], {'lines': pinned['lines'], 'questions': asked_}),
                         expected)


class SharedIdTests(SimpleTestCase):
    """F3: the question ids both answers define - top-level or on a line or review - compared case-insensitively, for
    the operator console; each reference of the checker's to one reaches every question carrying it in either answer
    (never fewer), which is one question where their texts are the same (G1 of round 3: SharedIdWordingTests)."""

    def test_the_ids_both_answers_define_are_listed_as_the_reader_wrote_them(self):
        reader = f.reader_result([q.coded('45380', ids=[{'id': 'Q2', 'question': 'Was a biopsy taken?'}])],
                                 questions=[q.asked('Q1', 'Which site?'), q.asked(3, 'Which payer?'),
                                            q.asked('Q5', 'Which day?')])
        checker = f.checker_result([q.reviewed('L1', '45380', ids=[{'id': ' q2 ', 'question': 'Which polyp?'}])],
                                   missed=[{**q.added('45378'), 'question': {'id': '3', 'question': 'How long?'}}],
                                   questions=[q.asked('q1', 'Which knee?')])
        self.assertEqual(result.shared_ids(reader, checker), ['Q1', 3, 'Q2'])
        self.assertEqual(result.shared_ids(q.READER, q.CHECKER), [])
        self.assertEqual(result.shared_ids(None, {'reviews': 'not a list', 'questions': 7}), [])

    def test_a_reference_of_the_checker_to_a_shared_id_reaches_both_questions(self):
        out = combined([q.coded('20610', 'needs_answer', ids=['Q1'])],
                       [q.reviewed('L1', '20610', ids=['Q1'], status='needs_answer')],
                       missed=[q.added('J3301', 'needs_answer', ids=['Q1'])],
                       reader_questions=[q.asked('Q1', 'Which knee was injected?', ['L1'])],
                       checker_questions=[q.asked('Q1', 'How many milligrams were injected?', ['M1'])])
        self.assertEqual(asked(out), [('Which knee was injected?', ['L1', 'M1'], ['20610', 'J3301'], 'reader'),
                                      ('How many milligrams were injected?', ['L1', 'M1'], ['20610', 'J3301'], 'checker')])


class DanglingAsWrittenTests(SimpleTestCase):
    def test_a_dangling_reference_is_given_exactly_as_written(self):
        # F8: an integer id stays an integer (the console shows 7, not "7"); a string keeps its spacing
        reader = f.reader_result([q.coded('20610', ids=[7, ' q9 ', 'Q1'])], questions=[q.asked('Q1', 'Which knee?')])
        self.assertEqual(result.dangling_references(reader, f.checker_result([])),
                         [{'item': 'L1', 'code': '20610', 'reference': 7},
                          {'item': 'L1', 'code': '20610', 'reference': ' q9 '}])


class OperatorConsoleRoundTwoTests(r.CustomerCase, TestCase):
    def test_the_console_shows_a_dangling_integer_as_written_and_the_ids_both_answers_defined(self):
        enc = self.started()
        reader = f.reader_result([q.coded('20610', 'needs_answer', ids=['Q1', 7])],
                                 questions=[q.asked('Q1', 'Which knee was injected?', ['L1'])])
        checker = f.checker_result([q.reviewed('L1', '20610', ids=['Q1'], status='needs_answer')],
                                   questions=[q.asked('q1', 'How many milligrams were injected?')])
        self.code_round(enc, reader=reader, checker=checker)
        page = ops.client(f.user('platform-operator')).get(f'/ops/encounters/{enc.pk}').content.decode('utf-8')
        self.assertIn('<li>L1 <span class="mono">20610</span> names <span class="mono">7</span></li>', page)
        self.assertIn('<h3>Question ids both the reader and the checker defined</h3>', page)
        self.assertIn(SHARED_SENTENCE, page)
        self.assertIn('<li><span class="mono">&quot;Q1&quot;</span></li>', page)
        clean = self.started(title='Synthetic note whose ids are its own')
        self.code_round(clean, reader=q.READER, checker=q.CHECKER)
        page = ops.client(f.user('platform-operator-2')).get(f'/ops/encounters/{clean.pk}').content.decode('utf-8')
        self.assertNotIn('both the reader and the checker defined', page)


class MergeCostTests(SimpleTestCase):
    """F6: the merge costs in proportion to what it reads. The refutation's case - 1,500 distinct questions sharing
    the id Q1, and 100 lines and 100 reviews each naming Q1 five times - took 103 s at the first build (a quadratic
    scan per reference) and 22 ms on origin/main (which reads no ids); the bound is generous."""

    def test_many_questions_sharing_one_id_are_merged_well_within_the_bound(self):
        reader = f.reader_result([q.coded('45380', 'needs_answer', ids=['Q1'] * 5) for _ in range(100)],
                                 questions=[q.asked('Q1', f'Synthetic question number {n}?') for n in range(1500)])
        checker = f.checker_result([q.reviewed(f'L{n}', '45380', ids=['Q1'] * 5, status='needs_answer')
                                    for n in range(1, 101)])
        reader_msg, checker_msg = f.reader_message(reader), f.checker_message(checker)
        started = time.perf_counter()
        parsed_reader, parsed_checker = result.read_reader(reader_msg), result.read_checker(checker_msg)
        out = result.combine(parsed_reader, parsed_checker)
        listed = result.listing(parsed_reader)
        dangling = result.dangling_references(parsed_reader, parsed_checker)
        shared = result.shared_ids(parsed_reader, parsed_checker)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 5.0)
        lines = [f'L{n}' for n in range(1, 101)]
        self.assertEqual(len(out['questions']), 1500)
        self.assertTrue(all(item['lines'] == lines for item in out['questions']))
        self.assertTrue(all(row['question'].count('\n') == 1499 and row['second_check']['question'] == row['question']
                            for row in out['codes']))
        self.assertEqual((len(listed['questions']), dangling, shared), (1500, [], []))


# --- round 3 (the lead's decisions on the refutation of round 2) ------------------------------------------------------

KNEE = 'Which knee received the injection?'  # the Q2R-1 checker's synthetic input
GUIDANCE = 'Was the needle placed under ultrasound guidance?'


class SharedIdWordingTests(r.CustomerCase, TestCase):
    """G1: the ids both answers define are listed whether their definitions stayed two questions or merged into one (a
    partial merge can still give a reference more than one), under a sentence that is true in either case."""

    @staticmethod
    def reader_and_checker(reader_questions):
        # the Q2R-1 input: the checker restates the reader's Q1 - id, text and all - to add its own missed code to it
        reader = f.reader_result([q.coded('20610', 'needs_answer', ids=['Q1'])], questions=reader_questions)
        checker = f.checker_result([q.reviewed('L1', '20610', ids=['Q1'], status='needs_answer')],
                                   missed=[q.added('J1030', 'needs_answer', ids=['Q1'])],
                                   questions=[q.asked('Q1', KNEE, ['L1', 'M1'])])
        return reader, checker

    def test_a_checker_restating_the_readers_question_adds_none_and_the_console_says_so_truly(self):
        enc = self.started()
        reader, checker = self.reader_and_checker([q.asked('Q1', KNEE, ['L1'])])
        round_ = self.code_round(enc, reader=reader, checker=checker)
        self.assertEqual([(item['text'], item['lines'], item['codes'], item['source']) for item in round_.questions],
                         [(KNEE, ['L1', 'M1'], ['20610', 'J1030'], 'reader')])
        self.assertEqual(result.shared_ids(round_.reader_result, round_.checker_result), ['Q1'])
        page = ops.client(f.user('platform-operator')).get(f'/ops/encounters/{enc.pk}').content.decode('utf-8')
        # the console's questions: one, naming both lines
        self.assertEqual(page.split('<h3>Questions</h3><ol>', 1)[1].split('</ol>', 1)[0],
                         f'<li>{KNEE} <span class="muted">(reader; lines L1, M1; codes 20610, J1030)</span></li>')
        # the id is still listed, under a sentence as true of one question as of two
        self.assertIn('<h3>Question ids both the reader and the checker defined</h3>', page)
        self.assertIn(f'<p class="muted">{SHARED_SENTENCE}</p>', page)
        self.assertIn('<li><span class="mono">&quot;Q1&quot;</span></li>', page)
        self.assertNotIn('reaches both questions', page)

    def test_an_id_whose_definitions_merged_is_still_listed_as_a_partial_merge_reaches_two_questions(self):
        # the reader wrote Q1 twice and the checker restates one of them: the checker's references reach both
        reader, checker = self.reader_and_checker([q.asked('Q1', KNEE, ['L1']), q.asked('Q1', GUIDANCE)])
        out = combine(reader, checker)
        self.assertEqual(asked(out), [(KNEE, ['L1', 'M1'], ['20610', 'J1030'], 'reader'),
                                      (GUIDANCE, ['L1', 'M1'], ['20610', 'J1030'], 'reader')])
        self.assertEqual(shown(out), {'L1': (f'{KNEE}\n{GUIDANCE}', f'{KNEE}\n{GUIDANCE}'),
                                      'M1': (f'{KNEE}\n{GUIDANCE}', None)})
        self.assertEqual(result.shared_ids(reader, checker), ['Q1'])
