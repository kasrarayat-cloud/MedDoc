"""Customer exports (BUILD-SPEC 8; studio.exports): the physician PDF report, the only report made since the owner's
direction of 2026-11-21, as the draft and the approved report through the API - what each lists (read with pypdf, in
the PDF's own words), the readiness rules, the stored bytes served exactly with their sha256 and one export.created
audit row, the earlier marker of an export made from an earlier round or before a later decision, the display hygiene,
the tenancy of a download, the refusal of a kind or format that is not one (TXT and CSV included: none is made any
more), and the TXT and CSV exports an earlier release stored, still listed and served exactly as stored. The PDF's
layout and wording in depth have their own modules: tests/test_physician_report.py and
tests/test_physician_report_scan.py. Synthetic data only."""
import hashlib
import io
import json
import re

from django.test import TestCase
from pypdf import PdfReader

from studio import decisions, exports, models, state
from tests.support import rounds as r

Export = models.ExportArtifact
ACK = decisions.ACKNOWLEDGEMENTS
WHEN = r'\d{1,2} [A-Z][a-z]{2} \d{4}, \d\d:\d\d UTC'  # a saved time as the report prints it
ROW = re.compile(r'(?<!\S)\d\d (\d{5}) (?:CPT suggestion|Approved code) ')  # a line of the report's codes table
ENTRY = re.compile(r'(?<!\S)\d\d (\d{5}) / ')  # a code's entry among the report's reasons
ROWS_END = ('What still needs your decision', 'REVIEWER APPROVAL RECORD', 'APPROVED BY', 'THE REASONS, IN THE RECORD')
ENTRIES_END = ('DOCUMENTATION NOTES', 'REVIEW SCOPE')


def pdf_text(data: bytes) -> str:
    """A stored PDF's text as CustomerCase.report_text reads it: every page, joined, white space squeezed."""
    return ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages).split())


def own_part(text: str, code: str, start, ends) -> str:
    """The part of ``text`` that is ``code``'s own: from its start (``start``: the pattern of a row or of an entry) up
    to the next start or the first of ``ends``, so a check about one code never reads another code's words."""
    found = [match for match in start.finditer(text) if match.group(1) == code]
    assert len(found) == 1, (code, len(found))
    after = found[0].end()
    stops = [match.start() for match in start.finditer(text, after)][:1]
    stops += [position for position in (text.find(end, after) for end in ends) if position != -1]
    return text[found[0].start():min(stops, default=len(text))]


class ExportCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.encounter(title='Synthetic EGD and colonoscopy')
        self.round = r.write_round(self.enc, codes=[
            r.row('45385', 'ready', reason='A 9 mm polyp was removed with a cold snare (page 2).',
                  check_reason='The snare is documented.'),
            r.row('45380', 'needs_review', modifiers=['XS'], agrees=False,
                  reason='=HYPERLINK("http://x") a separate lesion', check_reason='XS fits less well than 59.'),
            r.row('43239', 'needs_answer', question='Which site was biopsied?', reason='Biopsy \x1b[2Jsite unclear.'),
            r.row('43251', 'not_supported', reason='Claude Fable 5.2 found no snare in the upper tract.')],
            questions=[{'id': 'q1', 'text': 'Which site was biopsied?', 'codes': ['43239'], 'source': 'reader'}],
            problems=['Bowel preparation quality was not recorded.'],
            citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}]})
        self.client = self.client_for(self.reviewer)

    def post(self, path, body, client=None):
        return (client or self.client).post(path, data=json.dumps(body), content_type='application/json')

    def export(self, kind, fmt='pdf', client=None):
        """POST an export as the page sends it: naming the round it shows, the latest (FIX-SPEC-2 section 5)."""
        number = state.latest_round(self.enc).number
        return self.post(f'/api/encounters/{self.enc.pk}/reports', {'kind': kind, 'fmt': fmt, 'round': number},
                         client=client)

    def line_of(self, code):
        return next(row['line'] for row in self.round.codes if row['code'] == code)

    def approve(self, code, user=None, kind='human'):
        client = self.client_for(user) if user else self.client
        response = self.post(f'/api/encounters/{self.enc.pk}/decisions',
                             {'round': self.round.number, 'line': self.line_of(code), 'code': code,
                              'action': 'approve', 'acknowledgement': ACK[kind]}, client=client)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def download(self, row, client=None):
        response = (client or self.client).get(row['download_url'])
        self.assertEqual(response.status_code, 200)
        return response

    def row_of(self, text, code):
        """``code``'s line of the codes table: its status, line, modifiers, units and saved decision."""
        return own_part(text, code, ROW, ROWS_END)

    def entry_of(self, text, code):
        """``code``'s entry among the reasons: its quotes with their pages, reason, second check and question."""
        return own_part(text, code, ENTRY, ENTRIES_END)


