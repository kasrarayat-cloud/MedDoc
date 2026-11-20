"""Citations per line (FIX-SPEC section 1; finding INT-3b): a citation is filed under a line only inside that line's
marker section and only when the marker names the code on that line; prose that merely mentions a code, a heading or a
code fence after the last section, a marker that is not a whole line, and a block a section change splits never file a
citation under the wrong line. Synthetic answers only; nothing reaches the network."""
from django.test import SimpleTestCase, TestCase

from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r

READER = f.reader_result([f.code('45385', 'ready'), f.code('45380', 'not_supported')])
CHECKER = f.checker_result([r.review('L1', '45385'), r.review('L2', '45380')], missed=[r.missed('45378')])


def texts(found, key):
    return [item['text'] for item in found.get(key, [])]


class SectionTests(SimpleTestCase):
    def reader(self, *blocks, result_=READER):
        return f.message([*blocks, f.text_block(f.fenced(result_))])

    def test_prose_that_mentions_a_code_does_not_start_its_section(self):
        found = result.citations(self.reader(
            f.text_block('LINE L1 45385\n'),
            f.text_block('The sigmoid polyp was removed with a hot snare.',
                         [f.page_cite('hot snare polypectomy of the 8 mm sigmoid polyp', 1)]),
            f.text_block('\nCode 45380 is not reported for the same lesion; the biopsy was of that polyp.',
                         [f.page_cite('cold biopsy of the same polyp before the snare', 1)]),
            f.text_block('\nThe removal was complete.', [f.page_cite('the polyp was completely removed', 2)]),
            f.text_block('\n\nLINE L2 45380\nNo separate biopsy.', [f.page_cite('no other lesions were biopsied', 2)])),
            None)
        self.assertEqual(texts(found, 'L1'), ['hot snare polypectomy of the 8 mm sigmoid polyp',
                                              'cold biopsy of the same polyp before the snare',
                                              'the polyp was completely removed'])
        self.assertEqual(texts(found, 'L2'), ['no other lesions were biopsied'])

    def test_a_heading_or_the_final_json_after_the_last_section_files_under_the_document(self):
        fenced, quote = f.fenced(READER), 'removed by cold snare'
        at = fenced.index(quote)  # a citation inside the final JSON: the JSON's own text, cited
        reader = f.message([
            f.text_block('LINE L1 45385\n'), f.text_block('Removed.', [f.page_cite('removed by cold snare', 1)]),
            f.text_block('\nLINE L2 45380\n'), f.text_block('A biopsy.', [f.page_cite('biopsy taken', 1)]),
            f.text_block('\n\n## Documentation problems\nThe note is not signed.', [f.page_cite('Signature: ____', 3)]),
            f.text_block(fenced[:at]), f.text_block(quote, [f.page_cite(quote, 1)]),
            f.text_block(fenced[at + len(quote):])])
        found = result.citations(reader, None)
        self.assertEqual(texts(found, 'L1'), ['removed by cold snare'])
        self.assertEqual(texts(found, 'L2'), ['biopsy taken'])
        self.assertEqual(texts(found, '_document'), ['Signature: ____', 'removed by cold snare'])

    def test_a_marker_that_is_not_a_whole_line_never_files_under_the_line_before_it(self):
        for marker in ('- LINE L2 45380', '1. LINE L2 45380', '**LINE L2 45380**', 'LINE L2 45380 (biopsy)',
                       'line L2 45380', 'LINE L2: 45380', 'Line 2 45380', 'REVIEW 45380', '  LINE L2 45380'):
            with self.subTest(marker=marker):
                found = result.citations(self.reader(
                    f.text_block('LINE L1 45385\n'), f.text_block('Removed.', [f.page_cite('removed by snare', 1)]),
                    f.text_block(f'\n{marker}\n'), f.text_block('A biopsy.', [f.page_cite('cold forceps biopsy', 2)])),
                    None)
                self.assertEqual(texts(found, 'L1'), ['removed by snare'])
                self.assertEqual(texts(found, '_document'), ['cold forceps biopsy'])
                self.assertNotIn('L2', found)

    def test_a_line_all_in_bold_after_the_last_section_files_under_the_document(self):
        found = result.citations(self.reader(
            f.text_block('LINE L1 45385\n'), f.text_block('Removed.', [f.page_cite('removed by snare', 1)]),
            f.text_block('\n**Note:** a bold lead-in is no heading.', [f.page_cite('a lead-in', 1)]),
            f.text_block('\n\n**Code choice**\n'), f.text_block('Why.', [f.page_cite('the note says', 2)])), None)
        self.assertEqual(texts(found, 'L1'), ['removed by snare', 'a lead-in'])
        self.assertEqual(texts(found, '_document'), ['the note says'])

    def test_prose_with_the_marker_words_ends_no_section_but_a_line_led_by_one_does(self):
        found = result.citations(self.reader(
            f.text_block('LINE L1 45385\n'),
            f.text_block('The first coder missed 2 polyps; review 3 of the images agrees.',
                         [f.page_cite('two polyps', 1)]),
            f.text_block('\nReview of 45380:\n'), f.text_block('Biopsy.', [f.page_cite('biopsy', 2)])), None)
        self.assertEqual(texts(found, 'L1'), ['two polyps'])
        self.assertEqual(texts(found, '_document'), ['biopsy'])

    def test_a_marker_naming_another_code_than_its_line_files_under_the_document(self):
        found = result.citations(self.reader(
            f.text_block('LINE L2 45385\n'), f.text_block('Removed.', [f.page_cite('removed by snare', 1)]),
            f.text_block('\nLINE L3 45378\n'), f.text_block('More.', [f.page_cite('to the cecum', 1)])), None)
        self.assertEqual(found, {'_document': [{'text': 'removed by snare', 'page': 1, 'source': 'reader'},
                                               {'text': 'to the cecum', 'page': 1, 'source': 'reader'}]})

    def test_the_checker_files_reviews_under_reader_lines_and_missed_codes_under_m_lines(self):
        checker = f.message([
            f.text_block('### REVIEW L1 45385\n'), f.text_block('Agreed.', [f.char_cite('cold snare', 10)]),
            f.text_block('\nMISSED M1 45378\n'), f.text_block('A colonoscopy.', [f.char_cite('to the cecum', 40)]),
            f.text_block('\nLINE L2 45380\n'), f.text_block('Not a checker marker.', [f.char_cite('biopsy', 60)]),
            f.text_block(f.fenced(CHECKER))])
        found = result.citations(self.reader(), checker)
        self.assertEqual(found['L1'], [{'text': 'cold snare', 'page': None, 'source': 'checker'}])
        self.assertEqual(found['M1'], [{'text': 'to the cecum', 'page': None, 'source': 'checker'}])
        self.assertEqual(found['_document'], [{'text': 'biopsy', 'page': None, 'source': 'checker'}])

    def test_a_cited_block_split_by_a_section_change_files_under_the_document(self):
        found = result.citations(self.reader(
            f.text_block('LINE L1 45385\n'),
            f.text_block('The polyp was removed.\nLINE L2 45380\n', [f.page_cite('polyp was removed', 1)]),
            f.text_block('\nLINE L2 45380\nA biopsy was taken.', [f.page_cite('biopsy taken', 2)])), None)
        self.assertEqual(texts(found, '_document'), ['polyp was removed'])
        self.assertEqual(texts(found, 'L2'), ['biopsy taken'])

    def test_a_heading_marker_and_hcpcs_codes_are_read(self):
        reader_result = f.reader_result([f.code('G2211'), f.code('0001U'), f.code('45385')])
        found = result.citations(f.message([
            f.text_block('# LINE L1 G2211\n'), f.text_block('Visit.', [f.page_cite('ongoing care', 1)]),
            f.text_block('\nLINE L2 0001U\n'), f.text_block('Lab.', [f.page_cite('red cell antigen', 1)]),
            f.text_block('\n##  LINE L3 45385\n'), f.text_block('Two spaces.', [f.page_cite('snare', 2)]),
            f.text_block(f.fenced(reader_result))]), None)
        self.assertEqual((texts(found, 'L1'), texts(found, 'L2'), texts(found, '_document')),
                         (['ongoing care'], ['red cell antigen'], ['snare']))


