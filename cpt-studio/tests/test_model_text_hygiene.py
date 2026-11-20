"""Display hygiene of the text this pass newly shows (the SEC-S4 residue; BUILD-SPEC 7.4): a review's reason shown as a
note on the encounter, a documentation problem kept as its JSON text, a reason written as a list and a list of questions
all pass the vendor-name filter (customer.shown) on the page and in the draft export, like every other text the coding
review wrote. A modifier is never rewritten: it is part of the code line Fable returned (FIX-SPEC-2 section 7), so a
name written there is shown as written and left to the scanners. Synthetic data only; nothing reaches the network."""
from django.test import TestCase

from tests.support import coding as f
from tests.support import rounds as r


class NewTextHygieneTests(r.CustomerCase, TestCase):
    def test_the_text_this_pass_newly_shows_passes_the_vendor_name_filter(self):
        enc = self.started()
        reader = f.reader_result(
            [{**f.code('45385'), 'reason': ['Claude Fable 5.2 read it:', 'a polyp was removed.']},
             {**f.code('45380', 'needs_answer'), 'question': ['Per OpenAI policy, which site?', 'Was it separate?']}],
            problems=[{'problem': 'Anthropic found no signature.'}])
        checker = f.checker_result([r.review('L1', '45385'), r.review('L2', '45380', status='needs_answer'),
                                    f.review('99999', 'disagree', reason='As claude-fable-5-2 read it, no.')])
        self.code_round(enc, reader=reader, checker=checker)
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        codes = {code['line']: code for code in payload['codes']}
        self.assertEqual(codes['L1']['reason'], 'The system read it: a polyp was removed.')
        self.assertEqual(codes['L2']['question'], 'Per the system policy, which site?\nWas it separate?')
        self.assertEqual([q['text'] for q in payload['questions']], ['Per the system policy, which site?',
                                                                      'Was it separate?'])
        self.assertEqual(payload['notes'], ['{"problem": "the system found no signature."}',
                                            'The second check made a comment that could not be tied to one line: As '
                                            'the system read it, no.'])
        draft = self.export_text(enc, 'draft')
        for name in ('Claude', 'claude', 'OpenAI', 'Anthropic', 'fable'):
            with self.subTest(name=name):
                self.assertNotIn(name, draft)
                self.assertNotIn(name, str(payload))

    def test_a_modifier_is_shown_exactly_as_the_coding_review_wrote_it(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45378', modifiers=['PT', 'Anthropic'])]),
                        checker=f.checker_result([r.review('L1', '45378')]))
        (code,) = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        self.assertEqual(code['modifiers'], ['PT', 'Anthropic'])
        self.assertIn('modifiers: PT, Anthropic', self.export_text(enc, 'draft'))
