"""Synthetic custody preparation guards; no external vault/provider is exercised."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken

try:
    from . import recovery_kit as kit
except ImportError:
    import recovery_kit as kit


class RecoveryKitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.secrets = self.root / 'backup-secrets'; self.secrets.mkdir(mode=0o700)
        self.backups = self.root / 'backups'; self.backups.mkdir(mode=0o700)
        self.handoff = self.root / 'handoff'
        self.key = self.secrets / 'current.key'
        self.key_bytes = Fernet.generate_key()
        self.write(self.key, self.key_bytes)
        self.cipher = Fernet(self.key_bytes)
        self.run_id = '20260920T095332Z-a9da0017'
        self.backup = self.backups / self.run_id; self.backup.mkdir(mode=0o700)
        plain = b'Synthetic database fixture only; not PostgreSQL'
        encrypted = self.cipher.encrypt(plain)
        self.manifest = {'format': 1, 'complete': True, 'database': 'quillmd_fresh', 'run_id': self.run_id,
                         'image_id': 'sha256:' + 'c' * 64, 'files': [],
                         'tables': {'synthetic': {'rows': 7, 'sha256': 'd' * 64}},
                         'dump': {'sha256': kit.offsite.backup.digest(plain), 'size': len(plain),
                                  'cipher_sha256': kit.offsite.backup.digest(encrypted)}}
        payload = self.cipher.encrypt(json.dumps(self.manifest).encode())
        self.write(self.backup / 'manifest.json.fernet', payload)
        self.sha = kit.offsite.backup.digest(payload)
        self.report = self.root / 'offsite.json'
        self.write(self.report, json.dumps({'complete': True, 'live_transport': True, 'transport_verified': True,
                   'restore_verified': True, 'backup_run_id': self.run_id, 'manifest_cipher_sha256': self.sha}).encode())
        self.config = {'version': 1, 'endpoint': 'https://s3.us-west-004.backblazeb2.com', 'region': 'us-west-004',
                       'bucket': 'synthetic-test-bucket', 'bucket_id': 'b' * 24, 'prefix': kit.offsite.PREFIX,
                       'application_key_id': 'synthetic-key-id', 'application_key': 'DO-NOT-PRINT-synthetic-secret',
                       'owner_approval_reference': 'synthetic only', 'private_bucket_confirmed': True, 'synthetic_only': True}
        self.config_path = self.secrets / 'b2.json'; self.write(self.config_path, json.dumps(self.config).encode())
        for target, values in [(kit, {'PROJECT': self.root, 'RUNTIME': self.root, 'SECRETS': self.secrets,
                                     'LIVE_KEY': self.key, 'CONFIG': self.config_path, 'BACKUPS': self.backups,
                                     'HANDOFF': self.handoff}),
                               (kit.offsite, {'CONFIG_PARENT': self.secrets})]:
            for name, value in values.items():
                p = patch.object(target, name, value); p.start(); self.addCleanup(p.stop)
        def metadata(command, **kwargs):
            if command[0] == 'git':
                return 'a' * 40 + '\n'
            if command[:3] == ['docker', 'image', 'inspect']:
                return json.dumps([{'Id': 'sha256:' + 'c' * 64, 'Os': 'linux', 'Architecture': 'amd64',
                                    'RepoDigests': ['postgres@sha256:' + 'e' * 64]}])
            raise AssertionError('Unexpected subprocess')
        p = patch.object(kit.subprocess, 'check_output', side_effect=metadata)
        p.start(); self.addCleanup(p.stop)

    def write(self, path, data):
        kit.offsite.backup.write_private(path, data)

    def prepared(self):
        result = kit.prepare(self.report)
        return Path(result['selection_manifest']), self.handoff / kit.RETURNED_NAME

    def test_prepare_creates_only_nonsecret_manifest_and_empty_private_return_destination(self):
        original = self.key.read_bytes(), self.config_path.read_bytes()
        selection, returned = self.prepared()
        data = selection.read_bytes()
        self.assertNotIn(self.key_bytes, data)
        self.assertNotIn(self.config['application_key'].encode(), data)
        self.assertEqual(returned.read_bytes(), b'')
        self.assertEqual(selection.stat().st_mode & 0o777, 0o600)
        self.assertEqual(returned.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.handoff.stat().st_mode & 0o777, 0o700)
        manifest = json.loads(data)
        self.assertFalse(manifest['independent_custody_verified'])
        self.assertFalse(manifest['disk_unlock_material']['required_for_clean_offsite_restore'])
        self.assertEqual(manifest['row_count'], 7)
        self.assertTrue(manifest['restore_prerequisites']['requires_current_account_evidence_and_shared_allowance'])
        self.assertEqual(manifest['restore_prerequisites']['transport_version'], kit.offsite.TRANSPORT_VERSION)
        self.assertEqual((self.key.read_bytes(), self.config_path.read_bytes()), original)

    def test_existing_selection_is_preserved(self):
        selection, _ = self.prepared(); before = selection.read_bytes()
        with self.assertRaises(FileExistsError):
            kit.prepare(self.report)
        self.assertEqual(selection.read_bytes(), before)

    def test_existing_returned_material_is_preserved(self):
        self.handoff.mkdir(mode=0o700)
        returned = self.handoff / kit.RETURNED_NAME
        self.write(returned, b'Existing owner material preserved')
        self.prepared()
        self.assertEqual(returned.read_bytes(), b'Existing owner material preserved')

    def test_existing_returned_symlink_refused_before_selection_write(self):
        self.handoff.mkdir(mode=0o700)
        (self.handoff / kit.RETURNED_NAME).symlink_to(self.key)
        with self.assertRaises(RuntimeError):
            kit.prepare(self.report)
        self.assertEqual(list(self.handoff.glob('selection-*')), [])

    def test_unsafe_source_secret_directory_refused(self):
        self.secrets.chmod(0o755)
        with self.assertRaises(RuntimeError):
            kit.prepare(self.report)
        self.assertFalse(self.handoff.exists())

    def test_missing_or_mismatched_local_image_refused(self):
        with patch.object(kit.subprocess, 'check_output', return_value=json.dumps(
                [{'Id': 'sha256:' + '0' * 64, 'Os': 'linux', 'Architecture': 'amd64', 'RepoDigests': []}])):
            with self.assertRaises(RuntimeError):
                kit.image_requirements(self.manifest['image_id'])

    def test_symlink_handoff_directory_refused(self):
        self.handoff.symlink_to(self.secrets, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            kit.prepare(self.report)
        self.assertFalse((self.secrets / kit.RETURNED_NAME).exists())

    def test_nonprivate_handoff_directory_refused(self):
        self.handoff.mkdir(mode=0o755)
        self.handoff.chmod(0o755)
        with self.assertRaises(RuntimeError):
            kit.prepare(self.report)
        self.assertEqual(list(self.handoff.iterdir()), [])

    def test_returned_copy_works_without_live_key_or_config_and_does_not_claim_custody(self):
        selection, returned = self.prepared()
        returned.write_bytes(self.key_bytes)
        self.key.unlink(); self.config_path.unlink()
        result = kit.verify_returned(selection, returned)
        self.assertTrue(result['returned_key_authenticates_selected_manifest'])
        self.assertFalse(result['live_key_read'])
        self.assertFalse(result['independent_custody_verified'])
        self.assertFalse(result['isolated_restore_performed'])
        self.assertEqual(result['network_calls'], 0)

    def test_wrong_returned_key_never_falls_back_to_valid_live_key(self):
        selection, returned = self.prepared()
        returned.write_bytes(Fernet.generate_key())
        with self.assertRaises(InvalidToken):
            kit.verify_returned(selection, returned)
        self.assertEqual(self.key.read_bytes(), self.key_bytes)

    def test_live_key_path_refused(self):
        selection, _ = self.prepared()
        with self.assertRaises(RuntimeError):
            kit.verify_returned(selection, self.key)

    def test_returned_key_symlink_and_hardlink_refused(self):
        selection, returned = self.prepared()
        returned.unlink(); returned.symlink_to(self.key)
        with self.assertRaises(RuntimeError):
            kit.verify_returned(selection, returned)
        returned.unlink(); os.link(self.key, returned)
        with self.assertRaises(RuntimeError):
            kit.verify_returned(selection, returned)

    def test_returned_key_nonprivate_mode_refused(self):
        selection, returned = self.prepared()
        returned.write_bytes(self.key_bytes); returned.chmod(0o644)
        with self.assertRaises(RuntimeError):
            kit.verify_returned(selection, returned)

    def test_missing_and_empty_returned_keys_fail_without_fallback(self):
        selection, returned = self.prepared()
        with self.assertRaises(ValueError):
            kit.verify_returned(selection, returned)
        returned.unlink()
        with self.assertRaises(FileNotFoundError):
            kit.verify_returned(selection, returned)

    def test_bad_manifest_hash_or_image_refused(self):
        selection, returned = self.prepared(); returned.write_bytes(self.key_bytes)
        data = json.loads(selection.read_text())
        for field, value in [('manifest_cipher_sha256', '0' * 64), ('postgres_image_id', 'sha256:' + '0' * 64)]:
            changed = dict(data, **{field: value}); selection.write_text(json.dumps(changed))
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                kit.verify_returned(selection, returned)

    def test_incomplete_or_simulated_offsite_report_not_accepted(self):
        data = json.loads(self.report.read_text())
        for field in ['complete', 'live_transport', 'transport_verified', 'restore_verified']:
            self.report.write_text(json.dumps(dict(data, **{field: False})))
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                kit.prepare(self.report)

    def test_cli_failure_redacts_private_contents_and_exception_text(self):
        selection, returned = self.prepared()
        returned.write_bytes(b'DO-NOT-PRINT-private-invalid-key')
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = kit.main(['verify-returned', '--selection', str(selection), '--returned-key', str(returned)])
        self.assertEqual(code, 1)
        self.assertEqual(set(json.loads(captured.getvalue())), {'complete', 'error_class', 'independent_custody_verified'})
        self.assertNotIn('DO-NOT-PRINT', captured.getvalue())
        self.assertNotIn(self.key_bytes.decode(), captured.getvalue())


if __name__ == '__main__':
    unittest.main()
