#!/usr/bin/env python3
"""Prove the private service's own boundary, then exec its fixed application.

The probe and server have the same PID, UID and mount namespace. No namespace
entry, additional capabilities, policy changes or provider calls are needed.
"""
import argparse
from datetime import datetime, timezone
import errno
import grp
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import sys
import tempfile


ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
STATE = Path('/var/lib/quillmd')
ACCOUNT = 'quillmd-app'
CAP_FIELDS = ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')
DENIED = (errno.EACCES, errno.EPERM)
SURFACES = ('doctor', 'admin', 'worker')


class BoundaryFailure(RuntimeError):
    """Contains only a fixed check label, never exception text or configuration."""


def require(condition, label):
    if not condition:
        raise BoundaryFailure(label)


def process_status():
    result = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            if key in (*CAP_FIELDS, 'NoNewPrivs', 'Uid', 'Gid', 'Groups'):
                result[key] = value.strip()
    return result


def check_identity(status):
    account = pwd.getpwnam(ACCOUNT)
    group = grp.getgrnam(ACCOUNT)
    require(account.pw_uid != 0 and account.pw_gid == group.gr_gid, 'private_account')
    require(account.pw_shell in ('/usr/sbin/nologin', '/sbin/nologin', '/bin/false'), 'nologin_account')
    require([int(n) for n in status.get('Uid', '').split()] == [account.pw_uid] * 4, 'uid')
    require([int(n) for n in status.get('Gid', '').split()] == [group.gr_gid] * 4, 'gid')
    groups = {int(n) for n in status.get('Groups', '').split()}
    require(groups <= {group.gr_gid}, 'supplementary_groups')
    require(all(status.get(key) and int(status[key], 16) == 0 for key in CAP_FIELDS), 'capabilities')
    require(status.get('NoNewPrivs') == '1', 'no_new_privileges')
    return {'uid': account.pw_uid, 'gid': group.gr_gid, 'supplementary_groups': sorted(groups),
            'all_capability_sets_empty': True, 'no_new_privileges': True}


def denied_open(path, flags, label):
    """Open without reading or truncating; an absent path is not denial proof."""
    try:
        fd = os.open(path, flags | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        # Read-only mounts legitimately deny source writes with EROFS. That
        # error is not accepted as evidence of read denial for secret files.
        accepted = DENIED + ((errno.EROFS,) if flags & (os.O_WRONLY | os.O_RDWR) else ())
        require(exc.errno in accepted, label + '_inconclusive')
        return {'denied': True, 'errno': exc.errno}
    else:
        os.close(fd)
        raise BoundaryFailure(label + '_accessible')


def denied_docker_socket():
    # Opening a socket as a regular file fails even when connect would succeed.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        try:
            client.connect('/run/docker.sock')  # No request bytes are sent.
        except OSError as exc:
            require(exc.errno in DENIED, 'docker_socket_inconclusive')
            return {'denied': True, 'errno': exc.errno}
        raise BoundaryFailure('docker_socket_accessible')


def private_directory(path, uid, gid):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not path.is_symlink(), 'state_directory_type')
    require(info.st_uid == uid and info.st_gid == gid and stat.S_IMODE(info.st_mode) == 0o700,
            'state_directory_permissions')


def writable_canary(path, uid, gid):
    private_directory(path, uid, gid)
    fd, name = tempfile.mkstemp(prefix='.quillmd-boundary-', dir=path)
    marker = b'QuillMD synthetic boundary control\n'
    try:
        with os.fdopen(fd, 'w+b') as stream:
            info = os.fstat(stream.fileno())
            require(info.st_uid == uid and info.st_gid == gid and stat.S_IMODE(info.st_mode) == 0o600,
                    'canary_permissions')
            stream.write(marker)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            require(stream.read() == marker, 'canary_readback')
        return {'read_write_delete': True, 'directory_mode': '0700', 'file_mode': '0600'}
    finally:
        os.unlink(name)


