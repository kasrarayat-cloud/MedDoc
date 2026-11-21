"""The physician PDF report against the inputs refutation round 5 broke the round-4 repairs with (session 738699b2,
2026-11-21), synthetic data only.

A version of one- or two-digit numbers joined by dashes goes with its name and the family after it ("Claude 3-5
Sonnet"), while a longer number (a CPT code, a date) stays; a family continues a Claude model id but not another vendor's
("gpt-4o - OPUS 2 processor" keeps the device), and a whole Claude id is replaced whole. Members whose names print no
ink are each an "Unnamed member" (an agent stays marked as one), in the record and in the Prepared row. A modifier that
prints nothing is no modifier, and a second-check comment whose reason prints nothing reads as one with no reason. The
walk records its scan of the PDF downloads as skipped, never as passed. The scanner places a clean quotation's undrawn
characters at once. Characters are built with chr() so no invisible or look-alike character sits in this file."""
import json
import pathlib
import time

from django.test import SimpleTestCase, TestCase

from studio import customer, models, physician_report, state
from tests.support import rounds as r
from tests.test_physician_report import flat, text_of

BLANK = chr(0x2800) * 2


class RoundFiveFilterTests(SimpleTestCase):
    def test_a_dash_joined_version_and_its_family_go_with_the_name(self):
        cases = {
            'Claude 3-5 Sonnet read the snare.': 'The system read the snare.',
            'Claude 3-7 Sonnet agrees with the snare.': 'The system agrees with the snare.',
            'Did claude 3-5 haiku see the cecum?': 'Did the system see the cecum?',
            'Claude 4-1 Opus agrees.': 'The system agrees.',
            'Per Fable 45385-59 is supported.': 'Per the system 45385-59 is supported.',  # a CPT code is no version
            'Seen by Dr. Claude 2026-11-02 at 14:00.': 'Seen by Dr. The system 2026-11-02 at 14:00.',  # nor a date
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)

    def test_a_family_continues_a_claude_id_only_and_a_whole_id_goes_whole(self):
        cases = {
            'Programmed after gpt-4o - OPUS 2 processor fitted.': 'Programmed after the system - OPUS 2 processor fitted.',
            'claude-3.5 Sonnet 4 agrees.': 'The system agrees.',
            'Read by claude-3-5-sonnet-20241022 today.': 'Read by the system today.',
            'claude-opus-4-5 agreed.': 'The system agreed.',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)

    def test_blank_modifiers_and_an_unreadable_comment_print_nothing_dangling(self):
        self.assertEqual(physician_report._modifier_words([chr(0x200B)]), 'Modifiers: none')
        self.assertEqual(physician_report._modifier_words([chr(0x200B), 'XS']), 'Modifiers: XS')
        self.assertEqual(physician_report._modifier_words(['XS', BLANK, '59']), 'Modifiers: XS, 59')
        head = customer.UNPLACED_NOTE
        self.assertEqual(physician_report._unplaced(f'{head}: {chr(0x200B)}'), f'{head}.')
        self.assertEqual(physician_report._unplaced(f'{head}: {BLANK}'), f'{head}.')
        self.assertEqual(physician_report._unplaced(f'{head}: The site is not stated.'), f'{head}: The site is not stated.')

    def test_the_walk_records_its_scan_of_the_pdf_downloads_as_skipped(self):
        source = (pathlib.Path(__file__).resolve().parent.parent / 'ops' / 'walk.cjs').read_text(encoding='utf-8')
        self.assertNotIn("checkScan('scan.files'", source)  # the walk no longer scans the downloads' text ...
        self.assertIn("skip('scan.files'", source)  # ... and says so rather than reporting a pass

    def test_a_clean_quotation_of_many_undrawn_characters_is_placed_at_once(self):
        sc = r.scan_customer()
        document = ''.join('x' + chr(0x4E00) for _ in range(50000))
        started = time.monotonic()
        self.assertTrue(sc._of_document(('x' + chr(0xFFFD)) * 1000 + 'x', document))
        self.assertLess(time.monotonic() - started, 1)
        # one character or none still holds where the fixed-width reading fails
        self.assertTrue(sc._of_document('ab' + chr(0xFFFD) + 'cd', 'abcd'))
        self.assertFalse(sc._of_document('ab' + chr(0xFFFD) + 'cd', 'abXYcd'))


class RoundFiveNamesCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for(self.reviewer)

    def pdf(self, enc, kind='draft', client=None) -> bytes:
        client = client or self.client
        number = state.latest_round(enc).number
        made = client.post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': number}), content_type='application/json')
        self.assertEqual(made.status_code, 201, made.content)
        return client.get(made.json()['download_url']).content

    def test_members_whose_names_print_no_ink_are_each_an_unnamed_member(self):
        other = r.f.member(self.ws)
        models.User.objects.filter(pk=self.reviewer.pk).update(display_name=BLANK)
        models.User.objects.filter(pk=other.pk).update(display_name=chr(0x3000))
        models.User.objects.filter(pk=self.agent.pk).update(display_name=BLANK)
        for user in (self.reviewer, other, self.agent):
            user.refresh_from_db()
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'ready'), r.row('45378', 'ready')])
        self.decide(enc, 'L1', '45385', 'approve')
        self.decide(enc, 'L2', '45380', 'reject', user=other)
        self.decide(enc, 'L3', '45378', 'approve', user=self.agent, kind='agent')
        text = flat(text_of(self.pdf(enc)))
        self.assertIn('Unnamed member, Unnamed member, Unnamed member (automated agent)', text)
        self.assertIn('by Unnamed member', text.split('REVIEW SCOPE')[1])  # the Prepared row
