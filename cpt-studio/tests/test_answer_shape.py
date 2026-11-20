"""The shape of the final answer (FIX-SPEC section 2; findings INT-5, INT-6, INT-8): the last ```json block or nothing,
modifiers that are never dropped or turned into "no modifier", and a review that names no code making the answer
unreadable. Synthetic answers only; nothing reaches the network."""
import csv
import io
import json

from django.test import SimpleTestCase, TestCase

from studio import models, state
from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r

Round = models.CodingRound
DRAFT = {'codes': [{'code': '99213', 'units': 1, 'modifiers': [], 'status': 'ready', 'reason': 'Draft: low MDM.',
                    'evidence': [], 'question': None}], 'questions': [], 'documentation_problems': []}
# The final block's quote carries unescaped inner quotation marks, so it is not JSON.
BROKEN_FINAL = ('```json\n{"codes": [{"code": "99214", "units": 1, "modifiers": [], "status": "ready", '
                '"reason": "Moderate MDM.", "evidence": [{"quote": "patient said "the pain is worse"", "page": 2}], '
                '"question": null}], "questions": [], "documentation_problems": []}\n```\n')


def drafted(final):
    return (f'My first pass, before re-reading page 2:\n```json\n{json.dumps(DRAFT)}\n```\n'
            f'On re-reading page 2 the MDM is moderate.\nLINE L1 99214\n{final}')


class FinalAnswerTests(SimpleTestCase):
    """INT-5: the final answer is exactly the last ```json block; never an earlier draft block."""

    def test_a_broken_final_block_never_falls_back_to_an_earlier_draft(self):
        text = drafted(BROKEN_FINAL)
        self.assertIsNone(result.last_json(text))
        with self.assertRaises(result.Unreadable):
            result.read_reader(f.message([f.text_block(text)]))

    def test_a_final_block_without_its_closing_fence_is_read_to_the_end_of_the_text(self):
        final = {'codes': [{'code': '99214', 'status': 'ready'}]}
        self.assertEqual(result.last_json(drafted('```json\n' + json.dumps(final) + '\n')), final)
        self.assertIsNone(result.last_json(drafted(BROKEN_FINAL.rstrip('`\n'))))

    def test_the_checkers_broken_final_disagreement_is_not_replaced_by_its_draft_agreement(self):
        draft = {'reviews': [{'line': 'L1', 'code': '99214', 'verdict': 'agree'}], 'missed_codes': []}
        final = ('```json\n{"reviews": [{"line": "L1", "code": "99214", "verdict": "disagree", '
                 '"reason": "The note says "low complexity"."}], "missed_codes": []}\n```\n')
        text = f'Draft:\n```json\n{json.dumps(draft)}\n```\nREVIEW L1 99214\n{final}'
        with self.assertRaises(result.Unreadable):
            result.read_checker(f.message([f.text_block(text)]))

    def test_a_valid_final_block_wins_over_an_earlier_one(self):
        final = {'codes': [{'code': '99214', 'status': 'ready'}]}
        self.assertEqual(result.last_json(drafted('```json\n' + json.dumps(final) + '\n```\n')), final)


class ModifierTests(SimpleTestCase):
    """INT-6: modifiers are a list of strings; an integer item is its decimal string; any other shape is unreadable;
    absent modifiers are not given, never "no modifier"."""

    def combined(self, codes):
        reader = f.reader_result(codes)
        checker = f.checker_result([r.review(f'L{n}', item['code']) for n, item in enumerate(codes, start=1)])
        return result.combine(reader, checker)['codes']

    def test_an_integer_modifier_is_its_decimal_string(self):
        rows = self.combined([{**f.code('99214'), 'modifiers': [25]}, {**f.code('88305'), 'modifiers': ['26', 59]}])
        self.assertEqual([row['modifiers'] for row in rows], [['25'], ['26', '59']])
        self.assertEqual([row['status'] for row in rows], ['ready', 'ready'])

    def test_a_modifier_of_any_other_type_makes_the_answer_unreadable(self):
        for bad in ([25.0], [True], [None], [{'modifier': '25'}], '53', 25, {'0': '25'}):
            with self.subTest(modifiers=bad), self.assertRaises(result.Unreadable):
                result.read_reader(f.reader_message(f.reader_result([{**f.code('99214'), 'modifiers': bad}])))
        for bad in ([25.5], 'XS'):
            with self.subTest(missed=bad), self.assertRaises(result.Unreadable):
                result.read_checker(f.checker_message(f.checker_result(
                    [], missed=[{**r.missed('45380'), 'modifiers': bad}])))

    def test_absent_or_null_modifiers_are_not_given(self):
        absent = {key: value for key, value in f.code('99214').items() if key != 'modifiers'}
        rows = self.combined([absent, {**f.code('45385'), 'modifiers': None}, f.code('45378')])
        self.assertEqual([row['modifiers'] for row in rows], [None, None, []])

    def test_the_checker_is_given_the_modifiers_as_the_line_shows_them(self):
        reader = f.reader_result([{**f.code('99214'), 'modifiers': [25]}])
        self.assertEqual(result.listing(reader)['lines'][0]['modifiers'], ['25'])