class DraftTests(ExportCase):
    def test_the_draft_report_lists_every_code_with_its_status_reason_second_check_and_quotes(self):
        response = self.export('draft')
        self.assertEqual(response.status_code, 201, response.content)
        row = response.json()
        self.assertEqual(set(row), {'id', 'kind', 'fmt', 'filename', 'generated_at', 'download_url', 'current'})
        self.assertEqual((row['kind'], row['fmt'], row['current']), ('draft', 'pdf', True))
        self.assertRegex(row['filename'], r'^CPT-Studio-draft-r1-\d{8}T\d{6}\.pdf$')
        download = self.download(row)
        self.assertEqual(download['Content-Type'], 'application/pdf')
        self.assertEqual(download['Content-Disposition'], f'attachment; filename="{row["filename"]}"')
        text = pdf_text(download.content)
        pages = [' '.join((page.extract_text() or '').split())
                 for page in PdfReader(io.BytesIO(download.content)).pages]
        for number, page in enumerate(pages, start=1):  # the synthetic notice frames every page, as the banners did
            with self.subTest(page=number):
                self.assertIn('Synthetic data · Not for billing or claims', page)
        for expected in ('DRAFT · REVIEW REQUIRED', 'CPT coding summary',
                         'Report format PDF · cpt-studio-customer-export@3',
                         'What still needs your decision Question: Which site was biopsied?',
                         'DOCUMENTATION NOTES – Bowel preparation quality was not recorded.'):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        # the encounter, its date of service and insurance, as the identity strip under its labels holds them
        strip = text[text.index('DOCUMENT DATE OF SERVICE INSURANCE SPECIALTY ENCOUNTER'):text.index('CPT SUGGESTIONS')]
        for expected in ('Synthetic EGD and colonoscopy', '2 Nov 2026', 'Medicare'):
            with self.subTest(strip=expected):
                self.assertIn(expected, strip)
        self.assertRegex(text, rf'Prepared {WHEN} by {re.escape(self.reviewer.label())}(?!\w)')
        self.assertRegex(text, rf'Coding review Review 1, finished {WHEN}')
        # every code, numbered in the round's order, each line with its own status, modifiers and units
        starts = [text.index(f'{number:02d} {code} CPT suggestion')
                  for number, code in enumerate(('45385', '45380', '43239', '43251'), start=1)]
        self.assertEqual(starts, sorted(starts))
        for code, expected in (('45385', ('Ready for approval', 'Line L1 · Modifiers: none', 'UNITS 1')),
                               ('45380', ('Needs your review', 'Line L2 · Modifiers: XS', 'UNITS 1')),
                               ('43239', ('Needs your answer', 'Line L3', 'UNITS 1')),
                               ('43251', ('Not supported', 'Line L4', 'UNITS 1'))):
            line = self.row_of(text, code)
            for words in expected:
                with self.subTest(code=code, words=words):
                    self.assertIn(words, line)
        entries = {code: self.entry_of(text, code) for code in ('45385', '45380', '43239', '43251')}
        for code, expected in (('45385', ('“removed with a cold snare” Page 2',
                                          'Reason: A 9 mm polyp was removed with a cold snare (page 2).',
                                          'Second check: agrees. The snare is documented.')),
                               ('45380', ('Second check: disagrees. XS fits less well than 59.',)),
                               ('43239', ('Question: Which site was biopsied?',
                                          # a control character in saved text never reaches the report
                                          'Reason: Biopsy [2Jsite unclear.')),
                               # display hygiene: the coding review's vendor name reads "the system"
                               ('43251', ('Reason: The system found no snare in the upper tract.',))):
            for words in expected:
                with self.subTest(code=code, entry=words):
                    self.assertIn(words, entries[code])
        self.assertNotIn('\x1b', text)
        self.assertNotIn('Claude', text)
        stored = Export.objects.get(pk=row['id'])
        self.assertEqual(bytes(stored.content), download.content)
        self.assertEqual(stored.sha256, hashlib.sha256(download.content).hexdigest())
        self.assertNotIn('X-Content-SHA256', download)
        event = models.AuditEvent.objects.get(encounter=self.enc, event='export.created')
        self.assertEqual((event.data['kind'], event.data['fmt'], event.data['export']), ('draft', 'pdf', row['id']))

    def test_the_draft_report_shows_each_lines_current_decision(self):
        """A line's current decision, who made it and when, beside its status; no decision where none is saved."""
        self.approve('45385')
        text = self.report_text(self.enc, 'draft')
        self.assertIn('DRAFT · REVIEW REQUIRED', text)
        starts = [text.index(f'{number:02d} {code} CPT suggestion')
                  for number, code in enumerate(('45385', '45380', '43239', '43251'), start=1)]
        self.assertEqual(starts, sorted(starts))
        approved = self.row_of(text, '45385')
        self.assertRegex(approved, rf'Approved by {re.escape(self.reviewer.label())} · {WHEN}')
        for words in ('Ready for approval', 'Line L1 · Modifiers: none', 'UNITS 1'):
            with self.subTest(approved=words):
                self.assertIn(words, approved)
        self.assertIn('“removed with a cold snare” Page 2', self.entry_of(text, '45385'))
        for code, status, words in (('45380', 'Decision needed', 'Line L2 · Modifiers: XS'),
                                    ('43239', 'Answer needed', 'Line L3'),
                                    ('43251', 'Not supported', 'Line L4')):
            with self.subTest(undecided=code):
                line = self.row_of(text, code)
                self.assertIn(status, line)
                self.assertIn(words, line)
                self.assertNotRegex(line, r'(?:Approved|Rejected) by')
        entry = self.entry_of(text, '45380')
        self.assertIn('Second check: disagrees. XS fits less well than 59.', entry)
        self.assertIn('Reason: =HYPERLINK("http://x") a separate lesion', entry)  # printed as text, never evaluated
        self.assertIn('1 approved · 0 rejected', text)

    def test_nothing_is_exported_before_the_round_is_done(self):
        r.write_round(self.enc, state_=models.CodingRound.RUNNING)
        response = self.export('draft')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {'error': exports.NOTHING_YET,
                                           'details': {'blockers': ['The coding review has not finished.']}})
        # an unknown kind or format is refused before the round is read (the PDF is the only format since 2026-11-21)
        for body in ({'kind': 'reviewed', 'fmt': 'pdf', 'round': 2}, {'kind': 'draft', 'fmt': 'docx', 'round': 2},
                     {'kind': 'approved', 'fmt': 'PDF', 'round': 2}, {'kind': 'draft', 'round': 2}):
            with self.subTest(body=body):
                refused = self.post(f'/api/encounters/{self.enc.pk}/reports', body)
                self.assertEqual((refused.status_code, refused.json()['error']),
                                 (400, 'Choose a draft or an approved PDF report.'))
        self.assertEqual(exports.FORMAT_REQUIRED, 'Choose a draft or an approved PDF report.')
        self.assertEqual(Export.objects.count(), 0)


