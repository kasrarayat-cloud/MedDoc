"""The physician PDF report against the inputs refutation round 1 broke it with (session 738699b2, 2026-11-21).

Each test reproduces one demonstrated counterexample, synthetic data only: questions on decided lines counted as open;
the agent line only for agent approvals; no "has a source" claim over unchecked quotations; characters no report font
draws shown visibly and kept searchable; control and invisible characters neither joining numbers nor reassembling a
vendor name past the name filter; a quotation never cut from its locator; stored values too tall for one row still
printed; the header keeping the encounter reference under a long title; no non-embedded font; headings kept with their
content."""
import io
import json

from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader

from studio import models, physician_pdf, state
from tests.support import rounds as r
from tests.test_physician_report import flat, text_of

# lens 4's synthetic word list (refutation round 1), so its failing layouts are reproduced exactly
WORDS = ('the procedure note documents the service in detail including the site the instrument and the completed '
         'technique with the findings and the plan').split()


def words(n, start=0):
    return ' '.join(WORDS[(start + i) % len(WORDS)] for i in range(n))


class RefutedCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for(self.reviewer)

    def make(self, enc, kind, client=None):
        number = state.latest_round(enc).number
        return (client or self.client).post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': number}), content_type='application/json')

    def pdf(self, enc, kind, client=None) -> bytes:
        made = self.make(enc, kind, client)
        self.assertEqual(made.status_code, 201, made.content)
        return (client or self.client).get(made.json()['download_url']).content

    # --- L1-1: what is open is one list; the count and the status agree with it ------------------------------------------

    def test_a_question_on_a_decided_line_is_still_open(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')],
                      questions=[{'id': 'q1', 'text': 'Was the resected polyp retrieved?', 'lines': ['L1'],
                                  'source': 'checker'}])
        self.decide(enc, 'L1', '45385', 'approve')
        text = flat(text_of(self.pdf(enc, 'draft')))
        self.assertIn('01 01 Pending Suggested code Open review item Review status', text)
        self.assertIn('Question: Was the resected polyp retrieved?', text)
        self.assertNotIn('Complete', text)

    def test_no_codes_and_a_question_is_pending(self):
        enc = self.encounter()
        r.write_round(enc, codes=[], questions=[{'id': 'q1', 'text': 'Was the scope advanced to the cecum?',
                                                 'source': 'reader'}])
        text = flat(text_of(self.pdf(enc, 'draft')))
        self.assertIn('00 01 Pending Suggested codes Open review item Review status', text)

    # --- L1-2: the agent line is about approvals ---------------------------------------------------------------------------

    def test_an_agent_rejection_alone_carries_no_agent_line(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'needs_review')])
        self.decide(enc, 'L1', '45385', 'approve')
        self.decide(enc, 'L2', '45380', 'reject', user=self.agent, kind='agent')
        text = flat(text_of(self.pdf(enc, 'draft')))
        self.assertNotIn('Agent-executed synthetic review', text)
        self.assertIn('Reviewbot (automated agent)', text)  # the rejection's reviewer is still named

    def test_mixed_human_and_agent_approvals_say_which(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'needs_review')])
        self.decide(enc, 'L1', '45385', 'approve')
        self.decide(enc, 'L2', '45380', 'approve', user=self.agent, kind='agent')
        text = flat(text_of(self.pdf(enc, 'approved')))
        self.assertIn('Agent-executed synthetic review — not clinical approval — 1 of 2 approvals, marked on each code',
                      text)
        self.assertIn('Approvals marked as agent-executed are synthetic reviews, not clinical approval.', text)

    # --- L1-3: no source claim over unchecked quotations -------------------------------------------------------------------

    def test_unchecked_quotations_are_never_called_the_documents_words(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'ready')],
                      citations={'_document': [{'text': 'a passage filed under no line', 'page': 1, 'source': 'reader'}]})
        self.decide(enc, 'L1', '45385', 'approve')
        self.decide(enc, 'L2', '45380', 'approve')
        for kind in ('approved', 'draft'):
            text = flat(text_of(self.pdf(enc, kind)))
            self.assertNotIn('has a source.', text)
            self.assertIn("The coding review's own quotations, not checked against the document", text)
            self.assertNotIn('Exact words from the document', text)

    # --- L1-4, L2-4, L2-6, L2-7: characters no report font draws ----------------------------------------------------------

    def test_characters_no_font_draws_are_shown_visibly_and_stay_searchable(self):
        enc = self.encounter(title='Synthetic note ⦁ 李')
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': 'Sedation ⦁ midazolam 5 ㎎ IV; patient smiled 😀; a sessile 𝖯𝗈𝗅𝗒𝗉 removed', 'page': 2,
             'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc, 'draft')))
        self.assertNotIn('\x00', text)
        # shown as U+FFFD, never as a blank box and never as another character (refutation round 2: a compatibility form
        # changed numbers and spelled names), and searchable as that
        self.assertIn('midazolam 5 � IV', text)
        self.assertIn('a sessile ����� removed', text)
        self.assertIn('Sedation � midazolam', text)
        self.assertIn('Synthetic note � �', text)
        self.assertIn('Some cannot be drawn in this PDF and are shown as �', text)

    def test_right_to_left_text_is_said_to_be_in_stored_order(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': 'Family history in Hebrew שלום noted', 'page': 1, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc, 'draft')))
        self.assertIn('Right-to-left text', text)
        self.assertIn('Shown in its stored order, left to right', text)

    # --- L2-3, L2-5, L3-1, L3-4: control and invisible characters ----------------------------------------------------------

    def test_a_control_between_numbers_never_joins_them(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': 'Polyps removed: 2\x0b3 biopsy jars sent', 'page': 2, 'source': 'reader'},
            {'text': 'Withdrawal time 6\x0c8 minutes, 4\x1c5 \x85 7', 'page': 3, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc, 'draft')))
        self.assertIn('Polyps removed: 2 3 biopsy jars sent', text)
        self.assertIn('Withdrawal time 6 8 minutes, 4 5 7', text)
        self.assertNotIn('23 biopsy', text)

    def test_an_invisible_character_never_carries_a_vendor_name_into_the_pdf(self):
        enc = self.encounter(title='Note for \u2068Dr Example\u2069 visit')
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='Cl\u200eaude read the snare; Cla\u200bude agreed.',
                                        check_reason='Gem\x01ini agrees.', question='Did Anth\x7fropic see it?')],
                      problems=['Fa\u2060ble could not tell the site.', 'Op\ufeffenAI saw it.'])
        data = self.pdf(enc, 'draft')
        text = flat(text_of(data))
        lowered = text.lower()
        for name in ('claude', 'anthropic', 'fable', 'openai'):
            self.assertNotIn(name, lowered)
        self.assertNotIn('gemini', lowered)  # a control becomes a space: "Gem ini", never the name
        self.assertIn('Note for Dr Example visit', text)  # the isolates are dropped, not drawn as boxes
        self.assertNotIn('�', text)

    # --- L4-1: a quotation and its locator are never cut apart ------------------------------------------------------------

    def test_a_locator_always_sits_on_the_page_of_its_quotation(self):
        # refutation round 1's family (lens 4, f1b): the second box split from its locator for many first-passage lengths
        for n1 in range(20, 112, 4):
            enc = self.encounter()
            r.write_round(enc, codes=[
                r.row('45385', 'ready', reason='A polyp was removed by cold snare.',
                      evidence=[{'quote': 'first passage: ' + words(n1), 'page': 2},
                                {'quote': 'second passage: ' + words(60, 5), 'page': 3}]),
                r.row('45380', 'needs_review', modifiers=['59'], reason='A separate lesion was biopsied.'),
                r.row('45378', 'needs_answer', question='Was the cecum reached?',
                      reason='A diagnostic colonoscopy is documented.')],
                questions=[{'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45378'], 'source': 'reader'}],
                problems=['Bowel preparation quality was not recorded.'],
                citations={'L2': [{'text': 'a separate area was biopsied with forceps', 'page': 3, 'source': 'reader'}]})
            for page in text_of(self.pdf(enc, 'draft')):
                page = ' '.join(page.split())
                if 'second passage:' in page:
                    self.assertIn('not checked against the document · Page 3', page, n1)
                if 'first passage:' in page:
                    self.assertIn('not checked against the document · Page 2', page, n1)

    # --- L2-1, L4-6, L4-7, L2-2: stored values too tall for one row --------------------------------------------------------

    def test_values_too_tall_for_one_row_are_still_printed(self):
        enc = self.encounter()
        modifiers = ['59 distinct procedural service: a separate lesion in a separate segment, documented separately'] * 22
        r.write_round(enc, codes=[r.row('45385', 'ready', modifiers=modifiers),
                                  r.row('45380', 'ready', units=int('9' * 200)),
                                  r.row('45378', 'ready', units=123456)])
        text = flat(text_of(self.pdf(enc, 'draft')))
        # one occurrence may straddle a page break, where the next page's running header comes between the words
        self.assertEqual((text.count('documented'), text.count('separately')), (22, 22))
        self.assertIn('Units: ' + '9' * 200, text.replace(' ', '').replace('Units:', 'Units: '))
        self.assertIn('Units: 123456', text)  # never broken as "12345" over "6"

    def test_many_long_reviewer_names_still_print(self):
        enc = self.encounter()
        codes = [r.row(f'4{5300 + n}', 'ready') for n in range(20)]
        r.write_round(enc, codes=codes)
        for n in range(20):
            member = self._member_named(f'Reviewer {n:02d} ' + 'Synthetic' * 12)
            self.decide(enc, f'L{n + 1}', codes[n]['code'], 'approve', user=member)
        text = flat(text_of(self.pdf(enc, 'approved')))
        self.assertIn('Reviewer 19', text)

    def _member_named(self, name):
        from tests.support import coding as f
        member = f.member(self.ws)
        models.User.objects.filter(pk=member.pk).update(display_name=name[:120])
        member.refresh_from_db()
        return member

    # --- L4-5: the header keeps the reference and the coding review ---------------------------------------------------------

    def test_a_long_title_never_pushes_the_reference_out_of_the_header(self):
        title = ('Synthetic colonoscopy and upper endoscopy note with polypectomy biopsy and dilation for a synthetic '
                 'patient record used only for layout testing of header lines')[:160]
        enc = self.encounter(title=title)
        r.write_round(enc, codes=[r.row('45385', 'ready')], problems=['One.', 'Two.', 'Three.'])
        ref = enc.pk.hex[:8].upper()
        for page in text_of(self.pdf(enc, 'draft')):
            self.assertIn(f'{ref} · Coding review 1', ' '.join(page.split()))

    # --- L6-5: every font is embedded --------------------------------------------------------------------------------------

    def test_no_font_is_left_unembedded(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')], problems=['Bowel preparation quality was not recorded.'])
        data = self.pdf(enc, 'draft')
        self.assertNotIn(b'/Helvetica', data)
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            for font in page['/Resources']['/Font'].values():
                font = font.get_object()
                descendant = font['/DescendantFonts'][0].get_object() if '/DescendantFonts' in font else font
                descriptor = descendant.get('/FontDescriptor')
                self.assertIsNotNone(descriptor, font.get('/BaseFont'))
                descriptor = descriptor.get_object()
                self.assertTrue(any(key in descriptor for key in ('/FontFile2', '/FontFile', '/FontFile3')),
                                font.get('/BaseFont'))

    # --- L4-2, L4-3: headings stay with their content ------------------------------------------------------------------------

    def test_the_evidence_title_shares_a_page_with_the_first_evidence(self):
        # lens 4's f2 family: the section title was left at a page foot above ~270 pt of blank space
        for lines in (4, 5, 6):
            for q in (110, 125, 140, 155):
                enc = self.encounter()
                codes = [r.row('45385', 'ready', reason='A polyp was removed by cold snare.')]
                codes += [r.row(f'4538{n}', 'needs_review', reason='Documented.') for n in range(1, lines)]
                citations = {'L1': [{'text': 'first passage: ' + words(q), 'page': 2, 'source': 'reader'}]}
                citations.update({f'L{n + 1}': [{'text': f'passage {n}: removed by cold snare', 'page': 1,
                                                 'source': 'reader'}] for n in range(1, lines)})
                r.write_round(enc, codes=codes, citations=citations, questions=[
                    {'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45385'], 'source': 'reader'}])
                for page in text_of(self.pdf(enc, 'draft')):
                    page = ' '.join(page.split())
                    if 'THE REASONS, IN THE RECORD' in page:
                        self.assertIn('01 45385 /', page, (lines, q))

    def test_the_notes_heading_shares_a_page_with_the_first_note(self):
        # lens 4's f3 family: long titles and one to three notes left the heading alone at a page foot
        title = ('Synthetic colonoscopy and upper endoscopy note with polypectomy biopsy and dilation for a synthetic '
                 'patient record used only for layout testing of header lines')
        for cut in (148, 152, 156, 160):
            for problems in (1, 2, 3):
                enc = self.encounter(title=title[:cut])
                r.write_round(enc, codes=[
                    r.row('45385', 'ready', reason='A polyp was removed by cold snare.'),
                    r.row('45380', 'needs_review', modifiers=['59'], reason='A separate lesion was biopsied.')],
                    questions=[{'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45380'], 'source': 'reader'}],
                    problems=[f'Documentation problem {k}: bowel preparation quality was not recorded.'
                              for k in range(1, problems + 1)],
                    citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}],
                               'L2': [{'text': 'a separate area was biopsied with forceps', 'page': 3,
                                       'source': 'reader'}]})
                for page in text_of(self.pdf(enc, 'draft')):
                    page = ' '.join(page.split())
                    if 'DOCUMENTATION NOTES' in page:
                        self.assertIn('Documentation problem 1:', page, (cut, problems))


