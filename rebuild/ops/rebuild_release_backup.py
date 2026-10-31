#!/usr/bin/env python3
"""One locked pre-install step: an encrypted backup of the live rebuild, then its isolated restore check.

It runs the INSTALLED tracked tool, /opt/meddoc-pro/rebuild/ops/backup_restore.py, with the arguments the scheduled
capture uses (ops/scheduled_backup.py:126-129), and differs from the scheduled capture in three ways only:

  * no 540 s supervisor timeout (scheduled_backup.py:29). Every scheduled capture since 2026-10-12 was killed by
    it: the tool reads every referenced file twice through one helper container per read. A long ceiling remains
    so that a hung child cannot hold the locks forever;
  * the four native operation locks are held, non-blocking, for the backup AND the restore check (the engine's
    own legacy_model_activation.operation_locks), so no scheduled capture, offsite run, alert check or install
    can overlap it;
  * the restore check follows at once (decrypt and verify every object in memory, restore into a network-less,
    read-only, tmpfs PostgreSQL, compare every table hash and invariant), then a daemon-side read proves the
    drill container is gone.

The key file and the role file are passed to the tool BY PATH ONLY. This module never opens, reads, hashes or
prints them, nor rebuild/.env (the tool opens them itself: backup_restore.py source_options and key_at).

Without --execute it is a read-only preflight that prints the two exact commands. With --execute it writes one
private report; install_rebuild_release verifies that report (verify_report: complete, restore passed, the backup
still intact on disk, and fresh) and binds its sha256 into the release declaration.
"""
import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

APP = Path('/opt/meddoc-pro/rebuild')
SOURCE = Path(__file__).resolve().parents[2]
TOOL = APP / 'ops/backup_restore.py'
PYTHON = APP / '.venv/bin/python'
KEY = APP / '.runtime/backup-secrets/fresh-backup-current-20260917.key'
ROLES = APP / '.runtime/db-role-secrets/fresh-db-roles.json'
FORMAT = 'quillmd-rebuild-release-backup-v1'
#: Identical to scheduled_backup.SUMMARY_KEYS (a test pins the equality): the tool's printed summary.
SUMMARY_KEYS = frozenset({'complete', 'run_id', 'database', 'table_count', 'row_count', 'file_count', 'file_bytes',
                          'source_commit', 'encrypted', 'manifest_cipher_sha256'})
RUN_PATTERN = re.compile(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}')
RESTORE_PATTERN = re.compile(r'[a-f0-9]{16}')
DRILL_LABEL = 'quillmd.restore-run'
#: The scheduled child's environment (scheduled_backup.py:129), plus a locale.
CHILD_ENV = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'LANG': 'C.UTF-8'}
BACKUP_CEILING_SECONDS = 4 * 3600
RESTORE_CEILING_SECONDS = 45 * 60
SCHEDULED_TIMEOUT_NOT_APPLIED = 540
MIN_FREE_BYTES = 2 * 1024 ** 3
MAX_REPORT_BYTES = 1024 * 1024
MAX_CHILD_STDOUT = 4 * 1024 * 1024


class Refusal(RuntimeError):
    """A fixed, non-sensitive label."""


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def installer():
    rebuild = str(SOURCE / 'rebuild')
    if rebuild not in sys.path:
        sys.path.insert(0, rebuild)
    return importlib.import_module('ops.install_rebuild_release')


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate_json_key')
        value[key] = item
    return value


def loads(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique)
    except ValueError:
        raise Refusal('json_document') from None


def private_directory(path):
    path = Path(path)
    info = path.lstat()
    require(path.is_absolute() and path.resolve() == path and stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, 'private_directory')
    return path


def private_bytes(path, limit):
    path = Path(path)
    info = path.lstat()
    require(path.is_absolute() and path.resolve() == path and stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
            and info.st_size <= limit, 'private_file')
    raw = path.read_bytes()
    require(len(raw) == info.st_size, 'private_file_stable')
    return raw


