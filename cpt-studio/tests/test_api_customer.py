"""The customer API (BUILD-SPEC 6; client contract customer-2026-11-22): the contract's keys exactly (held to
ops/verification/customer-contract.json by the shipped reader, ops/scan_customer.py, and to the spec's own key lists),
the export formats it lists (PDF, CSV and TXT: studio.exports.FORMATS, one sentence refusing any other),
tenancy (404 outside the membership), the reviewer gate, answers starting a new round with every answer so far, the
vendor-name scan over every customer JSON response, the in-page view's headers, a Word document's converted view, the
earlier review (an encounter with no round), the upload with its insurance, and the display hygiene. Synthetic data only;
nothing reaches the network."""
import hashlib
import json
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from studio import api, client_contract, customer, decisions, exports, jobs, models, state
from studio.fable import document as fable_document
from tests.support import coding as f
from tests.support import rounds as r

Round = models.CodingRound
SESSION_KEYS = {'user', 'workspace', 'role', 'can_review', 'acknowledgement', 'counts'}
ROW_KEYS = {'id', 'title', 'state', 'state_label', 'service_date', 'insurance', 'created_at', 'kind'}
ENCOUNTER_KEYS = {'id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document',
                  'context', 'progress', 'round', 'codes', 'questions', 'answers', 'notes', 'readiness', 'reports',
                  'activity'}
# BUILD-SPEC 6's document keys, and the two this build adds (view_media_type, converted)
DOCUMENT_KEYS = {'name', 'media_type', 'size', 'kind', 'original_url', 'view_url', 'view_media_type', 'converted'}
PROGRESS_KEYS = {'phase', 'busy', 'started_at', 'finished_at', 'server_time', 'message', 'can_stop', 'can_resume',
                 'can_retry', 'error'}
CODE_KEYS = {'line', 'code', 'units', 'modifiers', 'status', 'status_label', 'reason', 'second_check', 'question',
             'quotes', 'decision', 'allowed_actions'}
QUESTION_KEYS = {'id', 'text', 'codes', 'lines'}
DOCX_BYTES = b'PK\x03\x04 synthetic word bytes, never opened by the tests'
CONVERTED = b'%PDF-1.7\n% the synthetic conversion of a Word file\n%%EOF\n'


class ApiCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.sc = r.scan_customer()
        self.client = self.client_for(self.reviewer)

    def get_json(self, url, client=None, status=200):
        response = (client or self.client).get(url)
        self.assertEqual(response.status_code, status, response.content[:400])
        self.assertEqual(response['Cache-Control'], 'no-store')
        return response.json()

    def post_json(self, url, body=None, client=None):
        return (client or self.client).post(url, data=json.dumps(body or {}), content_type='application/json')

    def assert_contract(self, payload, schema):
        self.assertEqual(self.sc.shape_problems(payload, self.sc.CONTRACT[schema]), [])

    def assert_clean(self, response):
        """No hard hit of the shared denylist in a customer JSON response's body or headers."""
        hits = self.sc.scan_headers(dict(response.items()), self.sc.scan_context(), 'response')
        if response.get('Content-Type', '').startswith('application/json'):
            self.sc.scan_json(response.json(), self.sc.scan_context(), hits=hits)
        self.assertEqual([hit for hit in hits if hit['severity'] == 'hard'], [])