class ApprovedTests(ExportCase):
    def test_the_approved_export_needs_an_approval_and_lists_approved_codes_only(self):
        refused = self.export('approved')
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.json(), {'error': exports.APPROVED_NOT_YET,
                                          'details': {'blockers': ['No code has been approved.']}})
        self.approve('45385')
        first = self.approve('45380', user=self.agent, kind='agent')
        reject = self.post(f'/api/encounters/{self.enc.pk}/decisions',
                           {'round': 1, 'line': 'L2', 'code': '45380', 'action': 'revoke', 'decision': first['id']},
                           client=self.client_for(self.agent))
        self.assertEqual(reject.status_code, 201)
        self.approve('45380', user=self.agent, kind='agent')
        row = self.export('approved').json()
        text = pdf_text(self.download(row).content)
        self.assertIn('APPROVED CODES', text)
        self.assertIn('Approved CPT codes', text)
        # the two approved lines, in order, and no other
        self.assertEqual([match.group(1) for match in ROW.finditer(text)], ['45385', '45380'])
        self.assertLess(text.index('01 45385 Approved code'), text.index('02 45380 Approved code'))
        human = self.row_of(text, '45385')
        self.assertRegex(human, rf'Approved by {re.escape(self.reviewer.label())} {WHEN}')
        self.assertIn('Line L1 · Modifiers: none', human)
        self.assertIn('UNITS 1', human)
        self.assertNotIn(exports.AGENT_LINE, human)  # a human's approval
        agent = self.row_of(text, '45380')
        self.assertRegex(agent, rf'Approved by Reviewbot \(automated agent\) {WHEN}')
        self.assertIn('Line L2 · Modifiers: XS', agent)
        self.assertIn('UNITS 1', agent)
        self.assertIn(exports.AGENT_LINE, agent)  # an agent's approval
        self.assertNotIn('43239', text)
        self.assertNotIn('43251', text)
        self.assertNotIn('What still needs your decision', text)  # questions belong to the draft
        self.assertNotIn('Which site was biopsied?', text)


