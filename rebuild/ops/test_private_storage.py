"""Security contracts for read-only access across the application UID boundary."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import private_storage as storage
except ImportError:
    import private_storage as storage


class PrivateStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        info = self.root.stat()
        self.expected = {'uid': os.getuid(), 'gid': os.getgid(),
                         'device': info.st_dev, 'inode': info.st_ino}

    def file(self, name='synthetic.bin', data=b'synthetic\x00file\nbytes'):
        path = self.root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    def test_complete_binary_read_and_recursive_inventory(self):
        path = self.file('one/synthetic.bin', bytes(range(256)) * 2000)
        metadata, data = storage._collect(self.root, self.expected, 'read', 'one/synthetic.bin')
        self.assertEqual(data, path.read_bytes())
        self.assertEqual(metadata['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(storage._collect(self.root, self.expected, 'inventory'),
                         {'one/synthetic.bin': metadata})

    def test_traversal_noncanonical_and_deep_paths_refused(self):
        for path in ('../secret', '/secret', 'a/../b', 'a//b', './a', '.', 'a\\b', '',
                     'a\x00b', '/'.join(['a'] * 33), 'a' * 4097):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                storage._relative(path)

    def test_symlink_files_directories_and_root_refused(self):
        self.file()
        (self.root / 'link').symlink_to(self.root / 'synthetic.bin')
        for action, relative in [('read', 'link'), ('inventory', None)]:
            with self.assertRaises(RuntimeError):
                storage._collect(self.root, self.expected, action, relative)
        (self.root / 'link').unlink()
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        for action, relative in [('read', 'link/synthetic.bin'), ('inventory', None)]:
            with self.assertRaises(RuntimeError):
                storage._collect(self.root, self.expected, action, relative)
        with self.assertRaises(RuntimeError):
            storage._collect(self.root / 'link', self.expected, 'inventory')

    def test_pinned_root_replacement_is_refused(self):
        wrong = dict(self.expected, inode=self.expected['inode'] + 1)
        with self.assertRaises(RuntimeError):
            storage._collect(self.root, wrong, 'inventory')

    def test_nonprivate_modes_and_hardlinks_refused(self):
        path = self.file()
        for mode in (0o644, 0o640, 0o666):
            path.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                storage._collect(self.root, self.expected, 'read', path.name)
        path.chmod(0o600)
        os.link(path, self.root / 'hardlink')
        with self.assertRaises(RuntimeError):
            storage._collect(self.root, self.expected, 'inventory')

    def test_nonregular_and_oversized_files_refused(self):
        os.mkfifo(self.root / 'fifo', 0o600)
        with self.assertRaises(RuntimeError):
            storage._collect(self.root, self.expected, 'inventory')
        (self.root / 'fifo').unlink()
        self.file(data=b'12345')
        with patch.object(storage, 'MAX_OBJECT_BYTES', 4), self.assertRaises(RuntimeError):
            storage._collect(self.root, self.expected, 'inventory')

    def test_inventory_entry_count_is_bounded(self):
        self.file('one')
        self.file('two')
        with patch.object(storage, 'MAX_ENTRIES', 1), self.assertRaises(RuntimeError):
            storage._collect(self.root, self.expected, 'inventory')

    def test_unapproved_roots_refused_before_docker(self):
        for root in ('/etc', '/var/lib/quillmd', '/var/lib/quillmd/files/sub',
                     '/var/lib/quillmd/../files', '/var/lib/quillmd-else/files'):
            with self.subTest(root=root), patch.object(storage, 'run_helper') as run:
                with self.assertRaises(RuntimeError):
                    storage.read_file(Path(root), 'synthetic.bin')
                run.assert_not_called()

    def test_command_runs_nonroot_without_network_caps_or_writable_mounts(self):
        expected = dict(self.expected, uid=1234, gid=1235)
        response = subprocess.CompletedProcess([], 0, b'{}', b'')
        with patch.object(storage, '_installation', return_value=expected), \
                patch.object(storage, 'run_helper', return_value=response) as run:
            self.assertEqual(storage.inventory(Path('/var/lib/quillmd/files')), {})
        args = run.call_args.args[0]
        for flag in ('--pull=never', '--network=none', '--read-only', '--cap-drop=ALL',
                     '--security-opt=no-new-privileges:true', '--pids-limit=32'):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index('--user') + 1], '1234:1235')
        self.assertEqual(args.count('--mount'), 1)
        self.assertEqual(args[args.index('--mount') + 1],
                         'type=bind,src=/var/lib/quillmd/files,dst=/data,readonly')
        self.assertFalse(any(v.startswith(('--pid', '--privileged', '--group-add', '--cap-add'))
                             for v in args if v != '--pids-limit=32'))
        self.assertNotIn('synthetic.bin', args)
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['expected'], expected)

    def test_document_bytes_are_verified_before_return(self):
        data = b'complete synthetic binary\x00'
        metadata = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'mode': 0o600}
        reply = json.dumps(metadata).encode() + b'\n' + data
        with patch.object(storage, '_execute', return_value=reply):
            self.assertEqual(storage.read_file('/var/lib/quillmd/files', 'file'), data)
        for malformed in (reply[:-1], reply + b'extra', b'no header', b'{"size":0}\n',
                          json.dumps(dict(metadata, mode=0o644)).encode() + b'\n' + data):
            with self.subTest(reply=malformed[:20]), patch.object(storage, '_execute', return_value=malformed):
                with self.assertRaisesRegex(RuntimeError, 'protected output was suppressed'):
                    storage.read_file('/var/lib/quillmd/files', 'file')

    def test_malformed_inventory_and_duplicate_keys_refused(self):
        valid = {'sha256': 'a' * 64, 'size': 3, 'mode': 0o600}
        serialized = json.dumps(valid)
        invalid = [b'not-json', b'[]', json.dumps({'../outside': valid}).encode(),
                   ('{"same":' + serialized + ',"same":' + serialized + '}').encode(),
                   json.dumps({'file': dict(valid, size=True)}).encode(),
                   json.dumps({'file': dict(valid, extra='bad')}).encode()]
        for value in invalid:
            with self.subTest(value=value[:30]), patch.object(storage, '_execute', return_value=value):
                with self.assertRaises(RuntimeError):
                    storage.inventory('/var/lib/quillmd/files')

    def test_helper_failure_never_exposes_stderr_or_content(self):
        response = subprocess.CompletedProcess([], 1, b'PRIVATE_CONTENT', b'PRIVATE_SECRET')
        with patch.object(storage, '_installation', return_value=self.expected), \
                patch.object(storage, 'run_helper', return_value=response):
            with self.assertRaises(RuntimeError) as caught:
                storage.inventory('/var/lib/quillmd/files')
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_state_root_preserves_legacy_default_and_requires_exact_new_path(self):
        self.assertEqual(storage.state_root(self.root), self.root / '.runtime')
        (self.root / '.env').write_text('QUILLMD_STATE_DIR=/var/lib/quillmd\n')
        self.assertEqual(storage.state_root(self.root), Path('/var/lib/quillmd'))
        for value in ('/tmp/quillmd', '/var/lib/quillmd/', '/var/lib/../lib/quillmd', 'relative'):
            (self.root / '.env').write_text('QUILLMD_STATE_DIR=' + value + '\n')
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                storage.state_root(self.root)

    def test_generated_helper_compiles_without_host_dependencies(self):
        source = storage._helper_source()
        compile(source, '<private-storage-helper>', 'exec')
        self.assertNotIn('dotenv', source)
        self.assertNotIn('subprocess', source)

    def installation_fixture(self):
        account = SimpleNamespace(pw_uid=2345, pw_gid=2346)
        identity = self.file('state-identity.json', json.dumps({
            'version': 1, 'account': {'name': storage.APP_ACCOUNT, 'uid': 2345, 'gid': 2346},
            'roots': {str(root): {'device': 8, 'inode': index + 10}
                      for index, root in enumerate(sorted(storage.APPROVED_ROOTS))}
        }).encode())
        real_stat = Path.lstat
        def lstat(path):
            if path in (Path('/'), Path('/var'), Path('/var/lib'), storage.STATE_DIR):
                return SimpleNamespace(st_uid=0, st_gid=2346 if path == storage.STATE_DIR else 0,
                                       st_mode=0o040710 if path == storage.STATE_DIR else 0o040755)
            return real_stat(path)
        return account, identity, lstat

    def test_identity_proof_pins_uid_and_root_without_granting_operator_membership(self):
        account, identity, lstat = self.installation_fixture()
        with patch.object(storage, 'IDENTITY_FILE', identity), patch.object(Path, 'lstat', lstat), \
                patch.object(storage.pwd, 'getpwnam', return_value=account), \
                patch.object(storage.os, 'getgrouplist', return_value=[2346]):
            result = storage._installation(Path('/var/lib/quillmd/files'))
            self.assertEqual(result, {'uid': 2345, 'gid': 2346, 'device': 8, 'inode': 10})
            original = json.loads(identity.read_text())
            original['account']['uid'] = 3456
            identity.write_text(json.dumps(original))
            with self.assertRaises(RuntimeError):
                storage._installation(Path('/var/lib/quillmd/files'))

    def encrypted_fixture(self, document_changes=None):
        account = SimpleNamespace(pw_uid=2345, pw_gid=2346)
        document = {'version': 2, 'account': {'name': storage.APP_ACCOUNT, 'uid': 2345, 'gid': 2346},
                    'device_source': storage.DEVICE_SOURCE,
                    'roots': {str(root): {'inode': index + 10} for index, root in enumerate(sorted(storage.APPROVED_ROOTS))}}
        document.update(document_changes or {})
        identity = self.file('state-identity.json', json.dumps(document).encode())
        _, _, lstat = self.installation_fixture()
        identity.write_text(json.dumps(document))
        identity.chmod(0o600)
        return account, identity, lstat

    def test_encrypted_identity_resolves_the_current_device_of_the_open_volume(self):
        account, identity, lstat = self.encrypted_fixture()
        real_stat = storage.os.stat
        def stat(path, *args, **kwargs):
            if path == storage.DEVICE_SOURCE:
                return SimpleNamespace(st_mode=0o060600, st_rdev=64514)
            return real_stat(path, *args, **kwargs)
        with patch.object(storage, 'IDENTITY_FILE', identity), patch.object(Path, 'lstat', lstat), \
                patch.object(storage.pwd, 'getpwnam', return_value=account), \
                patch.object(storage.os, 'getgrouplist', return_value=[2346]), patch.object(storage.os, 'stat', stat):
            self.assertEqual(storage._installation(Path('/var/lib/quillmd/files')),
                             {'uid': 2345, 'gid': 2346, 'device': 64514, 'inode': 10})
        # A different minor after the next boot is followed, because the pin names the device, not its number.
        def stat_after_reboot(path, *args, **kwargs):
            if path == storage.DEVICE_SOURCE:
                return SimpleNamespace(st_mode=0o060600, st_rdev=64512)
            return real_stat(path, *args, **kwargs)
        with patch.object(storage, 'IDENTITY_FILE', identity), patch.object(Path, 'lstat', lstat), \
                patch.object(storage.pwd, 'getpwnam', return_value=account), \
                patch.object(storage.os, 'getgrouplist', return_value=[2346]), patch.object(storage.os, 'stat', stat_after_reboot):
            self.assertEqual(storage._installation(Path('/var/lib/quillmd/mail'))['device'], 64512)

    def test_encrypted_identity_refuses_closed_volume_and_malformed_documents(self):
        real_stat = storage.os.stat
        def closed(path, *args, **kwargs):
            if path == storage.DEVICE_SOURCE:
                raise FileNotFoundError(path)
            return real_stat(path, *args, **kwargs)
        def not_a_block_device(path, *args, **kwargs):
            if path == storage.DEVICE_SOURCE:
                return SimpleNamespace(st_mode=0o100600, st_rdev=0)
            return real_stat(path, *args, **kwargs)
        for label, changes, stat in (
                ('closed', None, closed),
                ('regular file', None, not_a_block_device),
                ('other source', {'device_source': '/dev/mapper/pg-encrypted'}, closed),
                ('numeric device', {'roots': {str(root): {'inode': 10, 'device': 8} for root in storage.APPROVED_ROOTS}}, closed),
                ('extra key', {'extra': True}, closed)):
            account, identity, lstat = self.encrypted_fixture(changes)
            with self.subTest(label), patch.object(storage, 'IDENTITY_FILE', identity), patch.object(Path, 'lstat', lstat), \
                    patch.object(storage.pwd, 'getpwnam', return_value=account), \
                    patch.object(storage.os, 'getgrouplist', return_value=[2346]), patch.object(storage.os, 'stat', stat), \
                    self.assertRaises(RuntimeError):
                storage._installation(Path('/var/lib/quillmd/files'))
            identity.unlink()

    def test_extra_application_group_or_nonprivate_proof_refuses(self):
        account, identity, lstat = self.installation_fixture()
        with patch.object(storage, 'IDENTITY_FILE', identity), patch.object(Path, 'lstat', lstat), \
                patch.object(storage.pwd, 'getpwnam', return_value=account):
            with patch.object(storage.os, 'getgrouplist', return_value=[2346, 999]), \
                    self.assertRaises(RuntimeError):
                storage._installation(Path('/var/lib/quillmd/files'))
            identity.chmod(0o644)
            with patch.object(storage.os, 'getgrouplist', return_value=[2346]), \
                    self.assertRaises(RuntimeError):
                storage._installation(Path('/var/lib/quillmd/files'))


if __name__ == '__main__':
    unittest.main()