class ContractTests(ApiCase):
    def test_the_session_list_and_encounter_carry_exactly_the_contracts_keys(self):
        done = self.done()
        queued = self.started(title='Queued note', pdf=False)
        session = self.get_json('/api/session')
        self.assertEqual(set(session), SESSION_KEYS)
        self.assert_contract(session, 'session')
        self.assertEqual(session['acknowledgement'], decisions.ACKNOWLEDGEMENTS['human'])
        self.assertEqual(session['counts'], {'documents': 2, 'queue': 1})
        listing = self.get_json('/api/encounters')
        self.assert_contract(listing, 'list')
        self.assertEqual([row['id'] for row in listing['encounters']], [str(queued.pk), str(done.pk)])
        self.assertEqual(set(listing['encounters'][0]), ROW_KEYS)
        self.assertEqual((listing['encounters'][0]['kind'], listing['encounters'][1]['kind']), ('paste', 'upload'))
        self.assertEqual(listing['encounters'][1]['insurance'], 'medicare')
        for enc in (done, queued):
            payload = self.get_json(f'/api/encounters/{enc.pk}')
            self.assertEqual(set(payload), ENCOUNTER_KEYS)
            self.assertEqual(set(payload['document']), DOCUMENT_KEYS)
            self.assertEqual(set(payload['progress']), PROGRESS_KEYS)
            self.assert_contract(payload, 'encounter')
        payload = self.get_json(f'/api/encounters/{done.pk}')
        self.assertEqual(set(payload['codes'][0]), CODE_KEYS)
        self.assertEqual(set(payload['questions'][0]), QUESTION_KEYS)

    def test_an_export_of_each_format_is_listed_as_the_contract_has_it(self):
        """The formats a request may name (exports.FORMATS: the physician PDF, CSV and TXT) are the contract's report
        formats, each export the page lists holds to the contract, and any other format is refused with one sentence."""
        report = self.sc.CONTRACT['types']['report']['keys']
        self.assertEqual(set(report['fmt']['enum']), set(exports.FORMATS))
        self.assertEqual(set(exports.FORMATS), {'pdf', 'csv', 'txt'})
        enc = self.done()
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        made = []
        for kind, fmt in (('draft', 'pdf'), ('draft', 'csv'), ('draft', 'txt'), ('approved', 'pdf')):
            response = self.post_json(f'/api/encounters/{enc.pk}/reports', {'kind': kind, 'fmt': fmt, 'round': 1})
            self.assertEqual(response.status_code, 201, response.content)
            self.assert_clean(response)
            self.assertEqual(self.sc.shape_problems(response.json(), {'ref': 'report'}), [])
            made.append((response.json()['kind'], response.json()['fmt']))
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assert_contract(payload, 'encounter')
        self.assertEqual(sorted((item['kind'], item['fmt']) for item in payload['reports']), sorted(made))
        for fmt in ('docx', 'PDF', 'xlsx', None):
            with self.subTest(fmt=fmt):
                refused = self.post_json(f'/api/encounters/{enc.pk}/reports', {'kind': 'draft', 'fmt': fmt, 'round': 1})
                self.assertEqual((refused.status_code, refused.json()['error']),
                                 (400, 'Choose a draft or an approved export as PDF, CSV or TXT.'))
        self.assertEqual(models.ExportArtifact.objects.filter(encounter=enc).count(), 4)

    def test_a_done_round_reads_as_its_codes_questions_quotes_and_notes(self):
        enc = self.done()
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual((payload['state'], payload['state_label']), ('awaiting_answer', 'Questions for you'))
        self.assertEqual(payload['progress']['phase'], 'done')
        self.assertEqual(payload['round'], {'number': 1, 'trigger': 'upload',
                                            'finished_at': payload['progress']['finished_at']})
        codes = {code['code']: code for code in payload['codes']}
        self.assertEqual([(code['line'], code['code']) for code in payload['codes']],
                         [('L1', '45385'), ('L2', '45380'), ('L3', '43239'), ('L4', '43251'), ('M1', '45378')])
        self.assertEqual({code: row['status'] for code, row in codes.items()},
                         {'45385': 'ready', '45380': 'needs_answer', '43239': 'needs_review', '43251': 'not_supported',
                          '45378': 'needs_review'})
        self.assertEqual(codes['45385']['status_label'], 'Ready for approval')
        self.assertEqual(codes['45385']['allowed_actions'], ['approve', 'reject'])
        self.assertEqual(codes['43239']['allowed_actions'], ['approve', 'reject'])
        self.assertEqual(codes['45380']['allowed_actions'], [])
        self.assertEqual(codes['43251']['allowed_actions'], [])
        self.assertEqual(codes['43239']['second_check'], {'agrees': False, 'reason': 'The biopsy site is not stated.'})
        self.assertEqual(codes['45378']['second_check'], {
            'agrees': None, 'reason': 'The second check found this code and listed it as ready for approval; it needs '
                                      'your review.'})
        self.assertEqual(codes['45380']['question'], 'Was a biopsy taken from a separate site?')
        # quotes are the API's citations (the reader's on page 1, then the checker's on page 2), each passage once
        self.assertEqual(codes['45385']['quotes'], [{'text': 'removed by cold snare', 'page': 1},
                                                    {'text': 'cold snare', 'page': 2}])
        self.assertEqual([q['text'] for q in payload['questions']],
                         ['Was a biopsy taken from a separate site?',
                          'Which site was biopsied during the upper endoscopy?'])
        round_ = state.latest_round(enc)
        self.assertEqual(payload['questions'][0]['id'], decisions.question_id(round_, round_.questions[0]))
        self.assertEqual((payload['questions'][0]['codes'], payload['questions'][0]['lines']), (['45380'], ['L2']))
        self.assertEqual((payload['questions'][1]['codes'], payload['questions'][1]['lines']), (['43239'], ['L3']))
        self.assertEqual(payload['notes'], ['The note is not signed.'])
        self.assertEqual(payload['readiness'], {'draft': True, 'approved': False,
                                                'blockers': ['No code has been approved.']})
        self.assertEqual(payload['document'], {
            'name': 'synthetic-note.pdf', 'media_type': 'application/pdf', 'size': len(f.PDF_BYTES), 'kind': 'upload',
            'original_url': f'/api/encounters/{enc.pk}/original',
            'view_url': f'/api/encounters/{enc.pk}/original?view=1', 'view_media_type': 'application/pdf',
            'converted': False})
        self.assertEqual(payload['context'], {'service_date': '2026-11-02', 'insurance': 'medicare'})
        self.assertEqual([item['text'] for item in payload['activity']],
                         [f'Uploaded by {self.reviewer.label()}.', 'Coding review 1 finished with 2 questions.'])

    def test_a_code_with_no_citation_shows_its_evidence_quotes(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', evidence=[{'quote': 'snare', 'page': 3},
                                                                     {'quote': 'snare', 'page': 3}])],
                      citations={'L2': [{'text': 'elsewhere', 'page': 1, 'source': 'reader'}],
                                 '45385': [{'text': 'filed under a code, not a line', 'page': 1, 'source': 'reader'}]})
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual(payload['codes'][0]['quotes'], [{'text': 'snare', 'page': 3}])

    def test_processing_failed_and_stopped_rounds_have_no_codes_and_say_what_can_be_done(self):
        enc = self.started()
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual((payload['state'], payload['progress']['phase'], payload['progress']['busy']),
                         ('processing', 'queued', True))
        self.assertTrue(payload['progress']['can_stop'])
        self.assertEqual(payload['readiness']['blockers'], ['The coding review has not finished.'])
        round_ = state.latest_round(enc)
        Round.objects.filter(pk=round_.pk).update(state=Round.RUNNING, reader_result={'codes': []})
        self.assertEqual(self.get_json(f'/api/encounters/{enc.pk}')['progress']['phase'], 'checking')
        Round.objects.filter(pk=round_.pk).update(state=Round.RUNNING, reader_result=None)
        self.assertEqual(self.get_json(f'/api/encounters/{enc.pk}')['progress']['phase'], 'reading')
        self.assertEqual(self.post_json(f'/api/encounters/{enc.pk}/stop').status_code, 200)
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual((payload['state'], payload['progress']['phase']), ('stopped', 'stopped'))
        self.assertTrue(payload['progress']['can_resume'])
        self.assertEqual(payload['codes'], [])
        self.assert_contract(payload, 'encounter')
        self.assertEqual(self.post_json(f'/api/encounters/{enc.pk}/resume').status_code, 201)
        self.assertEqual(self.get_json(f'/api/encounters/{enc.pk}')['progress']['phase'], 'queued')
        failed = self.encounter(title='Failed note')
        r.write_round(failed, state_=Round.FAILED, failure_kind='busy', error=jobs.FAILURE_TEXT['busy'])
        payload = self.get_json(f'/api/encounters/{failed.pk}')
        self.assertEqual((payload['state'], payload['progress']['phase']), ('failed', 'failed'))
        self.assertEqual(payload['progress']['error'], {'text': 'The coding service is busy. Try again in a few minutes.'})
        self.assertTrue(payload['progress']['can_retry'])
        self.assertEqual(payload['readiness']['blockers'], ['The coding review could not finish.'])
        self.assert_contract(payload, 'encounter')

    def test_a_failure_at_the_spending_ceiling_is_not_offered_again(self):
        enc = self.encounter()
        r.write_round(enc, state_=Round.FAILED, failure_kind='ceiling', error=jobs.FAILURE_TEXT['ceiling'])
        self.assertFalse(self.get_json(f'/api/encounters/{enc.pk}')['progress']['can_retry'])
        response = self.post_json(f'/api/encounters/{enc.pk}/retry')
        self.assertEqual((response.status_code, response.json()['error']),
                         (409, 'This document reached its spending limit.'))

    def test_an_outdated_page_and_a_signed_out_caller_are_refused(self):
        for earlier in ('customer-2026-11-13', 'customer-2026-11-20', 'customer-2026-11-21'):
            response = self.client.get('/api/session', HTTP_X_CPT_STUDIO_CLIENT=earlier)
            self.assertEqual((response.status_code, response.json()), (409, client_contract.OUTDATED))
        self.assertEqual(Client().get('/api/session').status_code, 401)
        self.assertEqual(client_contract.VERSION, 'customer-2026-11-22')


