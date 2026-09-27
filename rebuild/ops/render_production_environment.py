#!/usr/bin/env python3
"""Render the production application environment from AWS Secrets Manager onto tmpfs. Root only.

Run by deploy/production/quillmd-production-environment.service before the application units, as
`python3 -B -E -s <this file> --execute`. The secret named in the reviewed production profile holds a
JSON object of environment NAME -> value. Only names in deployment_profile.ENVIRONMENT_NAMES are
accepted, so a private-preview setting cannot be carried into production by copying a file; values
may not contain a quote, backslash, newline or NUL, so the systemd EnvironmentFile it writes is read
back literally. The file lands at the profile's environment path, 0600 root, inside a root 0700
directory that systemd removes when the unit stops. Secret values are never printed; only the NAMES
rendered and the profile hash are reported.

The application identity cannot read the file (the launcher proves it) and cannot reach the
instance metadata service (the units deny it), so the instance role that reads the secret is not
available to the application.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

try:
    from . import deployment_profile
except ImportError:
    import deployment_profile

AWS_CLI = '/usr/local/bin/aws'  # AWS CLI v2 bundle installed by bootstrap-host.sh
MAX_SECRET_BYTES = 64 * 1024
MAX_VALUE_CHARACTERS = 8192
FORBIDDEN_CHARACTERS = frozenset('\n\r\x00\'\\')


class RenderError(RuntimeError):
    """Contains only a fixed label, never a secret name's value or provider output."""


def require(condition, label):
    if not condition:
        raise RenderError(label)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'secret_shape')
        result[key] = value
    return result


def parse(text, names=deployment_profile.ENVIRONMENT_NAMES):
    require(isinstance(text, str) and len(text.encode('utf-8')) <= MAX_SECRET_BYTES, 'secret_shape')
    try:
        data = json.loads(text, object_pairs_hook=_pairs)
    except RenderError:
        raise
    except (ValueError, RecursionError):
        raise RenderError('secret_shape') from None
    require(isinstance(data, dict) and data, 'secret_shape')
    for name, value in data.items():
        require(name in names, 'secret_name')
        require(isinstance(value, str) and 0 < len(value) <= MAX_VALUE_CHARACTERS
                and not set(value) & FORBIDDEN_CHARACTERS and value == value.strip(), 'secret_value')
        if name in deployment_profile.APPLICATION_FEATURE_FLAGS:
            require(value in ('0', '1'), 'feature_flag_value')
        if name == 'QUILLMD_DEEPGRAM_MIP_OPT_OUT':
            require(value == 'true', 'voice_privacy_value')
        if name == 'QUILLMD_DEEPGRAM_SMART_FORMAT':
            require(value in ('true', 'false'), 'voice_format_value')
    require(data.get('QUILLMD_DEPLOYMENT_PROFILE') == 'production', 'secret_profile')
    return data


def render(values):
    return ''.join(f"{name}='{values[name]}'\n" for name in sorted(values)).encode('utf-8')


def write(path, data, *, owner=0):
    path = Path(path)
    directory = path.parent
    info = directory.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == owner and stat.S_IMODE(info.st_mode) == 0o700,
            'environment_directory')
    if path.exists() or path.is_symlink():
        existing = path.lstat()
        require(stat.S_ISREG(existing.st_mode) and existing.st_uid == owner, 'environment_file')
    fd, temporary = tempfile.mkstemp(prefix='.application-env-', dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return hashlib.sha256(data).hexdigest()


def fetch(production, runner=subprocess.run):
    command = [AWS_CLI, 'secretsmanager', 'get-secret-value', '--region', production.region,
               '--secret-id', production.secret_name, '--query', 'SecretString', '--output', 'text']
    try:
        result = runner(command, capture_output=True, timeout=60,
                        env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/root', 'AWS_PAGER': ''})
    except (OSError, subprocess.TimeoutExpired):
        raise RenderError('secret_fetch') from None
    require(result.returncode == 0, 'secret_fetch')
    try:
        text = result.stdout.decode('utf-8')
    except UnicodeError:
        raise RenderError('secret_shape') from None
    return text[:-1] if text.endswith('\n') else text


def main(argv=None, runner=subprocess.run):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--execute', action='store_true', help='Fetch and write; without it nothing is fetched.')
    args = parser.parse_args(argv)
    try:
        production = deployment_profile.load_production()
        if not args.execute:
            print(json.dumps({'rendered': False, 'destination': str(production.environment_file),
                              'secret': production.secret_name, 'profile_sha256': production.sha256}))
            return 0
        require(os.geteuid() == 0, 'not_root')
        values = parse(fetch(production, runner))
        write(production.environment_file, render(values))
        print(json.dumps({'rendered': True, 'names': sorted(values), 'profile_sha256': production.sha256}))
        return 0
    except (RenderError, deployment_profile.ProfileError) as exc:
        print(json.dumps({'rendered': False, 'refused': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
