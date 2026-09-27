"""Deepgram request parameters: the Model Improvement opt-out by data mode, smart formatting by setting.

Deepgram documents both as boolean query parameters defaulting to false
(https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded) and says requests join the
Model Improvement Program — retained, and used for training — unless `mip_opt_out=true`
(https://developers.deepgram.com/trust-security/your-data). Both read 2026-09-27.

QUILLMD_DEEPGRAM_MIP_OPT_OUT unset follows the data mode: real mode sends `mip_opt_out=true`; synthetic mode
sends no `mip_opt_out` parameter, the request as it was before V1. Whether an opted-out request is priced
differently is unverified (docs/rebuild/v1/application-settings.md).

The provider is never called: `httpx.post` is a mock that returns a synthetic transcript.
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation
from core.jobs import NoProviderRequest, enqueue, request_parameters, run_one
from core.models import Job, Usage
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes
from core.tests.test_billing_boundary import BoundaryFixture, deepgram
from core.tests.test_billing_policy import STORAGES
from core.tests.test_v1_data_mode import COMPLETE_REAL, start
from quillmd import application_profile as profile

#: Synthetic mode, setting unset: exactly the request before V1 (146eb5fd sent model and smart_format only).
DEFAULT = {'model': 'nova-3-medical', 'smart_format': 'false'}
OPTED_OUT = {**DEFAULT, 'mip_opt_out': 'true'}
REAL = dict(SYNTHETIC_ONLY=False, QUILLMD_DATA_MODE='real', QUILLMD_DEEPGRAM_MIP_OPT_OUT='true')


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

    def test_synthetic_default_sends_the_request_as_before_without_the_parameter(self):
        """R5: synthetic mode with the setting unset records and sends no mip_opt_out at all."""
        job = self.queue('default-params')
        self.assertEqual(job.config['deepgram_parameters'], DEFAULT)
        post = self.run_worker()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['params'], DEFAULT)
        self.assertNotIn('mip_opt_out', post.call_args.kwargs['params'])
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')

    def test_an_explicit_synthetic_setting_is_recorded_and_sent(self):
        for value in ('true', 'false'):
            with self.subTest(value=value), override_settings(QUILLMD_DEEPGRAM_MIP_OPT_OUT=value):
                job = self.queue(f'explicit-{value}')
                self.assertEqual(job.config['deepgram_parameters'], {**DEFAULT, 'mip_opt_out': value})
                self.assertEqual(self.run_worker().call_args.kwargs['params'], {**DEFAULT, 'mip_opt_out': value})

    @override_settings(**REAL)
    def test_real_mode_records_and_sends_the_opt_out(self):
        job = self.queue('real-params')
        self.assertEqual(job.config['deepgram_parameters'], OPTED_OUT)
        self.assertEqual(self.run_worker().call_args.kwargs['params'], OPTED_OUT)

    def test_real_mode_never_sends_a_job_recorded_without_the_opt_out(self):
        """A job queued in synthetic mode (no parameter, or 'false') is refused by a real-mode worker, before any send."""
        for key, setting in (('queued-unset', None), ('queued-false', 'false')):
            with self.subTest(recorded=setting):
                with override_settings(QUILLMD_DEEPGRAM_MIP_OPT_OUT=setting):
                    job = self.queue(key)
                with override_settings(**REAL), patch.dict(os.environ, self.VOICE_ENV), \
                        patch('core.jobs.httpx.post', return_value=deepgram('Synthetic transcript.', f'req_{key}')) as post:
                    run_one()
                post.assert_not_called()
                job.refresh_from_db()
                self.assertEqual(job.state, 'failed')
                self.assertIn('Model Improvement opt-out', job.error)
                self.assertFalse(Usage.objects.filter(job=job).exists())

    @override_settings(QUILLMD_DEEPGRAM_SMART_FORMAT='true')
    def test_smart_formatting_is_a_setting_recorded_with_the_job(self):
        job = self.queue('smart-format')
        self.assertEqual(job.config['deepgram_parameters'], {**DEFAULT, 'smart_format': 'true'})
        self.assertEqual(self.run_worker().call_args.kwargs['params'], {**DEFAULT, 'smart_format': 'true'})

    def test_a_queued_job_keeps_the_parameters_it_was_queued_with(self):
        self.queue('queued-before-change')
        with override_settings(QUILLMD_DEEPGRAM_SMART_FORMAT='true', QUILLMD_DEEPGRAM_MIP_OPT_OUT='true'):
            self.assertEqual(self.run_worker().call_args.kwargs['params'], DEFAULT)

    def test_smart_formatting_does_not_change_the_priced_configuration(self):
        """Smart Formatting is 'Included' on https://deepgram.com/pricing (read 2026-09-27): no quote moves."""
        with patch.dict(os.environ, self.VOICE_ENV):
            before = generation.configuration()['pricing_version']
            with override_settings(QUILLMD_DEEPGRAM_SMART_FORMAT='true'):
                self.assertEqual(generation.configuration()['pricing_version'], before)


