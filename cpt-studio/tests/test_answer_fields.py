"""The answer's fields (FIX-SPEC-2 section 2; findings PARSE-3, PARSE-4, PARSE-8): every field is read in the shape the
instructions give it, a lossless conversion of the shape aside - digits as units, an integer modifier as its string, a
list of reasons joined, a list of questions or one question object, one top-level question object, a documentation
problem that is no string as its JSON text - and a blank modifier item, which carries nothing, is removed; any other
shape makes the answer unreadable, so nothing Fable wrote is dropped, altered or guessed. A code is a string of the code
shape, a status one of the allowed values, and a line label the reader writes on its own items must be its place in
the list. Synthetic answers only; nothing reaches the network."""
from django.test import SimpleTestCase, TestCase

from studio import models, state
from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_line_identity import code_row


def reader_of(*codes, questions=(), problems=()):
    """A reader result whose questions and problems are written as given (a tuple is a list; anything else as is)."""
    out = f.reader_result(list(codes))
    out['questions'] = list(questions) if isinstance(questions, tuple) else questions
    out['documentation_problems'] = list(problems) if isinstance(problems, tuple) else problems
    return out


def checker_of(reviews, *, missed=(), questions=()):
    out = f.checker_result(reviews, missed=missed)
    out['questions'] = list(questions) if isinstance(questions, tuple) else questions
    return out


def read(reader):
    return result.read_reader(f.reader_message(reader))


def combined(*codes, reviews=None, questions=(), problems=(), missed=(), checker_questions=()):
    reader = reader_of(*codes, questions=questions, problems=problems)
    if reviews is None:
        reviews = [r.review(f'L{n}', item['code']) for n, item in enumerate(codes, start=1)]
    checker = checker_of(reviews, missed=missed, questions=checker_questions)
    result.read_reader(f.reader_message(reader))
    result.read_checker(f.checker_message(checker))
    return result.combine(reader, checker)


class CodeAndStatusTests(SimpleTestCase):
    def test_a_code_is_a_string_of_the_code_shape(self):
        for code in ('45385', '0001U', '0591T', '1234F', 'G2211', 'J1100'):
            with self.subTest(code=code):
                self.assertEqual([row['code'] for row in combined(f.code(code))['codes']], [code])
        for code in ('45385-59', ' 45385', '45385 ', 'g2211', '4538', '453851', 'CPT 45385', '45385\n', 'GG211'):
            with self.subTest(code=code), self.assertRaises(result.Unreadable):
                read(reader_of(f.code(code)))
            with self.subTest(missed=code), self.assertRaises(result.Unreadable):
                result.read_checker(f.checker_message(f.checker_result([], missed=[r.missed(code)])))

    def test_a_missed_code_has_one_of_the_statuses_the_checker_is_given(self):
        for status in ('ready', 'needs_answer'):
            with self.subTest(status=status):
                checker = f.checker_result([], missed=[r.missed('45378', status)])
                self.assertEqual(result.read_checker(f.checker_message(checker)), checker)
        for status in ('not_supported', 'Ready', None, 3):
            with self.subTest(status=status), self.assertRaises(result.Unreadable):
                result.read_checker(f.checker_message(f.checker_result([], missed=[r.missed('45378', status)])))
        absent = {key: value for key, value in r.missed('45378').items() if key != 'status'}
        with self.assertRaises(result.Unreadable):
            result.read_checker(f.checker_message(f.checker_result([], missed=[absent])))


class ModifierTests(SimpleTestCase):
    def test_a_blank_modifier_item_carries_nothing_and_is_removed(self):
        # PARSE-3: ['25', ''] was stored as written; the page said "Modifiers not given" and the export printed "25, "
        rows = combined({**f.code('99214'), 'modifiers': ['25', '']}, {**f.code('20610'), 'modifiers': ['RT', ' ']},
                        {**f.code('45385'), 'modifiers': ['']}, {**f.code('45380'), 'modifiers': ['\t', 59]})['codes']
        self.assertEqual([row['modifiers'] for row in rows], [['25'], ['RT'], [], ['59']])
        self.assertEqual(result.listing(reader_of({**f.code('99214'), 'modifiers': ['25', '']}))['lines'][0][
            'modifiers'], ['25'])


