"""What a customer is shown, beyond the codes (findings SEC-S4, SEC-S3, FG-5, FG-6, SEC-OPS-IDENTITY-TO-CUSTOMER): the
evidence quotes the coding review wrote pass the vendor-name filter like its other text, a question names only the codes
of its lines, the exports show control characters escaped, the draft export's questions and notes are filtered, a
decided encounter is held to the contract, and a platform operator's act reads as CPT Studio's. Synthetic data only."""
import csv
import io
import json

from django.test import TestCase

from studio import models
from tests.support import operator as ops
from tests.support import rounds as r

Round = models.CodingRound
CONTROLS = ('\x0b', '\x0c', '\u202e', '\u202c', '\u2066', '\u2069', '\u200f', '\u061c', '\u2028', '\x85', '\r')


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
        for kind, fmt in (('draft', 'txt'), ('draft', 'csv')):
            with self.subTest(fmt=fmt):
                text = self.export_text(enc, kind, fmt)
                self.assertIn('The system (the system) reviewed this note', text)
                self.assertNotIn('laude', text)

    def test_a_cited_passage_of_the_document_is_shown_exactly(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')],
                      citations={'L1': [{'text': 'Dr. Claude Example removed the polyp', 'page': 2,
                                         'source': 'reader'}]})
        codes = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes']
        self.assertEqual(codes[0]['quotes'], [{'text': 'Dr. Claude Example removed the polyp', 'page': 2}])

    def test_the_draft_exports_questions_and_notes_pass_the_vendor_name_filter(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')],
                      questions=[{'id': 'q1', 'text': 'Per OpenAI policy, was the polyp retrieved?', 'codes': [],
                                  'lines': ['L1'], 'source': 'reader'}],
                      problems=['Claude Fable 5.2 found no signature.'])
        text = self.export_text(enc, 'draft')
        lines = text.splitlines()
        self.assertIn('- Per the system policy, was the polyp retrieved?', lines)
        self.assertIn('- The system found no signature.', lines)
        self.assertEqual([line for line in lines if 'OpenAI' in line or 'Claude' in line], [])


class ControlCharacterTests(r.CustomerCase, TestCase):
    def test_control_and_direction_characters_are_shown_escaped_in_both_exports(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row(
            '45385', 'ready', reason='Snare\x0bremoval\x0cdocumented \u202eDETCELES TON\u202c.\x85x\u2028y\rz',
            modifiers=['P\x0bT'], check_reason='Agreed\x0b.\u2066iso\u2069\u200f\u061c')],
            citations={'L1': [{'text': 'cold \x0csnare\r\nremoved', 'page': 1, 'source': 'reader'}]})
        raw_csv = self.export_text(enc, 'draft', 'csv')
        found = {repr(char): raw_csv.count(char) for char in CONTROLS if char in raw_csv.replace('\r\n', '\n')}
        self.assertEqual(found, {})
        rows = list(csv.reader(io.StringIO(raw_csv, newline='')))
        self.assertEqual(len(rows), 4)  # header, banner, one code, closing banner: nothing forged
        body = dict(zip(rows[0], rows[2]))
        self.assertEqual(body['modifiers'], 'P\\x0bT')
        self.assertIn('\\u202eDETCELES TON\\u202c', body['reason'])
        self.assertEqual(body['quotes'], '"cold \\x0csnare\nremoved" (page 1)')
        text = self.export_text(enc, 'draft')
        self.assertEqual({repr(char): text.count(char) for char in CONTROLS if char in text}, {})
        self.assertIn('\\u202eDETCELES TON\\u202c', text)


class DecidedContractTests(r.CustomerCase, TestCase):
    def test_a_decided_encounter_and_the_decision_answer_are_held_to_the_contract(self):
        sc = r.scan_customer()
        enc = self.done()
        approve = self.decide(enc, 'L1', '45385', 'approve', note='Checked.')
        reject = self.decide(enc, 'L3', '43239', 'reject')
        for response in (approve, reject):
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(set(response.json()), {'line', 'code', 'action', 'by', 'at', 'note'})
        response = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}')
        payload = response.json()
        self.assertEqual([code['decision']['action'] for code in payload['codes'] if code['decision']],
                         ['approve', 'reject'])
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