def new_path(path, label):
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)) and not path.exists()
            and not path.is_symlink(), label)
    private_directory(path.parent)
    return path


def commands(output, key=KEY, roles=ROLES, backup_directory='<run directory printed by the backup>'):
    """The two exact child command lines. Credentials appear as paths, never as content."""
    backup = [str(PYTHON), '-B', str(TOOL), 'backup', '--source', str(APP), '--output', str(output / 'backup'),
              '--key-file', str(key), '--database-credentials', str(roles)]
    restore = [str(PYTHON), '-B', str(TOOL), 'restore-check', '--backup', str(backup_directory), '--key-file',
               str(key), '--output', str(output / 'restore')]
    return backup, restore


def validate_summary(value, destination):
    """The tool's printed summary, checked as scheduled_backup.validate_summary checks it, against the disk."""
    require(type(value) is dict and set(value) == SUMMARY_KEYS | {'backup_directory'}, 'backup_summary_keys')
    require(value['complete'] is True and value['encrypted'] is True and value['database'] == 'quillmd_fresh'
            and isinstance(value['run_id'], str) and RUN_PATTERN.fullmatch(value['run_id'])
            and value['backup_directory'] == str(Path(destination) / value['run_id']), 'backup_identity')
    require(all(type(value[key]) is int and value[key] >= 0
                for key in ('table_count', 'row_count', 'file_count', 'file_bytes'))
            and value['table_count'] > 0, 'backup_totals')
    require(isinstance(value['source_commit'], str) and re.fullmatch('[a-f0-9]{40}', value['source_commit'])
            and isinstance(value['manifest_cipher_sha256'], str)
            and re.fullmatch('[a-f0-9]{64}', value['manifest_cipher_sha256']), 'backup_hashes')
    directory = private_directory(Path(destination) / value['run_id'])
    require(not (directory / 'INCOMPLETE').exists(), 'backup_incomplete_marker')
    stored = loads(private_bytes(directory / 'summary.json', 65536))
    require(stored == {key: value[key] for key in SUMMARY_KEYS}, 'backup_summary_on_disk')
    require(sha(private_bytes(directory / 'manifest.json.fernet', 256 * 1024 ** 2)) == value['manifest_cipher_sha256'],
            'backup_manifest_ciphertext')
    return value


def validate_restore(value, summary, output):
    """The restore check's own record (verification.json) must say: complete, isolated, every hash equal."""
    require(type(value) is dict and isinstance(value.get('run_id'), str) and RESTORE_PATTERN.fullmatch(value['run_id']),
            'restore_identity')
    require(value.get('complete') is True and value.get('stage') == 'complete'
            and value.get('container_retained') is False and not value.get('cleanup_failed'), 'restore_complete')
    require(value.get('backup_run_id') == summary['run_id'] and value.get('table_count') == summary['table_count']
            and value.get('file_count') == summary['file_count'], 'restore_matches_backup')
    require(value.get('all_table_hashes_match') is True and value.get('all_file_hashes_match') is True
            and value.get('decrypted_files_written') == 0 and value.get('restore_database_on_tmpfs_without_swap') is True
            and value.get('network') == 'none' and value.get('published_ports') == 0
            and value.get('workers_started') == 0 and value.get('provider_credentials_copied') is False
            and value.get('provider_actions') == 0, 'restore_isolated_and_exact')
    directory = private_directory(Path(output) / ('restore-' + value['run_id']))
    require(loads(private_bytes(directory / 'verification.json', 1024 * 1024)) == value, 'restore_record_on_disk')
    return value


def drill_absent(run_id, runner=subprocess.run):
    """Daemon-side, read-only: no container carries this drill's label any more."""
    result = runner(['docker', 'container', 'ls', '--all', '--quiet', '--no-trunc', '--filter',
                     'label=' + DRILL_LABEL + '=' + run_id], capture_output=True, timeout=30)
    require(result.returncode == 0 and len(result.stdout) <= 65536, 'drill_container_query')
    require(not result.stdout.strip(), 'drill_container_absent')
    return True