class QuotePipelineTests(r.CustomerCase, TestCase):
    def test_each_line_shows_the_quotes_of_its_own_section(self):
        enc = self.started()
        reader_msg = r.reader_message(READER, sections=[
            f.text_block('LINE L1 45385\n'),
            f.text_block('The polyp was removed with a hot snare.', [f.page_cite('hot snare polypectomy', 1)]),
            f.text_block('\nCode 45380 is not reported.', [f.page_cite('the polyp was completely removed', 2)]),
            f.text_block('\nLINE L2 45380\n'),
            f.text_block('No separate biopsy.', [f.page_cite('no other lesions were biopsied', 2)]),
            f.text_block('\n# Documentation problems\n', None),
            f.text_block('Unsigned.', [f.page_cite('Signature: ________', 3)])])
        self.code_round(enc, reader=READER, checker=CHECKER, reader_msg=reader_msg,
                        checker_msg=r.checker_message(CHECKER, sections=[]))
        codes = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        self.assertEqual([(code.get('line'), [(quote['text'], quote['page']) for quote in code['quotes']])
                          for code in codes],
                         [('L1', [('hot snare polypectomy', 1), ('the polyp was completely removed', 2)]),
                          ('L2', [('no other lesions were biopsied', 2)]),
                          ('M1', [])])
