"""The physician PDF report against the inputs refutation round 2 broke the round-1 repairs with (session 738699b2,
2026-11-21), synthetic data only.

A character no report font draws prints as U+FFFD and never as another character: a compatibility form spelled a vendor
name the display filter had already read, read circled 11 and 12 as 1112, and grew a short title past its room. A
character the report's fonts draw as nothing (U+FFFC) is deleted before the filter reads the text, and .notdef is never
drawn. The right-to-left note is given only for right-to-left letters actually printed. Modifiers go through the filter.
An agent's approval beside a human's rejection is marked as one of the decisions. A line awaiting an answer is an open
item of its own only when the round has no question to answer. A title that cleans to nothing prints as an untitled
document. A long quotation's locator never ends a page with one line under it, and a long first note does not move the
notes to a new page. Characters are built with chr() so no invisible or look-alike character sits in this file."""
import json

from django.test import SimpleTestCase, TestCase, override_settings

from studio import physician_pdf, state
from tests.support import rounds as r
from tests.test_physician_report import flat, text_of

FFFD = chr(0xFFFD)


def fullwidth(text):
    return ''.join(chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in text)


def math_bold(text):
    return ''.join(chr(0x1D400 + ord(c) - 65) if 'A' <= c <= 'Z' else chr(0x1D41A + ord(c) - 97) if 'a' <= c <= 'z'
                   else c for c in text)


def squared(text):
    return ''.join(chr(0x1F130 + ord(c) - 65) if 'A' <= c <= 'Z' else c for c in text)


VENDORS = ('claude', 'gemini', 'gpt', 'opus', 'fable', 'anthropic', 'openai')


