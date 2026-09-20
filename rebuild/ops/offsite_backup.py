#!/usr/bin/env python3
"""Offline backup preparation and budgeted isolated recovery; uploads use automatic_offsite."""
import argparse
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import signal
import secrets
import stat
import time
from types import SimpleNamespace

try:
    from . import backup_restore as backup
except ImportError:
    import backup_restore as backup

RUNTIME = Path('/opt/meddoc-pro/rebuild/.runtime')
CONFIG_PARENT = RUNTIME / 'backup-secrets'
PREFIX = 'quillmd-fresh/synthetic/'
TRANSPORT_VERSION = 'Native API v4; canonical policy, execution lock and shared durable budget'
RETIRED_TRANSPORT = ('Legacy transport is disabled: use the shared automatic_offsite.py run uploader '
                     'or offsite_backup.py --download-run-id recovery path.')
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
    """Keep the historical symbol fail-closed; standalone authorization was unbudgeted."""
    raise RuntimeError(RETIRED_TRANSPORT)


def shared_engine():
    # Lazy import: automatic_offsite imports the non-network validation primitives here.
    try:
        from . import automatic_offsite
    except ImportError:
        import automatic_offsite
    return automatic_offsite


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
    """Retired live client. Historical qualification evidence remains unchanged."""
    def __init__(self, *args, **kwargs):
        raise RuntimeError(RETIRED_TRANSPORT)

    def command(self, *args, **kwargs):
        raise RuntimeError(RETIRED_TRANSPORT)

    put = command
    get = command


class InventoriedDownload:
    """Adapt only a completely inventoried encrypted set to the recovery primitive."""
    def __init__(self, transport, run_id, manifest_hash):
        require(re.fullmatch(RUN_ID, run_id) and re.fullmatch(SHA, manifest_hash), 'Invalid recovery identity.')
        self.transport, self.identity = transport, (run_id, manifest_hash)
        prefix = PREFIX + run_id + '/' + manifest_hash + '/'
        self.rows = {}
        for row in transport.inventory():
            if row['fileName'].startswith(prefix):
                name = safe_object(row['fileName'][len(prefix):])
                # Native list versions is newest-first. A hide marker must not
                # resurrect an older version or silently select different bytes.
                self.rows.setdefault(name, row)
        require('manifest.json.fernet' in self.rows and all(
            row['action'] == 'upload' and 0 < row['contentLength'] <= MAX_CIPHER
            for row in self.rows.values()), 'Remote complete encrypted set is missing or hidden.')
        # No object content is downloaded unless the entire inventoried set fits
        # the remaining shared allowance. Requests themselves debit durably.
        transport.budget.preflight(len(self.rows), sum(row['contentLength'] + 65536 for row in self.rows.values()))

    def get(self, run_id, manifest_hash, name):
        require((run_id, manifest_hash) == self.identity and name in self.rows,
                'Object absent from the selected complete remote inventory.')
        row = self.rows[name]
        return self.transport.get(row, row['contentLength'])


@contextmanager
def recovery_deadline(deadline):
    """Bound CLI recovery as well as HTTP; the first timeout still runs restore cleanup."""
    require(signal.getsignal(signal.SIGALRM) == signal.SIG_DFL,
            'Recovery requires a dedicated bounded operator process.')
    remaining = deadline - time.monotonic()
    require(remaining > 0, 'Shared recovery runtime allowance has expired.')
    def expired(_signal, _frame):
        # backup.restore's finally block gets one bounded cleanup window. A
        # hung cleanup cannot leave this process holding the shared lock forever.
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.setitimer(signal.ITIMER_REAL, 45)
        raise RuntimeError('Shared recovery runtime allowance has expired.')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


def manual_status(engine, report, state, reason=None, *, locked=False, require_attempt=False):
    """Only a typed summary reaches the monitor; lock losers cannot replace a runner."""
    summary = {name: report[name] for name in ('attempt', 'started_at', 'backup_run_id',
                                              'manifest_cipher_sha256', 'restore_verified')}
    summary['run_id'] = summary.pop('backup_run_id')
    summary.update(version=1, action='isolated_restore', state=state, reason_code=reason, shared_accounting=True)
    if state != 'running':
        summary['finished_at'] = datetime.now(timezone.utc).isoformat()
    def write():
        path = engine.STATE / 'manual-status.json'
        previous = engine.read_json(path, {})
        if require_attempt and previous.get('attempt') != report['attempt']:
            return  # A newer manual attempt owns this summary; the immutable report still survives.
        engine.atomic(path, summary)
    if locked:
        write()
    else:
        try:
            with engine.exclusion(engine.STATE):
                write()
        except engine.Refusal as error:
            if error.code != 'lock_busy':
                raise


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
    if args.execute and args.backup:
        raise SystemExit('Manual uploads now share the scheduled engine: run automatic_offsite.py run. '
                           'It selects the authenticated completed local backup under canonical policy and accounting.')
    configuration(args.config)
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
    engine = shared_engine()
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'complete': False, 'live_transport': True,
              'backup_run_id': run_id, 'restore_verified': False, 'vault_recovery_demonstrated': False,
              'attempt': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4),
              'manifest_cipher_sha256': args.manifest_sha,
              'mode': 'download-only-recovery', 'shared_accounting': True,
              'decryption_key_source': 'explicit --key-file only; no live-key fallback'}
    report_path = output / ('offsite-' + run_id + '.json')
    require(not report_path.exists() and not report_path.is_symlink(),
            'Existing transfer evidence requires inspection before another attempt.')
    # Exclusive durable intent also survives SIGKILL or a hung cleanup process.
    backup.write_private(report_path.with_suffix('.started.json'), json.dumps(report, indent=2).encode() + b'\n')
    entered = False
    try:
        with engine.live_session(config_path=Path(args.config)) as transport:
            entered = True
            report['scope'] = transport.scope
            manual_status(engine, report, 'running', locked=True)
            with recovery_deadline(transport.budget.deadline):
                adapter = InventoriedDownload(transport, run_id, args.manifest_sha)
                destination, evidence = download_backup(run_id, args.manifest_sha, cipher, adapter, output)
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
                report.update(restore_verified=True, isolated_restore=restored)
        manual_status(engine, report, 'complete', require_attempt=True)
        report['complete'] = True  # Includes transport cleanup success.
    except Exception as error:
        reason = (error.code if isinstance(error, engine.Refusal) else
                  'cleanup_failed' if 'cleanup' in str(error).lower() else 'recovery_failed')
        report['reason_code'] = reason
        manual_status(engine, report, 'refused' if isinstance(error, engine.Refusal) else 'failed',
                      reason, require_attempt=entered)
        raise
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
