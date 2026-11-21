"""The final answer (FIX-SPEC-2 section 1; findings PARSE-1, PARSE-5, PARSE-9 and the INT-5 residue): the LAST fenced
block of the text whatever its fence - three or more backticks or tildes, with any info string or none, in any case - or,
when it does not parse as strict JSON, the widest {...} span of the whole text, never an earlier fence. Text after the
last fenced block that could hold the final answer, a repeated key, NaN, Infinity, -Infinity, the NUL character and lone
surrogates make the answer unreadable: the round fails as unreadable and nothing of a draft is ever shown. Synthetic
answers only; nothing reaches the network."""
import json

from django.test import SimpleTestCase, TransactionTestCase

from studio import models, state
from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r

Round = models.CodingRound
DRAFT = {'codes': [{'code': '99213', 'units': 1, 'modifiers': [], 'status': 'ready', 'reason': 'Draft: low MDM.',
                    'evidence': [], 'question': None}], 'questions': [], 'documentation_problems': []}
FINAL = {'codes': [{'code': '99214', 'units': 1, 'modifiers': [], 'status': 'ready', 'reason': 'Moderate MDM.',
                    'evidence': [], 'question': None}], 'questions': [], 'documentation_problems': []}
# PARSE-1's spellings of the final block's fence, and two more: a bare tilde fence and a longer backtick fence
FENCES = ('```JSON', '``` json', '```Json', '```', '~~~json', '~~~', '````json')


def closing(opener):
    char = opener[0]
    return char * (len(opener) - len(opener.lstrip(char)))


def drafted(opener, final=FINAL):
    """PARSE-1's reader text: a ```json draft, then the final answer under ``opener``."""
    return (f'My first pass, before re-reading page 2:\n```json\n{json.dumps(DRAFT)}\n```\n'
            f'On re-reading page 2 the MDM is moderate.\nLINE L1 99214\nModerate MDM.\n'
            f'{opener}\n{json.dumps(final)}\n{closing(opener)}\n')


def codes_of(parsed):
    return [item['code'] for item in parsed['codes']]


class LastFencedBlockTests(SimpleTestCase):
    def test_the_last_fenced_block_is_read_whatever_its_fence(self):
        for opener in FENCES:
            with self.subTest(fence=opener):
                text = drafted(opener)
                self.assertEqual(result.last_json(text), FINAL)
                parsed = result.read_reader(f.message([f.text_block(text)]))
                self.assertEqual(codes_of(parsed), ['99214'])
                self.assertEqual([line['code'] for line in result.listing(parsed)['lines']], ['99214'])  # the checker's

    def test_the_checkers_final_disagreement_is_read_under_any_fence(self):
        draft = {'reviews': [{'line': 'L1', 'code': '99214', 'verdict': 'agree', 'reason': 'Draft: agreed.'}],
                 'missed_codes': []}
        final = {'reviews': [{'line': 'L1', 'code': '99214', 'verdict': 'disagree', 'correct_code': '99213',
                              'reason': 'Final: only low MDM is documented.'}], 'missed_codes': []}
        reader = f.reader_result([f.code('99214')])
        for opener in FENCES:
            with self.subTest(fence=opener):
                text = (f'Draft:\n```json\n{json.dumps(draft)}\n```\nREVIEW L1 99214\nOnly low MDM.\n'
                        f'{opener}\n{json.dumps(final)}\n{closing(opener)}\n')
                (row,) = result.combine(reader, result.read_checker(f.message([f.text_block(text)])))['codes']
                self.assertEqual((row['status'], row['second_check']['agrees'], row['second_check']['reason']),
                                 ('needs_review', False, 'Final: only low MDM is documented.'))

    def test_a_final_answer_after_the_last_fenced_block_makes_the_answer_unreadable(self):
        # PARSE-1's extra variant: the draft is the last fenced block and the final answer follows it unfenced, so the
        # code cannot tell which of the two is final
        for final in (json.dumps(FINAL), '{"codes": [{"code": "99214", "reason": "the patient said "worse""}]}'):
            with self.subTest(final=final[:40]):
                text = (f'My first pass:\n```json\n{json.dumps(DRAFT)}\n```\n'
                        f'On re-reading page 2 the MDM is moderate.\n{final}\n')
                self.assertIsNone(result.last_json(text))
                with self.assertRaises(result.Unreadable):
                    result.read_reader(f.message([f.text_block(text)]))

    def test_a_final_block_that_holds_no_closing_brace_never_falls_back_to_an_earlier_draft(self):
        # the INT-5 residue: the widest span of the whole text was exactly the earlier draft object
        finals = ('```json\n{"codes": [{"code": "99214", "status": "ready"\n```\n',  # cut before any "}"
                  '```json\nThe draft above, with 99214 in place of 99213.\n```\n',  # prose in the final fence
                  '```json\n```\n',  # an empty final fence
                  '```json\n{"codes": [\n')  # a final fence never closed
        for final in finals:
            for fenced_draft in (True, False):
                with self.subTest(final=final[:30], fenced_draft=fenced_draft):
                    draft = f'```json\n{json.dumps(DRAFT)}\n```' if fenced_draft else json.dumps(DRAFT)
                    text = f'My first pass:\n{draft}\nOn re-reading page 2 the MDM is moderate.\n{final}'
                    self.assertIsNone(result.last_json(text))
                    with self.assertRaises(result.Unreadable):
                        result.read_reader(f.message([f.text_block(text)]))

    def test_the_widest_span_still_reads_an_answer_that_has_no_fence_or_sits_inside_the_last_one(self):
        self.assertEqual(result.last_json(f'The result: {json.dumps(FINAL)} done.'), FINAL)
        self.assertEqual(result.last_json(f'Analysis.\n```json\nFinal:\n{json.dumps(FINAL)}\n```\n'), FINAL)
        self.assertEqual(result.last_json(f'Analysis.\n```json\n{json.dumps(FINAL)}\n'), FINAL)  # never closed


