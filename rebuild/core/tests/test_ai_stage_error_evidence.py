"""Prospective private failure evidence; every provider response is an offline fixture."""
import hashlib
import json
import os
import stat
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from anthropic import BadRequestError
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from core import ai_stages
from core.ai_stage_error_evidence import build, MAX_BODY_BYTES
from core.jobs import enqueue, run_one
from core.models import AuditEvent, ProviderReceipt, Reservation, Usage
from core.security import private_path
from core.tests import test_ai_stages as fixtures


SECRET = 'synthetic-credential-never-retained'
CLINICAL = 'synthetic-private-clinical-sentinel'


def error400():
    body = {'type': 'error', 'error': {'type': 'invalid_request_error',
            'message': f'Unsupported schema. {CLINICAL} {SECRET}; Authorization: Bearer other-secret; x-api-key=second-secret'}}
    response = httpx.Response(400, json=body, headers={'request-id': 'req_offline_400'},
            request=httpx.Request('POST', 'https://provider.invalid/messages', headers={'x-api-key': SECRET}))
    return BadRequestError('Unsafe exception string ' + SECRET, response=response, body=body)


def envelope(exc, **kwargs):
    return build(exc, provider='anthropic', stage_id='offline-stage', stage='extractor',
                 attempt=1, credentials=(SECRET,), **kwargs)