@override_settings(EXPORT_LIMIT_PER_MEMBER=(10_000, 600), EXPORT_LIMIT_PER_WORKSPACE=(10_000, 3600))  # C5: layout cases, not limits
class RoundTwoCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for(self.reviewer)
        self.sc = r.scan_customer()

    def make(self, enc, kind):
        number = state.latest_round(enc).number
        return self.client.post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': number}), content_type='application/json')

    def pdf(self, enc, kind='draft') -> bytes:
        made = self.make(enc, kind)
        self.assertIn(made.status_code, (200, 201), made.content)  # release 1, C5: a current report is the stored copy
        return self.client.get(made.json()['download_url']).content

    def scan(self, enc, data):
        payload = self.client.get(f'/api/encounters/{enc.pk}').json()
        return self.sc.scan_pdf(self.sc.read_pdf(data), self.sc.scan_context(self.sc.quotations(payload)), 'draft.pdf')

    # --- R2-1-1, R2-2-1, R2-5-4: no compatibility form after the filter ----------------------------------------------------

    def test_letters_no_font_draws_never_spell_a_vendor_name(self):
        enc = self.encounter()
        r.write_round(enc, codes=[
            r.row('45385', 'ready', reason=f'{math_bold("Claude")} read the snare; {fullwidth("gpt-4o")} agreed.',
                  check_reason=f'{fullwidth("Gemini")} agrees.', question=f'Did {math_bold("Opus")} see the site?',
                  evidence=[{'quote': f'the {math_bold("Fable")} reading says snare', 'page': 2}]),
            r.row('45380', 'needs_review', reason=f'{squared("ANTHROPIC")} found a second lesion.')],
            problems=[f'{fullwidth("OpenAI")} could not tell the site.'])
        data = self.pdf(enc)
        text = flat(text_of(data))
        for name in VENDORS:
            self.assertNotIn(name, text.lower())
        self.assertIn(f'Reason: {FFFD * 6} read the snare; {FFFD * 6} agreed.', text)
        self.assertIn(f'“the {FFFD * 5} reading says snare”', text)
        self.assertIn(f'Reason: {FFFD * 9} found a second lesion.', text)
        self.assertIn(f'Some cannot be drawn in this PDF and are shown as {FFFD}', text)
        self.assertEqual(self.scan(enc, data), [])

    # --- R2-2-2: a compatibility form changed a number in an exact quotation -----------------------------------------------

    def test_circled_numbers_never_join_into_another_number(self):
        enc = self.encounter()
        jars = chr(0x246A) + chr(0x246B)  # circled 11 and 12: in neither report font
        polyps = chr(0x2472) + chr(0x2473)  # circled 19 and 20
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': f'Specimen jars {jars} were sent to pathology', 'page': 2, 'source': 'reader'},
            {'text': f'Polyps {polyps} and {chr(0x3251)} were removed', 'page': 3, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc)))
        self.assertIn(f'“Specimen jars {FFFD * 2} were sent to pathology”', text)
        self.assertIn(f'“Polyps {FFFD * 2} and {FFFD} were removed”', text)
        self.assertNotIn('1112', text)
        self.assertNotIn('1920', text)
        page = self.client.get(f'/api/encounters/{enc.pk}').json()
        self.assertIn(jars, page['codes'][0]['quotes'][0]['text'])  # the document page keeps every character

    # --- R2-3-1: a compatibility form grew a capped title past its room ----------------------------------------------------

    def test_a_ligature_title_prints_and_never_fails_the_pdf(self):
        enc = self.encounter(title=chr(0xFDFA) * 28)  # one ligature is eighteen letters in its compatibility form
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn(FFFD * 28, text)

    # --- R2-2-10: a character a font maps to .notdef ---------------------------------------------------------------------

    def test_a_character_mapped_to_notdef_prints_as_the_replacement_character(self):
        enc = self.encounter(title=f'Synthetic note {chr(0xFFFF)} visit')
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': f'Biopsy {chr(0xFFFF)} taken from the sigmoid', 'page': 2, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc)))
        self.assertIn(f'“Biopsy {FFFD} taken from the sigmoid”', text)
        self.assertIn(f'Synthetic note {FFFD} visit', text)
        self.assertNotIn(chr(0xFFFF), text)
        self.assertIn('Some cannot be drawn in this PDF', text)

    # --- R2-2-4, R2-5-1: what the fonts draw as nothing ------------------------------------------------------------------

    def test_a_character_the_fonts_draw_as_nothing_never_carries_a_vendor_name(self):
        hidden = (chr(0xFFFC), chr(0xFFF9), chr(0xFFFA), chr(0xFFFB))
        self.assertTrue(all(ord(ch) in physician_pdf._DRAWN_INVISIBLE for ch in hidden))  # measured from the fonts
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason=f'Cl{hidden[0]}aude read the snare.',
                                        check_reason=f'Gem{hidden[1]}ini agrees.',
                                        question=f'Did Op{hidden[2]}enAI see it?')],
                      problems=[f'Anth{hidden[3]}ropic could not tell the site.'])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('Reason: The system read the snare. Second check: agrees. The system agrees.', text)
        for name in VENDORS:
            self.assertNotIn(name, text.lower())
        for ch in hidden:
            self.assertNotIn(ch, text)

    # --- R2-2-6: the right-to-left note for letters printed as U+FFFD ------------------------------------------------------

    def test_right_to_left_letters_no_font_draws_raise_no_right_to_left_note(self):
        syriac = ''.join(chr(c) for c in (0x0712, 0x0713, 0x0714))
        thaana = ''.join(chr(c) for c in (0x0780, 0x0781))
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': f'Family history noted in Syriac {syriac} and Thaana {thaana}', 'page': 1, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc)))
        self.assertIn(f'Syriac {FFFD * 3} and Thaana {FFFD * 2}', text)
        self.assertNotIn('Right-to-left text', text)
        self.assertIn('Some cannot be drawn in this PDF', text)

    # --- R2-2-7: modifiers are the coding review's own text ----------------------------------------------------------------

    def test_modifiers_go_through_the_name_filter(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', modifiers=['59', 'Claude', fullwidth('Gemini'),
                                                                     f'Cl{chr(0x200B)}aude'])])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn(f'Modifiers: 59, the system, {FFFD * 6}, the system', text)  # filtered as one list (round 3)
        for name in VENDORS:
            self.assertNotIn(name, text.lower())

    # --- R2-1-5: an agent's approval beside a human's rejection ------------------------------------------------------------

    def test_an_agent_approval_beside_a_human_rejection_is_marked_as_one_of_the_decisions(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'needs_review')])
        self.decide(enc, 'L1', '45385', 'approve', user=self.agent, kind='agent')
        self.decide(enc, 'L2', '45380', 'reject')
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('Agent-executed synthetic review — not clinical approval — 1 of 1 approvals, marked on each code',
                      text)

    def test_every_decision_by_the_agent_carries_the_agent_line_unqualified(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'needs_review')])
        self.decide(enc, 'L1', '45385', 'approve', user=self.agent, kind='agent')
        self.decide(enc, 'L2', '45380', 'reject', user=self.agent, kind='agent')
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('REVIEW TYPE', text)  # record labels print in capitals
        self.assertIn('1 approved · 1 rejected Agent-executed synthetic review — not clinical approval', text)
        self.assertNotIn('approvals, marked on each code', text)

    # --- R2-1-4: open items in a round whose questions name codes but no lines ----------------------------------------------

    def test_a_line_awaiting_an_answer_is_covered_by_the_rounds_questions(self):
        cases = (
            ([{'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45378'], 'source': 'reader'}],
             'Was the cecum reached', '01 01 Pending'),
            ([{'id': 'q1', 'text': 'Per the policy, was the cecum reached?', 'codes': ['45378'], 'source': 'reader'}],
             'Asks: was the cecum reached?', '01 01 Pending'),
            ([{'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45378'], 'source': 'reader'},
              {'id': 'q2', 'text': 'Was the prep adequate?', 'codes': ['45378'], 'source': 'reader'}],
             'Was the cecum reached?\nWas the prep adequate?', '01 02 Pending'))
        for questions, own, metrics in cases:
            with self.subTest(own=own):
                enc = self.encounter()
                r.write_round(enc, codes=[r.row('45378', 'needs_answer', question=own)], questions=questions)
                text = flat(text_of(self.pdf(enc)))
                self.assertIn(metrics, text)
                self.assertNotIn('(L1) needs your answer', text)

    def test_a_line_awaiting_an_answer_in_a_round_with_no_question_is_open(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45378', 'needs_answer', question='Was the cecum reached?')])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('01 01 Pending', text)
        self.assertIn('45378 (L1) needs your answer: Was the cecum reached?', text)

    # --- R2-3-5: a title that cleans to nothing ----------------------------------------------------------------------------

    def test_a_title_that_cleans_to_nothing_is_untitled_with_no_dangling_separator(self):
        enc = self.encounter(title=chr(0x200B))
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        pages = text_of(self.pdf(enc))
        ref = enc.pk.hex[:8].upper()
        self.assertIn(f'Untitled document · {ref} · Coding review 1', flat(pages))
        for page in pages:
            for line in page.splitlines():
                self.assertFalse(line.strip().startswith('·'), line)

    # --- R2-3-2: a long quotation's locator and one line at a page foot ----------------------------------------------------

    def test_a_long_quotations_locator_never_ends_a_page_with_one_line_under_it(self):
        # refutation round 2's family (lens 3): a short first box, a second box, then a 200-token quotation that flows
        passage = ' '.join(f'q{k:03d}' for k in range(1, 201))
        checked = 0
        for first in range(10, 119, 12):
            for second in (101, 112, 124, 136):
                enc = self.encounter()
                r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'ready')], citations={
                    'L1': [{'text': 'first passage ' + ' '.join(['word'] * first), 'page': 3, 'source': 'reader'}],
                    'L2': [{'text': 'second passage ' + ' '.join(['term'] * second), 'page': 4, 'source': 'reader'},
                           {'text': passage, 'page': 7, 'source': 'reader'}]})
                for page in text_of(self.pdf(enc)):
                    lines = [line.strip() for line in page.splitlines() if line.strip()]
                    if 'Page 7' not in lines:
                        continue
                    after = lines[lines.index('Page 7') + 1:]
                    checked += 1
                    self.assertGreaterEqual(len(after), 2, (first, second, after))
        self.assertGreater(checked, 0)

    # --- R2-3-6: a long first note moved the whole notes section ----------------------------------------------------------

    def test_a_long_first_note_starts_under_the_evidence(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='A polyp was removed by cold snare.')],
                      problems=['Documentation problem: ' + ' '.join(['detail'] * 450), 'Second note.'],
                      citations={'L1': [{'text': 'first passage ' + ' '.join(['word'] * 20), 'page': 2,
                                         'source': 'reader'}]})
        for page in text_of(self.pdf(enc)):
            if 'first passage' in page:
                self.assertIn('DOCUMENTATION NOTES', page)
                self.assertIn('Documentation problem:', page)
                break
        else:
            self.fail('no page holds the quotation')