class UnitsTests(SimpleTestCase):
    def test_units_are_a_whole_number_or_its_digits_and_null_is_not_given(self):
        # zero is a value: the reader writes units 0 for a code it does not support (measured on the recorded answers)
        for written, shown in ((2, 2), ('2', 2), ('007', 7), (0, 0), ('0', 0), (None, None)):
            with self.subTest(units=written):
                (row,) = combined({**f.code('20610'), 'units': written})['codes']
                self.assertEqual(row['units'], shown)
                self.assertEqual(result.listing(reader_of({**f.code('20610'), 'units': written}))['lines'][0]['units'],
                                 shown)
        absent = {key: value for key, value in f.code('20610').items() if key != 'units'}
        self.assertIsNone(combined(absent)['codes'][0]['units'])

    def test_units_in_any_other_shape_make_the_answer_unreadable(self):
        for units in ('two', '2 ', '-1', '1.5', '\uff12', -1, 1.0, True, [2], {'n': 2}):
            with self.subTest(units=units), self.assertRaises(result.Unreadable):
                read(reader_of({**f.code('20610'), 'units': units}))
        with self.assertRaises(result.Unreadable):
            result.read_checker(f.checker_message(f.checker_result([], missed=[{**r.missed('45378'), 'units': 'two'}])))


class ReasonTests(SimpleTestCase):
    def test_a_reason_written_as_a_list_of_strings_is_joined_with_one_space(self):
        (row,) = combined({**f.code('99214'), 'reason': ['Moderate MDM.', 'Two chronic illnesses.']},
                          reviews=[{**r.review('L1', '99214', 'disagree'), 'reason': ['Low MDM.', 'One illness.']}])[
            'codes']
        self.assertEqual(row['reason'], 'Moderate MDM. Two chronic illnesses.')
        self.assertEqual(row['second_check']['reason'], 'Low MDM. One illness.')
        self.assertIsNone(combined({**f.code('99214'), 'reason': None})['codes'][0]['reason'])

    def test_a_reason_in_any_other_shape_makes_the_answer_unreadable(self):
        for reason in (5, ['a', 5], {'text': 'x'}, True, [None]):
            with self.subTest(reason=reason):
                with self.assertRaises(result.Unreadable):
                    read(reader_of({**f.code('99214'), 'reason': reason}))
                with self.assertRaises(result.Unreadable):
                    result.read_checker(f.checker_message(f.checker_result(
                        [{**r.review('L1', '99214'), 'reason': reason}])))


class QuestionTests(SimpleTestCase):
    def test_a_lines_question_list_asks_each_question_tied_to_that_line(self):
        # PARSE-4 (F): both of Fable's questions were dropped and CPT Studio's own question asked instead
        asked = ['Which knee was injected?', 'Was ultrasound guidance used?']
        out = combined({**f.code('20610', 'needs_answer'), 'question': asked},
                       reviews=[r.review('L1', '20610', status='needs_answer')])
        (row,) = out['codes']
        self.assertEqual(row['status'], 'needs_answer')
        self.assertEqual(row['question'], 'Which knee was injected?\nWas ultrasound guidance used?')
        self.assertEqual([(q['text'], q['lines']) for q in out['questions']],
                         [('Which knee was injected?', ['L1']), ('Was ultrasound guidance used?', ['L1'])])
        listed = result.listing(reader_of({**f.code('20610', 'needs_answer'), 'question': asked}))['lines']
        self.assertEqual(listed[0]['question'], 'Which knee was injected?\nWas ultrasound guidance used?')

    def test_a_lines_question_object_gives_its_question(self):
        out = combined({**f.code('20610', 'needs_answer'), 'question': {'question': 'Which knee was injected?'}},
                       reviews=[r.review('L1', '20610', status='needs_answer')])
        self.assertEqual(out['codes'][0]['question'], 'Which knee was injected?')
        self.assertEqual([(q['text'], q['lines']) for q in out['questions']], [('Which knee was injected?', ['L1'])])

    def test_a_reviews_question_list_is_asked_for_its_needs_answer_line(self):
        out = combined(f.code('45380', 'needs_answer'), reviews=[{**r.review('L1', '45380', status='needs_answer'),
                                                                  'question': ['Which site?', 'Was it separate?']}])
        self.assertEqual([(q['text'], q['lines'], q['source']) for q in out['questions']],
                         [('Which site?', ['L1'], 'checker'), ('Was it separate?', ['L1'], 'checker')])

    def test_one_top_level_question_object_is_a_one_item_list(self):
        # PARSE-4 (J): the ultrasound question, written as one object, was ignored
        question = {'question': 'Was ultrasound guidance used for the injection?', 'affects': ['20610']}
        out = combined({**f.code('20610'), 'modifiers': ['RT']}, questions=question,
                       checker_questions={'question': 'Which knee?', 'affects': 'L1'})
        self.assertEqual([(q['text'], q['lines'], q['source']) for q in out['questions']],
                         [('Was ultrasound guidance used for the injection?', ['L1'], 'reader'),
                          ('Which knee?', ['L1'], 'checker')])

    def test_a_question_in_any_other_shape_makes_the_answer_unreadable(self):
        for question in (3, ['Which knee?', 3], {'text': 'Which knee?'}, {'question': None}, True):
            with self.subTest(line_question=question), self.assertRaises(result.Unreadable):
                read(reader_of({**f.code('20610', 'needs_answer'), 'question': question}))
        for questions in ('Which knee?', 7, [7], [None], [{'text': 'Which knee?'}], [{'question': 'Q?',
                                                                                     'affects': {'code': '20610'}}]):
            with self.subTest(questions=questions), self.assertRaises(result.Unreadable):
                read(reader_of(f.code('20610'), questions=questions))
            with self.subTest(checker_questions=questions), self.assertRaises(result.Unreadable):
                result.read_checker(f.checker_message(checker_of([], questions=questions)))
        self.assertEqual(combined(f.code('20610'), questions=None)['questions'], [])


