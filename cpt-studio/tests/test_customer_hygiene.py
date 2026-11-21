"""What a customer is shown, beyond the codes (findings SEC-S4, SEC-S3, FG-5, FG-6, SEC-OPS-IDENTITY-TO-CUSTOMER): the
evidence quotes the coding review wrote pass the vendor-name filter like its other text, a question names only the codes
of its lines, the PDF report (the only export since the owner's direction of 2026-11-21) prints no control or
direction character, the draft report's questions and notes are filtered, a decided encounter (with its PDF reports
listed) is held to the contract, and a platform operator's act reads as CPT Studio's. Synthetic data only."""
import io
import json

from django.test import TestCase
from pypdf import PdfReader

from studio import models
from tests.support import operator as ops
from tests.support import rounds as r

Round = models.CodingRound
CONTROLS = ('\x0b', '\x0c', '\u202e', '\u202c', '\u2066', '\u2069', '\u200f', '\u061c', '\u2028', '\x85', '\r')
# what pypdf reads U+2066, U+2069, U+061C and ESC as when a PDF draws them (measured 2026-11-21, cleaning bypassed)
NO_GLYPH = '\x00'


class ModelTextTests(r.CustomerCase, TestCase):
    def test_an_evidence_quote_the_coding_review_wrote_passes_the_vendor_name_filter(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45378', 'needs_review', listed_by='checker', evidence=[
            {'quote': 'Claude Fable 5.2 (claude-fable-5-2) reviewed this note', 'page': 1}])],
            questions=[{'id': 'q1', 'text': 'Was the polyp retrieved?', 'codes': ['claude-fable-5-2'], 'lines': [],
                        'source': 'reader'}],
            citations={'_document': [{'text': 'SYNTHETIC NOTE', 'page': 1, 'source': 'reader'}]})
        payload = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()
        self.assertEqual(payload['codes'][0]['quotes'], [{'text': 'The system (the system) reviewed this note',
                                                          'page': 1}])
        self.assertEqual(payload['questions'][0]['codes'], [])
        text = self.report_text(enc, 'draft')
        self.assertIn('“The system (the system) reviewed this note”', text)
        self.assertNotIn('laude', text)

    def test_a_cited_passage_of_the_document_is_shown_exactly(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')],
                      citations={'L1': [{'text': 'Dr. Claude Example removed the polyp', 'page': 2,
                                         'source': 'reader'}]})
        codes = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        self.assertEqual(codes[0]['quotes'], [{'text': 'Dr. Claude Example removed the polyp', 'page': 2}])

    def test_the_draft_reports_questions_and_notes_pass_the_vendor_name_filter(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')],
                      questions=[{'id': 'q1', 'text': 'Per OpenAI policy, was the polyp retrieved?', 'codes': [],
                                  'lines': ['L1'], 'source': 'reader'}],
                      problems=['Claude Fable 5.2 found no signature.'])
        text = self.report_text(enc, 'draft')
        self.assertIn('What still needs your decision Question: Per the system policy, was the polyp retrieved?', text)
        self.assertIn('DOCUMENTATION NOTES – The system found no signature.', text)
        self.assertNotIn('OpenAI', text)
        self.assertNotIn('Claude', text)


