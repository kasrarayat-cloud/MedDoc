"""Each question once, for every document (D370, D372). The reader writes each question once, in its top-level list,
with an id (Q1, Q2..), and a code names the questions it depends on in question_ids; the checker is given the reader's
questions with their ids, refers to them, and writes only its new ones (C1, C2..). The site merges by id - and by
today's exact-text merge, never by reading what a question means (D358) - shows each question once naming every line it
affects, and never loses one: today's shape reads exactly as today, a mixed answer additively, a duplicate id stays
separate questions, an id naming no question carries no text (the operator console lists it), and a needs_answer line
no question names still gets one a member can answer. Synthetic answers only; nothing reaches the network."""
import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from studio import models, state
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

    def test_the_rules_the_change_does_not_touch_are_kept_word_for_word(self):
        office = ("Write for the physician's office. Never mention artificial intelligence, models, software, vendors "
                  "or 'the first coder'; say 'the coding review' or 'the second check' if you must refer to a review.")
        for system in (prompts.READER_SYSTEM, prompts.CHECKER_SYSTEM):
            self.assertIn(office, system)
            self.assertIn('End your last section with a line that holds exactly `END`.', system)
        self.assertIn('agreeing with a wrong code is the worst outcome, and an unnecessary question is the second '
                      'worst. Also list any code the document supports that the first coder missed, and any question '
                      'that must be answered before a code can be approved. List only questions the coding review did '
                      'not already ask.', prompts.CHECKER_SYSTEM)
        self.assertIn('each starting with a line that holds exactly `LINE L<n> <code>`', prompts.READER_SYSTEM)
        self.assertIn('each starting with a line that holds exactly `REVIEW L<n> <code>`', prompts.CHECKER_SYSTEM)
        self.assertIn('each starting with a line that holds exactly `MISSED M<k> <code>`', prompts.CHECKER_SYSTEM)
        self.assertIn('"status": "ready | needs_answer | not_supported"', prompts.READER_SYSTEM)
        self.assertIn('"correct_status": "ready | needs_answer | not_supported"', prompts.CHECKER_SYSTEM)
        self.assertIn('"status": "ready | needs_answer"', prompts.CHECKER_SYSTEM)
        self.assertIn('Status meanings. "ready": the document fully supports the code exactly as written, and a human '
                      'coder can approve it.', prompts.READER_SYSTEM)

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
