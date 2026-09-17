import copy
import errno
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken

try:
    from . import offsite_backup as offsite
except ImportError:
    import offsite_backup as offsite


class MemoryTransport:
    """Explicit fake; no remote service or client process is exercised."""
    def __init__(self, *args):
        self.data, self.writes, self.reads = {}, [], []

    def put(self, run, manifest_hash, name, payload):
        self.writes.append(name)
        self.data[(run, manifest_hash, name)] = payload

    def get(self, run, manifest_hash, name):
        self.reads.append(name)
        return self.data[(run, manifest_hash, name)]


class OffsiteSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cipher = Fernet(Fernet.generate_key())
        self.run_id = '20260917T200000Z-aabbccdd'
        self.config = {'version': 1, 'endpoint': 'https://s3.us-west-004.backblazeb2.com',
                       'region': 'us-west-004', 'bucket': 'synthetic-test-bucket', 'bucket_id': 'a' * 24,
                       'prefix': offsite.PREFIX, 'application_key_id': 'synthetic-key-id',
                       'application_key': 'synthetic-key-value', 'owner_approval_reference': 'synthetic fixture only',
                       'private_bucket_confirmed': True, 'synthetic_only': True}
        plain = b'SYNTHETIC database bytes, not a usable database dump'
        encrypted = self.cipher.encrypt(plain)
        self.manifest = {'format': 1, 'complete': True, 'database': 'quillmd_fresh',
                         'run_id': self.run_id, 'image_id': 'sha256:' + 'b' * 64, 'files': [],
                         'dump': {'sha256': offsite.backup.digest(plain), 'size': len(plain),
                                  'cipher_sha256': offsite.backup.digest(encrypted)}}
        self.objects = {'database.dump.fernet': encrypted,
                        'manifest.json.fernet': self.cipher.encrypt(json.dumps(self.manifest).encode())}

    def response(self):
        return {'authorizationToken': 'synthetic-secret-token', 'apiInfo': {'storageApi': {
            's3ApiUrl': self.config['endpoint'], 'allowed': {
                'buckets': [{'id': self.config['bucket_id'], 'name': self.config['bucket']}],
                'namePrefix': offsite.PREFIX, 'capabilities': sorted(offsite.CAPABILITIES)}}}}

    def test_scope_requires_one_bucket_exact_prefix_and_no_delete_or_admin_rights(self):
        good = self.response()
        result = offsite.verify_scope(self.config, good)
        self.assertTrue(result['provider_verified'])
        self.assertNotIn('synthetic-secret-token', json.dumps(result))
        for key, value in [('buckets', None), ('namePrefix', 'quillmd-fresh/'),
                           ('capabilities', sorted(offsite.CAPABILITIES | {'deleteFiles'})),
                           ('capabilities', sorted(offsite.CAPABILITIES | {'listAllBucketNames'})),
                           ('capabilities', ['readFiles'])]:
            response = self.response()
            response['apiInfo']['storageApi']['allowed'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                offsite.verify_scope(self.config, response)

    def test_alternate_endpoint_or_partner_capability_refused(self):
        response = self.response()
        response['apiInfo']['storageApi']['s3ApiUrl'] = 'https://unexpected.invalid'
        with self.assertRaises(RuntimeError):
            offsite.verify_scope(self.config, response)
        response = self.response()
        response['apiInfo']['groupsApi'] = {'capabilities': ['all']}
        with self.assertRaises(RuntimeError):
            offsite.verify_scope(self.config, response)

    def test_configuration_refuses_unknown_prefix_endpoint_and_nonprivate_file(self):
        path = self.root / 'b2.json'
        def write(config):
            path.write_text(json.dumps(config)); path.chmod(0o600)
        with patch.object(offsite, 'CONFIG_PARENT', self.root):
            write(self.config)
            self.assertEqual(offsite.configuration(path)['prefix'], offsite.PREFIX)
            for key, value in [('prefix', 'other/'), ('endpoint', 'http://127.0.0.1'),
                               ('private_bucket_confirmed', False), ('synthetic_only', False)]:
                config = dict(self.config, **{key: value}); write(config)
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    offsite.configuration(path)
            write(self.config); path.chmod(0o644)
            with self.assertRaises(RuntimeError):
                offsite.configuration(path)

    def test_plaintext_and_extra_key_refused_before_any_upload(self):
        for objects in (dict(self.objects, **{'database.dump.fernet': b'plaintext'}),
                        dict(self.objects, **{'backup.key': b'key'})):
            transport = MemoryTransport()
            with self.assertRaises((RuntimeError, InvalidToken)):
                offsite.transfer_roundtrip(self.manifest, objects, self.cipher, transport, self.root)
            self.assertEqual(transport.writes, [])

    def test_wrong_key_refused_before_any_upload(self):
        transport = MemoryTransport()
        with self.assertRaises(InvalidToken):
            offsite.transfer_roundtrip(self.manifest, self.objects, Fernet(Fernet.generate_key()), transport, self.root)
        self.assertEqual(transport.writes, [])

    def test_manifest_path_traversal_or_unknown_object_refused(self):
        manifest = copy.deepcopy(self.manifest)
        for name in ('../backup.key', '/secret', 'objects/../private', 'summary.json'):
            manifest['files'] = [{'path': 'originals/synthetic.docx', 'object': name, **manifest['dump']}]
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                offsite.validate_manifest(manifest, self.run_id)
        manifest['files'] = [{'path': '../outside', 'object': 'objects/' + 'c' * 64 + '.fernet', **manifest['dump']}]
        with self.assertRaises(RuntimeError):
            offsite.validate_manifest(manifest, self.run_id)

    def test_roundtrip_downloads_all_encrypted_objects_and_publishes_manifest_last(self):
        transport = MemoryTransport()
        destination, report = offsite.transfer_roundtrip(self.manifest, self.objects, self.cipher, transport, self.root)
        self.assertTrue(report['transport_verified'])
        self.assertFalse(report['encryption_key_uploaded'])
        self.assertEqual(transport.writes[-1], 'manifest.json.fernet')
        self.assertEqual(set(transport.reads), set(self.objects))
        for name, data in self.objects.items():
            self.assertEqual((destination / name).read_bytes(), data)
            self.assertEqual((destination / name).stat().st_mode & 0o777, 0o600)
        self.assertFalse((destination / 'INCOMPLETE').exists())

    def test_tampered_download_retains_incomplete_marker(self):
        class CorruptTransport(MemoryTransport):
            def get(self, run, manifest_hash, name):
                data = super().get(run, manifest_hash, name)
                return data[:-4] + b'xxxx' if name == 'database.dump.fernet' else data
        with self.assertRaises(RuntimeError):
            offsite.transfer_roundtrip(self.manifest, self.objects, self.cipher, CorruptTransport(), self.root)
        self.assertTrue((self.root / self.run_id / 'INCOMPLETE').exists())

    def test_download_only_recovery_does_not_need_local_backup_or_upload(self):
        transport = MemoryTransport()
        manifest_hash = offsite.backup.digest(self.objects['manifest.json.fernet'])
        transport.data = {(self.run_id, manifest_hash, name): data for name, data in self.objects.items()}
        destination, report = offsite.download_backup(self.run_id, manifest_hash, self.cipher, transport, self.root)
        self.assertTrue(report['all_objects_authenticated'])
        self.assertEqual(transport.writes, [])
        self.assertTrue((destination / 'database.dump.fernet').exists())

    def test_duplicate_destination_does_not_overwrite_recovery_data(self):
        destination = self.root / self.run_id
        destination.mkdir(mode=0o700)
        sentinel = destination / 'keep'
        sentinel.write_bytes(b'SYNTHETIC original')
        with self.assertRaises(FileExistsError):
            offsite.download_backup(self.run_id, 'a' * 64, self.cipher, MemoryTransport(), self.root)
        self.assertEqual(sentinel.read_bytes(), b'SYNTHETIC original')

    def test_transport_commands_never_receive_credentials_or_list_delete_flags(self):
        client = object.__new__(offsite.McTransport)
        client.config, client.scratch = self.config, self.root
        client.client_config = self.root / 'config'
        client.environment = {'PATH': '/usr/bin:/bin', 'MC_REGION': self.config['region']}
        with patch.object(offsite.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as execute:
            client.put(self.run_id, 'a' * 64, 'database.dump.fernet', self.objects['database.dump.fernet'])
        args, kwargs = execute.call_args
        command = args[0]
        self.assertIn('put', command)
        self.assertIn('--disable-multipart', command)
        self.assertNotIn(self.config['application_key'], repr(command))
        self.assertNotIn(self.config['application_key_id'], repr(command))
        self.assertNotIn('rm', command)
        self.assertNotIn('ls', command)
        self.assertNotIn('--insecure', command)
        self.assertNotIn('MC_INSECURE', kwargs['env'])
        self.assertFalse((self.root / 'upload.fernet').exists())

    def test_target_rejects_keyfile_traversal_unknown_runs(self):
        client = object.__new__(offsite.McTransport)
        client.config = self.config
        for name in ('backup.key', '../manifest.json.fernet', 'summary.json'):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                client.target(self.run_id, 'a' * 64, name)
        with self.assertRaises(RuntimeError):
            client.target('../run', 'a' * 64, 'manifest.json.fernet')

    def test_local_backup_plan_rejects_misplaced_plaintext(self):
        source = self.root / self.run_id
        source.mkdir(mode=0o700)
        (source / 'objects').mkdir(mode=0o700)
        for name, payload in self.objects.items():
            offsite.backup.write_private(source / name, payload)
        key = self.root / 'test.key'
        offsite.backup.write_private(key, self.cipher._signing_key + self.cipher._encryption_key)
        # Supply the Fernet object directly; never rely on a hand-made key file.
        with patch.object(offsite.backup, 'key_at', return_value=self.cipher):
            offsite.authenticated_plan(source, key)
            offsite.backup.write_private(source / 'patient-plaintext.txt', b'SYNTHETIC ONLY')
            with self.assertRaises(RuntimeError):
                offsite.authenticated_plan(source, key)

    def test_cli_hands_downloaded_ciphertext_to_networkless_restore_adapter(self):
        key = self.root / 'test.key'
        key.write_bytes(b'synthetic placeholder'); key.chmod(0o600)
        output = self.root / 'roundtrip'; output.mkdir(mode=0o700)
        fake = MemoryTransport()
        def simulated_restore(args):
            self.assertEqual(Path(args.backup), output / self.run_id)
            self.assertFalse(args.keep_container)
            self.assertTrue((Path(args.backup) / 'database.dump.fernet').is_file())
            print(json.dumps({'complete': True, 'all_table_hashes_match': True, 'all_file_hashes_match': True,
                              'network': 'none', 'provider_actions': 0, 'workers_started': 0}))
        argv = ['offsite_backup.py', '--config', 'fixture-config', '--backup', 'fixture-backup',
                '--key-file', str(key), '--output', str(output), '--execute']
        with patch('sys.argv', argv), patch.object(offsite, 'configuration', return_value=self.config), \
             patch.object(offsite, 'authenticated_plan', return_value=(self.manifest, self.objects)), \
             patch.object(offsite.backup, 'key_at', return_value=self.cipher), \
             patch.object(offsite, 'authorize', return_value={'fixture': True}), \
             patch.object(offsite, 'McTransport', return_value=fake), \
             patch.object(offsite.backup, 'restore', side_effect=simulated_restore) as restored, \
             patch('sys.stdout', new_callable=io.StringIO):
            offsite.main()
        restored.assert_called_once()
        evidence = json.loads((output / ('offsite-' + self.run_id + '.json')).read_text())
        self.assertTrue(evidence['restore_verified'])
        self.assertFalse(evidence['vault_recovery_demonstrated'])

    def restore_arguments(self):
        source = self.root / self.run_id
        source.mkdir(mode=0o700)
        for name, payload in self.objects.items():
            offsite.backup.write_private(source / name, payload)
        return SimpleNamespace(backup=source, key_file=self.root / 'fixture.key',
                               output=self.root / 'restore-output', keep_container=False)

    def test_restore_requires_exact_local_image_and_never_pulls(self):
        args = self.restore_arguments()
        commands = []

        def simulated_command(command, **kwargs):
            commands.append(command)
            if command[:3] == ['docker', 'image', 'inspect']:
                self.assertEqual(command[-1], self.manifest['image_id'])
                return (self.manifest['image_id'] + '\n').encode()
            self.assertEqual(command[:2], ['docker', 'run'])
            self.assertIn('--pull=never', command)
            self.assertEqual(command[command.index('--network') + 1], 'none')
            self.assertEqual(command[-1], self.manifest['image_id'])
            raise RuntimeError('Fixture stops before starting any container.')

        with patch.object(offsite.backup, 'key_at', return_value=self.cipher), \
             patch.object(offsite.backup, 'run', side_effect=simulated_command):
            with self.assertRaisesRegex(RuntimeError, 'Fixture stops'):
                offsite.backup.restore(args)
        self.assertEqual(len(commands), 2)
        report = json.loads(next(args.output.glob('*/verification.json')).read_text())
        self.assertFalse(report['complete'])
        self.assertFalse(report['container_retained'])

    def test_missing_or_mismatched_local_image_cannot_start_restore(self):
        args = self.restore_arguments()
        for inspected in (RuntimeError('Fixture image absent.'), b'sha256:' + b'c' * 64):
            with self.subTest(inspected=type(inspected).__name__):
                def simulated_inspect(command, **kwargs):
                    self.assertEqual(command[:3], ['docker', 'image', 'inspect'])
                    if isinstance(inspected, Exception):
                        raise inspected
                    return inspected
                with patch.object(offsite.backup, 'key_at', return_value=self.cipher), \
                     patch.object(offsite.backup, 'run', side_effect=simulated_inspect) as execute:
                    with self.assertRaises(RuntimeError):
                        offsite.backup.restore(args)
                execute.assert_called_once()
        reports = [json.loads(path.read_text()) for path in args.output.glob('*/verification.json')]
        self.assertEqual(len(reports), 2)
        self.assertTrue(all(not report['complete'] and not report['container_retained'] for report in reports))


if __name__ == '__main__':
    unittest.main()