class ControlCharacterTests(r.CustomerCase, TestCase):
    def raw_report_text(self, enc, kind):
        """The PDF report made through the API, every page's text as pypdf reads it, white space NOT squeezed (squeezing
        would hide a control that is white space, such as VT, FF, NEL, LS or CR)."""
        client = self.client_for(self.reviewer)
        made = client.post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': 1}), content_type='application/json')
        self.assertEqual(made.status_code, 201, made.content)
        data = client.get(made.json()['download_url']).content
        return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages)

    def test_control_and_direction_characters_never_reach_the_pdf_report(self):
        """A control or direction character the coding review wrote is never printed: each becomes a space or goes, so
        none can break, forge or reorder a printed line, and the words around it stay apart and in their stored order.
        (Measured 2026-11-21 with the report's cleaning bypassed: pypdf then reads U+202E, U+202C and U+200F as
        themselves and U+2066, U+2069 and U+061C as NUL, so the absence check sees them; a white-space control it would
        not see either way, so for those the check is the words around them staying apart.)"""
        enc = self.encounter()
        r.write_round(enc, codes=[r.row(
            '45385', 'ready', reason='Snare\x0bremoval\x0cdocumented \u202eDETCELES TON\u202c.\x85x\u2028y\rz',
            modifiers=['P\x0bT'], check_reason='Agreed\x0b.\u2066iso\u2069\u200f\u061c')],
            citations={'L1': [{'text': 'cold \x0csnare\r\nremoved', 'page': 1, 'source': 'reader'}]})
        for kind in ('draft', 'approved'):
            if kind == 'approved':
                self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
            with self.subTest(kind=kind):
                raw = self.raw_report_text(enc, kind)
                self.assertEqual({repr(char): raw.count(char) for char in CONTROLS + (NO_GLYPH,) if char in raw}, {})
                text = ' '.join(raw.split())
                self.assertIn('Line L1 · Modifiers: P T', text)
                self.assertIn('Reason: Snare removal documented DETCELES TON. x y z', text)
                self.assertIn('“cold snare removed” Page 1', text)
                if kind == 'draft':
                    self.assertIn('Second check: agrees. Agreed', text)


class DecidedContractTests(r.CustomerCase, TestCase):
    def test_a_decided_encounter_and_the_decision_answer_are_held_to_the_contract(self):
        sc = r.scan_customer()
        enc = self.done()
        approve = self.decide(enc, 'L1', '45385', 'approve', note='Checked.')
        reject = self.decide(enc, 'L3', '43239', 'reject')
        for response in (approve, reject):
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(set(response.json()), {'id', 'line', 'code', 'action', 'by', 'at', 'note'})
        for kind in ('draft', 'approved'):  # the PDF report, the only export made, is listed as the contract has it
            self.assertEqual(self.client_for(self.reviewer).post(
                f'/api/encounters/{enc.pk}/reports', data=json.dumps({'kind': kind, 'fmt': 'pdf', 'round': 1}),
                content_type='application/json').status_code, 201)
        response = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}')
        payload = response.json()
        self.assertEqual([code['decision']['action'] for code in payload['codes'] if code['decision']],
                         ['approve', 'reject'])
        self.assertEqual(sorted((item['kind'], item['fmt']) for item in payload['reports']),
                         [('approved', 'pdf'), ('draft', 'pdf')])
        self.assertEqual(sc.shape_problems(payload, sc.CONTRACT['encounter']), [])
        for decided in (approve, reject, response):
            hits = sc.scan_json(decided.json(), sc.scan_context())
            self.assertEqual([hit for hit in hits if hit['severity'] == 'hard'], [])


class OperatorActTests(r.CustomerCase, TestCase):
    def test_an_operators_retry_reads_as_cpt_studios_and_never_names_the_operator(self):
        enc = self.encounter()
        r.write_round(enc, state_=Round.FAILED, failure_kind='busy', error='The coding service is busy.')
        operator_user = r.f.user('platform-operator')
        models.User.objects.filter(pk=operator_user.pk).update(display_name='Dana Opsperson')
        response = ops.client(operator_user).post(f'/ops/encounters/{enc.pk}/retry')
        self.assertEqual(response.status_code, 303)
        texts = [item['text'] for item in
                 self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['activity']]
        self.assertIn('CPT Studio asked for the coding review again.', texts)
        self.assertNotIn('Opsperson', json.dumps(texts))
        stopped = self.client_for(self.reviewer).post(f'/api/encounters/{enc.pk}/stop')
        self.assertEqual(stopped.status_code, 200)
        self.assertIn(f'Stopped by {self.reviewer.label()}.',
                      [item['text'] for item in self.client_for(self.viewer).get(
                          f'/api/encounters/{enc.pk}').json()['activity']])

    def test_a_former_members_acts_keep_their_name(self):
        enc = self.encounter(user=self.agent)
        models.Membership.objects.filter(user=self.agent).update(active=False)
        texts = [item['text'] for item in
                 self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['activity']]
        self.assertEqual(texts, [f'Uploaded by {self.agent.label()}.'])
