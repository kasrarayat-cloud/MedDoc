"""The round's questions (FIX-SPEC section 3; finding INT-7): the two top-level lists, then each line's own question
when its text is not listed yet, every question naming the lines it affects - so a needs_answer line always has a
question the member can answer, and answering it starts the next round. Synthetic answers only; nothing reaches the
network."""
import json

from django.test import SimpleTestCase, TestCase

from studio import models, state
from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r

Round = models.CodingRound
QUESTION = 'Was the biopsy from a separate site?'


class QuestionListTests(SimpleTestCase):
    def combine(self, codes, reviews, reader_questions=(), checker_questions=(), missed=()):
        return result.combine(f.reader_result(codes, questions=reader_questions),
                              f.checker_result(reviews, missed=missed, questions=checker_questions))

    def test_a_question_written_only_on_its_line_is_asked(self):
        combined = self.combine([f.code('45385'), f.code('45380', 'needs_answer', question=QUESTION)],
                                [r.review('L1', '45385'), r.review('L2', '45380', status='needs_answer')])
        self.assertEqual(combined['codes'][1]['status'], 'needs_answer')
        self.assertEqual([(q['text'], q.get('lines'), q['codes']) for q in combined['questions']],
                         [(QUESTION, ['L2'], ['45380'])])

    def test_a_line_question_already_listed_is_asked_once_with_case_and_spaces_folded(self):
        combined = self.combine(
            [f.code('45380', 'needs_answer', question='was the biopsy  from a SEPARATE site?')],
            [r.review('L1', '45380', status='needs_answer')],
            reader_questions=[{'question': QUESTION, 'affects': []}])
        self.assertEqual([(q['id'], q['text'], q.get('lines')) for q in combined['questions']],
                         [('q1', QUESTION, ['L1'])])

    def test_affects_names_every_line_of_a_code_or_a_line_by_its_label(self):
        combined = self.combine(
            [f.code('20610', modifiers=['RT']), f.code('20610', 'needs_answer', modifiers=['LT'])],
            [r.review('L1', '20610'), r.review('L2', '20610')],
            reader_questions=[{'question': 'Which knee was injected?', 'affects': ['20610']}],
            checker_questions=[{'question': 'Was the left knee aspirated first?', 'affects': ['L2', 45380, None]}])
        self.assertEqual([(q['text'], q.get('lines'), q['codes'], q['source']) for q in combined['questions']],
                         [('Which knee was injected?', ['L1', 'L2'], ['20610'], 'reader'),
                          ('Was the left knee aspirated first?', ['L2'], ['20610'], 'checker')])

    def test_a_needs_answer_line_no_question_names_gets_one_the_member_can_answer(self):
        agreed = self.combine([f.code('45380', 'needs_answer')],
                              [r.review('L1', '45380', status='needs_answer', question='Which site was sampled?')])
        self.assertEqual([(q['text'], q.get('lines')) for q in agreed['questions']],
                         [('Which site was sampled?', ['L1'])])
        silent = self.combine([f.code('45380', 'needs_answer')], [r.review('L1', '45380', status='needs_answer')])
        self.assertEqual([(q['text'], q.get('lines')) for q in silent['questions']],
                         [(result.UNASKED_QUESTION.format(code='45380'), ['L1'])])

    def test_a_plain_string_question_is_kept(self):
        combined = self.combine([f.code('45385')], [r.review('L1', '45385')], reader_questions=['Which payer applies?'])
        self.assertEqual([(q['text'], q.get('lines')) for q in combined['questions']], [('Which payer applies?', [])])


class AnswerableTests(r.CustomerCase, TestCase):
    def test_a_line_question_can_be_answered_and_starts_the_next_round(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45385'), f.code('45380', 'needs_answer',
                                                                              question=QUESTION)]),
                        checker=f.checker_result([r.review('L1', '45385'),
                                                  r.review('L2', '45380', status='needs_answer')]))
        client = self.client_for(self.reviewer)
        payload = client.get(f'/api/encounters/{enc.pk}').json()
        self.assertEqual(payload['state'], 'awaiting_answer')
        self.assertEqual([(q['text'], q.get('lines'), q['codes']) for q in payload['questions']],
                         [(QUESTION, ['L2'], ['45380'])])
        response = client.post(f'/api/encounters/{enc.pk}/answers', data=json.dumps(
            {'answers': [{'question_id': payload['questions'][0]['id'], 'text': 'Yes, the ascending colon.'}]}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        round2 = state.latest_round(enc)
        self.assertEqual((round2.number, round2.trigger, round2.state), (2, Round.ANSWERS, Round.QUEUED))
        self.assertEqual(round2.context['answers'], [{'question': QUESTION, 'answer': 'Yes, the ascending colon.'}])
