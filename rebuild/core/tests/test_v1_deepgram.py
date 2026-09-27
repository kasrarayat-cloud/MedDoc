"""Deepgram request parameters: the Model Improvement opt-out on every request, smart formatting by setting.

Deepgram documents both as boolean query parameters defaulting to false
(https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded) and says requests join the
Model Improvement Program — retained, and used for training — unless `mip_opt_out=true`
(https://developers.deepgram.com/trust-security/your-data). Both read 2026-09-27.

The provider is never called: `httpx.post` is a mock that returns a synthetic transcript.
"""
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation
from core.jobs import NoProviderRequest, enqueue, request_parameters, run_one
from core.models import Job
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes
from core.tests.test_billing_boundary import BoundaryFixture, deepgram
from core.tests.test_billing_policy import STORAGES

DEFAULT = {'model': 'nova-3-medical', 'smart_format': 'false', 'mip_opt_out': 'true'}


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class TranscriptionRequestParameters(BoundaryFixture, TestCase):
    def queue(self, key):
        recording = private_path(f'uploads/{key}.wav')
        recording.parent.mkdir(parents=True, exist_ok=True)
        recording.write_bytes(wav_bytes(tag=key))
        with patch.dict(os.environ, self.VOICE_ENV):
            return enqueue(self.encounter, self.user, kind='transcription', input_path=f'uploads/{key}.wav')

    def run_worker(self):
        with patch.dict(os.environ, self.VOICE_ENV), \
                patch('core.jobs.httpx.post', return_value=deepgram('Synthetic transcript.', 'req_synthetic_params')) as post:
            self.assertTrue(run_one())
        return post

    def test_a_new_job_records_and_sends_the_opt_out_by_default(self):
        job = self.queue('default-params')
        self.assertEqual(job.config['deepgram_parameters'], DEFAULT)
        post = self.run_worker()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['params'], DEFAULT)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')

    @override_settings(QUILLMD_DEEPGRAM_SMART_FORMAT='true')
    def test_smart_formatting_is_a_setting_recorded_with_the_job(self):
        job = self.queue('smart-format')
        self.assertEqual(job.config['deepgram_parameters'], {**DEFAULT, 'smart_format': 'true'})
        self.assertEqual(self.run_worker().call_args.kwargs['params'], {**DEFAULT, 'smart_format': 'true'})

    def test_a_queued_job_keeps_the_parameters_it_was_queued_with(self):
        self.queue('queued-before-change')
        with override_settings(QUILLMD_DEEPGRAM_SMART_FORMAT='true'):
            self.assertEqual(self.run_worker().call_args.kwargs['params'], DEFAULT)

    def test_smart_formatting_does_not_change_the_priced_configuration(self):
        """Smart Formatting is 'Included' on https://deepgram.com/pricing (read 2026-09-27): no quote moves."""
        with patch.dict(os.environ, self.VOICE_ENV):
            before = generation.configuration()['pricing_version']
            with override_settings(QUILLMD_DEEPGRAM_SMART_FORMAT='true'):
                self.assertEqual(generation.configuration()['pricing_version'], before)


class RecordedParameters(SimpleTestCase):
    def test_a_job_queued_before_parameters_were_recorded_still_opts_out(self):
        legacy = SimpleNamespace(config={'voice_rate_minute': '0.006'})
        self.assertEqual(request_parameters(legacy), DEFAULT)
        self.assertEqual(request_parameters(SimpleNamespace(config=None)), DEFAULT)

    def test_an_unrecognised_recorded_value_sends_nothing(self):
        for recorded in ({**DEFAULT, 'mip_opt_out': 'no'}, {**DEFAULT, 'model': 'another-model'},
                         {**DEFAULT, 'callback': 'https://example.invalid'}, {'model': 'nova-3-medical'}, 'model=nova-3-medical'):
            with self.subTest(recorded=recorded), self.assertRaises(NoProviderRequest):
                request_parameters(SimpleNamespace(config={'deepgram_parameters': recorded}))
