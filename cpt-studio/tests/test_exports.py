"""Customer exports (BUILD-SPEC 8; studio.exports): the draft and approved exports as TXT and CSV, the readiness rules,
the SYNTHETIC banners, formula neutralising and control-character escaping, stored bytes served exactly, the earlier
marker of an export made from an earlier round, the display hygiene and the tenancy of a download. Synthetic data
only."""
import csv
import hashlib
import io
import json

from django.test import TestCase

from studio import decisions, exports, models
from tests.support import rounds as r

Export = models.ExportArtifact
ACK = decisions.ACKNOWLEDGEMENTS


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
            citations={'45385': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}]})
        self.client = self.client_for(self.reviewer)

    def post(self, path, body, client=None):
        return (client or self.client).post(path, data=json.dumps(body), content_type='application/json')

    def export(self, kind, fmt, client=None):
        return self.post(f'/api/encounters/{self.enc.pk}/reports', {'kind': kind, 'fmt': fmt}, client=client)

    def approve(self, code, user=None, kind='human'):
        client = self.client_for(user) if user else self.client
        response = self.post(f'/api/encounters/{self.enc.pk}/decisions',
                             {'code': code, 'action': 'approve', 'acknowledgement': ACK[kind]}, client=client)
        self.assertEqual(response.status_code, 201, response.content)

    def download(self, row, client=None):
        response = (client or self.client).get(row['download_url'])
        self.assertEqual(response.status_code, 200)
        return response


