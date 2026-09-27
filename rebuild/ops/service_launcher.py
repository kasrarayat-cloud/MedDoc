#!/usr/bin/env python3
"""Prove the private service's own boundary, then exec its fixed application.

The probe and server have the same PID, UID and mount namespace. No namespace
entry, additional capabilities, policy changes or provider calls are needed.

Two profiles, selected only by the fixed `--profile` argument in a reviewed unit file:

- `private` (the default, and what every deploy/quillmd-fresh-* unit runs): the synthetic VPS
  system. Its constants and checks below are unchanged; ops/fixtures holds a byte-identical copy of
  the launcher as it was before profiles existed, and test_service_launcher_profiles.py proves
  the private path still refuses and accepts exactly as that copy does.
- `production`: the reviewed record in production_profile.json (ops/deployment_profile.py). Every
  host value comes from that record. A missing, unactivated or mixed record refuses, and so does an
  environment file that carries private values or contradicts the record's modes.
"""
import argparse
from datetime import datetime, timezone
import errno
import grp
import hashlib
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


def check_identity(status, account_name=None):
    account_name = ACCOUNT if account_name is None else account_name
    account = pwd.getpwnam(account_name)
    group = grp.getgrnam(account_name)
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
    # Parser and SDK workspaces hold uploaded and filled documents. They live on the
    # encrypted state volume, never the service's private /tmp on the root disk; the
    # unit's TMPDIR can be overridden by the environment file, so it is enforced here.
    os.environ['TMPDIR'] = str(STATE / 'tmp')
    tempfile.tempdir = None
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
    for name in ('files', 'mail', 'proofs', 'tmp'):
        checks['state_' + name] = writable_canary(STATE / name, uid, gid)
    require(tempfile.gettempdir() == str(STATE / 'tmp'), 'temporary_directory')
    checks['temporary_directory'] = {'path': str(STATE / 'tmp'), 'on_state_volume': True}
    namespace = os.readlink('/proc/self/ns/mnt')
    require(re.fullmatch(r'mnt:\[\d+\]', namespace) is not None, 'mount_namespace_identity')
    return {'format': 1, 'event': 'quillmd_service_boundary', 'passed': True, 'surface': surface,
            'recorded_at': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
            'mount_namespace': namespace, 'release': os.environ['QUILLMD_RELEASE_SHA'],
            'identity': identity, 'checks': checks,
            'evidence_scope': 'startup probe followed by exec in same PID and mount namespace',
            'provider_calls': 0}


# ------------------------------------------------------------------------------------------------
# Production profile. Nothing below runs for the private units: they pass no --profile argument.
# ------------------------------------------------------------------------------------------------
PROFILES = ('private', 'production')
DOCKER_SOCKETS = (('docker_socket', '/run/docker.sock'), ('docker_socket_legacy_path', '/var/run/docker.sock'))
INSTANCE_METADATA = ('169.254.169.254', 80)
PRIVATE_INSTALLATION = Path('/opt/meddoc-pro')
MAX_CA_BUNDLE_BYTES = 1024 * 1024


def _profile_module():
    try:
        from . import deployment_profile
    except ImportError:
        import deployment_profile
    return deployment_profile


def production_profile():
    """The reviewed, ACTIVATED production record; a missing/unactivated/mixed one refuses."""
    module = _profile_module()
    try:
        return module.load_production()
    except module.ProfileError as exc:
        raise BoundaryFailure(str(exc)) from None


def production_command(surface, profile):
    require(surface in SURFACES, 'surface')
    python = str(profile.python)
    if surface == 'worker':
        return [python, str(profile.app_root / 'manage.py'), 'worker']
    row = profile.surface(surface)
    return [python, '-m', 'gunicorn', 'quillmd.wsgi:application', '--bind', f'{row.bind}:{row.port}',
            '--workers', str(row.workers), '--timeout', '120']