class ProblemTests(SimpleTestCase):
    def test_a_documentation_problem_that_is_no_string_is_kept_as_its_json_text(self):
        out = combined(f.code('45385'), problems=['No signature.', 4, {'problem': 'No date of service'}])
        self.assertEqual(out['problems'], ['No signature.', '4', '{"problem": "No date of service"}'])
        reader = {**reader_of(f.code('45385')), 'documentation_problems': 'The note is not signed.'}
        checker = f.checker_result([r.review('L1', '45385')])
        self.assertEqual(result.combine(read(reader), checker)['problems'], ['The note is not signed.'])


class OwnLineLabelTests(SimpleTestCase):
    def test_a_line_label_that_disagrees_with_the_lists_order_makes_the_answer_unreadable(self):
        # PARSE-8: the reader numbered its own items against their order, and each knee's quote went to the other knee
        swapped = [{**f.code('20610', modifiers=['LT']), 'line': 'L2'}, {**f.code('20610', modifiers=['RT']), 'line': 'L1'}]
        with self.assertRaises(result.Unreadable):
            read(reader_of(*swapped))
        for label in ('L2', '1', 1, 'L01', 'M1', 'L12', True):
            with self.subTest(label=label), self.assertRaises(result.Unreadable):
                read(reader_of({**f.code('20610'), 'line': label}))
        missed = [{**r.missed('45378'), 'line': 'M2'}, {**r.missed('45380'), 'line': 'M1'}]
        with self.assertRaises(result.Unreadable):
            result.read_checker(f.checker_message(f.checker_result([], missed=missed)))

    def test_labels_that_agree_with_the_lists_order_are_read(self):
        rows = combined({**f.code('20610', modifiers=['RT']), 'line': 'L1'},
                        {**f.code('20610', modifiers=['LT']), 'line': ' l2 '}, {**f.code('45385'), 'line': None},
                        {**f.code('45378'), 'line': ''})['codes']
        self.assertEqual([(row['line'], row['modifiers']) for row in rows],
                         [('L1', ['RT']), ('L2', ['LT']), ('L3', []), ('L4', [])])


