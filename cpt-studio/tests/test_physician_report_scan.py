"""The physician PDF report as a customer download (owner directive 2026-11-21): each PDF made through the API as the page
makes it, downloaded, and read by the customer scanner's own PDF path (ops/scan_customer.py read_pdf and scan_pdf, loaded
by tests.support.rounds.scan_customer) against the shared denylist (ops/verification/customer-denylist.json), with the
encounter's own quotations set aside as the scanner sets them aside on the deployed site. Covered: a draft and an approved
PDF of a round whose reasons, questions and notes name vendors and models; a line the second check added, in its own
words; a round made after answers, or after a retry, naming its trigger; an earlier round's PDF, still listed once a
later round replaced it, whose modifier names a vendor outside the quotation (refutation L3-2); a phrase the page break
cuts in two (L6-3); and a viewer's PDF, which holds what a reviewer's does. Synthetic data only; nothing reaches the
network."""
import io
import json
import re
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.test import TestCase
from pypdf import PdfReader

from studio import customer, exports, models, state
from tests.support import rounds as r

Round = models.CodingRound
QUOTE = 'Dr. Claude Example removed the polyp with a cold snare'  # the document's own words: a synthetic doctor's name


def flat(data: bytes) -> str:
    """The PDF's text, every page, white space squeezed."""
    return ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages).split())


class PhysicianReportScanCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.sc = r.scan_customer()

    def made(self, enc, kind, user=None):
        """A PDF made through the API as the page makes it (naming the round it shows) and downloaded by the same
        member: its bytes, the download response and the report as the page lists it."""
        client = self.client_for(user or self.reviewer)
        shown = client.get(f'/api/encounters/{enc.pk}').json()['round']['number']
        made = client.post(f'/api/encounters/{enc.pk}/reports', content_type='application/json',
                           data=json.dumps({'kind': kind, 'fmt': 'pdf', 'round': shown}))
        self.assertEqual(made.status_code, 201, made.content)
        got = client.get(made.json()['download_url'])
        self.assertEqual((got.status_code, got['Content-Type']), (200, 'application/pdf'))
        return got.content, got, made.json()

    def scanned(self, enc, data, response, name):
        """The customer scanner's reading of a downloaded PDF, as it reads one on the deployed site: the reading, and
        the hits of its text, its metadata (the encounter's own quotations set aside) and the download's headers."""
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        ctx = self.sc.scan_context(self.sc.quotations(payload))
        self.assertTrue(self.sc.is_pdf(data, response['Content-Type']))
        reading = self.sc.read_pdf(data)  # Unreadable, and so a failed test, when it cannot be read
        hits = self.sc.scan_pdf(reading, ctx, name)
        self.sc.scan_headers(dict(response.items()), ctx, name, hits)
        return reading, hits


class VendorNameTests(PhysicianReportScanCase):
    def test_a_draft_and_an_approved_pdf_of_a_round_naming_vendors_pass_the_customer_scan(self):
        enc = self.encounter()
        r.write_round(enc, codes=[
            r.row('45385', 'ready', reason='Claude Fable 5.2 read the note: a polyp was removed by cold snare.',
                  check_reason='Anthropic agrees, and claude-fable-5-2 found the snare.'),
            r.row('45380', 'needs_review', modifiers=['59'], agrees=False,
                  reason='Gemini (gemini-4-argon) saw a separate biopsy site.',
                  check_reason='The Anthropic checker disagrees: AnthropicTimeout.'),
            r.row('45378', 'needs_answer', question='Fable asks: was the cecum reached?',
                  reason='A diagnostic colonoscopy is documented.')],
            questions=[{'id': 'q1', 'text': 'Per Anthropic policy, was the cecum reached?', 'codes': ['45378'],
                        'source': 'reader'}],
            problems=['Claude found no signature.', 'GeminiTimeout and fable_unknown were recorded by Gemini.'],
            citations={'L1': [{'text': QUOTE, 'page': 2, 'source': 'reader'}]})
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        for kind in ('draft', 'approved'):
            with self.subTest(kind=kind):
                data, response, _ = self.made(enc, kind)
                reading, hits = self.scanned(enc, data, response, f'{kind}.pdf')
                self.assertEqual(hits, [])
                self.assertGreaterEqual(len(reading.pages), 2)
                self.assertEqual(reading.metadata['Author'], 'QuillMD CPT Studio')  # the metadata was read and scanned
                text = flat(data)
                self.assertIn(f'“{QUOTE}”', text)  # the document's own words, exactly
                self.assertIn('Reason: The system read the note: a polyp was removed by cold snare.', text)
                # the control: with no quotation set aside, the scanner finds the name in the quotation and nowhere else
                bare = self.sc.scan_pdf(reading, self.sc.scan_context(), f'{kind}.pdf')
                self.assertEqual({hit['id'] for hit in bare}, {'provider_name'})
                self.assertTrue(all('Claude Example' in hit['match'] for hit in bare), bare)
        draft = flat(self.made(enc, 'draft')[0])
        for words in ('Second check: agrees. The system agrees, and the system found the snare.',
                      'Reason: The system (the system) saw a separate biopsy site.',
                      'Question: Per the system policy, was the cecum reached?',
                      '– The system found no signature.'):
            self.assertIn(words, draft)