def prepare_production_environment(surface, profile):
    """Refuse an environment file that is not this profile's, then force the profile's values."""
    require(surface in SURFACES, 'surface')
    env = os.environ
    for name in ('QUILLMD_SECRET_KEY', 'QUILLMD_DB_PASSWORD'):
        require(bool(env.get(name)), 'required_environment')
    # A private environment file carries no declaration, so it cannot start production units.
    require(env.get('QUILLMD_DEPLOYMENT_PROFILE') == 'production', 'profile_declaration')
    require(env.get('QUILLMD_DB_USER') == profile.roles['runtime'], 'runtime_database_user')
    require(env.get('QUILLMD_DB_NAME') == profile.database_name, 'runtime_database_name')
    require(env.get('QUILLMD_DB_HOST') == profile.database_host
            and env.get('QUILLMD_DB_PORT') == str(profile.database_port), 'database_endpoint')
    require(re.fullmatch('[a-f0-9]{40}', env.get('QUILLMD_RELEASE_SHA', '')) is not None, 'release_identity')
    require(env.get('QUILLMD_DATA_MODE', profile.data_mode) == profile.data_mode, 'data_mode')
    require(env.get('QUILLMD_PAYMENT_MODE', profile.payment_mode) == profile.payment_mode, 'payment_mode')
    # Live mode takes only a restricted live key; a test key here is a sandbox file copied into production.
    stripe_key = env.get('STRIPE_SECRET_KEY', '')
    require(stripe_key == '' or stripe_key.startswith('rk_live_'), 'payment_mode')
    require(env.get('QUILLMD_EMAIL_MODE') == profile.email_mode, 'email_mode')
    require(env.get('QUILLMD_APP_BASE_URL') == profile.doctor_origin, 'public_origin')
    require(env.get('QUILLMD_AI_MODE') == profile.ai_mode
            and env.get('QUILLMD_AI_PROVIDER') == profile.ai_provider, 'ai_mode')
    require(env.get('QUILLMD_HTTPS') == '1' and env.get('QUILLMD_TRUST_PROXY') == '1', 'transport')
    require(not any(name in env for name in _profile_module().PRIVATE_ONLY_ENVIRONMENT), 'private_only_setting')
    # libpq reads PG* from the environment; only the two TLS values set below may reach the application.
    require(not any(name.startswith('PG') for name in env), 'database_client_environment')
    os.environ['QUILLMD_ADMIN_SITE'] = '1' if surface == 'admin' else '0'
    os.environ['QUILLMD_ENV_MANAGED'] = '1'
    os.environ['QUILLMD_STATE_DIR'] = str(profile.state_root)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['QUILLMD_DEPLOYMENT_PROFILE'] = 'production'
    os.environ['QUILLMD_DATA_MODE'] = profile.data_mode
    os.environ['QUILLMD_PAYMENT_MODE'] = profile.payment_mode
    os.environ['PGSSLMODE'] = profile.sslmode
    os.environ['PGSSLROOTCERT'] = str(profile.ca_bundle)
    os.environ['TMPDIR'] = str(profile.state_root / 'tmp')
    tempfile.tempdir = None
    os.umask(0o077)


def absent_socket(path, label):
    """The profile says the host has NO Docker. A socket that exists, even denied, contradicts it."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        try:
            client.connect(path)  # No request bytes are sent.
        except FileNotFoundError:
            return {'absent': True}
        except OSError as exc:
            require(exc.errno not in DENIED, label + '_present')
            raise BoundaryFailure(label + '_inconclusive') from None
        raise BoundaryFailure(label + '_accessible')


def denied_instance_metadata():
    """The service identity must not reach IMDS, which would hand it the instance role's credentials."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        try:
            client.connect(INSTANCE_METADATA)  # No request bytes are sent.
        except OSError as exc:
            # systemd IPAddressDeny answers EPERM at once; a timeout or unreachable network proves nothing.
            require(exc.errno in DENIED, 'instance_metadata_inconclusive')
            return {'denied': True, 'errno': exc.errno}
        raise BoundaryFailure('instance_metadata_accessible')


def absent_path(path, label):
    try:
        os.lstat(path)
    except FileNotFoundError:
        return {'absent': True}
    except OSError:
        raise BoundaryFailure(label + '_inconclusive') from None
    raise BoundaryFailure(label + '_present')