def verify_report(path, *, base, now, max_age):
    """For install_rebuild_release: the report is complete, its backup is intact and restorable, and it is fresh."""
    raw = private_bytes(path, MAX_REPORT_BYTES)
    value = loads(raw)
    require(type(value) is dict and value.get('format') == FORMAT and value.get('complete') is True
            and value.get('stage') == 'complete' and value.get('drill_container_absent') is True, 'complete_backup_report')
    require(value.get('source') == str(APP) and value.get('source_commit') == base, 'backup_of_the_base_release')
    output = Path(value['output'])
    summary = validate_summary(value['backup']['summary'], output / 'backup')
    require(summary['source_commit'] == base, 'backup_source_commit_is_base')
    result = validate_restore(value['restore']['result'], summary, output / 'restore')
    finished = dt.datetime.fromisoformat(value['finished_at'])
    require(finished.tzinfo is not None and dt.timedelta(0) <= now - finished <= max_age, 'fresh_backup_report')
    return {'report_sha256': sha(raw), 'run_id': summary['run_id'], 'restore_run_id': result['run_id'],
            'finished_at': value['finished_at'], 'source_commit': summary['source_commit'],
            'table_count': summary['table_count'], 'row_count': summary['row_count'],
            'file_count': summary['file_count'], 'file_bytes': summary['file_bytes']}


def run_child(argv, timeout, runner=subprocess.run):
    """One child; its stdout is the tool's JSON record, its stderr is never retained (only its size)."""
    started = time.monotonic()
    try:
        result = runner(argv, cwd=str(APP), env=dict(CHILD_ENV), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'argv': argv, 'exit_code': None, 'timed_out': True,
                'elapsed_seconds': round(time.monotonic() - started, 3)}, None
    record = {'argv': argv, 'exit_code': result.returncode, 'timed_out': False,
              'elapsed_seconds': round(time.monotonic() - started, 3), 'stderr_bytes': len(result.stderr)}
    stdout = result.stdout if len(result.stdout) <= MAX_CHILD_STDOUT else None
    return record, stdout


def held_locks(installer_module):
    rows = []
    runtime = APP / '.runtime'
    for relative in installer_module.LOCK_FILES[:4]:
        info = (runtime / relative).lstat()
        rows.append({'path': str(runtime / relative),
                     'device_inode': '%02x:%02x:%d' % (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)})
    return rows


def preflight(args, installer_module):
    """Read-only: the paths, the tools, the locks, the time window and the free space."""
    rows = []

    def check(name, function):
        try:
            rows.append({'check': name, 'passed': True, 'detail': function()})
        except Exception as error:
            rows.append({'check': name, 'passed': False, 'reason': installer_module.reason(error)})
    check('new_private_output', lambda: str(new_path(args.output, 'new_private_output')))
    check('new_private_report', lambda: str(new_path(args.report, 'new_private_report')))
    check('credential_paths_only', lambda: credential_paths(args))
    check('installed_tool', lambda: require(TOOL.is_file() and PYTHON.exists(), 'installed_backup_tool') or True)
    check('engine_pins', lambda: installer_module.pinned_bytes() and True)
    check('coordination_locks_free', installer_module.locks_free)
    check('outside_scheduled_windows', lambda: installer_module.outside_scheduled_windows(now_utc()))
    check('free_space', lambda: free_space(args.output))
    return rows


def credential_paths(args):
    """Absolute paths outside the output; never opened, read or hashed here."""
    for path in (args.key_file, args.database_credentials):
        require(path.is_absolute() and str(path) == os.path.normpath(str(path))
                and not path.is_relative_to(args.output), 'credential_path_outside_output')
    return {'key_file': str(args.key_file), 'database_credentials': str(args.database_credentials),
            'opened_by_this_module': False}


def free_space(output):
    free = shutil.disk_usage(Path(output).parent).free
    require(free >= MIN_FREE_BYTES, 'free_space_for_backup')
    return {'free_bytes': free}