class TenancyAndRoleTests(ApiCase):
    def test_every_customer_url_of_another_workspace_answers_404(self):
        enc = self.done()
        export = self.post_json(f'/api/encounters/{enc.pk}/reports', {'kind': 'draft', 'fmt': 'txt', 'round': 1}).json()
        outsider = self.client_for(self.outsider)
        for url in (f'/api/encounters/{enc.pk}', f'/api/encounters/{enc.pk}/original',
                    f'/api/encounters/{enc.pk}/original?view=1', export['download_url']):
            with self.subTest(url=url):
                self.assertEqual(outsider.get(url).status_code, 404)
        for action in ('answers', 'decisions', 'stop', 'resume', 'retry', 'reports'):
            with self.subTest(action=action):
                response = self.post_json(f'/api/encounters/{enc.pk}/{action}', {}, client=outsider)
                self.assertEqual(response.status_code, 404)
        self.assertNotIn(str(enc.pk), json.dumps(self.get_json('/api/encounters', client=outsider)))

    def test_every_change_needs_the_csrf_token(self):
        enc = self.done()
        strict = self.client_for(self.reviewer, enforce_csrf_checks=True)
        for action in ('answers', 'decisions', 'stop', 'resume', 'retry', 'reports'):
            with self.subTest(action=action):
                self.assertEqual(self.post_json(f'/api/encounters/{enc.pk}/{action}', {}, client=strict).status_code,
                                 403)
        self.assertEqual(strict.post('/api/encounters', {'text': f.NOTE, 'synthetic_attestation': 'yes'}).status_code,
                         403)
        self.assertEqual(models.Encounter.objects.count(), 1)

    def test_a_viewer_reads_and_exports_but_changes_nothing(self):
        enc = self.done()
        viewer = self.client_for(self.viewer)
        payload = self.get_json(f'/api/encounters/{enc.pk}', client=viewer)
        self.assertFalse(payload['permissions']['can_review'])
        self.assertTrue(all(code['allowed_actions'] == [] for code in payload['codes']))
        self.assertFalse(payload['progress']['can_retry'])
        question = payload['questions'][0]['id']
        bodies = {'answers': {'answers': [{'question_id': question, 'text': 'Yes.'}]},
                  'decisions': {'round': 1, 'line': 'L1', 'code': '45385', 'action': 'approve',
                                'acknowledgement': decisions.ACKNOWLEDGEMENTS['human']},
                  'stop': {}, 'resume': {}, 'retry': {}}
        for action, body in bodies.items():
            with self.subTest(action=action):
                response = self.post_json(f'/api/encounters/{enc.pk}/{action}', body, client=viewer)
                self.assertEqual((response.status_code, response.json()['error']), (403, api.REVIEWER_ONLY))
        upload = viewer.post('/api/encounters', {'text': f.NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(upload.status_code, 403)
        self.assertEqual(models.CodeDecision.objects.count(), 0)
        self.assertEqual(models.CodingAnswer.objects.count(), 0)
        self.assertEqual(self.post_json(f'/api/encounters/{enc.pk}/reports', {'kind': 'draft', 'fmt': 'csv', 'round': 1},
                                        client=viewer).status_code, 201)


class UploadTests(ApiCase):
    def test_an_upload_stores_the_insurance_and_queues_round_one_with_it(self):
        pdf = SimpleUploadedFile('synthetic-egd.pdf', f.PDF_BYTES, content_type='application/pdf')
        response = self.client.post('/api/encounters', {
            'file': pdf, 'title': 'Synthetic EGD', 'service_date': '2026-11-05', 'insurance': 'medicaid',
            'synthetic_attestation': 'yes', 'client_key': '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assert_clean(response)
        enc = models.Encounter.objects.get(pk=response.json()['id'])
        self.assertEqual(enc.user_values, {'service_date': '2026-11-05', 'insurance': 'medicaid'})
        round_ = state.latest_round(enc)
        self.assertEqual((round_.number, round_.trigger, round_.state), (1, Round.UPLOAD, Round.QUEUED))
        self.assertEqual(round_.context, {'service_date': '2026-11-05', 'insurance': 'medicaid', 'answers': []})
        self.assertEqual(enc.jobs.get().idempotency_key, f'code:{round_.pk}')
        self.assertEqual(enc.state, 'processing')
        again = self.client.post('/api/encounters', {
            'file': SimpleUploadedFile('synthetic-egd.pdf', f.PDF_BYTES), 'synthetic_attestation': 'yes',
            'client_key': '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f'})
        self.assertEqual((again.status_code, again.json()['id']), (201, str(enc.pk)))  # the same attempt, once
        self.assertEqual(models.Encounter.objects.count(), 1)

    def test_a_paste_without_insurance_reads_as_not_sure_and_bad_input_is_refused(self):
        response = self.client.post('/api/encounters', {'text': f.NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201)
        enc = models.Encounter.objects.get(pk=response.json()['id'])
        self.assertEqual(enc.user_values, {'insurance': 'unknown'})
        self.assertEqual(state.latest_round(enc).context['insurance'], 'unknown')
        for fields, message in (({'text': f.NOTE, 'synthetic_attestation': 'yes', 'insurance': 'blue-cross'},
                                 'Choose the insurance: Medicare, Medicaid, commercial or other, or not sure.'),
                                ({'text': f.NOTE}, 'Confirm that the document is synthetic and contains no real patient '
                                                   'information.'),
                                ({'text': f.NOTE, 'synthetic_attestation': 'yes', 'service_date': '2026-W43'},
                                 'Service date must be a date in YYYY-MM-DD form.')):
            with self.subTest(fields=fields):
                refused = self.client.post('/api/encounters', fields)
                self.assertEqual((refused.status_code, refused.json()['error']), (400, message))
        wrong = self.client.post('/api/encounters', {'file': SimpleUploadedFile('note.pdf', b'not a pdf'),
                                                     'synthetic_attestation': 'yes'})
        self.assertEqual((wrong.status_code, wrong.json()['error']),
                         (400, 'The file is named .pdf but is not a PDF document.'))
        self.assertEqual(models.Encounter.objects.count(), 1)


class AnswerTests(ApiCase):
    def test_answers_start_a_new_round_with_every_answer_so_far(self):
        enc = self.done()
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        first, second = payload['questions']
        response = self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [
            {'question_id': first['id'], 'text': '  Yes, from the rectum.  '}]})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'round': {'number': 2, 'trigger': 'answers', 'finished_at': None}})
        round2 = state.latest_round(enc)
        self.assertEqual(round2.context['answers'], [{'question': first['text'], 'answer': 'Yes, from the rectum.'}])
        self.assertEqual(round2.context['insurance'], 'medicare')
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual((payload['state'], payload['progress']['phase'], payload['codes'], payload['questions']),
                         ('processing', 'queued', [], []))
        self.assertEqual(payload['answers'], [{'question': first['text'], 'answer': 'Yes, from the rectum.',
                                               'by': self.reviewer.label(), 'at': payload['answers'][0]['at']}])
        # round 2 asks the second question again (the first was answered: its code is ready now); its answer goes into
        # round 3 with the first
        r2_codes = [dict(item, status='ready', question=None) if item['code'] == '45380' else item
                    for item in r.READER['codes']]
        r2_reader = {**r.READER, 'codes': r2_codes, 'questions': [{'question': second['text'], 'affects': ['43239']}]}
        self.code_round(enc, reader=r2_reader, checker={**r.CHECKER, 'questions': []})
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        (asked,) = payload['questions']
        self.assertNotEqual(asked['id'], second['id'])  # a round's questions have the round's own ids
        stale = self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [
            {'question_id': second['id'], 'text': 'The antrum.'}]})
        self.assertEqual((stale.status_code, stale.json()['error']), (409, decisions.STALE_QUESTIONS))
        response = self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [
            {'question_id': asked['id'], 'text': 'The antrum.'}]})
        self.assertEqual(response.status_code, 201)
        round3 = state.latest_round(enc)
        self.assertEqual((round3.number, round3.trigger), (3, Round.ANSWERS))
        self.assertEqual(round3.context['answers'], [{'question': first['text'], 'answer': 'Yes, from the rectum.'},
                                                     {'question': second['text'], 'answer': 'The antrum.'}])
        events = list(models.AuditEvent.objects.filter(encounter=enc, event='answers.recorded')
                      .values_list('data', flat=True))
        self.assertEqual([event['count'] for event in events], [1, 1])
        texts = [item['text'] for item in self.get_json(f'/api/encounters/{enc.pk}')['activity']]
        self.assertIn(f'{self.reviewer.label()} answered 1 question.', texts)

    def test_answers_are_refused_while_a_round_runs_and_when_they_are_not_answers(self):
        enc = self.done()
        question = self.get_json(f'/api/encounters/{enc.pk}')['questions'][0]['id']
        for body, status, message in (
                ({'answers': []}, 400, 'Write an answer to at least one question, then send.'),
                ({'answers': [{'question_id': question, 'text': '   '}]}, 400,
                 'An answer cannot be empty. Write it, or leave that question out.'),
                ({'answers': [{'question_id': question, 'text': 'x' * 2001}]}, 400,
                 'An answer can be at most 2,000 characters. Shorten it, then send.'),
                ({'answers': [{'question_id': question, 'text': 'a'}, {'question_id': question, 'text': 'b'}]}, 400,
                 'Answer each question once.'),
                ({'answers': [{'question_id': 'f3100000-0000-4000-8000-000000000001', 'text': 'Yes.'}]}, 409,
                 decisions.STALE_QUESTIONS)):
            with self.subTest(body=str(body)[:60]):
                response = self.post_json(f'/api/encounters/{enc.pk}/answers', body)
                self.assertEqual((response.status_code, response.json()['error']), (status, message))
        self.assertEqual(self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [
            {'question_id': question, 'text': 'x' * 2000}]}).status_code, 201)
        again = self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [
            {'question_id': question, 'text': 'Yes.'}]})
        self.assertEqual((again.status_code, again.json()['error']), (409, decisions.NO_QUESTIONS))
        self.assertEqual(models.CodingAnswer.objects.count(), 1)


