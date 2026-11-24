"""The physician PDF report against the inputs refutation round 3 broke the round-2 repairs with (session 738699b2,
2026-11-21), synthetic data only.

A vendor name run continues across any gap a reader sees as space or nothing - a line break, a tab, a non-breaking or
zero-width space, a word joiner, a dash - and across a version written with dots, dashes or underscores, so "Claude"
and "Opus" on either side of one leave no model family behind; a model family continues only Anthropic's names, so a
device beside "organ of Corti" is left as written. Modifiers are filtered as one list ("the system" mid-list). A title,
or a question, that prints no ink (blank Braille cells, invisible text) is treated as absent. A space no report font
draws prints as a space, and a quotation with a character the scanner deletes while the report prints U+FFFD is still
the document's own words. Characters are built with chr() so no invisible or look-alike character sits in this file."""
import json

from django.test import TestCase, override_settings

from studio import customer, physician_pdf, state
from tests.support import rounds as r
from tests.test_physician_report import flat, text_of

FFFD = chr(0xFFFD)
VENDOR_OR_FAMILY = ('claude', 'gemini', 'anthropic', 'openai', 'opus', 'sonnet', 'haiku')


@override_settings(EXPORT_LIMIT_PER_MEMBER=(10_000, 600), EXPORT_LIMIT_PER_WORKSPACE=(10_000, 3600))  # C5: layout cases, not limits
class RoundThreeCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for(self.reviewer)
        self.sc = r.scan_customer()

    def pdf(self, enc, kind='draft') -> bytes:
        number = state.latest_round(enc).number
        made = self.client.post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': number}), content_type='application/json')
        self.assertIn(made.status_code, (200, 201), made.content)  # release 1, C5: a current report is the stored copy
        return self.client.get(made.json()['download_url']).content

    def scan(self, enc, data):
        payload = self.client.get(f'/api/encounters/{enc.pk}').json()
        return self.sc.scan_pdf(self.sc.read_pdf(data), self.sc.scan_context(self.sc.quotations(payload)), 'draft.pdf')

    # --- R3-1-1, R3-1-7: one run across a gap or a dashed version ----------------------------------------------------------

    def test_a_vendor_run_across_any_gap_leaves_no_model_family_behind(self):
        cases = {
            'Claude' + chr(10) + 'Opus 4.5 read the snare.': 'The system read the snare.',
            'Claude' + chr(0x200B) + ' 3.5 Sonnet agrees.': 'The system agrees.',
            'Did Claude 3' + chr(9) + 'Haiku see the cecum?': 'Did the system see the cecum?',
            'Claude' + chr(0x2060) + 'Opus 4.5 could not tell the site.': 'The system could not tell the site.',
            'Claude' + chr(0xA0) + 'Opus' + chr(0xA0) + '4.5 read the snare.': 'The system read the snare.',
            'Claude' + chr(0x2011) + '3.5 Sonnet agrees.': 'The system agrees.',
            'Claude-3.5 Sonnet read the snare.': 'The system read the snare.',
            # versions are numbers of one or two digits joined by dots, dashes or underscores (rounds 4 and 5): a longer
            # number after a name is a code or a date, left as written
            'Read by claude_3_5_sonnet_20241022.': 'Read by the system_20241022.',
            'Claude Opus 4-5 agreed.': 'The system agreed.',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='Claude' + chr(10) + 'Opus 4.5 read the snare.',
                                        check_reason='Claude-3.5 Sonnet agrees.',
                                        question='Did Claude 3' + chr(9) + 'Haiku see the cecum?')],
                      problems=['Claude' + chr(0x2060) + 'Opus 4.5 could not tell the site.'],
                      citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}]})
        data = self.pdf(enc)
        text = flat(text_of(data))
        self.assertIn('Reason: The system read the snare. Second check: agrees. The system agrees.', text)
        for name in VENDOR_OR_FAMILY:
            self.assertNotIn(name, text.lower())
        self.assertEqual(self.scan(enc, data), [])

    # --- R3-1-3: a model family continues only Anthropic's names ----------------------------------------------------------

    def test_a_device_beside_a_word_the_filter_takes_for_a_name_is_left_as_written(self):
        reason = 'Electrode insertion preserved the organ of Corti - OPUS 2 processor fitted.'
        self.assertEqual(customer.shown(reason),
                         'Electrode insertion preserved the organ of the system - OPUS 2 processor fitted.')
        self.assertEqual(customer.shown('Implant: Astra - SONNET 2'), 'Implant: the system - SONNET 2')
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('92603', 'ready', reason=reason)])
        self.assertIn('OPUS 2 processor fitted', flat(text_of(self.pdf(enc))))

    # --- R3-1-4: modifiers filtered as one list ----------------------------------------------------------------------------

    def test_modifiers_read_the_system_mid_list(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', modifiers=['59', 'Claude', 'gemini-2.5', 'XS', 'Opus 4.5'])])
        self.assertIn('Modifiers: 59, the system, the system, XS, Opus 4.5', flat(text_of(self.pdf(enc))))

    # --- R3-1-5, R3-2-4: a title that prints no ink ------------------------------------------------------------------------

    def test_a_title_of_blank_braille_cells_is_untitled(self):
        self.assertTrue(physician_pdf.blank(chr(0x2800) * 3))
        self.assertFalse(physician_pdf.blank('A' + chr(0x2800)))
        enc = self.encounter(title=chr(0x2800) * 3)
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        pages = text_of(self.pdf(enc))
        ref = enc.pk.hex[:8].upper()
        self.assertIn(f'Untitled document · {ref} · Coding review 1', flat(pages))
        for page in pages:
            for line in page.splitlines():
                self.assertFalse(line.strip(' ' + chr(0x2800)).startswith('·'), line)

    # --- R3-1-6: a question that prints nothing ----------------------------------------------------------------------------

    def test_a_question_of_invisible_text_is_counted_as_the_page_counts_it_and_said_to_be_unreadable(self):
        # since round 4 (R4-2-3): the page offers the question (fable.result.blank_question keeps it), so the report counts
        # it too, and says it has no readable text rather than printing an empty "Question:"; the lines awaiting an
        # answer are finished by answering it, as the page says on each line
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45378', 'needs_answer', question='Was the cecum reached?'),
                                  r.row('45385', 'needs_answer', question='Was the polyp removed whole?')],
                      questions=[{'id': 'q1', 'text': chr(0x200B), 'codes': [], 'source': 'reader'}])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('02 01 Pending', text)
        self.assertIn('Question: no readable text', text)
        self.assertNotIn('Question: ·', text)

    # --- R3-2-1, R3-4-2: a space no font draws ----------------------------------------------------------------------------

    def test_an_ideographic_space_prints_as_a_space_and_the_quotation_stays_the_documents(self):
        wide = chr(0x3000)
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason=f'Polyp{wide}removed{wide}by{wide}snare.')],
                      citations={'L1': [{'text': f'Dr. Claude Example removed the polyp{wide}with a cold snare.',
                                         'page': 2, 'source': 'reader'}]})
        data = self.pdf(enc)
        text = flat(text_of(data))
        self.assertIn('Reason: Polyp removed by snare.', text)
        self.assertIn('“Dr. Claude Example removed the polyp with a cold snare.”', text)
        self.assertNotIn(FFFD, text)
        self.assertNotIn('Some cannot be drawn in this PDF', text)
        self.assertEqual(self.scan(enc, data), [])

    # --- R3-3-1: the first note's last line alone at the top of a page -----------------------------------------------------

    def test_the_first_notes_last_line_never_stands_alone_at_the_top_of_a_page(self):
        # refutation round 3's family (lens 3, 15 of 24 drafts left the note's fifth line alone above REVIEW SCOPE)
        vocab = ('the colonoscope was advanced to the cecum and the appendiceal orifice and ileocecal valve were identified '
                 'a sessile polyp in the sigmoid colon was removed with a cold snare and retrieved for pathology the mucosa '
                 'was otherwise normal throughout withdrawal time was recorded hemostasis was confirmed').split()

        def words(n, start=0):
            return ' '.join(vocab[(start + i) % len(vocab)] for i in range(n))

        continued = 0
        for cited in (104, 105, 106, 108, 110, 112):
            for reasoned in (108, 112, 116, 120):
                enc = self.encounter()
                r.write_round(enc, codes=[r.row('45385', 'ready', reason='A polyp was removed by cold snare; '
                                                + words(reasoned, 2) + '.')],
                              problems=['Documentation problem: ' + words(70)],
                              citations={'L1': [{'text': 'first passage ' + words(cited), 'page': 2, 'source': 'reader'}]})
                pages = text_of(self.pdf(enc))
                for previous, page in zip(pages, pages[1:]):
                    if 'DOCUMENTATION NOTES' not in previous or 'DOCUMENTATION NOTES' in page:
                        continue
                    lines = [line.strip() for line in page.splitlines() if line.strip()]
                    body = lines[next(i for i, line in enumerate(lines) if line.endswith(f'of {len(pages):02d}')) + 1:]
                    if 'REVIEW SCOPE' in body and body.index('REVIEW SCOPE') > 0:
                        continued += 1
                        self.assertGreaterEqual(body.index('REVIEW SCOPE'), 2, (cited, reasoned, body[:3]))
        self.assertGreater(continued, 0)  # the family does carry a note over a page break: the check is not vacuous