class RoundTwoStructureTests(SimpleTestCase):
    def setUp(self):
        self.s = physician_pdf._styles()

    def test_displayable_never_substitutes_another_character(self):
        for ch in (chr(0x338E), chr(0x246A), chr(0xFDFA), chr(0x1D402), chr(0xFF23), chr(0xFFFF)):
            self.assertEqual(physician_pdf.displayable(f'a{ch}b'), f'a{FFFD}b', hex(ord(ch)))

    def test_a_later_long_quotation_starts_only_where_its_locator_and_two_lines_fit(self):
        long_item = physician_pdf.EvidenceItem('word ' * 600, 'Page 7')
        row = physician_pdf.CodeRow(code='45385', caption='', label='', details=(), units='1', status='',
                                    evidence_ref='', evidence=(physician_pdf.EvidenceItem('A short passage.', 'Page 3'),
                                                               long_item), note='')
        report = physician_pdf.PhysicianReport(
            kind=physician_pdf.DRAFT, status_line='', identity_line='', report_ref='', footer_note='', eyebrow='',
            title='', subtitle='', strip=(), metrics=(), codes_heading='', codes_side_note='', rows=(row,),
            empty_rows_text='', evidence_eyebrow='', evidence_title='', evidence_identity='', no_evidence_text='')
        flow = physician_pdf._evidence_flow(report, self.s)
        index = next(i for i, item in enumerate(flow) if isinstance(item, physician_pdf.Paragraph)
                     and item.text.startswith('<font face="CPTReportMonoRegular"'))
        self.assertIsInstance(flow[index - 1], physician_pdf.CondPageBreak)
        style = self.s['quote_long']
        self.assertGreaterEqual(flow[index - 1].height, style.spaceBefore + 3 * style.leading)

    def test_the_notes_heading_starts_only_where_two_lines_of_the_first_note_fit(self):
        report = physician_pdf.PhysicianReport(
            kind=physician_pdf.DRAFT, status_line='', identity_line='', report_ref='', footer_note='', eyebrow='',
            title='', subtitle='', strip=(), metrics=(), codes_heading='', codes_side_note='', rows=(),
            empty_rows_text='', notes_title='Documentation notes', notes=('First.', 'Second.'))
        flow = physician_pdf._notes_flow(report, self.s)
        self.assertIsInstance(flow[0], physician_pdf.CondPageBreak)
        self.assertGreaterEqual(flow[0].height, 2 * self.s['note_item'].leading)
        self.assertEqual([getattr(item, 'text', None) for item in flow[3:]], ['First.', 'Second.'])
        self.assertFalse(any(isinstance(item, physician_pdf.KeepTogether) for item in flow))