class VendorNameScanTests(ApiCase):
    def test_no_customer_json_response_carries_a_vendor_or_model_name(self):
        enc = self.encounter()
        r.write_round(enc, codes=[
            r.row('45385', 'ready', reason='Claude Fable 5.2 read the note: a polyp was removed by snare.',
                  check_reason='As claude-fable-5-2 and gpt-4o agree, the snare is documented.'),
            r.row('43239', 'needs_review', reason='The Anthropic reader saw a biopsy (AnthropicTimeout aside).',
                  agrees=False, check_reason='GEMINI-4-ARGON would not code it; readingGemini disagreed.'),
            r.row('45380', 'needs_answer', question='Fable asks: was a biopsy taken from a separate site?')],
            questions=[{'id': 'q1', 'text': 'Per OpenAI policy, was a biopsy taken from a separate site?',
                        'codes': ['45380'], 'source': 'reader'}],
            problems=['The google_unknown step and Corti found no signature.'])
        responses = [self.client.get('/api/session'), self.client.get('/api/encounters'),
                     self.client.get(f'/api/encounters/{enc.pk}')]
        payload = responses[-1].json()
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/decisions', {
            'round': 1, 'line': 'L1', 'code': '45385', 'action': 'approve',
            'acknowledgement': decisions.ACKNOWLEDGEMENTS['human']}))
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/reports', {'kind': 'approved', 'fmt': 'txt',
                                                                               'round': 1}))
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/reports', {'kind': 'draft', 'fmt': 'pdf',
                                                                               'round': 1}))
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [
            {'question_id': payload['questions'][0]['id'], 'text': 'Yes.'}]}))
        responses.append(self.client.get(f'/api/encounters/{enc.pk}'))
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/stop'))
        responses.append(self.client.get(f'/api/encounters/{enc.pk}'))
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/resume'))
        responses.append(self.post_json(f'/api/encounters/{enc.pk}/decisions', {'code': 'x', 'action': 'nope'}))
        for response in responses:
            with self.subTest(response=response.content[:80]):
                self.assertIn(response.status_code, (200, 201, 400))
                self.assert_clean(response)
        codes = {code['code']: code for code in payload['codes']}
        self.assertEqual(codes['45385']['reason'], 'The system read the note: a polyp was removed by snare.')
        self.assertEqual(codes['45385']['second_check']['reason'], 'As the system and the system agree, the snare is '
                                                                   'documented.')
        self.assertEqual(codes['45380']['question'], 'The system asks: was a biopsy taken from a separate site?')
        self.assertEqual(payload['notes'], ['The system_unknown step and the system found no signature.'])
        self.assertEqual(payload['questions'][0]['text'], 'Per the system policy, was a biopsy taken from a separate '
                                                          'site?')