class StoredAndEarlierTests(ExportCase):
    def test_a_download_serves_the_stored_bytes_and_an_earlier_rounds_export_is_marked_earlier(self):
        first = self.export('draft').json()
        stored = bytes(Export.objects.get(pk=first['id']).content)
        r.write_round(self.enc, codes=[r.row('45385', 'ready')])  # a new round (after answers)
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']], [(first['id'], False)])
        self.assertEqual(self.download(first).content, stored)  # still served, exactly as stored
        second = self.export('draft').json()
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']],
                         [(second['id'], True), (first['id'], False)])
        self.assertRegex(pdf_text(stored), rf'Coding review Review 1, finished {WHEN}')
        self.assertEqual(payload['activity'][-1]['text'], f'Draft download made by {self.reviewer.label()}.')

    def test_an_export_made_before_a_later_decision_on_the_same_round_is_marked_earlier(self):
        self.approve('45385')
        approved = self.export('approved').json()
        self.assertTrue(approved['current'])
        self.approve('45380')  # a later decision on the same round changes what an approved export would list
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']], [(approved['id'], False)])
        again = self.export('approved').json()
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']],
                         [(again['id'], True), (approved['id'], False)])

    def test_another_workspace_and_an_unknown_id_answer_404(self):
        row = self.export('draft').json()
        self.assertEqual(self.client_for(self.outsider).get(row['download_url']).status_code, 404)
        self.assertEqual(self.client.get('/api/reports/f6100000-0000-4000-8000-000000000001/download').status_code, 404)
        legacy = self.client.get('/api/reports/not-a-uuid/download')
        self.assertEqual(legacy.status_code, 404)


