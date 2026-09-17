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


if __name__ == '__main__':
    unittest.main()
