"""Where a citation section ends (FIX-SPEC-2 section 4; findings PARSE-2, PARSE-6, PARSE-7 and the INT-3b residue). The
reader and the checker are asked to end their last section with a line holding exactly END; a section ends at the next
marker line, an END line, or the start of the final answer - its fence, or the start of the widest {...} span when the
answer has no fence. A citation outside every section, and a cited text block whose own text holds a marker or END, go
under "_document": never under a line whose section they are not in. Synthetic answers only; nothing reaches the
network."""
import json

from django.test import SimpleTestCase, TestCase

from studio.fable import prompts, result
from tests.support import coding as f
from tests.support import rounds as r

READER = f.reader_result([f.code('45385'), f.code('45380')])
CHECKER = f.checker_result([r.review('L1', '45385'), r.review('L2', '45380')])


def texts(found, key):
    return [item['text'] for item in found.get(key, [])]


def reader(*blocks, result_=READER):
    return f.message([*blocks, f.text_block(f.fenced(result_))])


class EndLineTests(SimpleTestCase):
    def test_both_answers_are_asked_to_end_their_last_section_with_an_end_line(self):
        for system in (prompts.READER_SYSTEM, prompts.CHECKER_SYSTEM):
            with self.subTest(system=system[:30]):
                self.assertIn('End your last section with a line that holds exactly `END`', system)
        self.assertEqual(prompts.END_MARK, 'END')

    def test_a_plain_closing_paragraph_after_the_end_line_files_under_the_document(self):
        # PARSE-2 / INT-3b input 2, with the END line the instructions now ask for: the signature line was filed under
        # 45380 and reached the approved export
        for closing in ('\n\nDocumentation problems\n', '\n\nOverall, ', '\n\nDOCUMENTATION PROBLEMS:\n',
                        '\n\n*Documentation problems*\n', '\n\n**Documentation problems:** '):
            with self.subTest(closing=closing):
                found = result.citations(reader(
                    f.text_block('LINE L1 45385\n'),
                    f.text_block('The polyp was removed by hot snare.', [f.page_cite('hot snare polypectomy', 1)]),
                    f.text_block('\n\nLINE L2 45380\n'),
                    f.text_block('A biopsy was taken.', [f.page_cite('biopsy taken', 1)]),
                    f.text_block('\nEND'), f.text_block(closing),
                    f.text_block('The note is not signed.', [f.page_cite('Signature: ________', 3)])), None)
                self.assertEqual((texts(found, 'L1'), texts(found, 'L2'), texts(found, '_document')),
                                 (['hot snare polypectomy'], ['biopsy taken'], ['Signature: ________']))

    def test_the_end_line_ends_a_checker_section_too(self):
        checker = f.message([f.text_block('REVIEW L1 45385\n'), f.text_block('Agreed.', [f.char_cite('cold snare', 9)]),
                             f.text_block('\nREVIEW L2 45380\n'), f.text_block('Agreed.', [f.char_cite('biopsy', 40)]),
                             f.text_block('\nEND\n\nOverall, '), f.text_block('fine.', [f.char_cite('Signature', 80)]),
                             f.text_block(f.fenced(CHECKER))])
        found = result.citations(reader(), checker)
        self.assertEqual((texts(found, 'L1'), texts(found, 'L2'), texts(found, '_document')),
                         (['cold snare'], ['biopsy'], ['Signature']))

    def test_a_line_starting_with_a_hash_or_a_rule_ends_the_section(self):
        for closing in ('\n#Documentation problems\n', '\n---\n', '\n* * *\n', '\n___\n'):
            with self.subTest(closing=closing):
                found = result.citations(reader(
                    f.text_block('LINE L2 45380\n'), f.text_block('A biopsy.', [f.page_cite('biopsy taken', 1)]),
                    f.text_block(closing), f.text_block('Unsigned.', [f.page_cite('Signature: ________', 3)])), None)
                self.assertEqual((texts(found, 'L2'), texts(found, '_document')),
                                 (['biopsy taken'], ['Signature: ________']))

    def test_without_an_end_line_a_plain_paragraph_after_the_last_section_stays_in_it(self):
        # the known limit, pinned with the finding's own input: without the END line the instructions ask for, an
        # unheaded paragraph after the last section cannot be told apart from that section's own prose without reading
        # it, which the coding path never does
        found = result.citations(reader(
            f.text_block('LINE L2 45380\n'), f.text_block('A biopsy was taken.', [f.page_cite('biopsy taken', 1)]),
            f.text_block('\n\nDocumentation problems\n'),
            f.text_block('The note is not signed.', [f.page_cite('Signature: ________', 3)])), None)
        self.assertEqual(texts(found, 'L2'), ['biopsy taken', 'Signature: ________'])


