"""Lifecycle regression tests: bounded local child processes and fake Docker control.

No Docker daemon, host service, provider, real key or live backup is used here.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    from . import managed_helper as helper
except ImportError:
    import managed_helper as helper


def response(code=0, value=b''):
    return subprocess.CompletedProcess([], code, value, b'')


def arguments(code='print("synthetic")'):
    return ['docker', 'run', '--rm', '--pull=never', '--log-driver=none',
            '--network=none', helper.IMAGE, 'python', '-B', '-c', code]


class BoundedTransportTests(unittest.TestCase):
    def test_binary_duplex_transport_and_stderr_not_returned(self):
        data = bytes(range(256)) * 1024
        script = 'import sys; sys.stderr.write("SYNTHETIC_SECRET"); sys.stdout.buffer.write(sys.stdin.buffer.read())'
        result = helper._stream([sys.executable, '-B', '-c', script], data, 3, len(data), 65536)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, data)
        self.assertEqual(result.stderr, b'')

    def test_stream_limits_refuse_before_unbounded_read_and_never_quote_canary(self):
        for channel in ('stdout', 'stderr'):
            code = 'import sys; sys.' + channel + '.buffer.write(b"SYNTHETIC_SECRET"*1000)'
            with self.subTest(channel=channel), self.assertRaises(helper.HelperFailure) as caught:
                helper._stream([sys.executable, '-B', '-c', code], b'', 2, 32, 32)
            self.assertEqual(caught.exception.reason, 'output_limit')
            self.assertNotIn('SYNTHETIC_SECRET', str(caught.exception))
            self.assertFalse(hasattr(caught.exception, 'stdout'))

    def test_client_deadline_does_not_wait_for_child_sleep(self):
        started = time.monotonic()
        with self.assertRaises(helper.HelperFailure) as caught:
            helper._stream([sys.executable, '-B', '-c', 'import time; time.sleep(5)'], b'', 0.08, 64, 64)
        self.assertEqual(caught.exception.reason, 'deadline')
        self.assertLess(time.monotonic() - started, 2)

    def test_in_container_absolute_deadline_exits_without_a_parent_cleanup(self):
        prepared, wrapped = helper._prepared(
            ['docker', 'run', '--rm', '--pull=never', '--log-driver=none', helper.IMAGE, 'python', '-'],
            b'import time; time.sleep(5)', 0.12, 'synthetic-name', 'synthetic-token')
        started = time.monotonic()
        child = subprocess.run([sys.executable, '-B', '-c', prepared[-1]], input=wrapped, capture_output=True, timeout=2)
        self.assertEqual(child.returncode, 124)
        self.assertEqual(child.stdout + child.stderr, b'')
        self.assertLess(time.monotonic() - started, 1)

    def test_stalled_stdin_cannot_delay_absolute_alarm(self):
        prepared, _ = helper._prepared(
            ['docker', 'run', '--rm', '--pull=never', '--log-driver=none', helper.IMAGE, 'python', '-'],
            b'', 0.12, 'synthetic-name', 'synthetic-token')
        child = subprocess.Popen([sys.executable, '-B', '-c', prepared[-1]],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            child.stdin.write(b'import time;')
            child.stdin.flush()  # deliberately keep stdin open, no complete source
            self.assertEqual(child.wait(timeout=2), 124)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2)
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()


class ManagedOwnershipTests(unittest.TestCase):
    def test_fixed_binary_environment_and_image_no_untrusted_lookup(self):
        prepared, data = helper._prepared(arguments(), b'{}', 5, 'my-name', 'my-token')
        self.assertEqual(prepared[:2], ['/usr/bin/docker', 'run'])
        self.assertIn(helper.IMAGE, prepared)
        self.assertIn(helper.LABEL + '=my-token', prepared)
        self.assertEqual(helper.ENV['DOCKER_HOST'], 'unix:///run/docker.sock')
        self.assertIn('signal.setitimer', prepared[-1])
        for bad in (arguments() + ['extra'],
                    [part if part != helper.IMAGE else 'python:3-slim' for part in arguments()],
                    arguments()[:2] + ['--name=other'] + arguments()[2:]):
            with self.subTest(bad=bad), patch.object(helper, '_stream') as stream, self.assertRaises(helper.HelperFailure):
                helper.run_helper(bad, timeout=1)
            stream.assert_not_called()

    def test_timeout_cleans_owned_container_and_preserves_safe_reason(self):
        with patch.object(helper, '_stream', side_effect=helper.HelperFailure('deadline')), \
                patch.object(helper, 'cleanup', return_value='removed') as cleanup:
            with self.assertRaises(helper.HelperFailure) as caught:
                helper.run_helper(arguments(), timeout=1)
        cleanup.assert_called_once()
        name, token = cleanup.call_args.args
        self.assertEqual(name, 'quillmd-helper-' + token)
        self.assertRegex(token, '^[a-f0-9]{32}$')
        self.assertTrue(caught.exception.cleanup_complete)
        self.assertEqual(caught.exception.container_name, name)
        self.assertEqual(caught.exception.reason, 'deadline')

    def test_interruption_cleanup_and_uncertain_queued_create_not_claimed_complete(self):
        for outcome in ('removed', 'absent'):
            with self.subTest(outcome=outcome), patch.object(helper, '_stream', side_effect=KeyboardInterrupt), \
                    patch.object(helper, 'cleanup', return_value=outcome):
                with self.assertRaises(helper.HelperFailure) as caught:
                    helper.run_helper(arguments(), timeout=1)
            self.assertEqual(caught.exception.cleanup_complete, outcome == 'removed')

    def test_success_output_with_failed_cleanup_is_not_success(self):
        with patch.object(helper, '_stream', return_value=response(0, b'SYNTHETIC_SECRET')), \
                patch.object(helper, 'cleanup', side_effect=RuntimeError('SYNTHETIC_SECRET')):
            with self.assertRaises(helper.HelperFailure) as caught:
                helper.run_helper(arguments(), timeout=1)
        self.assertEqual(caught.exception.reason, 'cleanup_failed')
        self.assertFalse(caught.exception.cleanup_complete)
        self.assertNotIn('SYNTHETIC_SECRET', str(caught.exception))

    def test_competing_invocations_have_independent_names_and_cleanup(self):
        barrier = threading.Barrier(2)
        seen = []
        def stream(*args):
            barrier.wait(timeout=2)
            return response(0, b'{}')
        def cleanup(name, token):
            seen.append((name, token))
            return 'absent'
        with patch.object(helper, '_stream', side_effect=stream), patch.object(helper, 'cleanup', side_effect=cleanup):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: helper.run_helper(arguments(), timeout=2).stdout, range(2)))
        self.assertEqual(results, [b'{}', b'{}'])
        self.assertEqual(len(set(seen)), 2)
        self.assertTrue(all(name == 'quillmd-helper-' + token for name, token in seen))

    def test_redacted_failure_receipt_survives_outer_exception_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            with patch.object(helper, '_stream', side_effect=helper.HelperFailure('deadline')), \
                    patch.object(helper, 'cleanup', side_effect=RuntimeError('SYNTHETIC_SECRET')):
                with self.assertRaises(helper.HelperFailure):
                    helper.run_helper(arguments(), timeout=1, failure_directory=root)
            receipts = list(root.glob('helper-failure-*.json'))
            self.assertEqual(len(receipts), 1)
            raw = receipts[0].read_text()
            value = json.loads(raw)
            self.assertEqual(value['reason'], 'cleanup_failed')
            self.assertEqual(value['operation_reason'], 'deadline')
            self.assertFalse(value['cleanup_complete'])
            self.assertRegex(value['container_name'], '^quillmd-helper-[a-f0-9]{32}$')
            self.assertNotIn('SYNTHETIC_SECRET', raw)
            self.assertEqual(receipts[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(receipts[0].stat().st_nlink, 1)

    def test_failure_receipt_unsafe_directory_and_existing_entry_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.mkdir(mode=0o700)
            link = root / 'symlink'
            link.symlink_to(target, target_is_directory=True)
            failure = helper.HelperFailure('deadline', container_name='quillmd-helper-fixture')
            with self.assertRaises(helper.HelperFailure):
                helper._failure_receipt(link, 'a' * 32, failure)
            target.chmod(0o755)
            with self.assertRaises(helper.HelperFailure):
                helper._failure_receipt(target, 'a' * 32, failure)
            target.chmod(0o700)
            helper._failure_receipt(target, 'a' * 32, failure)
            before = next(target.iterdir()).read_bytes()
            with self.assertRaises(FileExistsError):
                helper._failure_receipt(target, 'a' * 32, failure)
            self.assertEqual(next(target.iterdir()).read_bytes(), before)

    def test_cleanup_uses_immutable_id_and_never_removes_name_replacement(self):
        original = {'Id': 'a' * 64, 'Name': '/mine', 'Image': helper.IMAGE, 'Token': 'token'}
        calls = []
        def control(argv):
            calls.append(argv)
            if argv[0] == 'inspect':
                return response(0, json.dumps(original).encode())
            if argv[0] == 'rm':
                return response()
            return response(0, ('b' * 64).encode())  # another actor reused the name
        with patch.object(helper, '_control', side_effect=control), self.assertRaises(helper.HelperFailure):
            helper.cleanup('mine', 'token')
        self.assertIn(['rm', '--force', 'a' * 64], calls)
        self.assertFalse(any(argv[0] == 'rm' and argv[-1] in {'mine', 'b' * 64} for argv in calls))

    def test_foreign_label_or_image_is_retained_and_failed_daemon_not_absence(self):
        for field, wrong in (('Token', 'foreign'), ('Image', 'sha256:' + 'b' * 64), ('Id', 'not-an-id')):
            row = {'Id': 'a' * 64, 'Name': '/mine', 'Image': helper.IMAGE, 'Token': 'token'}
            row[field] = wrong
            with self.subTest(field=field), patch.object(helper, '_control', return_value=response(0, json.dumps(row).encode())) as control:
                with self.assertRaises(helper.HelperFailure):
                    helper.cleanup('mine', 'token')
                control.assert_called_once()
        with patch.object(helper, '_control', return_value=response(1)) as control:
            with self.assertRaises(helper.HelperFailure):
                helper.cleanup('mine', 'token')
            self.assertEqual(control.call_count, 2)


if __name__ == '__main__':
    unittest.main()