class FieldPipelineTests(r.CustomerCase, TestCase):
    def payload(self, enc):
        return self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()

    def test_a_blank_modifier_item_never_reaches_the_page_or_the_exports(self):
        # PARSE-3 through the stage, the API, an approval and the approved report
        enc = self.started()
        self.code_round(enc, reader=reader_of({**f.code('99214', reason='Separately identifiable E/M.'),
                                               'modifiers': ['25', '']}),
                        checker=f.checker_result([r.review('L1', '99214')]))
        (code,) = self.payload(enc)['codes']
        self.assertEqual((code['modifiers'], code['status']), (['25'], 'ready'))
        self.assertEqual(self.decide(enc, 'L1', '99214', 'approve').status_code, 201)
        # the line's row: its modifiers end at 25 (never "25, "), then its units
        self.assertIn('Line L1 · Modifiers: 25 UNITS 1', code_row(self.report_text(enc, 'approved'), 1, '99214'))

    def test_a_stored_blank_modifier_item_is_shown_the_same_on_the_page_and_in_the_exports(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('99214', 'ready', modifiers=['25', '']), r.row('45385', 'ready',
                                                                                       modifiers=[' '])])
        self.assertEqual([code['modifiers'] for code in self.payload(enc)['codes']], [['25'], []])
        text = self.report_text(enc, 'draft')
        first, second = code_row(text, 1, '99214'), code_row(text, 2, '45385')
        self.assertIn('Ready for approval', first)
        self.assertIn('Line L1 · Modifiers: 25 UNITS 1', first)
        self.assertIn('Ready for approval', second)
        self.assertIn('Line L2 · Modifiers: none UNITS 1', second)

    def test_units_as_digits_and_a_question_object_reach_the_checker_the_page_and_the_export(self):
        # PARSE-4 (J): the checker was told units null, the question vanished and the export read "units not given"
        enc = self.started()
        reader = reader_of({**f.code('20610', reason='A knee injection is documented.'), 'units': '2',
                            'modifiers': ['RT']},
                           questions={'question': 'Was ultrasound guidance used for the injection?',
                                      'affects': ['20610']})
        fake = self.use(f.FakeCoder(reader=f.succeeded(r.reader_message(reader)),
                                    checker=f.succeeded(r.checker_message(f.checker_result([r.review('L1', '20610')])))))
        self.run_next()
        checker_text = fake.calls[1][1].stored['messages'][0]['content'][1]['text']
        self.assertIn('"units": 2', checker_text)
        payload = self.payload(enc)
        self.assertEqual([(code['units'], code['modifiers'], code['status']) for code in payload['codes']],
                         [(2, ['RT'], 'ready')])
        self.assertEqual([(q['text'], q['lines']) for q in payload['questions']],
                         [('Was ultrasound guidance used for the injection?', ['L1'])])
        self.assertEqual(self.decide(enc, 'L1', '20610', 'approve').status_code, 201)
        self.assertIn('Line L1 · Modifiers: RT UNITS 2', code_row(self.report_text(enc, 'approved'), 1, '20610'))

    def test_both_questions_of_a_needs_answer_line_are_asked_and_answerable(self):
        # PARSE-4 (F): the line's two questions were replaced by CPT Studio's own generic question
        enc = self.started()
        asked = ['Which knee was injected?', 'Was ultrasound guidance used?']
        self.code_round(enc, reader=reader_of({**f.code('20610', 'needs_answer'), 'question': asked}),
                        checker=f.checker_result([r.review('L1', '20610', status='needs_answer')]))
        payload = self.payload(enc)
        self.assertEqual(payload['state'], 'awaiting_answer')
        self.assertEqual([(q['text'], q['lines'], q['codes']) for q in payload['questions']],
                         [(asked[0], ['L1'], ['20610']), (asked[1], ['L1'], ['20610'])])
        self.assertNotIn('What does the coding review need to know', str(payload))
        self.assertEqual(payload['codes'][0]['question'], 'Which knee was injected?\nWas ultrasound guidance used?')
        self.assertEqual(state.latest_round(enc).questions[0]['source'], 'reader')

    def test_an_answer_in_the_recorded_answers_shape_is_read_and_units_zero_is_shown_as_written(self):
        # the shape measured on the recorded answers: a description field nothing reads, units 0 on a code the reader
        # does not support, question objects with what they affect - all read, nothing failed or dropped
        enc = self.started()
        reader = reader_of({**f.code('45385', reason='A cold snare removal is documented.'), 'description': 'x'},
                           {**f.code('45384', 'not_supported', reason='No hot biopsy forceps.'), 'units': 0,
                            'description': 'y'},
                           questions=[{'question': 'Was the polyp retrieved?', 'affects': ['45385']}])
        self.code_round(enc, reader=reader, checker=f.checker_result([r.review('L1', '45385'), {
            **r.review('L2', '45384', status='not_supported'), 'correct_units': 0}]))
        payload = self.payload(enc)
        self.assertEqual([(code['line'], code['units'], code['status']) for code in payload['codes']],
                         [('L1', 1, 'ready'), ('L2', 0, 'not_supported')])
        # its status label (the row's last column says "Not supported" again), then its line, modifiers and units
        self.assertIn('Not supported Line L2 · Modifiers: none UNITS 0',
                      code_row(self.report_text(enc, 'draft'), 2, '45384'))

    def test_a_field_in_a_shape_that_cannot_be_read_fails_the_round_before_the_checker_is_sent(self):
        enc = self.started()
        reader = reader_of({**f.code('20610'), 'units': 'two'})
        fake = self.use(f.FakeCoder(reader=f.succeeded(r.reader_message(reader)),
                                    checker=f.succeeded(r.checker_message(f.checker_result([])))))
        self.run_next()
        round_ = state.latest_round(enc)
        self.assertEqual((round_.state, round_.failure_kind), (models.CodingRound.FAILED, 'unreadable'))
        self.assertEqual(fake.roles(), ['reader'])