class DraftTests(ExportCase):
    def test_the_draft_txt_lists_every_code_between_two_banners(self):
        response = self.export('draft', 'txt')
        self.assertEqual(response.status_code, 201, response.content)
        row = response.json()
        self.assertEqual(set(row), {'id', 'kind', 'fmt', 'filename', 'generated_at', 'download_url', 'current'})
        self.assertEqual((row['kind'], row['fmt'], row['current']), ('draft', 'txt', True))
        self.assertRegex(row['filename'], r'^CPT-Studio-draft-r1-\d{8}T\d{6}\.txt$')
        download = self.download(row)
        self.assertEqual(download['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(download['Content-Disposition'], f'attachment; filename="{row["filename"]}"')
        text = download.content.decode('utf-8')
        lines = text.splitlines()
        self.assertEqual(lines[0], exports.SYNTHETIC_LINE)
        self.assertEqual(lines[-1], exports.SYNTHETIC_LINE)
        for expected in ('CPT STUDIO — CODES — DRAFT, NOT APPROVED', 'Export format: cpt-studio-customer-export@3',
                         'Encounter: Synthetic EGD and colonoscopy', 'Date of service: 2026-11-02', 'Insurance: Medicare',
                         f'by {self.reviewer.label()}', '1. 45385 — Ready for approval — units 1 — modifiers: none',
                         '   Reason: A 9 mm polyp was removed with a cold snare (page 2).',
                         '   Second check: agrees. The snare is documented.',
                         '   Quote: "removed with a cold snare" (page 2)',
                         '2. 45380 — Needs your review — units 1 — modifiers: XS',
                         '   Second check: disagrees. XS fits less well than 59.',
                         '3. 43239 — Needs your answer', '   Question: Which site was biopsied?',
                         '4. 43251 — Not supported', 'Questions for the practice', '- Which site was biopsied?',
                         'Documentation notes', '- Bowel preparation quality was not recorded.'):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        self.assertRegex(text, r'Coding review: 1, finished \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ')
        self.assertIn('Reason: Biopsy \\x1b[2Jsite unclear.', text)  # the control character shown escaped
        self.assertNotIn('\x1b', text)
        self.assertIn('Reason: The system found no snare in the upper tract.', text)  # display hygiene
        self.assertNotIn('Claude', text)
        stored = Export.objects.get(pk=row['id'])
        self.assertEqual(bytes(stored.content), download.content)
        self.assertEqual(stored.sha256, hashlib.sha256(download.content).hexdigest())
        self.assertNotIn('X-Content-SHA256', download)
        event = models.AuditEvent.objects.get(encounter=self.enc, event='export.created')
        self.assertEqual((event.data['kind'], event.data['fmt'], event.data['export']), ('draft', 'txt', row['id']))

    def test_the_draft_csv_has_the_columns_banner_rows_and_neutralised_cells(self):
        self.approve('45385')
        row = self.export('draft', 'csv').json()
        download = self.download(row)
        self.assertEqual(download['Content-Type'], 'text/csv; charset=utf-8')
        raw = download.content.decode('utf-8')
        self.assertTrue(raw.endswith('\r\n'))
        rows = list(csv.reader(io.StringIO(raw, newline='')))
        self.assertEqual(rows[0], list(exports.CSV_COLUMNS))
        self.assertEqual(rows[0], ['kind', 'code', 'units', 'modifiers', 'status', 'reason', 'quotes', 'decision',
                                   'decided_by', 'decided_at'])
        self.assertEqual((rows[1][0], rows[-1][0]), (exports.SYNTHETIC_LINE, exports.SYNTHETIC_LINE))
        self.assertIn('coding review 1', rows[1][5])
        self.assertIn('insurance: Medicare', rows[1][5])
        body = {line[1]: dict(zip(rows[0], line)) for line in rows[2:-1]}
        self.assertEqual(list(body), ['45385', '45380', '43239', '43251'])
        self.assertEqual({key: body['45385'][key] for key in ('kind', 'units', 'modifiers', 'status', 'quotes',
                                                              'decision', 'decided_by')},
                         {'kind': 'draft', 'units': '1', 'modifiers': '', 'status': 'ready',
                          'quotes': '"removed with a cold snare" (page 2)', 'decision': 'approved',
                          'decided_by': self.reviewer.label()})
        self.assertRegex(body['45385']['decided_at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertTrue(body['45380']['reason'].startswith("'=HYPERLINK"))  # a formula never runs
        self.assertIn('Second check: disagrees. XS fits less well than 59.', body['45380']['reason'])
        self.assertEqual(body['45380']['modifiers'], 'XS')
        self.assertIn('\\x1b[2J', body['43239']['reason'])
        self.assertEqual(body['43239']['decision'], '')
        for line in rows:
            for cell in line:
                self.assertFalse(cell.startswith(exports.FORMULA_PREFIXES), cell)

    def test_nothing_is_exported_before_the_round_is_done(self):
        r.write_round(self.enc, state_=models.CodingRound.RUNNING)
        response = self.export('draft', 'txt')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {'error': exports.NOTHING_YET,
                                           'details': {'blockers': ['The coding review has not finished.']}})
        refused = self.post(f'/api/encounters/{self.enc.pk}/reports', {'kind': 'reviewed', 'fmt': 'pdf'})
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(Export.objects.count(), 0)


class ApprovedTests(ExportCase):
    def test_the_approved_export_needs_an_approval_and_lists_approved_codes_only(self):
        refused = self.export('approved', 'txt')
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.json(), {'error': exports.APPROVED_NOT_YET,
                                          'details': {'blockers': ['No code has been approved.']}})
        self.approve('45385')
        self.approve('45380', user=self.agent, kind='agent')
        reject = self.post(f'/api/encounters/{self.enc.pk}/decisions', {'code': '45380', 'action': 'revoke'},
                           client=self.client_for(self.agent))
        self.assertEqual(reject.status_code, 201)
        self.approve('45380', user=self.agent, kind='agent')
        row = self.export('approved', 'txt').json()
        text = self.download(row).content.decode('utf-8')
        self.assertIn('CPT STUDIO — APPROVED CODES', text)
        self.assertIn('1. 45385 — units 1 — modifiers: none', text)
        self.assertRegex(text, rf'   Approved by {self.reviewer.label()} \(human\) at \d{{4}}-')
        self.assertIn('2. 45380 — units 1 — modifiers: XS', text)
        self.assertRegex(text, r'   Approved by Reviewbot \(automated agent\) \(agent\) at \d{4}-')
        self.assertIn(exports.AGENT_LINE, text)
        self.assertNotIn('43239', text)
        self.assertNotIn('43251', text)
        self.assertNotIn('Questions for the practice', text)
        csv_row = self.export('approved', 'csv').json()
        rows = list(csv.reader(io.StringIO(self.download(csv_row).content.decode('utf-8'), newline='')))
        self.assertEqual([line[1] for line in rows[2:-1]], ['45385', '45380'])
        self.assertEqual({line[7] for line in rows[2:-1]}, {'approved'})
        self.assertEqual(rows[3][8], 'Reviewbot (automated agent)')


class StoredAndEarlierTests(ExportCase):
    def test_a_download_serves_the_stored_bytes_and_an_earlier_rounds_export_is_marked_earlier(self):
        first = self.export('draft', 'txt').json()
        stored = bytes(Export.objects.get(pk=first['id']).content)
        r.write_round(self.enc, codes=[r.row('45385', 'ready')])  # a new round (after answers)
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']], [(first['id'], False)])
        self.assertEqual(self.download(first).content, stored)  # still served, exactly as stored
        second = self.export('draft', 'csv').json()
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']],
                         [(second['id'], True), (first['id'], False)])
        self.assertIn('Coding review: 1,', stored.decode('utf-8'))
        self.assertEqual(payload['activity'][-1]['text'], f'Draft download made by {self.reviewer.label()}.')

    def test_an_export_made_before_a_later_decision_on_the_same_round_is_marked_earlier(self):
        self.approve('45385')
        approved = self.export('approved', 'txt').json()
        self.assertTrue(approved['current'])
        self.approve('45380')  # a later decision on the same round changes what an approved export would list
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']], [(approved['id'], False)])
        again = self.export('approved', 'txt').json()
        payload = self.client.get(f'/api/encounters/{self.enc.pk}').json()
        self.assertEqual([(report['id'], report['current']) for report in payload['reports']],
                         [(again['id'], True), (approved['id'], False)])

    def test_another_workspace_and_an_unknown_id_answer_404(self):
        row = self.export('draft', 'txt').json()
        self.assertEqual(self.client_for(self.outsider).get(row['download_url']).status_code, 404)
        self.assertEqual(self.client.get('/api/reports/f6100000-0000-4000-8000-000000000001/download').status_code, 404)
        legacy = self.client.get('/api/reports/not-a-uuid/download')
        self.assertEqual(legacy.status_code, 404)
