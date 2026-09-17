#!/usr/bin/env python3
"""Explicit encrypted B2 round trip; no scheduling, deletion or provisioning."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import tempfile
from types import SimpleNamespace

import requests

try:
    from . import backup_restore as backup
except ImportError:
    import backup_restore as backup

RUNTIME = Path('/opt/meddoc-pro/rebuild/.runtime')
CONFIG_PARENT = RUNTIME / 'backup-secrets'
PREFIX = 'quillmd-fresh/synthetic/'
MC = Path('/usr/local/bin/mc')
MC_RELEASE = 'RELEASE.2025-08-13T08-35-41Z'
CAPABILITIES = {'listFiles', 'readFiles', 'writeFiles'}
MAX_CIPHER = backup.MAX_OBJECT_BYTES * 2
RUN_ID = r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}'
SHA = r'[a-f0-9]{64}'


def require(value, message='Offsite backup validation failed.'):
    if not value:
        raise RuntimeError(message)


def read_private(path, limit=MAX_CIPHER):
    path = Path(path).absolute()
    info = path.lstat()
    require(info.st_nlink == 1, 'Hardlinked private material refused.')
    return backup.read_private(path, limit)


def configuration(path):
    path = Path(path).absolute()
    require(path.parent == CONFIG_PARENT and path.resolve() == path,
            'Use the protected operator backup-secrets configuration directory.')
    config = json.loads(read_private(path, 16384))
    required = {'version', 'endpoint', 'region', 'bucket', 'bucket_id', 'prefix',
                'application_key_id', 'application_key', 'owner_approval_reference',
                'private_bucket_confirmed', 'synthetic_only'}
    require(type(config) is dict and set(config) == required and config['version'] == 1,
            'Unknown or missing backup configuration fields.')
    require(config['private_bucket_confirmed'] is True and config['synthetic_only'] is True
            and isinstance(config['owner_approval_reference'], str)
            and 1 <= len(config['owner_approval_reference']) <= 256, 'Owner destination approval is missing.')
    require(re.fullmatch(r'[a-z]{2}-[a-z]+-[0-9]{3}', config['region'])
            and config['endpoint'] == 'https://s3.' + config['region'] + '.backblazeb2.com',
            'Only the approved HTTPS Backblaze endpoint format is supported.')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', config['bucket'])
            and re.fullmatch(r'[a-f0-9]{24}', config['bucket_id'])
            and config['prefix'] == PREFIX, 'Bucket or synthetic prefix is invalid.')
    for name in ('application_key_id', 'application_key'):
        require(isinstance(config[name], str) and 8 <= len(config[name]) <= 256
                and not any(character.isspace() for character in config[name]), 'Missing private application key.')
    return config


def verify_scope(config, response):
    api = response.get('apiInfo', {}).get('storageApi', {})
    allowed = api.get('allowed', {})
    require(api.get('s3ApiUrl') == config['endpoint'], 'Provider endpoint differs from approved endpoint.')
    require(allowed.get('buckets') == [{'id': config['bucket_id'], 'name': config['bucket']}],
            'Key must be restricted to exactly the approved named bucket.')
    require(allowed.get('namePrefix') == PREFIX and set(allowed.get('capabilities', [])) == CAPABILITIES,
            'Key scope must have the exact synthetic prefix and read/list/write-file capabilities only.')
    require(not response.get('apiInfo', {}).get('groupsApi', {}).get('capabilities'),
            'Partner or account administration capability is not permitted.')
    # Never retain authorizationToken, account identifiers or raw provider data.
    return {'provider_verified': True, 'single_approved_bucket': True, 'prefix': PREFIX,
            'capabilities': sorted(CAPABILITIES), 'bucket_privacy': 'owner-confirmed; not API-verified'}


def authorize(config):
    with requests.Session() as session:
        session.trust_env = False  # No inherited proxies, netrc or custom CA override.
        response = session.get('https://api.backblazeb2.com/b2api/v4/b2_authorize_account',
                               auth=(config['application_key_id'], config['application_key']),
                               timeout=(10, 30), allow_redirects=False)
        require(response.status_code == 200 and len(response.content) <= 65536,
                'Provider scope authorization failed; no upload attempted.')
        return verify_scope(config, response.json())


def safe_object(value):
    require(value in ('manifest.json.fernet', 'database.dump.fernet')
            or re.fullmatch(r'objects/' + SHA + r'\.fernet', value), 'Only encrypted backup objects may be transferred.')
    return value


def validate_manifest(manifest, run_id):
    require(manifest.get('format') == 1 and manifest.get('complete') is True
            and manifest.get('database') == backup.SOURCE_DATABASE and manifest.get('run_id') == run_id
            and re.fullmatch(RUN_ID, run_id) and re.fullmatch(r'sha256:' + SHA, manifest.get('image_id', '')),
            'Invalid authenticated fresh backup manifest.')
    require(isinstance(manifest.get('files'), list) and len(manifest['files']) <= 10000,
            'Invalid authenticated file population.')
    paths = [row['path'] for row in manifest['files']]
    require(len(paths) == len(set(paths)), 'Duplicate restored file paths.')
    for path in paths:
        backup.safe_relative(path)
        require(path != '.' and len(path.encode()) <= 4096, 'Invalid restored file path.')
    require(all(re.fullmatch(r'objects/' + SHA + r'\.fernet', row['object']) for row in manifest['files']),
            'Referenced files require hashed encrypted object names.')
    entries = [('database.dump.fernet', manifest['dump'])] + [(row['object'], row) for row in manifest['files']]
    require(len({name for name, _ in entries}) == len(entries), 'Duplicate encrypted object names.')
    for name, row in entries:
        safe_object(name)
        require(type(row.get('size')) is int and 0 <= row['size'] <= backup.MAX_OBJECT_BYTES
                and re.fullmatch(SHA, row.get('sha256', '')) and re.fullmatch(SHA, row.get('cipher_sha256', '')),
                'Invalid authenticated object metadata.')
    return entries


def validate_bundle(manifest, objects, cipher):
    entries = validate_manifest(manifest, manifest.get('run_id', ''))
    require(set(objects) == {'manifest.json.fernet', *[name for name, _ in entries]},
            'Only the exact authenticated encrypted-object set can be uploaded.')
    require(json.loads(cipher.decrypt(objects['manifest.json.fernet'])) == manifest,
            'Local manifest does not authenticate.')
    for name, row in entries:
        payload = objects[name]
        require(len(payload) <= MAX_CIPHER and backup.digest(payload) == row['cipher_sha256'],
                'Local ciphertext does not match authenticated manifest.')
        plain = cipher.decrypt(payload)
        require(len(plain) == row['size'] and backup.digest(plain) == row['sha256'],
                'Local object authentication failed.')


def authenticated_plan(path, key_file):
    path, key_file = Path(path).absolute(), Path(key_file).absolute()
    require(not key_file.is_relative_to(path), 'Encryption keys must remain outside backup storage.')
    cipher = backup.key_at(key_file)
    root, manifest = backup.load_backup(path, cipher)
    require(re.fullmatch(RUN_ID, manifest.get('run_id', '')) and root.name == manifest['run_id'],
            'Backup directory and authenticated run ID differ.')
    validate_manifest(manifest, manifest['run_id'])
    objects = {'manifest.json.fernet': read_private(root / 'manifest.json.fernet')}
    entries = [('database.dump.fernet', manifest['dump'])] + [(row['object'], row) for row in manifest['files']]
    require(len({name for name, _ in entries}) == len(entries), 'Duplicate encrypted object names.')
    for name, row in entries:
        safe_object(name)
        require(type(row.get('size')) is int and 0 <= row['size'] <= backup.MAX_OBJECT_BYTES
                and re.fullmatch(SHA, row.get('sha256', '')) and re.fullmatch(SHA, row.get('cipher_sha256', '')),
                'Invalid authenticated object metadata.')
        payload = read_private(root / name)
        require(backup.digest(payload) == row['cipher_sha256'], 'Local ciphertext does not match authenticated manifest.')
        plain = cipher.decrypt(payload)
        require(len(plain) == row['size'] and backup.digest(plain) == row['sha256'],
                'Local encrypted object does not authenticate to its documented bytes.')
        del plain
        objects[name] = payload
    # summary.json may exist locally but is never uploaded. Anything else is a
    # mistaken backup scope, including misplaced keys and plaintext artifacts.
    permitted = set(objects) | {'summary.json'}
    for item in root.rglob('*'):
        info = item.lstat()
        relative = str(item.relative_to(root))
        require(not stat.S_ISLNK(info.st_mode), 'Backup symlinks are forbidden.')
        if stat.S_ISDIR(info.st_mode):
            require(relative == 'objects', 'Unexpected backup directory.')
        else:
            require(stat.S_ISREG(info.st_mode) and relative in permitted and info.st_nlink == 1,
                    'Backup contains unexpected or linked material.')
    return manifest, objects


class McTransport:
    """Established S3 client; credentials live only in temporary private config."""
    def __init__(self, config, scratch):
        self.config = config
        self.scratch = backup.private_dir(scratch)
        info = MC.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not (info.st_mode & 0o022),
                'Use the reviewed root-owned MinIO client.')
        version = subprocess.run([str(MC), '--version'], capture_output=True, timeout=10, check=False)
        require(version.returncode == 0 and MC_RELEASE.encode() in version.stdout, 'MinIO client version requires qualification.')
        self.client_config = self.scratch / 'mc-config'
        self.client_config.mkdir(mode=0o700)
        backup.write_private(self.client_config / 'config.json', json.dumps({'version': '10', 'aliases': {
            'quillmdoffsite': {'url': config['endpoint'], 'accessKey': config['application_key_id'],
                             'secretKey': config['application_key'], 'api': 'S3v4', 'path': 'on'}}}).encode())
        # A narrow environment also excludes inherited MC_HOST aliases,
        # MC_INSECURE/MC_DEBUG and all application/provider/payment credentials.
        self.environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
                            'MC_REGION': config['region'], 'MC_NO_COLOR': '1', 'MC_QUIET': '1',
                            'MC_DISABLE_PAGER': '1'}

    def target(self, run_id, manifest_hash, name):
        require(re.fullmatch(RUN_ID, run_id) and re.fullmatch(SHA, manifest_hash), 'Invalid remote backup identity.')
        safe_object(name)
        # Content-address the authenticated manifest. A repeated transfer can
        # create an additional identical B2 object version, never replace bytes
        # belonging to a different authenticated backup with the same run ID.
        return 'quillmdoffsite/' + self.config['bucket'] + '/' + PREFIX + run_id + '/' + manifest_hash + '/' + name

    def command(self, args):
        def bounded_file_size():
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_CIPHER, MAX_CIPHER))
            os.umask(0o077)
        result = subprocess.run([str(MC), '--config-dir', str(self.client_config), '--quiet', '--no-color', *args],
                                env=self.environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=180, check=False, preexec_fn=bounded_file_size)
        require(result.returncode == 0, 'Scoped encrypted-object transfer failed; no raw client output emitted.')

    def put(self, run_id, manifest_hash, name, payload):
        safe_object(name)
        require(len(payload) <= MAX_CIPHER, 'Encrypted object exceeds transfer limit.')
        local = self.scratch / 'upload.fernet'
        backup.write_private(local, payload)
        try:
            self.command(['put', '--disable-multipart', str(local), self.target(run_id, manifest_hash, name)])
        finally:
            local.unlink()

    def get(self, run_id, manifest_hash, name):
        local = self.scratch / 'download.fernet'
        require(not local.exists() and not local.is_symlink(), 'Download staging collision.')
        try:
            self.command(['get', self.target(run_id, manifest_hash, name), str(local)])
            return read_private(local)
        finally:
            if local.exists() and not local.is_symlink():
                local.unlink()


def download_backup(run_id, manifest_hash, cipher, transport, output, expected_manifest=None):
    require(re.fullmatch(RUN_ID, run_id) and re.fullmatch(SHA, manifest_hash), 'Invalid recovery identity.')
    destination = backup.private_dir(output) / run_id
    destination.mkdir(mode=0o700)  # Exclusive: partial attempts are retained.
    (destination / 'objects').mkdir(mode=0o700)
    marker = destination / 'INCOMPLETE'
    backup.write_private(marker, b'Offsite transfer has not completed verification.\n')
    received_manifest = transport.get(run_id, manifest_hash, 'manifest.json.fernet')
    require(backup.digest(received_manifest) == manifest_hash, 'Downloaded encrypted manifest differs.')
    remote_manifest = json.loads(cipher.decrypt(received_manifest))
    entries = validate_manifest(remote_manifest, run_id)
    require(expected_manifest is None or remote_manifest == expected_manifest,
            'Downloaded authenticated manifest differs.')
    backup.write_private(destination / 'manifest.json.fernet', received_manifest)
    for name, expected in entries:
        safe_object(name)
        payload = transport.get(run_id, manifest_hash, name)
        require(len(payload) <= MAX_CIPHER and backup.digest(payload) == expected['cipher_sha256'],
                'Downloaded ciphertext hash differs.')
        plain = cipher.decrypt(payload)
        require(len(plain) == expected['size'] and backup.digest(plain) == expected['sha256'],
                'Downloaded object failed authenticated plaintext verification.')
        del plain
        backup.write_private(destination / name, payload)
    marker.unlink()
    return destination, {'transport_verified': True, 'object_count': len(entries) + 1,
                         'manifest_cipher_sha256': manifest_hash, 'remote_prefix': PREFIX + run_id + '/' + manifest_hash + '/',
                         'all_ciphertext_hashes_match': True, 'all_objects_authenticated': True,
                         'encryption_key_uploaded': False, 'plaintext_uploaded': False}


def transfer_roundtrip(manifest, objects, cipher, transport, output):
    # The transport entry point validates too: accidental direct use cannot send
    # a plaintext payload, encryption key, extra file or unauthenticated bundle.
    validate_bundle(manifest, objects, cipher)
    run_id = manifest['run_id']
    manifest_hash = backup.digest(objects['manifest.json.fernet'])
    # Publish the authentic encrypted manifest last, after every data object.
    for name in sorted(set(objects) - {'manifest.json.fernet'}) + ['manifest.json.fernet']:
        transport.put(run_id, manifest_hash, name, objects[name])
    return download_backup(run_id, manifest_hash, cipher, transport, output, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--backup', help='Local encrypted backup for upload and download verification.')
    source.add_argument('--download-run-id', help='Recover an offsite run without a surviving local backup.')
    parser.add_argument('--manifest-sha', help='Authenticated ciphertext identity from the offsite receipt; required for recovery.')
    parser.add_argument('--key-file', required=True)
    parser.add_argument('--output', required=True, help='Existing operator-owned 0700 directory for round-trip evidence.')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    config = configuration(args.config)
    cipher = backup.key_at(args.key_file)
    if args.backup:
        require(args.manifest_sha is None, 'Recovery hash is only valid for download mode.')
        manifest, objects = authenticated_plan(args.backup, args.key_file)
        run_id = manifest['run_id']
    else:
        require(re.fullmatch(RUN_ID, args.download_run_id or '') and re.fullmatch(SHA, args.manifest_sha or ''),
                'Recovery requires the exact run ID and manifest ciphertext hash.')
        run_id, objects = args.download_run_id, {}
    output = backup.private_dir(args.output)
    require(not Path(args.key_file).absolute().is_relative_to(output), 'Keep recovery keys separate from downloaded backup.')
    if not args.execute:
        print(json.dumps({'prepared': True, 'network_calls': 0, 'encrypted_object_count': len(objects),
                          'remote_verified': False, 'restore_verified': False}))
        return
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'complete': False, 'live_transport': True,
              'backup_run_id': run_id, 'restore_verified': False, 'vault_recovery_demonstrated': False,
              'mode': 'upload-roundtrip' if args.backup else 'download-only-recovery'}
    report_path = output / ('offsite-' + run_id + '.json')
    require(not report_path.exists(), 'Existing transfer evidence requires inspection before another attempt.')
    try:
        report['scope'] = authorize(config)
        with tempfile.TemporaryDirectory(prefix='.offsite-transport-', dir=output) as temporary:
            transport = McTransport(config, Path(temporary))
            if args.backup:
                destination, evidence = transfer_roundtrip(manifest, objects, cipher, transport, output)
            else:
                destination, evidence = download_backup(run_id, args.manifest_sha, cipher, transport, output)
            report.update(evidence)
        restore_output = output / ('restore-' + run_id)
        restore_output.mkdir(mode=0o700)
        captured = io.StringIO()
        with redirect_stdout(captured):
            backup.restore(SimpleNamespace(backup=str(destination), key_file=args.key_file,
                                           output=str(restore_output), keep_container=False))
        restored = json.loads(captured.getvalue().strip())
        require(restored.get('complete') is True and restored.get('all_table_hashes_match') is True
                and restored.get('all_file_hashes_match') is True and restored.get('network') == 'none'
                and restored.get('provider_actions') == 0 and restored.get('workers_started') == 0,
                'Downloaded backup did not pass isolated restoration.')
        report.update(complete=True, restore_verified=True, isolated_restore=restored)
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        backup.write_private(report_path, json.dumps(report, indent=2).encode() + b'\n')
    print(json.dumps({'complete': True, 'evidence': str(report_path), 'restore_verified': True,
                      'vault_recovery_demonstrated': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Offsite backup refused or failed. Inspect private evidence; no credentials or provider output emitted.')
