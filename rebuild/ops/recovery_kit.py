#!/usr/bin/env python3
"""Prepare nonsecret recovery instructions; authenticate an explicitly returned key.

This helper never copies a secret, calls a provider, creates keys, or asserts
independent custody. The owner must retrieve the selected material into an
independent encrypted store before a returned-copy recovery can be qualified.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from cryptography.fernet import Fernet

try:
    from . import offsite_backup as offsite
except ImportError:
    import offsite_backup as offsite

PROJECT = Path('/opt/meddoc-pro/rebuild')
RUNTIME = PROJECT / '.runtime'
SECRETS = RUNTIME / 'backup-secrets'
LIVE_KEY = SECRETS / 'fresh-backup-current-20260917.key'
CONFIG = SECRETS / 'b2-offsite.json'
BACKUPS = RUNTIME / 'new-system-backups'
HANDOFF = RUNTIME / 'recovery-custody-handoff-20260920'
RETURNED_NAME = 'returned-fresh-backup.key'


def require(value):
    if not value:
        raise RuntimeError('Recovery material validation failed.')


def private_file(path, maximum=1024 * 1024):
    """Open the checked inode without following links; never echo its contents."""
    path = Path(path).absolute()
    require(path.resolve() == path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and before.st_uid == os.getuid() and stat.S_IMODE(before.st_mode) == 0o600
            and before.st_size <= maximum)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as opened:
        after = os.fstat(opened.fileno())
        require((after.st_dev, after.st_ino, after.st_size, after.st_mode, after.st_uid, after.st_nlink)
                == (before.st_dev, before.st_ino, before.st_size, before.st_mode, before.st_uid, before.st_nlink))
        content = opened.read(maximum + 1)
    require(len(content) <= maximum)
    return content


def manifest_with(key_bytes, run_id, expected_hash):
    require(re.fullmatch(offsite.RUN_ID, run_id) and re.fullmatch(offsite.SHA, expected_hash))
    root = offsite.backup.private_dir(BACKUPS / run_id)
    require(not (root / 'INCOMPLETE').exists())
    encrypted = private_file(root / 'manifest.json.fernet', offsite.MAX_CIPHER)
    require(hashlib.sha256(encrypted).hexdigest() == expected_hash)
    manifest = json.loads(Fernet(key_bytes.strip()).decrypt(encrypted))
    offsite.validate_manifest(manifest, run_id)
    return manifest


def image_requirements(image_id):
    metadata = json.loads(subprocess.check_output(
        ['docker', 'image', 'inspect', image_id], stderr=subprocess.PIPE, text=True))[0]
    require(metadata['Id'] == image_id and metadata['Os'] == 'linux'
            and re.fullmatch(r'[a-z0-9_]+', metadata['Architecture']))
    digests = metadata.get('RepoDigests') or []
    require(all(isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9._:/-]+@sha256:[a-f0-9]{64}', value)
                for value in digests))
    return {'image_id': image_id, 'repository_digests': digests,
            'architecture': metadata['Architecture'], 'os': metadata['Os'],
            'requires_authorized_preinstallation_on_recovery_host': True}


def prepare(report_file):
    offsite.backup.private_dir(SECRETS)
    report = json.loads(private_file(report_file))
    require(report.get('complete') is True and report.get('live_transport') is True
            and report.get('transport_verified') is True and report.get('restore_verified') is True)
    run_id, manifest_sha = report['backup_run_id'], report['manifest_cipher_sha256']
    manifest = manifest_with(private_file(LIVE_KEY, 1024), run_id, manifest_sha)
    config = offsite.configuration(CONFIG)
    # Only approved public fields enter the manifest. In particular, neither the
    # B2 key nor Fernet value/fingerprint is copied into this prepared kit.
    selection = {
        'version': 1, 'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
        'contains_secret_values': False, 'independent_custody_verified': False,
        'backup_run_id': run_id, 'manifest_cipher_sha256': manifest_sha,
        'database': manifest['database'], 'postgres_image_id': manifest['image_id'],
        'table_count': len(manifest['tables']),
        'row_count': sum(row['rows'] for row in manifest['tables'].values()),
        'file_count': len(manifest['files']),
        'destination': {field: config[field] for field in ('endpoint', 'region', 'bucket', 'bucket_id', 'prefix')},
        'secret_selection': [
            {'purpose': 'Decrypt and authenticate the offsite database/files/manifest', 'source': str(LIVE_KEY),
             'vault_name': 'QuillMD current Fernet backup key', 'copy_created_by_helper': False},
            {'purpose': 'Retrieve the encrypted objects from the approved B2 bucket/prefix', 'source': str(CONFIG),
             'vault_name': 'QuillMD scoped B2 recovery configuration', 'copy_created_by_helper': False}],
        'disk_unlock_material': {
            'required_for_clean_offsite_restore': False,
            'unattended_key': '/etc/quillmd/quillmd-fresh-luks.key',
            'recovery_passphrase': '/etc/quillmd/quillmd-fresh-luks.recovery-passphrase',
            'purpose': 'Open an existing surviving VPS LUKS volume; cannot decrypt Fernet backups',
            'copied': False},
        'restore_prerequisites': {
            'repository': 'https://github.com/kasrarayat-cloud/MedDoc',
            'reviewed_code_commit': subprocess.check_output(
                ['git', '-C', str(PROJECT.parent), 'rev-parse', 'HEAD'], stderr=subprocess.PIPE, text=True).strip(),
            'locked_dependencies': 'rebuild/requirements.txt',
            'entrypoint': 'rebuild/ops/offsite_backup.py', 'transport_version': offsite.TRANSPORT_VERSION,
            'requires_current_account_evidence_and_shared_allowance': True,
            'operator_consumer_runbook': 'docs/rebuild/offsite-consumers-20260920.md',
            'postgres_runtime': image_requirements(manifest['image_id']),
            'postgres_image_must_be_available_locally': True, 'implicit_image_pull': False},
        'returned_key_destination': str(HANDOFF / RETURNED_NAME),
        'custody_evidence_needed': ['Owner-controlled encrypted store independent of this VPS',
                                   'Custodian and nonsecret item references',
                                   'Actual retrieval from that store, followed by a successful isolated restore'],
    }
    require(re.fullmatch(r'[a-f0-9]{40}', selection['restore_prerequisites']['reviewed_code_commit']))
    offsite.backup.private_dir(HANDOFF, create=True)
    target = HANDOFF / ('selection-' + run_id + '.json')
    returned = HANDOFF / RETURNED_NAME
    if returned.exists() or returned.is_symlink():
        private_file(returned, 1024)
    # Exclusive writes preserve earlier selections and returned material.
    offsite.backup.write_private(target, json.dumps(selection, indent=2).encode() + b'\n')
    if not returned.exists():
        offsite.backup.write_private(returned, b'')
    return {'prepared': True, 'selection_manifest': str(target), 'secret_copies_created': 0,
            'independent_custody_verified': False, 'network_calls': 0}


def verify_returned(selection_file, returned_key):
    offsite.backup.private_dir(HANDOFF)
    selection_file = Path(selection_file).absolute()
    returned_key = Path(returned_key).absolute()
    require(selection_file.parent == HANDOFF and selection_file.resolve() == selection_file
            and returned_key == HANDOFF / RETURNED_NAME and returned_key.resolve() == returned_key
            and returned_key != LIVE_KEY and not returned_key.is_relative_to(SECRETS))
    selection = json.loads(private_file(selection_file))
    require(selection.get('version') == 1 and selection.get('contains_secret_values') is False)
    if LIVE_KEY.exists():
        live, returned = LIVE_KEY.stat(), returned_key.lstat()
        require((live.st_dev, live.st_ino) != (returned.st_dev, returned.st_ino))
    # No live-key read and no fallback: only this explicit returned file can
    # authenticate the selected encrypted manifest, even if the live key is absent.
    manifest = manifest_with(private_file(returned_key, 1024), selection['backup_run_id'],
                             selection['manifest_cipher_sha256'])
    require(manifest['image_id'] == selection['postgres_image_id'])
    return {'returned_key_authenticates_selected_manifest': True,
            'backup_run_id': selection['backup_run_id'],
            'manifest_cipher_sha256': selection['manifest_cipher_sha256'],
            'independent_custody_verified': False, 'isolated_restore_performed': False,
            'live_key_read': False, 'network_calls': 0,
            'limitation': 'Origin requires external custody evidence; run the download-only isolated restore using this returned key.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--offsite-report', required=True)
    verify = commands.add_parser('verify-returned')
    verify.add_argument('--selection', required=True)
    verify.add_argument('--returned-key', required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.offsite_report) if args.command == 'prepare' else verify_returned(args.selection, args.returned_key)
    except Exception as failure:
        print(json.dumps({'complete': False, 'error_class': type(failure).__name__,
                          'independent_custody_verified': False}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