class DisplayHygieneTests(TestCase):
    """customer.shown: the shared denylist's four name rules as replacements; nothing else changes."""
    CASES = {
        'Claude Fable 5.2 read the note.': 'The system read the note.',
        'Read by claude-fable-5-2 and gpt-4o.': 'Read by the system and the system.',
        'the Claude model agreed': 'the system model agreed',
        'Interpreted by GEMINI-4-ARGON': 'Interpreted by the system',
        'fable_unknown': 'The system_unknown',
        'held: AnthropicTimeout': 'held: the systemTimeout',
        'the readingGemini step': 'the readingthe system step',
        'A corticosteroid injection was given; the cortical margin was smooth.':
            'A corticosteroid injection was given; the cortical margin was smooth.',
        'An affable nurse and Aesop\'s fables, Geminid meteors, googled.':
            'An affable nurse and Aesop\'s fables, Geminid meteors, googled.',
        'Argon plasma coagulation; carbon dioxide insufflation.': 'Argon plasma coagulation; carbon dioxide insufflation.',
        'A 6 mm polyp at 45385.': 'A 6 mm polyp at 45385.',
    }

    def test_vendor_and_model_names_become_the_system_and_nothing_else_changes(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)
        self.assertIsNone(customer.shown(None))
        self.assertEqual(customer.shown(7), 7)

    def test_the_names_are_the_shared_denylists_and_a_filtered_vector_is_clean(self):
        sc = r.scan_customer()
        patterns = {p['id']: p['source'] for p in r.denylist()['patterns']}
        names = customer.NAMES
        self.assertEqual(patterns['provider_name'], rf'(?<![a-z0-9])(?:{names})(?![a-z0-9])')
        joined = customer.JOINED_NAMES
        self.assertEqual(patterns['provider_name_joined'], rf'(?:{joined})(?=[A-Z])|(?<=[a-z])(?:{joined})')
        self.assertEqual(patterns['model_id'], r'\b(?:gpt|chatgpt|claude|gemini)-[a-z0-9]')
        self.assertTrue(customer._MODEL_ID.pattern.startswith(r'\b(?:gpt|chatgpt|claude|gemini)-[a-z0-9]'))
        self.assertEqual(patterns['interpreter_model'], r'\b(?:gemini-4-(?:argon|carbon)|claude-fable-5-2)\b')
        name_rules = {'provider_name', 'provider_name_joined', 'model_id', 'interpreter_model'}
        for vector in r.denylist()['vectors']:
            if vector['surface'] == 'bundle':
                continue
            with self.subTest(vector=vector['text']):
                cleaned = customer.shown(vector['text'])
                hits = {hit['id'] for hit in sc.scan_text(cleaned, sc.scan_context(), vector['surface'])}
                self.assertFalse(hits & name_rules, cleaned)
                if not set(vector['hits']) & name_rules:
                    self.assertEqual(cleaned, vector['text'])  # a text with no name is never changed