def verified_ca_bundle(path, expected_sha256, owner_uid=0):
    """The pinned RDS CA bundle: root-owned, not group/world writable, exactly the reviewed bytes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise BoundaryFailure('database_ca_bundle') from None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == owner_uid and not info.st_mode & 0o022
                and 0 < info.st_size <= MAX_CA_BUNDLE_BYTES, 'database_ca_bundle')
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            require(total <= MAX_CA_BUNDLE_BYTES, 'database_ca_bundle')
            chunks.append(chunk)
    finally:
        os.close(fd)
    data = b''.join(chunks)
    require(hashlib.sha256(data).hexdigest() == expected_sha256, 'database_ca_bundle')
    return {'sha256': expected_sha256, 'bytes': len(data)}


def production_state_parent(profile, gid):
    parent = profile.state_root.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and parent.st_gid == gid
            and stat.S_IMODE(parent.st_mode) == 0o710, 'state_parent_permissions')
    # The encrypted data volume, never the root-disk directory underneath an absent mount.
    require(os.path.ismount(profile.state_root), 'state_volume_not_mounted')


def probe_production(surface, profile):
    prepare_production_environment(surface, profile)
    identity = check_identity(process_status(), profile.account)
    uid, gid = identity['uid'], identity['gid']
    production_state_parent(profile, gid)
    app = profile.app_root
    checks = {}
    for label, path, flags in (
        ('environment_file', profile.environment_file, os.O_RDONLY),
        ('operator_configuration', profile.operator_directory, os.O_RDONLY | os.O_DIRECTORY),
        ('code_write', app / 'manage.py', os.O_WRONLY),
        ('launcher_write', app / 'ops/service_launcher.py', os.O_WRONLY),
        ('profile_write', app / 'ops/production_profile.json', os.O_WRONLY),
    ):
        checks[label] = denied_open(path, flags, label)
    for label, path in DOCKER_SOCKETS:
        checks[label] = absent_socket(path, label)
    checks['instance_metadata'] = denied_instance_metadata()
    checks['private_installation'] = absent_path(PRIVATE_INSTALLATION, 'private_installation')
    checks['database_ca_bundle'] = verified_ca_bundle(profile.ca_bundle, profile.ca_bundle_sha256)
    for name in _profile_module().STATE_SUBDIRECTORIES:
        checks['state_' + name] = writable_canary(profile.state_root / name, uid, gid)
    require(tempfile.gettempdir() == str(profile.state_root / 'tmp'), 'temporary_directory')
    checks['temporary_directory'] = {'path': str(profile.state_root / 'tmp'), 'on_state_volume': True}
    namespace = os.readlink('/proc/self/ns/mnt')
    require(re.fullmatch(r'mnt:\[\d+\]', namespace) is not None, 'mount_namespace_identity')
    return {'format': 1, 'event': 'quillmd_service_boundary', 'passed': True, 'surface': surface,
            'profile': 'production', 'profile_sha256': profile.sha256,
            'recorded_at': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
            'mount_namespace': namespace, 'release': os.environ['QUILLMD_RELEASE_SHA'],
            'identity': identity, 'checks': checks,
            'database': {'host': profile.database_host, 'name': profile.database_name,
                         'role': profile.roles['runtime'], 'sslmode': profile.sslmode},
            'evidence_scope': 'startup probe followed by exec in same PID and mount namespace',
            'provider_calls': 0}


def save_proof(surface, report, state=None):
    destination = (STATE if state is None else state) / 'proofs' / (surface + '.json')
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
    parser.add_argument('--profile', choices=PROFILES, default='private')
    args = parser.parse_args(argv)
    try:
        if args.profile == 'production':
            profile = production_profile()
            report = probe_production(args.surface, profile)
            save_proof(args.surface, report, profile.state_root)
            print(json.dumps(report, sort_keys=True), flush=True)
            os.chdir(profile.app_root)
            command = production_command(args.surface, profile)
        else:
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
        failure = {'event': 'quillmd_service_boundary', 'passed': False,
                   'surface': args.surface, 'check': label}
        if args.profile == 'production':
            failure['profile'] = 'production'
        print(json.dumps(failure), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