class SecondCheckLineTests(PhysicianReportScanCase):
    def test_a_line_the_second_check_added_appears_in_the_draft_in_its_own_words(self):
        enc = self.encounter()
        added = {**r.row('45378', 'needs_review', listed_by='checker',
                         reason='The second check read a diagnostic colonoscopy to the cecum.',
                         evidence=[{'quote': 'colonoscopy to the cecum', 'page': 1}]), 'listed_status': 'ready'}
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='A polyp was removed by cold snare.'), added])
        self.assertEqual([row['line'] for row in state.latest_round(enc).codes], ['L1', 'M1'])
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        data, response, _ = self.made(enc, 'draft')
        self.assertEqual(self.scanned(enc, data, response, 'draft.pdf')[1], [])
        text = flat(data)
        own = customer.ADDED_WITH_STATUS.format(status='ready for approval')
        for words in ('45378', 'Line M1 · Modifiers: none', 'Needs your review', 'Decision needed',
                      'Reason: The second check read a diagnostic colonoscopy to the cecum.',
                      f'Second check: no verdict. {own}', '“colonoscopy to the cecum”',
                      "The coding review's quotation, not checked against the document · Page 1",
                      '1 code line has no saved decision: 45378 (M1).'):
            self.assertIn(words, text)
        # once approved, the approved PDF lists it with who approved it
        self.assertEqual(self.decide(enc, 'M1', '45378', 'approve').status_code, 201)
        data, response, _ = self.made(enc, 'approved')
        self.assertEqual(self.scanned(enc, data, response, 'approved.pdf')[1], [])
        text = flat(data)
        self.assertIn('Line M1 · Modifiers: none', text)
        self.assertEqual(text.count(f'Approved by {self.reviewer.label()}'), 4)  # two code rows, two evidence headings


class TriggerTests(PhysicianReportScanCase):
    def test_a_round_made_after_answers_or_after_a_retry_names_its_trigger(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45378', 'needs_answer', question='Was the cecum reached?')],
                      questions=[{'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45378'], 'source': 'reader'}])
        r.write_round(enc, codes=[r.row('45378', 'ready', reason='The cecum was reached.')], trigger=Round.ANSWERS)
        data, response, report = self.made(enc, 'draft')
        self.assertIn('-r2-', report['filename'])
        self.assertEqual(self.scanned(enc, data, response, 'draft.pdf')[1], [])
        text = flat(data)
        self.assertIn('Review 2, after the practice answered questions, finished', text)
        self.assertIn('Coding review 2', text)
        r.write_round(enc, codes=[r.row('45378', 'ready', reason='The cecum was reached.')], trigger=Round.RETRY)
        data, response, report = self.made(enc, 'draft')
        self.assertIn('-r3-', report['filename'])
        self.assertIn('Review 3, after a retry, finished', flat(data))
        self.assertEqual(self.scanned(enc, data, response, 'draft.pdf')[1], [])


class EarlierRoundTests(PhysicianReportScanCase):
    def test_an_earlier_rounds_pdf_naming_a_vendor_in_a_modifier_fails_the_scan_once_a_later_round_replaces_it(self):
        """Refutation L3-2: once a later round replaces the one a PDF was made from, the PDF stays listed and the JSON no
        longer holds its words, so the PDF path is its only reader. A modifier "Claude" (part of the code line, never
        filtered) printed outside the quotation - wrapped onto a line of its own beside the cited "Dr. Claude Example
        ..." - is the product's wording, and the scan finds it."""
        enc = self.encounter()
        modifiers = ['59', 'XS', 'XU', 'PT', 'KX', 'GA', 'RT', 'Claude']
        citations = {'L1': [{'text': QUOTE, 'page': 2, 'source': 'reader'}]}
        r.write_round(enc, codes=[r.row('45385', 'ready', modifiers=modifiers, reason='A polyp was removed by cold snare.')],
                      citations=citations)
        earlier, _, report = self.made(enc, 'draft')
        r.write_round(enc, codes=[r.row('45385', 'ready', modifiers=['59'], reason='A polyp was removed by cold snare.')],
                      citations=citations, trigger=Round.ANSWERS)
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        self.assertEqual([(item['id'], item['current']) for item in payload['reports']], [(report['id'], False)])
        ctx = self.sc.scan_context(self.sc.quotations(payload))
        self.assertEqual(self.sc.scan_json(payload, ctx), [])  # the JSON shows round 2: no modifier "Claude"
        reading = self.sc.read_pdf(earlier)
        lines = [(page, index, line.strip()) for page, text in enumerate(reading.pages, start=1)
                 for index, line in enumerate(text.split('\n'), start=1)]
        printed = [(page, index) for page, index, line in lines if line.endswith('Claude') and 'Example' not in line]
        self.assertEqual(len(printed), 1, lines)  # the modifier, printed outside every quotation
        self.assertIn(f'“{QUOTE}”', flat(earlier))  # and the quotation, with the same name, exactly
        hits = self.sc.scan_pdf(reading, ctx, 'draft.pdf')
        self.assertEqual([(hit['id'], hit['where']) for hit in hits],
                         [('provider_name', f'draft.pdf page {printed[0][0]} line {printed[0][1]}')])