class StructureTests(SimpleTestCase):
    """The layout guarantees as structure, independent of where a page happens to break (the API-level sweeps above
    depend on exact positions; these do not)."""

    def setUp(self):
        self.s = physician_pdf._styles()

    def test_a_short_quotation_and_its_locator_are_one_row_that_cannot_split(self):
        block = physician_pdf._quote_block(physician_pdf.EvidenceItem('A short passage.', 'Page 3'), self.s)
        table = block[-1]
        self.assertIsInstance(table, physician_pdf.Table)
        self.assertEqual(len(table._cellvalues), 1)  # one row: the quotation and the locator share one cell
        self.assertEqual(len(table._cellvalues[0][0]), 2)
        table.wrap(physician_pdf.CONTENT_WIDTH, physician_pdf.FRAME_HEIGHT)
        self.assertEqual(table.split(physician_pdf.CONTENT_WIDTH, 30), [])  # never cut: it moves whole

    def test_a_long_quotation_flows_with_its_locator_first(self):
        item = physician_pdf.EvidenceItem('word ' * 900, "The coding review's quotation, not checked · Page 2")
        block = physician_pdf._quote_block(item, self.s)
        self.assertEqual(len(block), 1)
        self.assertIsInstance(block[0], physician_pdf.Paragraph)
        self.assertTrue(block[0].text.startswith('<font face="CPTReportMonoRegular"'), block[0].text[:80])
        self.assertEqual((block[0].style.allowWidows, block[0].style.allowOrphans), (0, 0))

    def test_the_notes_heading_travels_with_the_first_note(self):
        # since refutation round 2 by a page break that leaves room for two lines of the first note, rather than one
        # unsplittable group that moved a long first note to a new page (test_physician_report_refuted_r2)
        report = physician_pdf.PhysicianReport(
            kind=physician_pdf.DRAFT, status_line='', identity_line='', report_ref='', footer_note='', eyebrow='',
            title='', subtitle='', strip=(), metrics=(), codes_heading='', codes_side_note='', rows=(),
            empty_rows_text='', notes_title='Documentation notes', notes=('First.', 'Second.'))
        flow = physician_pdf._notes_flow(report, self.s)
        self.assertIsInstance(flow[0], physician_pdf.CondPageBreak)
        self.assertEqual([getattr(item, 'text', '') for item in flow[3:]], ['First.', 'Second.'])
