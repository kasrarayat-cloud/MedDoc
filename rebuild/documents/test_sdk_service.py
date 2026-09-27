"""Actual subprocess bounds and fail-closed parent response validation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from documents import sdk_service
from documents.service import DocumentError


class SdkParentTests(unittest.TestCase):
    def child(self, code):
        with tempfile.TemporaryDirectory() as directory:
            return sdk_service._bounded_process([sys.executable, '-I', '-c', code], Path(directory), {'PATH': '/usr/bin:/bin'})

    def test_real_child_stdout_and_stderr_are_drained_without_echo(self):
        code, output = self.child("import sys; sys.stderr.write('private diagnostic'); print('{\"ok\":true}')")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {'ok': True})
        self.assertNotIn(b'private', output)

    def test_actual_stdout_and_stderr_floods_refuse_and_child_is_reaped(self):
        for fd, size in [(1, sdk_service.MAX_RESPONSE + 65536), (2, 131072)]:
            with self.subTest(fd=fd), self.assertRaisesRegex(sdk_service.SdkUnavailable, 'exceeded'):
                self.child(f"import os; os.write({fd}, b'x'*{size}); import time; time.sleep(30)")

    def test_actual_child_timeout_is_bounded(self):
        with patch.object(sdk_service, 'TIMEOUT_SECONDS', 0.05), self.assertRaisesRegex(sdk_service.SdkUnavailable, 'time limit'):
            self.child('import time; time.sleep(30)')

    def response(self, code, value):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(sdk_service, 'configuration', return_value=(Path('/reviewed/runtime'), Path('/reviewed/manifest'), 'a'*64)), \
                patch.object(sdk_service, '_bounded_process', return_value=(code, raw)), \
                patch.dict(os.environ, {'QUILLMD_STATE_DIR': directory}, clear=True):
            return sdk_service.run(Path(directory), {'operation': 'inspect'})

    def test_nonzero_review_refusal_has_fixed_parent_message(self):
        with self.assertRaises(DocumentError) as caught:
            self.response(2, {'error': 'untrusted source content', 'code': 'unsupported_assertion'})
        self.assertEqual(caught.exception.code, 'unsupported_assertion')
        self.assertNotIn('untrusted', str(caught.exception))
        with self.assertRaises(sdk_service.SdkUnavailable):
            self.response(2, {'error': 'private SDK stack trace', 'code': 'unknown_diagnostic'})

    def test_duplicate_keys_malformed_mapping_and_false_success_refuse(self):
        base = {'backend': sdk_service.BACKEND, 'format': 'docx', 'source_sha256': sdk_service.WM_IOV_SHA256,
                'fields': [{'key': str(n)} for n in range(90)], 'review_requirements': [{}]*14}
        self.assertEqual(self.response(0, base)['backend'], sdk_service.BACKEND)
        for code, value in [(0, b'{"backend":"one","backend":"two"}'),
                            (2, base), (0, {**base, 'source_sha256': '0'*64}),
                            (0, {**base, 'fields': [{'key': []}]*90})]:
            with self.subTest(code=code), self.assertRaises(sdk_service.SdkUnavailable):
                self.response(code, value)

    def test_actual_second_process_cannot_overlap_or_deadlock_processor_slot(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'QUILLMD_STATE_DIR': directory}):
            code = ('from documents import sdk_service as s; s.SLOT_TIMEOUT_SECONDS=0.1\n'
                    'try:\n with s._processing_slot(): print("acquired")\n'
                    'except s.SdkUnavailable: print("busy")\n')
            with sdk_service._processing_slot():
                result = subprocess.check_output([sys.executable, '-c', code], text=True)
                self.assertEqual(result.strip(), 'busy')
            result = subprocess.check_output([sys.executable, '-c', code], text=True)
            self.assertEqual(result.strip(), 'acquired')



class ManagedRootPairingTests(unittest.TestCase):
    """The launcher-fixed state root selects the reviewed Word installation; private is unchanged."""
    PRODUCTION_STATE = '/var/lib/quillmd-production'

    def activated(self):
        from ops import deployment_profile
        raw = json.loads(deployment_profile.PROFILE_PATH.read_text())
        raw['database']['host'] = 'quillmd-production.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'
        raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
        return deployment_profile.validate(raw)

    def test_private_state_keeps_the_private_installation_and_never_reads_the_production_record(self):
        with patch('ops.deployment_profile.load_production', side_effect=AssertionError('read')), \
                patch.dict(os.environ, {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_STATE_DIR': '/var/lib/quillmd'}, clear=True):
            self.assertEqual(sdk_service._managed_word_root(), Path('/opt/meddoc-pro/rebuild/.word-sdk'))
            self.assertTrue(sdk_service._managed_state(Path('/var/lib/quillmd')))

    def test_unknown_or_unactivated_states_fall_back_to_the_private_installation(self):
        for state in ('', '/tmp/other', self.PRODUCTION_STATE):
            with self.subTest(state=state), patch.dict(os.environ, {'QUILLMD_STATE_DIR': state}, clear=True):
                # The checked-in production record is not activated, so it selects nothing.
                self.assertEqual(sdk_service._managed_word_root(), Path('/opt/meddoc-pro/rebuild/.word-sdk'))
        self.assertFalse(sdk_service._managed_state(Path(self.PRODUCTION_STATE)))
        self.assertFalse(sdk_service._managed_state(Path('/tmp/other')))

    def test_activated_production_state_selects_only_the_production_installation(self):
        with patch('ops.deployment_profile.load_production', return_value=self.activated()):
            with patch.dict(os.environ, {'QUILLMD_STATE_DIR': self.PRODUCTION_STATE}, clear=True):
                self.assertEqual(sdk_service._managed_word_root(), Path('/opt/quillmd-production/rebuild/.word-sdk'))
            self.assertTrue(sdk_service._managed_state(Path(self.PRODUCTION_STATE)))
            self.assertTrue(sdk_service._managed_state(Path('/var/lib/quillmd')))
            self.assertFalse(sdk_service._managed_state(Path('/var/lib/quillmd-production/files')))
            with patch.dict(os.environ, {'QUILLMD_STATE_DIR': '/var/lib/quillmd'}, clear=True):
                self.assertEqual(sdk_service._managed_word_root(), Path('/opt/meddoc-pro/rebuild/.word-sdk'))

    def test_managed_configuration_refuses_a_runtime_outside_the_paired_installation(self):
        values = {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_STATE_DIR': '/var/lib/quillmd',
                  'QUILLMD_WORD_RUNTIME': '/opt/quillmd-production/rebuild/.word-sdk/runtime',
                  'QUILLMD_WORD_MANIFEST': '/opt/quillmd-production/rebuild/.word-sdk/manifest.json',
                  'QUILLMD_WORD_MANIFEST_SHA256': 'a' * 64}
        with patch('ops.deployment_profile.load_production', return_value=self.activated()), \
                patch.dict(os.environ, values, clear=True), \
                self.assertRaisesRegex(sdk_service.SdkUnavailable, 'reviewed application installation'):
            sdk_service.configuration()

    def test_managed_slot_refuses_an_unpaired_state_root(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_STATE_DIR': directory}, clear=True), \
                self.assertRaisesRegex(sdk_service.SdkUnavailable, 'managed Word processing state is unavailable'):
            with sdk_service._processing_slot():
                pass


if __name__ == '__main__':
    unittest.main()