class CitedBlockTests(SimpleTestCase):
    def test_a_cited_block_holding_a_marker_or_an_end_line_files_under_the_document(self):
        # PARSE-6: the block's citation was filed under the LAST section change inside it
        for block in ('\nLINE L1 45385\nThe 6 mm polyp was removed by cold snare.\nLINE L2 45380\n',
                      'LINE L1 45385\nThe 6 mm polyp was removed by cold snare.\nLINE L2 45380\n',
                      '\n# Documentation problems\nThe note is not signed.\nLINE L2 45380\n',
                      '\nLINE L1 45385\nThe polyp was removed.',
                      'The polyp was removed.\nEND\n',
                      '\nLINE L2 45380\nA biopsy was taken.'):
            with self.subTest(block=block[:30]):
                found = result.citations(reader(
                    f.text_block('LINE L1 45385\n'), f.text_block(block, [f.page_cite('the cited passage', 1)]),
                    f.text_block('A biopsy was taken.', [f.page_cite('biopsy taken', 1)])), None)
                self.assertIn('the cited passage', texts(found, '_document'))
                self.assertNotIn('the cited passage', texts(found, 'L1') + texts(found, 'L2'))

    def test_a_checker_block_holding_two_review_markers_files_under_the_document(self):
        checker = f.message([f.text_block('REVIEW L1 45385\nThe snare is documented.\nREVIEW L2 45380\n',
                                          [f.char_cite('cold snare', 9)]),
                             f.text_block('A biopsy.', [f.char_cite('biopsy', 40)]), f.text_block(f.fenced(CHECKER))])
        found = result.citations(reader(), checker)
        self.assertEqual((texts(found, '_document'), texts(found, 'L2')), (['cold snare'], ['biopsy']))
        self.assertNotIn('L1', found)


class FinalAnswerStartTests(SimpleTestCase):
    def test_the_start_of_an_unfenced_final_answer_ends_the_last_section(self):
        # PARSE-7: a citation inside an unfenced final JSON was filed under the last line
        unfenced, quote = json.dumps(READER, indent=1), 'removed by cold snare'
        at = unfenced.index(quote)
        message = f.message([
            f.text_block('LINE L1 45385\n'), f.text_block('Removed.', [f.page_cite('hot snare polypectomy', 1)]),
            f.text_block('\nLINE L2 45380\n'), f.text_block('A biopsy.', [f.page_cite('biopsy taken', 1)]),
            f.text_block('\n\nFinal result:\n' + unfenced[:at]), f.text_block(quote, [f.page_cite(quote, 1)]),
            f.text_block(unfenced[at + len(quote):])])
        self.assertEqual(result.last_json(result.message_text(message)), READER)
        found = result.citations(message, None)
        self.assertEqual((texts(found, 'L1'), texts(found, 'L2'), texts(found, '_document')),
                         (['hot snare polypectomy'], ['biopsy taken'], [quote]))

    def test_the_start_of_a_final_answer_under_any_fence_ends_the_last_section(self):
        for opener, closer in (('~~~json', '~~~'), ('```JSON', '```'), ('```', '```')):
            with self.subTest(fence=opener):
                body = json.dumps(READER, indent=1)
                at = body.index('removed by cold snare')
                message = f.message([
                    f.text_block('LINE L2 45380\n'), f.text_block('A biopsy.', [f.page_cite('biopsy taken', 1)]),
                    f.text_block(f'\n\n{opener}\n{body[:at]}'),
                    f.text_block('removed by cold snare', [f.page_cite('removed by cold snare', 1)]),
                    f.text_block(f'{body[at + 21:]}\n{closer}\n')])
                found = result.citations(message, None)
                self.assertEqual((texts(found, 'L2'), texts(found, '_document')),
                                 (['biopsy taken'], ['removed by cold snare']))


class EndPipelineTests(r.CustomerCase, TestCase):
    def test_a_closing_paragraph_after_end_never_reaches_a_lines_quotes_or_the_approved_export(self):
        enc = self.started()
        reader_msg = r.reader_message(READER, sections=[
            f.text_block('LINE L1 45385\n'),
            f.text_block('The polyp was removed by hot snare.', [f.page_cite('hot snare polypectomy', 1)]),
            f.text_block('\n\nLINE L2 45380\n'), f.text_block('A biopsy was taken.\nEND\n\nOverall, '),
            f.text_block('the note is not signed.', [f.page_cite('Signature: ________', 3)])])
        self.code_round(enc, reader=READER, checker=CHECKER, reader_msg=reader_msg,
                        checker_msg=r.checker_message(CHECKER, sections=[]))
        codes = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        # L2 has no citation of its own, so it shows the evidence its JSON gave - never the signature line
        self.assertEqual([(code['line'], [quote['text'] for quote in code['quotes']]) for code in codes],
                         [('L1', ['hot snare polypectomy']), ('L2', ['removed by cold snare'])])
        self.assertEqual(self.decide(enc, 'L2', '45380', 'approve').status_code, 201)
        approved = self.report_text(enc, 'approved')
        self.assertIn('removed by cold snare', approved)  # the approved line's own quote is printed; the signature not
        self.assertNotIn('Signature', approved)