class PageBreakTests(PhysicianReportScanCase):
    """Refutation L6-3: a phrase the page break cuts in two - "tool" the last word of a page, "calls" the first of the
    next, the running header and footer between them in the text - is read as one."""
    FILLER = 600

    def render(self, plant=None):
        words = [f'w{number:03d}' for number in range(self.FILLER)]
        if plant is not None:
            words[plant], words[plant + 1] = 'tool', 'calls'
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='The coding review notes ' + ' '.join(words) + '.',
                                        check_reason='Agreed.')],
                      citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}]})
        data, _, _ = self.made(enc, 'draft')
        return enc, self.sc.read_pdf(data)

    @staticmethod
    def words(text):
        return re.findall(r'\bw\d{3}\b|\btool\b|\bcalls\b', text)

    def test_a_phrase_the_page_break_cuts_in_two_is_found(self):
        _, reading = self.render()
        breaks = [(number, self.words(page)[-1]) for number, page in enumerate(reading.pages[:-1])
                  if self.words(page) and self.words(reading.pages[number + 1])]
        self.assertTrue(breaks, 'the reason did not flow over a page break')
        page, last = breaks[0]
        found = None
        for shift in (0, -1, 1, -2, 2, -3, 3):  # "tool calls" is about as wide as the two tokens it replaces
            enc, reading = self.render(int(last[1:]) + shift)
            if self.words(reading.pages[page])[-1:] == ['tool'] and self.words(reading.pages[page + 1])[:1] == ['calls']:
                found = (enc, reading)
                break
        self.assertIsNotNone(found, 'no plant put "tool" at the foot of a page and "calls" at the head of the next')
        enc, reading = found
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        hits = self.sc.scan_pdf(reading, self.sc.scan_context(self.sc.quotations(payload)), 'draft.pdf')
        self.assertEqual([hit['id'] for hit in hits], ['tool_call'])
        self.assertRegex(hits[0]['where'], rf'^draft\.pdf page {page + 1} line \d+ to page {page + 2} line \d+$')


class ViewerTests(PhysicianReportScanCase):
    def test_a_viewers_pdf_holds_what_a_reviewers_does(self):
        enc = self.encounter()
        r.write_round(enc, codes=[
            r.row('45385', 'ready', reason='A polyp was removed by cold snare.'),
            r.row('45380', 'needs_review', modifiers=['59'], reason='A separate site was biopsied.')],
            problems=['Bowel preparation quality was not recorded.'],
            citations={'L1': [{'text': QUOTE, 'page': 2, 'source': 'reader'}]})
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        moment = datetime(2026, 11, 21, 14, 2, 9, tzinfo=dt_timezone.utc)
        clock = mock.Mock(now=mock.Mock(return_value=moment))  # exports' clock only, not the session's
        prepared = '21 Nov 2026, 14:02 UTC by {}'
        for kind in ('draft', 'approved'):
            with self.subTest(kind=kind):
                with mock.patch.object(exports, 'timezone', clock):
                    reviewers, _, _ = self.made(enc, kind)
                    viewers, response, report = self.made(enc, kind, user=self.viewer)  # any member may export
                self.assertEqual(self.scanned(enc, viewers, response, f'{kind}.pdf')[1], [])
                self.assertIn(prepared.format(self.viewer.label()), flat(viewers))
                # the same saved state gives the same report; only who prepared it differs
                self.assertEqual(flat(viewers), flat(reviewers).replace(prepared.format(self.reviewer.label()),
                                                                        prepared.format(self.viewer.label())))
                self.assertEqual(PdfReader(io.BytesIO(viewers)).metadata, PdfReader(io.BytesIO(reviewers)).metadata)
                self.assertTrue(report['filename'].endswith('.pdf'))
