"""Corti credentials from a protected dotenv-style file, parsed strictly as data.

The file is never sourced, interpolated or escape-decoded. Exactly four keys are
accepted. No error message, repr or exception chain carries a credential value,
a file line or the file's path: errors name keys and line numbers only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .base import FileRefused, ProviderUnavailable, read_regular_file

MAX_FILE_BYTES = 32_000
KEYS = ('CORTI_CLIENT_ID', 'CORTI_CLIENT_SECRET', 'CORTI_ENVIRONMENT', 'CORTI_TENANT_NAME')
ENVIRONMENTS = ('us', 'eu')
TENANT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}')
_ASSIGNMENT = re.compile(r'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*)')
_QUOTED = re.compile(r'''(?:"([^"]*)"|'([^']*)')[ \t]*(?:#.*)?''')
_INLINE_COMMENT = re.compile(r'[ \t]#.*')
_CONTROL = re.compile(r'[\x00-\x1f\x7f]')

_FILE_ERRORS = {
    'missing': 'The Corti credentials file does not exist.',
    'symlink': 'The Corti credentials file is a symbolic link; it was refused.',
    'not_regular': 'The Corti credentials file is not a regular file.',
    'shared_permissions': 'The Corti credentials file is accessible to group or other users; '
                          'it must be readable by its owner only (mode 600 or stricter).',
    'too_large': f'The Corti credentials file is larger than {MAX_FILE_BYTES:,} bytes.',
    'unreadable': 'The Corti credentials file cannot be read.',
}


class CredentialsError(ProviderUnavailable):
    """Credentials are unavailable or invalid. Messages never contain values."""


@dataclass(frozen=True, repr=False)
class CortiCredentials:
    client_id: str
    client_secret: str
    environment: str
    tenant: str

    def __repr__(self):
        return (f'CortiCredentials(environment={self.environment!r}, tenant={self.tenant!r}, '
                f'client_id=<redacted>, client_secret=<redacted>)')

    __str__ = __repr__


def load_corti_credentials(path) -> CortiCredentials:
    if not path:
        raise CredentialsError('No Corti credentials file is configured.')
    try:
        raw = read_regular_file(path, MAX_FILE_BYTES, owner_only=True)
    except FileRefused as exc:
        raise CredentialsError(_FILE_ERRORS[exc.reason]) from None
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise CredentialsError('The Corti credentials file is not valid UTF-8.') from None
    values = _parse(text)
    for key in KEYS:
        if key not in values:
            raise CredentialsError(f'{key} is missing from the Corti credentials file.')
    for key in ('CORTI_CLIENT_ID', 'CORTI_CLIENT_SECRET'):
        if not values[key].strip() or _CONTROL.search(values[key]):
            raise CredentialsError(f'{key} is empty or contains control characters.')
    if values['CORTI_ENVIRONMENT'] not in ENVIRONMENTS:
        raise CredentialsError('CORTI_ENVIRONMENT must be us or eu.')
    if not TENANT.fullmatch(values['CORTI_TENANT_NAME']):
        raise CredentialsError('CORTI_TENANT_NAME is not a valid tenant name '
                               '(a letter or digit, then up to 63 letters, digits, "_" or "-").')
    return CortiCredentials(client_id=values['CORTI_CLIENT_ID'], client_secret=values['CORTI_CLIENT_SECRET'],
                            environment=values['CORTI_ENVIRONMENT'], tenant=values['CORTI_TENANT_NAME'])


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(text.split('\n'), start=1):
        line = line.removesuffix('\r').strip()
        if not line or line.startswith('#'):
            continue
        match = _ASSIGNMENT.fullmatch(line)
        if not match:
            raise CredentialsError(f'Line {number} of the Corti credentials file is not a KEY=VALUE assignment.')
        key, value = match.groups()
        if key not in KEYS:
            raise CredentialsError(f'Line {number} of the Corti credentials file sets a key other than '
                                   f'{", ".join(KEYS)}.')
        if key in values:
            raise CredentialsError(f'{key} is set more than once in the Corti credentials file.')
        values[key] = _value(value, number)
    return values


def _value(value: str, number: int) -> str:
    if not value or value[0] not in '"\'':
        return _INLINE_COMMENT.sub('', value).rstrip()
    quoted = _QUOTED.fullmatch(value)
    if not quoted:
        raise CredentialsError(f'Line {number} of the Corti credentials file has an unterminated or '
                               'malformed quoted value.')
    content = quoted.group(1) if quoted.group(1) is not None else quoted.group(2)
    if '\\' in content:
        raise CredentialsError(f'Line {number} of the Corti credentials file uses an escape sequence; '
                               'escapes are not supported.')
    return content