def execute(args, installer_module, *, runner=subprocess.run):
    """The locked backup and restore check. Returns the report written to --report."""
    engine = installer_module.load_engine()
    legacy = engine.prior.legacy
    output = new_path(args.output, 'new_private_output')
    new_path(args.report, 'new_private_report')
    report = {'format': FORMAT, 'complete': False, 'stage': 'prepared', 'source': str(APP), 'source_commit': None,
              'output': str(output), 'started_at': now_utc().isoformat(),
              'credentials': credential_paths(args), 'scheduled_timeout_not_applied_seconds': SCHEDULED_TIMEOUT_NOT_APPLIED,
              'ceilings': {'backup_seconds': BACKUP_CEILING_SECONDS, 'restore_seconds': RESTORE_CEILING_SECONDS},
              'drill_container_absent': None}
    output.mkdir(mode=0o700)
    (output / 'backup').mkdir(mode=0o700)
    (output / 'restore').mkdir(mode=0o700)
    backup_argv, _ = commands(output, args.key_file, args.database_credentials)
    try:
        with legacy.operation_locks():
            report['locks'] = held_locks(installer_module)
            report['stage'] = 'backup'
            record, stdout = run_child(backup_argv, BACKUP_CEILING_SECONDS, runner)
            report['backup'] = record
            require(record['exit_code'] == 0 and stdout is not None, 'backup_command_failed')
            summary = validate_summary(loads(stdout), output / 'backup')
            record['summary'] = summary
            report['source_commit'] = summary['source_commit']
            report['stage'] = 'restore_check'
            _, restore_argv = commands(output, args.key_file, args.database_credentials, summary['backup_directory'])
            record, stdout = run_child(restore_argv, RESTORE_CEILING_SECONDS, runner)
            report['restore'] = record
            require(record['exit_code'] == 0 and stdout is not None, 'restore_check_failed')
            value = loads(stdout)
            require(type(value) is dict and isinstance(value.get('restore_directory'), str), 'restore_record')
            directory = value.pop('restore_directory')
            record['result'] = validate_restore(value, summary, output / 'restore')
            require(directory == str(output / 'restore' / ('restore-' + value['run_id'])), 'restore_directory')
            report['stage'] = 'drill_absence'
            report['drill_container_absent'] = drill_absent(value['run_id'], runner)
            report['stage'] = 'complete'
            report['complete'] = True
    except Exception as error:
        report['failure'] = installer_module.reason(error)
    finally:
        report['finished_at'] = now_utc().isoformat()
        installer_module.write_result(args.report, report)
    return report


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--key-file', type=Path, default=KEY)
    parser.add_argument('--database-credentials', type=Path, default=ROLES)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    for name in ('output', 'report', 'key_file', 'database_credentials'):
        path = getattr(args, name)
        if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
            parser.error('--' + name.replace('_', '-') + ' must be an absolute, normalized path')
    return args


def main(argv=None):
    args = arguments(argv)
    os.umask(0o077)
    sys.dont_write_bytecode = True
    module = installer()
    rows = preflight(args, module)
    backup_argv, restore_argv = commands(args.output, args.key_file, args.database_credentials)
    plan = {'format': FORMAT, 'execute': args.execute, 'checks': rows, 'backup_command': backup_argv,
            'restore_command': restore_argv, 'report': str(args.report)}
    print(json.dumps(plan, indent=1, sort_keys=True))
    if not all(row['passed'] for row in rows):
        return 1
    if not args.execute:
        return 0
    report = execute(args, module)
    print(json.dumps({key: report.get(key) for key in ('complete', 'stage', 'failure', 'source_commit', 'started_at',
                                                       'finished_at')}, sort_keys=True))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    try:
        code = main()
    except SystemExit:
        raise
    except BaseException as error:
        print(json.dumps({'complete': False, 'refused': type(error).__name__}), file=sys.stderr)
        code = 1
    sys.exit(code)
