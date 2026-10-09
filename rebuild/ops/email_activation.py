"""Bounded configuration edit for the controlled private email verification."""
from io import StringIO
import os
from pathlib import Path
import re
import stat
from dotenv import dotenv_values

ORIGIN = 'https://app.quillmd.com:9443'
RUNNING_RELEASE = 'dc4eb42ce021e436a3b717eb40edb10ace8e662c'
KEYS = frozenset({
    'QUILLMD_RELEASE_SHA', 'QUILLMD_EMAIL_MODE', 'QUILLMD_EMAIL_FROM',
    'QUILLMD_EMAIL_VERIFIED_DOMAIN', 'QUILLMD_APP_BASE_URL', 'RESEND_API_KEY',
    'QUILLMD_EMAIL_ALLOWED_RECIPIENTS', 'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME',
    'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD', 'QUILLMD_TRUST_PROXY',
})


def updated_environment(original, values):
    """Preserve every unrelated line; refuse duplicates or unsafe serialization."""
    from .direct_account_access import reject_legacy_environment
    reject_legacy_environment(original)
    if set(values) != KEYS:
        raise ValueError('Email configuration key set differs from the declared scope.')
    if (not re.fullmatch(r'[a-f0-9]{40}', values['QUILLMD_RELEASE_SHA'])
            or values['QUILLMD_APP_BASE_URL'] != ORIGIN
            or values['QUILLMD_EMAIL_MODE'] != 'resend'
            or values['QUILLMD_TRUST_PROXY'] != '1'):
        raise ValueError('Invalid private email release or origin settings.')
    if any(not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00')
           or '${' in value for value in values.values()):
        raise ValueError('Unsafe private configuration value.')
    previous = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    if previous.get('QUILLMD_RELEASE_SHA') != RUNNING_RELEASE:
        raise ValueError('Unexpected served release; inspect before applying configuration.')
    remaining = dict(values)
    seen = set()
    result = []
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=', line)
        key = match[1].decode() if match else None
        if key not in values:
            result.append(line)
            continue
        if key in seen:
            raise ValueError('Duplicate controlled environment setting.')
        seen.add(key)
        result.append(_line(key, remaining.pop(key)))
    if result and not result[-1].endswith(b'\n'):
        result.append(b'\n')
    result.extend(_line(key, value) for key, value in remaining.items())
    updated = b''.join(result)
    actual = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    if any(actual.get(key) != value for key, value in values.items()):
        raise ValueError('Configuration serialization did not preserve exact values.')
    if {k: v for k, v in previous.items() if k not in KEYS} != {k: v for k, v in actual.items() if k not in KEYS}:
        raise ValueError('Unrelated environment values changed.')
    return updated


def _line(key, value):
    # dotenv and systemd EnvironmentFile disagree on escapes in single quotes.
    # Double quotes share these escapes; neither parser expands bare dollar signs
    # here, and updated_environment rejects dotenv interpolation syntax above.
    quoted = value.replace('\\', '\\\\').replace('"', '\\"')
    return (key + '="' + quoted + '"\n').encode()


def replace_environment(path, expected, updated):
    path = Path(path)
    if path.resolve() != path:
        raise ValueError('Environment path must be canonical.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600
                or handle.read() != expected):
            raise ValueError('Protected environment differs from its verified baseline.')
    pending = path.with_name('.env.private-email-pending')
    out = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(out, 'wb') as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    current = path.lstat()
    if (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_ctime_ns) != (
            before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns):
        raise ValueError('Environment changed before replacement; pending file retained privately.')
    os.replace(pending, path)
    directory = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    if path.read_bytes() != updated or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError('Environment readback failed.')
