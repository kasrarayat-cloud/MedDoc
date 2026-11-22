"""Display hygiene of the text this pass newly shows (the SEC-S4 residue; BUILD-SPEC 7.4): a review's reason shown as a
note on the encounter, a documentation problem kept as its JSON text, a reason written as a list and a list of questions
all pass the vendor-name filter (customer.shown) on the page and in the draft report, like every other text the coding
review wrote. On the page a modifier is never rewritten: it is part of the code line Fable returned (FIX-SPEC-2 section
7), so a name written there is shown as written and left to the scanners. The PDF report, the only report since
2026-11-21, prints a line's modifiers through the same filter as one list (physician_report._modifier_words), so a name
written there reads "the system" in the report. Synthetic data only; nothing reaches the network."""
from django.test import TestCase

from tests.support import coding as f
from tests.support import rounds as r
from tests.test_line_identity import code_row


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
        draft = self.report_text(enc, 'draft')
        # each of these texts is printed in the report, filtered - so the names' absence below is no empty pass
        for shown in ('Reason: The system read it: a polyp was removed.',
                      'Question: Per the system policy, which site?', '– {"problem": "the system found no signature."}',
                      '– The second check made a comment that could not be tied to one line: As the system read it, '
                      'no.'):
            with self.subTest(shown=shown):
                self.assertIn(shown, draft)
        for name in ('Claude', 'claude', 'OpenAI', 'Anthropic', 'fable'):
            with self.subTest(name=name):
                self.assertNotIn(name, draft)
                self.assertNotIn(name, str(payload))

    def test_a_modifier_is_shown_as_written_on_the_page_and_as_one_filtered_list_in_the_report(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45378', modifiers=['PT', 'Anthropic'])]),
                        checker=f.checker_result([r.review('L1', '45378')]))
        (code,) = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        self.assertEqual(code['modifiers'], ['PT', 'Anthropic'])
        # the report prints both of the line's modifiers, in order, on its own row - the name through the filter
        draft = self.report_text(enc, 'draft')
        self.assertIn('Line L1 · Modifiers: PT, the system UNITS 1', code_row(draft, 1, '45378'))
        self.assertNotIn('Anthropic', draft)