class StageErrorEvidencePureTests(SimpleTestCase):
    def test_http400_retains_actual_cause_and_request_binding_in_sanitized_projection(self):
        exc = error400()
        with patch.object(BadRequestError, '__str__', side_effect=AssertionError('never stringify')):
            result = envelope(exc)
        self.assertEqual(result['exception_class'], 'BadRequestError')
        self.assertEqual(result['http_status'], 400)
        self.assertEqual(result['provider_request_id'], 'req_offline_400')
        self.assertEqual(result['provider_error']['type'], 'invalid_request_error')
        self.assertIn('Unsupported schema.', result['provider_error']['message'])
        self.assertIn(CLINICAL, result['provider_error']['message'])
        self.assertEqual(result['body_sha256'], hashlib.sha256(exc.response.content).hexdigest())
        self.assertTrue(result['sanitized'])
        self.assertFalse(result['exact_raw_response'])
        text = json.dumps(result)
        for secret in (SECRET, 'other-secret', 'second-secret', 'Unsafe exception string'):
            self.assertNotIn(secret, text)
        self.assertIsNone(result['actual_cost'])
        self.assertEqual(result['delivery_outcome'], 'unknown')

    def test_timeout_has_no_fabricated_http_response_or_zero_cost(self):
        result = envelope(TimeoutError('private ' + SECRET))
        self.assertEqual(result['exception_class'], 'TimeoutError')
        self.assertIsNone(result['http_status'])
        self.assertIsNone(result['provider_request_id'])
        self.assertIsNone(result['provider_error'])
        self.assertIsNone(result['actual_cost'])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_cached_httpx_status_is_fallback_only_for_absent_or_invalid_exception_status(self):
        response = httpx.Response(400, json={'error': {'type': 'invalid_request_error',
                                  'message': 'Unsupported schema.'}},
                                  request=httpx.Request('POST', 'https://provider.invalid/messages'))
        exc = httpx.HTTPStatusError('unsafe exception text', request=response.request, response=response)
        for value in (None, 'invalid', True, 999):
            with self.subTest(exception_status=value):
                exc.status_code = value
                self.assertEqual(envelope(exc)['http_status'], 400)
        exc.status_code = 429
        self.assertEqual(envelope(exc)['http_status'], 429)

    def test_openai_header_fallback_and_parsed_body_are_explicit(self):
        exc = Exception()
        exc.status_code = 429
        exc.response = SimpleNamespace(headers={'x-request-id': 'req_offline_429'})
        exc.body = {'error': {'type': 'rate_limit_error', 'message': 'Try later.'}, 'headers': {'authorization': SECRET}}
        result = envelope(exc)
        self.assertEqual(result['provider_request_id'], 'req_offline_429')
        self.assertEqual(result['body_source'], 'sdk_parsed_body')
        self.assertEqual(result['provider_error']['message'], 'Try later.')
        self.assertIsNone(result['body_sha256'])
        self.assertNotIn('authorization', json.dumps(result))

    def test_oversize_and_non_json_bodies_are_omitted_without_silent_truncation(self):
        for raw, expected in [(b'x' * (MAX_BODY_BYTES + 1), 'omitted_oversize'),
                              (b'<html>private</html>', 'omitted_non_json')]:
            with self.subTest(expected=expected):
                exc = Exception(); exc.response = SimpleNamespace(content=raw)
                result = envelope(exc)
                self.assertEqual(result['body_retention'], expected)
                self.assertEqual(result['body_bytes'], len(raw))
                self.assertEqual(result['body_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertIsNone(result['provider_error'])

    def test_unread_body_properties_never_trigger_network_read_or_mask_original(self):
        class Unread:
            @property
            def content(self):
                raise httpx.ResponseNotRead()
            def read(self):
                raise AssertionError('network read forbidden')
            def json(self):
                raise AssertionError('response parser forbidden')
        exc = Exception(); exc.response = Unread()
        result = envelope(exc)
        self.assertEqual(result['body_retention'], 'unavailable')
        self.assertIsNone(result['actual_cost'])

    def test_oversize_parsed_body_reports_only_a_measured_lower_bound(self):
        exc = Exception()
        exc.body = {'error': {'message': 'x' * (MAX_BODY_BYTES + 1)},
                    'not_retained': 'y' * MAX_BODY_BYTES}
        result = envelope(exc)
        self.assertEqual(result['body_retention'], 'omitted_oversize')
        self.assertIsNone(result['body_bytes'])
        self.assertGreater(result['body_bytes_lower_bound'], MAX_BODY_BYTES)
        self.assertIsNone(result['body_sha256'])
        self.assertIsNone(result['provider_error'])

    def test_credential_cannot_leak_through_exception_class_or_request_id(self):
        exc = type('SyntheticCredentialSecret', (Exception,), {})()
        exc.request_id = 'SyntheticCredentialSecret'
        result = build(exc, provider='anthropic', stage_id='offline', stage='extractor',
                       attempt=1, credentials=('SyntheticCredentialSecret',))
        self.assertEqual(result['exception_class'], 'Exception')
        self.assertIsNone(result['provider_request_id'])

    def test_quoted_header_patterns_and_explicit_message_bounds_are_sanitized(self):
        exc = Exception()
        exc.body = {'error': {'type': 'invalid_request_error',
                    'message': '\"x-api-key\": \"unknown-credential\"; \"Authorization\": \"Bearer another-credential\" ' + 'x' * 9000}}
        result = envelope(exc)
        text = json.dumps(result)
        self.assertNotIn('unknown-credential', text)
        self.assertNotIn('another-credential', text)
        self.assertEqual(result['truncated_fields'], ['message'])
        self.assertEqual(len(result['provider_error']['message']), 8192)


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='', ADMIN_SITE=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class StageErrorEvidenceDatabaseTests(TestCase):
    def setUp(self):
        fixtures.IndependentStageTests.setUp(self)

    live_config = fixtures.IndependentStageTests.live_config

    def run_failure(self, respond=None):
        job = enqueue(self.encounter, self.user, config=self.live_config())
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': SECRET}), \
             patch.object(ai_stages, '_response', side_effect=respond or error400()) as provider:
            self.assertTrue(run_one())
            self.assertFalse(run_one())
        self.assertEqual(provider.call_count, 1)
        job.refresh_from_db()
        stage = job.ai_stage_receipts.get()
        self.assertEqual(job.state, 'reconciliation')
        self.assertEqual(stage.state, 'unknown')
        self.assertEqual(stage.error_code, 'provider_unknown')
        self.assertIsNone(stage.actual_cost)
        self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.answers, {})
        self.assertNotIn(CLINICAL, job.error)
        self.assertNotIn(SECRET, job.error)
        return job, stage

    def diagnostic(self, stage):
        row = AuditEvent.objects.get(action='ai.stage_error_retained', target=str(stage.pk))
        path = private_path(row.details['evidence_path'])
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), row.details['evidence_sha256'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        for sentinel in (SECRET, CLINICAL, 'Unsupported schema.'):
            self.assertNotIn(sentinel, json.dumps(row.details))
        return json.loads(raw)

    def test_http_error_is_private_and_unknown_state_and_hold_are_unchanged(self):
        _, stage = self.run_failure()
        result = self.diagnostic(stage)
        self.assertEqual(result['http_status'], 400)
        self.assertIn('Unsupported schema.', result['provider_error']['message'])
        self.assertIn(CLINICAL, result['provider_error']['message'])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(stage.result_path, '')
        self.assertEqual(stage.provider_request_id, '')

    def test_previously_retained_response_is_never_replaced_by_error_diagnostics(self):
        original = {'id': 'msg_offline', 'content': 'original raw output'}
        def respond(*args):
            args[-1](SimpleNamespace(id='msg_offline', _request_id='req_original', model='synthetic-model',
                                    model_dump=lambda **kwargs: original))
            raise error400()
        _, stage = self.run_failure(respond)
        raw = json.loads(private_path(stage.result_path).read_bytes())
        self.assertEqual(raw['provider_output'], original)
        self.assertEqual(stage.provider_request_id, 'req_original')
        self.assertEqual(self.diagnostic(stage)['provider_request_id'], 'req_offline_400')

    def test_error_file_write_failure_does_not_change_original_unknown_outcome(self):
        retained = ai_stages.retain
        def retain(value):
            if value.get('contract') == 'ai-stage-error-evidence-v1':
                raise OSError('offline evidence write failure')
            return retained(value)
        with patch.object(ai_stages, 'retain', side_effect=retain):
            _, stage = self.run_failure()
        self.assertFalse(AuditEvent.objects.filter(action='ai.stage_error_retained', target=str(stage.pk)).exists())

    def test_error_audit_failure_rolls_back_only_diagnostics_and_preserves_original_state(self):
        with patch.object(ai_stages, 'audit', side_effect=DatabaseError('offline audit failure')):
            _, stage = self.run_failure()
        self.assertFalse(AuditEvent.objects.filter(action='ai.stage_error_retained', target=str(stage.pk)).exists())

    def test_error_projection_failure_cannot_replace_original_exception_outcome(self):
        with patch('core.ai_stage_error_evidence.build', side_effect=ValueError('offline projection failure')):
            _, stage = self.run_failure()
        self.assertEqual(stage.result_path, '')