class TxtAndCsvTests(ExportCase):
    """Owner direction 2026-11-21: the PDF is the only report. No TXT or CSV is made any more; those an earlier release
    stored are records, listed and served exactly as stored."""

    def test_a_txt_or_csv_request_is_refused_and_stores_nothing(self):
        self.approve('45385')  # both kinds are available, so only the format can refuse a request
        for kind in ('draft', 'approved'):
            for fmt in ('txt', 'csv'):
                with self.subTest(kind=kind, fmt=fmt):
                    refused = self.export(kind, fmt)
                    self.assertEqual((refused.status_code, refused.json()), (400, {'error': exports.FORMAT_REQUIRED,
                                                                                   'details': {}}))
        for fmt in ('txt', 'csv'):  # and below the API: exports.create makes neither
            with self.subTest(create=fmt), self.assertRaisesMessage(ValueError, exports.FORMAT_REQUIRED):
                exports.create(self.enc, self.reviewer, 'draft', fmt, round_number=self.round.number)
        self.assertEqual(Export.objects.count(), 0)
        self.assertFalse(models.AuditEvent.objects.filter(event='export.created').exists())
        self.assertEqual(self.client.get(f'/api/encounters/{self.enc.pk}').json()['reports'], [])
        for kind in ('draft', 'approved'):  # the control: the same requests naming the PDF are made
            with self.subTest(control=kind):
                self.assertEqual(self.export(kind).status_code, 201)
        self.assertEqual(sorted(Export.objects.values_list('kind', 'fmt')), [('approved', 'pdf'), ('draft', 'pdf')])
        self.assertEqual(models.AuditEvent.objects.filter(event='export.created').count(), 2)

    def test_a_txt_and_a_csv_export_stored_earlier_are_listed_and_served_as_stored(self):
        sc = r.scan_customer()
        contents = {'txt': 'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\nCPT STUDIO — CODES — DRAFT, NOT APPROVED\n'
                           '1. 45385 — Ready for approval — units 1 — modifiers: none\n'.encode('utf-8'),
                    'csv': '"kind","code","units","decision"\r\n"approved","45385","1","approved"\r\n'.encode('utf-8')}
        stored = {}
        for kind, fmt in (('draft', 'txt'), ('approved', 'csv')):  # as an earlier release stored them
            content = contents[fmt]
            stored[fmt] = Export.objects.create(
                encounter=self.enc, round=self.round, kind=kind, fmt=fmt,
                filename=f'CPT-Studio-{kind}-r1-20261120T101500.{fmt}', content=content,
                sha256=hashlib.sha256(content).hexdigest(), created_by=self.reviewer)
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual(sc.shape_problems(payload, sc.CONTRACT['encounter']), [])  # the contract's fmt names both
        listed = {report['id']: report for report in payload['reports']}
        self.assertEqual(set(listed), {str(export.pk) for export in stored.values()})
        for fmt, content_type in (('txt', 'text/plain; charset=utf-8'), ('csv', 'text/csv; charset=utf-8')):
            with self.subTest(fmt=fmt):
                export = stored[fmt]
                report = listed[str(export.pk)]
                self.assertEqual((report['kind'], report['fmt'], report['filename'], report['download_url']),
                                 (export.kind, fmt, export.filename, f'/api/reports/{export.pk}/download'))
                got = self.download(report)
                self.assertEqual(got.content, contents[fmt])
                self.assertEqual(got.content, bytes(Export.objects.get(pk=export.pk).content))
                self.assertEqual(hashlib.sha256(got.content).hexdigest(), export.sha256)
                self.assertEqual(got['Content-Type'], content_type)
                self.assertEqual(got['Content-Disposition'], f'attachment; filename="{export.filename}"')
                self.assertEqual(self.client_for(self.outsider).get(report['download_url']).status_code, 404)