class StrictJsonTests(SimpleTestCase):
    READER = ('{"document_kind": "synthetic", "services_found": [], "codes": [{"code": "45385", "units": 1, '
              '"modifiers": [], "status": "ready", "reason": "Snare.", "evidence": [], "question": null}], '
              '"documentation_problems": [], "questions": [], "codes": [{"code": "45380", "units": 1, "modifiers": [], '
              '"status": "ready", "reason": "Biopsy.", "evidence": [], "question": null}]}')
    CHECKER = ('{"reviews": [{"line": "L1", "code": "45385", "verdict": "disagree", "correct_code": "45380", '
               '"reason": "Only a biopsy is documented, not a snare.", "verdict": "agree"}], "missed_codes": [], '
               '"questions": []}')

    def test_a_repeated_key_makes_the_text_unparseable(self):
        # PARSE-5: json.loads kept the last value - a code Fable returned dropped (C1), a disagreement read as agreement
        for text in (self.READER, f'```json\n{self.READER}\n```'):
            with self.subTest(text=text[:20]):
                self.assertIsNone(result.last_json(text))
                with self.assertRaises(result.Unreadable):
                    result.read_reader(f.message([f.text_block(text)]))
        for text in (self.CHECKER, f'```json\n{self.CHECKER}\n```'):
            with self.subTest(text=text[:20]):
                with self.assertRaises(result.Unreadable):
                    result.read_checker(f.message([f.text_block(text)]))
        self.assertIsNone(result.last_json('{"question": null, "question": null}'))  # a repeat is a repeat
        self.assertEqual(result.last_json('{"a": {"b": 1}, "c": {"b": 2}}'), {'a': {'b': 1}, 'c': {'b': 2}})

    def test_non_finite_numbers_nul_and_lone_surrogates_make_the_text_unparseable(self):
        # PARSE-9: values JSON does not have, or the database cannot store (1e400 is read as infinity)
        good = json.dumps(FINAL)
        bad = {'NaN': good.replace('"units": 1', '"units": NaN'),
               'Infinity': good.replace('"units": 1', '"units": Infinity'),
               '-Infinity': good.replace('"units": 1', '"units": -Infinity'),
               '1e400': good.replace('"units": 1', '"units": 1e400'),
               'NUL': good.replace('"Moderate MDM."', '"a\\u0000b"'),
               'high surrogate': good.replace('"Moderate MDM."', '"a\\ud800b"'),
               'low surrogate': good.replace('"Moderate MDM."', '"a\\udc00b"'),
               'NUL in a key': good.replace('"questions"', '"ques\\u0000tions"'),
               'NUL in a field nothing shows': good[:-1] + ', "notes": "x\\u0000y"}'}
        for name, text in bad.items():
            with self.subTest(name=name):
                self.assertNotEqual(text, good)
                self.assertIsNone(result.last_json(f'```json\n{text}\n```'))
                self.assertIsNone(result.last_json(text))
                with self.assertRaises(result.Unreadable):
                    result.read_reader(f.message([f.text_block(f'```json\n{text}\n```')]))
        # a pair of surrogates is one character, and a finite number of any size is a number
        self.assertEqual(result.last_json('{"a": "\\ud83d\\ude00", "b": 1.5e300, "c": -0.0}'),
                         {'a': '\U0001F600', 'b': 1.5e300, 'c': -0.0})


class UnstorablePipelineTests(r.CustomerCase, TransactionTestCase):
    """PARSE-9 through the worker's own path (autocommit, as the worker runs): the round fails as unreadable after the
    reader's answer, never as an unexpected failure, and the checker is not sent."""

    def test_a_value_the_database_cannot_store_fails_the_round_as_unreadable(self):
        good = json.dumps(FINAL)
        for name, text in (('NaN', good.replace('"units": 1', '"units": NaN')),
                           ('NUL', good.replace('"Moderate MDM."', '"a\\u0000b"')),
                           ('lone surrogate', good.replace('"Moderate MDM."', '"a\\ud800b"'))):
            with self.subTest(name=name):
                enc = self.started(title=f'Synthetic {name} note')
                answer = f.message([f.text_block(f'LINE L1 99214\nModerate MDM.\n```json\n{text}\n```\n')])
                fake = self.use(f.FakeCoder(reader=f.succeeded(answer),
                                            checker=f.succeeded(r.checker_message(f.checker_result([])))))
                self.run_next()
                round_ = state.latest_round(enc)
                self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unreadable'))
                self.assertEqual(round_.error, 'The coding result could not be read. Try again.')
                self.assertIsNone(round_.reader_result)
                self.assertEqual(fake.roles(), ['reader'])