def fixed_command(surface):
    require(surface in SURFACES, 'surface')
    python = str(APP / '.venv/bin/python')
    if surface == 'worker':
        return [python, str(APP / 'manage.py'), 'worker']
    port = '9131' if surface == 'admin' else '9130'
    workers = '1' if surface == 'admin' else '2'
    return [python, '-m', 'gunicorn', 'quillmd.wsgi:application', '--bind', '127.0.0.1:' + port,
            '--workers', workers, '--timeout', '120']


def prepare_environment(surface):
    require(surface in SURFACES, 'surface')
    for name in ('QUILLMD_SECRET_KEY', 'QUILLMD_DB_PASSWORD'):
        require(bool(os.environ.get(name)), 'required_environment')
    require(os.environ.get('QUILLMD_DB_USER') == 'quillmd_runtime', 'runtime_database_user')
    require(os.environ.get('QUILLMD_DB_NAME') == 'quillmd_fresh', 'runtime_database_name')
    require(re.fullmatch('[a-f0-9]{40}', os.environ.get('QUILLMD_RELEASE_SHA', '')) is not None,
            'release_identity')
    # EnvironmentFile takes precedence over unit Environment entries. Enforce
    # these security-critical values here before importing application settings.
    os.environ['QUILLMD_ADMIN_SITE'] = '1' if surface == 'admin' else '0'
    os.environ['QUILLMD_ENV_MANAGED'] = '1'
    os.environ['QUILLMD_STATE_DIR'] = str(STATE)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.umask(0o077)


def probe(surface):
    prepare_environment(surface)
    identity = check_identity(process_status())
    uid, gid = identity['uid'], identity['gid']
    parent = STATE.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and parent.st_gid == gid
            and stat.S_IMODE(parent.st_mode) == 0o710, 'state_parent_permissions')
    checks = {}
    for label, path, flags in (
        ('shared_environment', ROOT / '.env', os.O_RDONLY),
        ('fresh_environment', APP / '.env', os.O_RDONLY),
        ('operator_runtime', APP / '.runtime', os.O_RDONLY | os.O_DIRECTORY),
        ('bootstrap_database_secret', APP / '.runtime/postgres.env', os.O_RDONLY),
        ('synthetic_account_credentials', APP / '.runtime/private-access.json', os.O_RDONLY),
        ('retained_credentials', ROOT / '.retained-service-credentials', os.O_RDONLY | os.O_DIRECTORY),
        ('code_write', APP / 'manage.py', os.O_WRONLY),
        ('launcher_write', APP / 'ops/service_launcher.py', os.O_WRONLY),
    ):
        checks[label] = denied_open(path, flags, label)
    checks['docker_socket'] = denied_docker_socket()
    for name in ('files', 'mail', 'proofs'):
        checks['state_' + name] = writable_canary(STATE / name, uid, gid)
    namespace = os.readlink('/proc/self/ns/mnt')
    require(re.fullmatch(r'mnt:\[\d+\]', namespace) is not None, 'mount_namespace_identity')
    return {'format': 1, 'event': 'quillmd_service_boundary', 'passed': True, 'surface': surface,
            'recorded_at': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
            'mount_namespace': namespace, 'release': os.environ['QUILLMD_RELEASE_SHA'],
            'identity': identity, 'checks': checks,
            'evidence_scope': 'startup probe followed by exec in same PID and mount namespace',
            'provider_calls': 0}


def save_proof(surface, report):
    destination = STATE / 'proofs' / (surface + '.json')
    if destination.exists() or destination.is_symlink():
        info = destination.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600, 'previous_proof_permissions')
    fd, name = tempfile.mkstemp(prefix='.quillmd-proof-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(report, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surface', choices=SURFACES, required=True)
    args = parser.parse_args(argv)
    try:
        report = probe(args.surface)
        save_proof(args.surface, report)
        print(json.dumps(report, sort_keys=True), flush=True)
        os.chdir(APP)
        command = fixed_command(args.surface)
        os.execv(command[0], command)
    except Exception as exc:
        # No raw exception message, environment value or clinical payload can
        # reach journald, including on unexpected filesystem/account failures.
        label = str(exc) if isinstance(exc, BoundaryFailure) else type(exc).__name__
        print(json.dumps({'event': 'quillmd_service_boundary', 'passed': False,
                          'surface': args.surface, 'check': label}), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