class ViewTests(ApiCase):
    def test_the_view_is_inline_and_framable_by_the_site_only_and_the_download_is_not(self):
        enc = self.done()
        view = self.client.get(f'/api/encounters/{enc.pk}/original?view=1')
        self.assertEqual(view.status_code, 200)
        self.assertEqual(view.content, f.PDF_BYTES)
        self.assertEqual(view['Content-Type'], 'application/pdf')
        self.assertEqual(view['Content-Disposition'], 'inline; filename="synthetic-note.pdf"')
        self.assertEqual(view['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(view['Content-Security-Policy'], "frame-ancestors 'self'")
        self.assertEqual(view['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('X-Content-SHA256', view)
        download = self.client.get(f'/api/encounters/{enc.pk}/original')
        self.assertEqual(download['Content-Disposition'], 'attachment; filename="synthetic-note.pdf"')
        self.assertEqual(download['X-Frame-Options'], 'DENY')
        self.assertIn("frame-ancestors 'none'", download['Content-Security-Policy'])
        plain = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
        with override_settings(STORAGES=plain):  # the page's static names without a collected manifest
            page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        csp = page['Content-Security-Policy']
        self.assertIn("frame-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("script-src 'self'", csp)

    def test_a_paste_is_viewed_as_its_text_and_has_no_download(self):
        enc = self.done(pdf=False)
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual(payload['document'], {
            'name': None, 'media_type': 'text/plain', 'size': len(f.NOTE.encode('utf-8')), 'kind': 'paste',
            'original_url': None, 'view_url': f'/api/encounters/{enc.pk}/original?view=1',
            'view_media_type': 'text/plain', 'converted': False})
        view = self.client.get(payload['document']['view_url'])
        self.assertEqual((view.status_code, view.content.decode('utf-8')), (200, f.NOTE))
        self.assertEqual(view['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(self.client.get(f'/api/encounters/{enc.pk}/original').status_code, 404)

    def test_a_word_document_is_viewed_as_the_pdf_the_coding_review_read(self):
        enc = f.encounter(self.ws, self.reviewer, title='Synthetic Word note', insurance='commercial')
        f.upload(enc, self.reviewer, data=DOCX_BYTES, filename='synthetic-note.docx',
                 media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        jobs.start_round(enc, enc.current_revision, Round.UPLOAD, self.reviewer)
        before = self.get_json(f'/api/encounters/{enc.pk}')['document']
        self.assertEqual((before['view_url'], before['view_media_type'], before['converted']), (None, None, False))
        self.assertEqual(self.client.get(f'/api/encounters/{enc.pk}/original?view=1').status_code, 404)
        with mock.patch.object(fable_document, 'convert_docx', return_value=CONVERTED) as convert:
            round1 = self.code_round(enc)
            self.assertEqual(round1.state, Round.DONE)
            self.assertEqual(convert.call_count, 1)
            self.assertEqual(round1.view_pdf_sha256, hashlib.sha256(CONVERTED).hexdigest())
            payload = self.get_json(f'/api/encounters/{enc.pk}')
            self.assertEqual(payload['document']['media_type'],
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            self.assertEqual((payload['document']['view_url'], payload['document']['view_media_type'],
                              payload['document']['converted']),
                             (f'/api/encounters/{enc.pk}/original?view=1', 'application/pdf', True))
            view = self.client.get(payload['document']['view_url'])
            self.assertEqual((view.status_code, view.content, view['Content-Type']), (200, CONVERTED, 'application/pdf'))
            self.assertEqual(view['Content-Disposition'], 'inline; filename="synthetic-note.pdf"')
            self.assertEqual(self.client.get(f'/api/encounters/{enc.pk}/original').content, DOCX_BYTES)
            # the next round of the same revision reads the stored conversion again: the same pages, one conversion
            question = payload['questions'][0]['id']
            self.post_json(f'/api/encounters/{enc.pk}/answers', {'answers': [{'question_id': question,
                                                                               'text': 'Yes.'}]})
            round2 = self.code_round(enc)
            self.assertEqual(convert.call_count, 1)
            self.assertEqual((round2.view_pdf_storage_name, round2.view_pdf_sha256),
                             (round1.view_pdf_storage_name, round1.view_pdf_sha256))
        sent = {run.request_body['messages'][0]['content'][0]['source']['data']['$original_sha256']
                for run in models.ProviderRun.objects.filter(encounter=enc)}
        self.assertEqual(sent, {round1.view_pdf_sha256})  # every send of both rounds carried the PDF the viewer shows
        self.assertEqual(models.ProviderRun.objects.filter(encounter=enc).count(), 4)


class EarlierReviewTests(ApiCase):
    def test_an_encounter_with_no_round_reads_as_an_earlier_review_and_retry_codes_it_again(self):
        enc = self.encounter(title='Earlier synthetic note')
        models.Encounter.objects.filter(pk=enc.pk).update(state='action_needed')  # a state of the earlier system
        legacy = models.Job.objects.create(encounter=enc, revision=enc.current_revision, kind='interpret',
                                           idempotency_key=f'interpret:{enc.pk}', deadline_at=enc.created_at)
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assert_contract(payload, 'encounter')
        self.assertEqual((payload['state'], payload['state_label']), ('earlier', 'Earlier review'))
        self.assertEqual((payload['codes'], payload['questions'], payload['notes'], payload['round']), ([], [], [], None))
        self.assertEqual(payload['progress']['message'], customer.EARLIER_MESSAGE)
        self.assertEqual((payload['progress']['phase'], payload['progress']['busy'], payload['progress']['can_retry']),
                         ('earlier', False, True))
        self.assertFalse(self.get_json(f'/api/encounters/{enc.pk}',
                                       client=self.client_for(self.viewer))['progress']['can_retry'])
        row = self.get_json('/api/encounters')['encounters'][0]
        self.assertEqual((row['state'], row['state_label']), ('earlier', 'Earlier review'))
        self.assertEqual(self.get_json('/api/session')['counts'], {'documents': 1, 'queue': 0})
        response = self.post_json(f'/api/encounters/{enc.pk}/retry')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['round']['trigger'], 'retry')
        round_ = state.latest_round(enc)
        self.assertEqual((round_.number, round_.trigger, round_.revision_id), (1, Round.RETRY, enc.current_revision_id))
        legacy.refresh_from_db()
        self.assertEqual((legacy.state, legacy.error), (models.Job.CANCELLED, decisions.SUPERSEDED_JOB))
        payload = self.get_json(f'/api/encounters/{enc.pk}')
        self.assertEqual((payload['state'], payload['progress']['phase']), ('processing', 'queued'))
        self.assertIn(f'{self.reviewer.label()} asked for the coding review again.',
                      [item['text'] for item in payload['activity']])


class ImportGraphTests(TestCase):
    def test_the_url_conf_loads_no_module_of_the_earlier_pipeline(self):
        """The new path imports none of the modules lane E removes (BUILD-SPEC 10), measured in a fresh process."""
        script = (
            'import django, sys; django.setup(); import cptstudio.urls; '
            'old = ("studio.review", "studio.customer_api", "studio.serializers", "studio.progress", "studio.reports", '
            '"studio.answers", "studio.interpretation", "studio.gi", "studio.validation", "studio.ingest", '
            '"studio.participants", "studio.providers", "studio.candidates", "studio.code_shapes", '
            '"studio.context_facts", "studio.evaluation", "studio.provider_holds"); '
            'print(sorted(m for m in sys.modules if any(m == o or m.startswith(o + ".") for o in old)))')
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'cptstudio.settings'}
        done = subprocess.run([sys.executable, '-c', script], cwd=settings.BASE_DIR, env=env, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        self.assertEqual(done.stdout.strip().splitlines()[-1], '[]')
