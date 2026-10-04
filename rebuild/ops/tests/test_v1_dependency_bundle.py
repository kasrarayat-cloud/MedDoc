"""Offline locator, ownership and actual bounded-child controls; zero host/DB/provider actions."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from ops import dependency_lock as lock
from ops import prepare_v1_dependency_bundle as bundle


class PrivateDependencyBundleTests(unittest.TestCase):
    def test_offline_projection_changes_only_the_exact_hash_bound_model_locator(self):
        raw = ('# preserved\nDjango==5.2.17 --hash=sha256:' + 'a' * 64 + '\n'
               + lock.MODEL_REQUIREMENT + ' --hash=sha256:' + lock.MODEL_SHA256 + '\n').encode()
        actual = bundle.offline_lock(raw)
        self.assertEqual(actual, raw.replace((lock.MODEL_REQUIREMENT + ' --hash=sha256:' + lock.MODEL_SHA256).encode(),
            ('en-core-web-sm==3.8.0 --hash=sha256:' + lock.MODEL_SHA256).encode()))
        self.assertNotIn(b'https://', actual)
        for altered in (raw.replace(lock.MODEL_SHA256.encode(), b'b' * 64), raw + raw, b'not the reviewed model'):
            with self.subTest(altered=altered[:20]), self.assertRaises(ValueError): bundle.offline_lock(altered)

    def test_wheel_filename_is_not_enough_internal_identity_and_license_material_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'wheel.whl'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('example-1.0.dist-info/METADATA', 'Name: example\nVersion: 1.0\nLicense-Expression: MIT\n')
                archive.writestr('example-1.0.dist-info/licenses/LICENSE', 'retained synthetic license fixture')
                archive.writestr('example/_vendor/another-2.0.dist-info/METADATA', 'Name: another\nVersion: 2.0\n')
            metadata = bundle.wheel_metadata(path, {'name': 'example', 'version': '1.0'})
            self.assertEqual(metadata['license_expression'], 'MIT')
            self.assertEqual(metadata['license_files'], {'example-1.0.dist-info/licenses/LICENSE':
                bundle.sha(b'retained synthetic license fixture')})
            with self.assertRaises(ValueError): bundle.wheel_metadata(path, {'name': 'another', 'version': '1.0'})

    def test_retry_identity_cannot_replace_an_existing_or_unrelated_packet(self):
        for run_id in ('../foreign', '/tmp/foreign', '', 'a' * 80, None):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                bundle.prepare(Path('/not-an-authorized-worktree'), 'a' * 40, run_id)

    def test_size_counts_own_bytes_and_rejects_external_links_without_traversing_them(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root = Path(directory); (root / 'lib').mkdir(); (root / 'lib/data').write_bytes(b'12345')
            (root / 'lib64').symlink_to(root / 'lib', target_is_directory=True)
            self.assertEqual(bundle.size(root), 5)
            (root / 'foreign').symlink_to(Path(external), target_is_directory=True)
            with self.assertRaises(ValueError): bundle.size(root)

    def test_actual_failed_child_exit_and_output_are_retained_instead_of_called_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'home').mkdir(); (root / 'tmp').mkdir()
            with self.assertRaises(ValueError): bundle.bounded([sys.executable, '-B', '-c',
                'print("retained synthetic child refusal");raise SystemExit(7)'], 'fault', root,
                deadline=time.monotonic() + 10)
            result = json.loads((root / 'fault.json').read_bytes())
            self.assertEqual(result['exit_code'], 7); self.assertIsNone(result['stop_reason'])
            self.assertIn(b'retained synthetic child refusal', (root / 'fault.log').read_bytes())

    def test_actual_owned_deadline_terminates_the_child_and_retains_its_real_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'home').mkdir(); (root / 'tmp').mkdir()
            started = time.monotonic()
            with self.assertRaises(ValueError): bundle.bounded([sys.executable, '-B', '-c',
                'import time;time.sleep(20)'], 'deadline', root, deadline=time.monotonic() - 1)
            result = json.loads((root / 'deadline.json').read_bytes())
            self.assertLess(time.monotonic() - started, 5)
            self.assertLess(result['exit_code'], 0); self.assertEqual(result['stop_reason'], 'technical_deadline')


if __name__ == '__main__':
    unittest.main()
