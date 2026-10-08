"""Returned ASR identity is evidence, never an inference from a configured alias."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from decimal import Decimal
from django.test import SimpleTestCase
from core.provider_models import transcription_models
from core.jobs import submit_transcription


MODEL_ID = '30089e05-99d1-4376-b32e-c263170674af'


class ReturnedProviderModelTests(SimpleTestCase):
    def metadata(self):
        return {'models': [MODEL_ID], 'model_info': {MODEL_ID: {
            'name': '3-medical-nova', 'version': 'returned-version', 'arch': 'nova-3'}}}

    def test_returned_identity_is_exact_and_configured_alias_is_separate(self):
        result = transcription_models(self.metadata())
        self.assertEqual(result['model_metadata_status'], 'returned')
        self.assertEqual(result['configured_model'], 'nova-3-medical')
        self.assertEqual(result['returned_models'], [{'uuid': MODEL_ID,
            'name': '3-medical-nova', 'version': 'returned-version', 'arch': 'nova-3'}])

    def test_absent_metadata_does_not_claim_the_configured_alias_was_returned(self):
        for metadata in (None, {}, {'duration': 2}):
            result = transcription_models(metadata)
            self.assertEqual(result['returned_models'], [])
            self.assertEqual(result['model_metadata_status'], 'not_returned')

    def test_unreferenced_malformed_duplicate_and_unbounded_metadata_is_uncertain(self):
        values = [{'models': [], 'model_info': self.metadata()['model_info']},
                  {'models': [MODEL_ID], 'model_info': {}},
                  {'models': [MODEL_ID] * 17, 'model_info': self.metadata()['model_info']},
                  {'models': [MODEL_ID, MODEL_ID], 'model_info': self.metadata()['model_info']},
                  {'models': ['-' * 36], 'model_info': {'-' * 36: {
                      'name': 'not-a-model-id', 'version': 'v', 'arch': 'a'}}},
                  {'models': [MODEL_ID], 'model_info': {MODEL_ID: {'name': 'x' * 201,
                      'version': 'v', 'arch': 'a'}}}]
        for metadata in values:
            self.assertEqual(transcription_models(metadata)['model_metadata_status'], 'incomplete')

    def test_paid_submission_retains_returned_metadata_and_usage_without_an_extra_request(self):
        data = {'metadata': {**self.metadata(), 'duration': 2, 'request_id': 'request1'},
                'results': {'channels': [{'alternatives': [{'transcript': 'Synthetic notes.'}]}]}}
        response = Mock(); response.json.return_value = data
        job = SimpleNamespace(config={'voice_max_cost': '0.20', 'voice_rate_minute': '0.10'})
        with patch('core.jobs.httpx.post', return_value=response) as post:
            result = submit_transcription(job, b'bounded-synthetic-audio', 'synthetic-test-key', {})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result[2]['returned_models'][0]['uuid'], MODEL_ID)
        self.assertEqual(result[2]['duration_seconds'], '2')
        self.assertEqual(result[5], 'request1')
        self.assertFalse(result[6])
        self.assertIsInstance(result[1], Decimal)
