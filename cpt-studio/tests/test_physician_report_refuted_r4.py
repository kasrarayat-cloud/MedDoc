"""The physician PDF report against the inputs refutation round 4 broke the round-3 repairs with (session 738699b2,
2026-11-21), synthetic data only.

A model family continues the Anthropic name right before it, whatever began the run ("Gemini Claude Opus 4.5"), and a
device after another name stays ("Dr. Claude Corti - OPUS 2"). A version is a one- or two-digit number joined by dots or
underscores, so a CPT code, a date or a range after a name is left as written. The gap between parts of a run includes
every dash and the invisible characters above the BMP. The PDF filters what the coding review wrote both as written and
as printed, so a modifier with a hidden gap reads "the system". A question the page offers is counted as the page counts
it and said to be unreadable when its text prints nothing; a line's own blank question, reason or note prints nothing
dangling; a member whose name prints no ink is an unnamed member. The notes heading never ends a page alone when the
first note is three lines. The character notes name the saved record. The scanner's undrawn-character matching is linear.
Characters are built with chr() so no invisible or look-alike character sits in this file."""
import json
import time

from django.test import TestCase

from studio import customer, models, physician_pdf, state
from tests.support import rounds as r
from tests.test_physician_report import flat, text_of

VOCAB = ('the colonoscope was advanced to the cecum and the appendiceal orifice and ileocecal valve were identified '
         'a sessile polyp in the sigmoid colon was removed with a cold snare and retrieved for pathology the mucosa '
         'was otherwise normal throughout withdrawal time was recorded hemostasis was confirmed').split()


def words(n, start=0):
    return ' '.join(VOCAB[(start + i) % len(VOCAB)] for i in range(n))


class RoundFourCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for(self.reviewer)
        self.sc = r.scan_customer()

    def pdf(self, enc, kind='draft') -> bytes:
        number = state.latest_round(enc).number
        made = self.client.post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': number}), content_type='application/json')
        self.assertEqual(made.status_code, 201, made.content)
        return self.client.get(made.json()['download_url']).content

    # --- R4-2-2, R4-2-6, R4-2-9, R4-2-5: the name runs ---------------------------------------------------------------------

    def test_a_family_continues_the_anthropic_name_before_it_and_nothing_else(self):
        cases = {
            'Gemini Claude Opus 4.5 read the snare.': 'The system read the snare.',
            'OpenAI-Claude Haiku 3 agrees.': 'The system agrees.',
            'Did Google Claude Sonnet 4.5 see the cecum?': 'Did the system see the cecum?',
            'Seen by Dr. Claude Corti - OPUS 2 processor fitted.': 'Seen by Dr. The system - OPUS 2 processor fitted.',
            'claude-3.5 Sonnet 4 agrees.': 'The system agrees.',
            'Claude' + chr(0x2800) + 'Opus 4.5 read it.': 'The system read it.',
            'Claude' + chr(0xE0020) + 'Opus 4.5 read it.': 'The system read it.',
            'Claude' + chr(0x058A) + '3.5 Sonnet agrees.': 'The system agrees.',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)

    def test_a_code_or_a_date_after_a_name_is_left_as_written(self):
        cases = {
            'Per Fable 45385-59 is supported.': 'Per the system 45385-59 is supported.',
            'Seen by Dr. Claude 2026-11-02 at 14:00.': 'Seen by Dr. The system 2026-11-02 at 14:00.',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='Per Fable 45385-59 is supported.')])
        self.assertIn('Reason: Per the system 45385-59 is supported.', flat(text_of(self.pdf(enc))))

    # --- R4-2-1: a modifier with a hidden gap ------------------------------------------------------------------------------

    def test_a_modifier_with_a_hidden_gap_reads_the_system(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', modifiers=['XS', 'Gemini' + chr(0x200B) + '2.5',
                                                                     'Claude' + chr(0x2060) + 'Opus'])])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('Modifiers: XS, the system, the system', text)
        for name in ('gemini', 'claude', 'opus'):
            self.assertNotIn(name, text.lower())

    # --- R4-2-3: a question the page offers, whose text prints nothing -----------------------------------------------------

    def test_an_unreadable_question_is_counted_as_the_page_counts_it(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')],
                      questions=[{'id': 'q1', 'text': chr(0x200B), 'lines': ['L1'], 'source': 'checker'}])
        self.decide(enc, 'L1', '45385', 'approve')
        self.assertEqual(len(self.client.get(f'/api/encounters/{enc.pk}').json()['questions']), 1)  # the page offers it
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('01 01 Pending', text)
        self.assertIn('Question about 45385: no readable text', text)
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45378', 'needs_answer', question='Which cecal landmark was seen?'),
                                  r.row('45385', 'ready')],
                      questions=[{'id': 'q1', 'text': 'Which site was biopsied?', 'lines': ['L2'], 'source': 'reader'},
                                 {'id': 'q2', 'text': chr(0x200B), 'lines': ['L1'], 'source': 'reader'}])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('02 03 Pending', text)
        self.assertIn('Question: Which site was biopsied?', text)
        self.assertIn('Question about 45378: no readable text', text)

    # --- R4-3-3, R4-2-7: a line's own blank text ---------------------------------------------------------------------------

    def test_a_lines_blank_question_reason_or_note_prints_nothing_dangling(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45378', 'needs_answer', question=chr(0x200B), reason=chr(0x2800) * 2),
                                  r.row('45385', 'needs_answer', question='Was the polyp removed whole?')],
                      problems=[chr(0x200B), 'The note is not signed.'])
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('45378 (L1) needs your answer.', text)
        self.assertIn('45385 (L2) needs your answer: Was the polyp removed whole?', text)
        self.assertNotIn('Question: ' + chr(0x2800), text)
        self.assertNotRegex(text, r'Question:\s*(?:01|02|Second|REVIEW|DOCUMENTATION|THE |$)')
        self.assertNotIn('Reason: Second check', text)
        self.assertIn('DOCUMENTATION NOTES – The note is not signed.', text)

    # --- R4-3-5, R4-2-8: a member whose name prints no ink -----------------------------------------------------------------

    def test_a_member_whose_name_prints_no_ink_is_an_unnamed_member(self):
        models.User.objects.filter(pk=self.reviewer.pk).update(display_name=chr(0x2800) * 2)
        self.reviewer.refresh_from_db()
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        self.decide(enc, 'L1', '45385', 'approve')
        for kind in ('approved', 'draft'):
            with self.subTest(kind=kind):
                text = flat(text_of(self.pdf(enc, kind)))
                self.assertIn('Unnamed member', text)
                self.assertNotIn('Not recorded', text.split('REVIEW SCOPE')[0])

    # --- R4-2-10: a space mark a font draws with ink -----------------------------------------------------------------------

    def test_a_space_mark_drawn_with_ink_is_not_blank(self):
        self.assertFalse(physician_pdf.blank(chr(0x1680) * 3))
        self.assertTrue(physician_pdf.blank(chr(0x3000) + chr(0x2800)))

    # --- R4-3-2: the character notes name the saved record -----------------------------------------------------------------

    def test_the_character_note_names_the_saved_record(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')], citations={'L1': [
            {'text': 'removed with a cold snare ' + chr(0x8178), 'page': 2, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(enc)))
        self.assertIn("Some cannot be drawn in this PDF and are shown as " + chr(0xFFFD) + "; CPT Studio's saved record "
                      "keeps every character", text)
        self.assertNotIn('document page', text)

    # --- R4-3-1: the notes heading and a three-line first note -------------------------------------------------------------

    def test_the_notes_heading_never_ends_a_page_alone_above_a_short_first_note(self):
        codes = ('45378', '45380', '45385', '43239', '43251', '45384', '45381')
        first = 'The procedure note does not state ' + words(33, 4) + '.'
        checked = 0
        for count in (5, 6, 7):
            for reasoned in (26, 28, 30, 32, 34):
                enc = self.encounter()
                r.write_round(enc, codes=[r.row(code, 'ready', reason='The note documents it: ' + words(reasoned, k))
                                          for k, code in enumerate(codes[:count])],
                              problems=[first, 'The note is not signed.'],
                              citations={f'L{k + 1}': [{'text': words(6, 3 * k), 'page': 2, 'source': 'reader'}]
                                         for k in range(count)})
                for page in text_of(self.pdf(enc)):
                    if 'DOCUMENTATION NOTES' in page:
                        checked += 1
                        self.assertIn('The procedure note does not state', ' '.join(page.split()), (count, reasoned))
        self.assertGreater(checked, 0)

    # --- R4-4-1: a quotation of undrawable characters scans in linear time -------------------------------------------------

    def test_a_quotation_of_many_undrawable_characters_scans_quickly(self):
        # 22 undrawable characters: about 13 s under the earlier wildcard pattern (which grew four times every two more),
        # milliseconds now
        run = ''.join(chr(0x4E00 + 7 * i) for i in range(22))
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'ready'), r.row('45378', 'ready')], citations={
            'L1': [{'text': words(45), 'page': 1, 'source': 'reader'}],
            'L2': [{'text': run, 'page': 2, 'source': 'reader'}],
            'L3': [{'text': words(36, 9), 'page': 3, 'source': 'reader'}]})
        data = self.pdf(enc)
        payload = self.client.get(f'/api/encounters/{enc.pk}').json()
        started = time.monotonic()
        hits = self.sc.scan_pdf(self.sc.read_pdf(data), self.sc.scan_context(self.sc.quotations(payload)), 'draft.pdf')
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(hits, [])
