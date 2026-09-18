import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
try:
    from . import backup_restore as b
except ImportError:
    import backup_restore as b


class BackupSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.cipher = Fernet(Fernet.generate_key())

    def test_private_write_refuses_existing_destination(self):
        dest = self.root / 'key'
        b.write_private(dest, b'synthetic')
        with self.assertRaises(FileExistsError):
            b.write_private(dest, b'replacement')
        self.assertEqual(dest.read_bytes(), b'synthetic')
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)

    def test_private_file_symlink_refused(self):
        dest = self.root / 'key'
        b.write_private(dest, b'synthetic')
        link = self.root / 'link'
        link.symlink_to(dest)
        with self.assertRaises(RuntimeError):
            b.read_private(link)

    def test_world_readable_key_refused(self):
        dest = self.root / 'key'
        b.write_private(dest, Fernet.generate_key())
        dest.chmod(0o644)
        with self.assertRaises(RuntimeError):
            b.key_at(dest)

    def test_path_traversal_and_noncanonical_paths_refused(self):
        for name in ('../secret', '/secret', 'one/../secret', 'a//b', 'a\\b', ''):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                b.safe_relative(name)

    def test_media_symlink_outside_root_refused(self):
        (self.root / 'out').symlink_to('/etc/passwd')
        with self.assertRaises(RuntimeError):
            b.file_data(self.root, 'out')

    def object(self):
        plain = b'synthetic original bytes'
        encrypted = self.cipher.encrypt(plain)
        path = self.root / 'object'
        b.write_private(path, encrypted)
        return path, {'cipher_sha256': b.digest(encrypted), 'sha256': b.digest(plain), 'size': len(plain)}

    def test_ciphertext_tamper_refused(self):
        path, metadata = self.object()
        path.write_bytes(path.read_bytes()[:-3] + b'abc')
        with self.assertRaises(RuntimeError):
            b.decrypt_checked(path, metadata, self.cipher)

    def test_wrong_key_refused(self):
        path, metadata = self.object()
        with self.assertRaises(InvalidToken):
            b.decrypt_checked(path, metadata, Fernet(Fernet.generate_key()))

    def test_authenticated_wrong_object_not_accepted(self):
        path, metadata = self.object()
        replacement = self.cipher.encrypt(b'different authenticated data')
        path.write_bytes(replacement)
        metadata['cipher_sha256'] = b.digest(replacement)
        with self.assertRaises(RuntimeError):
            b.decrypt_checked(path, metadata, self.cipher)

    def test_incomplete_backup_refused_before_decrypt(self):
        b.write_private(self.root / 'INCOMPLETE', b'failed')
        with self.assertRaises(RuntimeError):
            b.load_backup(self.root, self.cipher)

    def test_duplicate_restore_paths_refused(self):
        row = {'path': 'originals/synthetic.docx', 'object': 'objects/' + 'a' * 64 + '.fernet'}
        manifest = {'format': 1, 'complete': True, 'database': b.SOURCE_DATABASE,
                    'files': [row, row], 'image_id': 'sha256:' + 'a' * 64}
        b.write_private(self.root / 'manifest.json.fernet', self.cipher.encrypt(json.dumps(manifest).encode()))
        with self.assertRaises(RuntimeError):
            b.load_backup(self.root, self.cipher)

    def test_restore_check_writes_no_decrypted_documents_and_never_swaps(self):
        import inspect
        source = inspect.getsource(b.restore)
        self.assertNotIn("/ 'files'", source)
        self.assertEqual(source.count('write_private('), 1)
        self.assertIn("write_private(restored / 'verification.json'", source)
        self.assertIn("'--memory', '768m', '--memory-swap', '768m'", source)
        self.assertIn("'--tmpfs', '/var/lib/postgresql/data:", source)
        self.assertIn('decrypted_files_written=0', source)

    def test_restore_cleanup_rejects_other_container(self):
        metadata = {'Config': {'Labels': {b.LABEL: 'another-run'}},
                    'HostConfig': {'NetworkMode': 'none', 'PortBindings': {}}}
        with patch.object(b, 'inspect_container', return_value=metadata), patch.object(b, 'run') as execute:
            with self.assertRaises(RuntimeError):
                b.remove_owned_restore('unrelated', 'this-run')
            execute.assert_not_called()

    def test_restore_cleanup_rejects_published_port(self):
        metadata = {'Config': {'Labels': {b.LABEL: 'this-run'}},
                    'HostConfig': {'NetworkMode': 'bridge', 'PortBindings': {'5432/tcp': []}}}
        with patch.object(b, 'inspect_container', return_value=metadata), patch.object(b, 'run') as execute:
            with self.assertRaises(RuntimeError):
                b.remove_owned_restore('quillmd-restore-this-run', 'this-run')
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