class RecordedParameters(SimpleTestCase):
    def test_a_job_queued_before_parameters_were_recorded_sends_the_current_setting(self):
        legacy = SimpleNamespace(config={'voice_rate_minute': '0.006'})
        self.assertEqual(request_parameters(legacy), DEFAULT)
        self.assertEqual(request_parameters(SimpleNamespace(config=None)), DEFAULT)
        with override_settings(QUILLMD_DEEPGRAM_MIP_OPT_OUT='true'):
            self.assertEqual(request_parameters(legacy), OPTED_OUT)
        with override_settings(**REAL):
            self.assertEqual(request_parameters(legacy), OPTED_OUT)

    def test_an_unrecognised_recorded_value_sends_nothing(self):
        for recorded in ({**OPTED_OUT, 'mip_opt_out': 'no'}, {**DEFAULT, 'model': 'another-model'},
                         {**DEFAULT, 'callback': 'https://example.invalid'}, {'model': 'nova-3-medical'},
                         {'model': 'nova-3-medical', 'mip_opt_out': 'true'}, {**DEFAULT, 'smart_format': True}, 'model=nova-3-medical'):
            with self.subTest(recorded=recorded), self.assertRaises(NoProviderRequest):
                request_parameters(SimpleNamespace(config={'deepgram_parameters': recorded}))

    @override_settings(**REAL)
    def test_real_mode_refuses_any_recorded_request_without_the_opt_out(self):
        self.assertEqual(request_parameters(SimpleNamespace(config={'deepgram_parameters': OPTED_OUT})), OPTED_OUT)
        for recorded in (DEFAULT, {**DEFAULT, 'mip_opt_out': 'false'}):
            with self.subTest(recorded=recorded), self.assertRaises(NoProviderRequest):
                request_parameters(SimpleNamespace(config={'deepgram_parameters': recorded}))


class OptOutDefaultFollowsTheDataMode(SimpleTestCase):
    def test_the_profile_default(self):
        self.assertIsNone(profile.deepgram_mip_opt_out({}, 'synthetic'))
        self.assertIsNone(profile.deepgram_mip_opt_out({'QUILLMD_DEEPGRAM_MIP_OPT_OUT': ' '}, 'synthetic'))
        self.assertEqual(profile.deepgram_mip_opt_out({}, 'real'), 'true')
        for mode in ('synthetic', 'real'):
            for value in ('true', 'false'):
                with self.subTest(mode=mode, value=value):
                    self.assertEqual(profile.deepgram_mip_opt_out({'QUILLMD_DEEPGRAM_MIP_OPT_OUT': value}, mode), value)
            with self.subTest(mode=mode, value='yes'), self.assertRaises(profile.ProfileError):
                profile.deepgram_mip_opt_out({'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'yes'}, mode)

    def test_the_setting_at_a_service_start(self):
        expression = '{"mode": s.QUILLMD_DATA_MODE, "mip": s.QUILLMD_DEEPGRAM_MIP_OPT_OUT}'
        for env, expected in (({}, {'mode': 'synthetic', 'mip': None}),
                              ({'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'true'}, {'mode': 'synthetic', 'mip': 'true'}),
                              ({'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'false'}, {'mode': 'synthetic', 'mip': 'false'}),
                              (COMPLETE_REAL, {'mode': 'real', 'mip': 'true'}),
                              ({**COMPLETE_REAL, 'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'true'}, {'mode': 'real', 'mip': 'true'})):
            with self.subTest(env=env):
                result = start(env, expression)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), expected)
        result = start({**COMPLETE_REAL, 'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'false'}, expression)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("QUILLMD_DEEPGRAM_MIP_OPT_OUT must be 'true'", result.stderr)