class ReviewIdentityTests(SimpleTestCase):
    """INT-8: a review whose code is not a non-empty string cannot be shown, so the answer is unreadable."""

    def test_a_review_that_names_no_code_makes_the_checker_answer_unreadable(self):
        for bad in ({'line': 'L1', 'code': 45385, 'verdict': 'disagree'}, {'line': 'L1', 'code': '  '},
                    {'line': 'L1', 'verdict': 'agree'}, 'agree'):
            with self.subTest(review=bad), self.assertRaises(result.Unreadable):
                result.read_checker(f.message([f.text_block(f.fenced(f.checker_result([bad])))]))


class PipelineShapeTests(r.CustomerCase, TestCase):
    """The same rules through the real coding stage, the customer API and the exports."""

    def test_a_broken_final_reader_block_fails_the_round_and_no_checker_is_sent(self):
        enc = self.started()
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.message([f.text_block(drafted(BROKEN_FINAL))])),
                                    checker=f.succeeded(r.checker_message(f.checker_result([])))))
        self.run_next()
        round_ = state.latest_round(enc)
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unreadable'))
        self.assertEqual(fake.roles(), ['reader'])

    def test_a_review_with_a_numeric_code_fails_the_round(self):
        enc = self.started()
        checker = f.checker_result([{'line': 'L1', 'code': 45385, 'verdict': 'disagree',
                                     'reason': 'Only a cold forceps biopsy is documented, not a snare.'}])
        self.code_round(enc, reader=f.reader_result([f.code('45385')]), checker=checker)
        round_ = state.latest_round(enc)
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unreadable'))

    def test_modifier_25_written_as_a_number_reaches_the_page_and_the_approved_export(self):
        enc = self.started()
        reader = f.reader_result([{**f.code('99214', reason='Significant, separately identifiable E/M.'),
                                   'modifiers': [25]}])
        self.code_round(enc, reader=reader, checker=f.checker_result([r.review('L1', '99214')]))
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        self.assertEqual(payload['codes'][0]['modifiers'], ['25'])
        self.assertEqual(self.decide(enc, 'L1', '99214', 'approve').status_code, 201)
        text = self.export_text(enc, 'approved')
        self.assertIn('1. 99214 — units 1 — modifiers: 25', text)
        self.assertNotIn('modifiers: none', text)

    def test_modifiers_not_given_read_not_given_on_the_page_and_in_both_exports(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('99214', 'ready', modifiers=None), r.row('45385', 'ready', units=None)])
        codes = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        self.assertEqual([(code['modifiers'], code['units']) for code in codes], [(None, 1), ([], None)])
        text = self.export_text(enc, 'draft')
        self.assertIn('1. 99214 — Ready for approval — units 1 — modifiers: not given', text)
        self.assertIn('2. 45385 — Ready for approval — units not given — modifiers: none', text)
        rows = list(csv.reader(io.StringIO(self.export_text(enc, 'draft', 'csv'), newline='')))
        body = {line[1]: dict(zip(rows[0], line)) for line in rows[2:-1]}
        self.assertEqual((body['99214']['modifiers'], body['99214']['units']), ('not given', '1'))
        self.assertEqual((body['45385']['modifiers'], body['45385']['units']), ('', 'not given'))
