"""The Anthropic credentials file, parsed strictly as data (moved from studio/participants/credentials.py and the file
reader of studio/providers/base.py, which lane E removes; the rules are unchanged).

The file is never sourced, interpolated or escape-decoded. It must be a regular file, not a symlink, readable by its
owner only and at most 32,000 bytes, of KEY=VALUE lines: ANTHROPIC_API_KEY (required) and ANTHROPIC_WORKSPACE_ID
(optional). Any other key, or a key set twice, refuses the whole file. No error message, repr or exception chain
carries a value, a file line or the file's path: errors name keys and line numbers only.

Both values go into HTTP headers, so the key must be visible ASCII with no space: a value the HTTP library would refuse
while preparing the request is refused here, before anything is sent.
"""
from __future__ import annotations

import errno
import os
import re
import stat
from dataclasses import dataclass
from typing import Optional

MAX_FILE_BYTES = 32_000
API_KEY, WORKSPACE_ID = 'ANTHROPIC_API_KEY', 'ANTHROPIC_WORKSPACE_ID'
KEYS = (API_KEY, WORKSPACE_ID)
_HEADER_VALUE = re.compile(r'[\x21-\x7e]+')  # visible ASCII, no space or control character
_WORKSPACE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')
_ASSIGNMENT = re.compile(r'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*)')
_QUOTED = re.compile(r'''(?:"([^"]*)"|'([^']*)')[ \t]*(?:#.*)?''')
_INLINE_COMMENT = re.compile(r'[ \t]#.*')
_FILE_ERRORS = {
    'missing': 'The Anthropic credentials file does not exist.',
    'symlink': 'The Anthropic credentials file is a symbolic link; it was refused.',
    'not_regular': 'The Anthropic credentials file is not a regular file.',
    'shared_permissions': 'The Anthropic credentials file is accessible to group or other users; it must be readable '
                          'by its owner only (mode 600 or stricter).',
    'too_large': f'The Anthropic credentials file is larger than {MAX_FILE_BYTES:,} bytes.',
}


class CredentialsError(Exception):
    """The credentials are unavailable or invalid. The message never contains a value, a line or the path."""


@dataclass(frozen=True, repr=False)
class Credentials:
    api_key: str
    workspace_id: Optional[str] = None  # anthropic-workspace-id, needed only by a key not scoped to a workspace

    def __repr__(self):
        workspace = '<not configured>' if self.workspace_id is None else '<configured>'
        return f'Credentials(api_key=<redacted>, workspace_id={workspace})'

    __str__ = __repr__


def load(path) -> Credentials:
    """The credentials in the file at ``path`` (settings.ANTHROPIC_CREDENTIALS_FILE), or CredentialsError."""
    if not path:
        raise CredentialsError('No Anthropic credentials file is configured.')
    try:
        raw = _read_regular_file(path, MAX_FILE_BYTES)
    except _Refused as exc:
        raise CredentialsError(_FILE_ERRORS.get(exc.reason, 'The Anthropic credentials file cannot be read.')) from None
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise CredentialsError('The Anthropic credentials file is not valid UTF-8.') from None
    values = _parse(text)
    if API_KEY not in values:
        raise CredentialsError(f'{API_KEY} is missing from the Anthropic credentials file.')
    if not _HEADER_VALUE.fullmatch(values[API_KEY]):
        raise CredentialsError(f'{API_KEY} is empty or contains a space, a control character or a character that is '
                               'not ASCII.')
    workspace = values.get(WORKSPACE_ID)
    if workspace is not None and not _WORKSPACE.fullmatch(workspace):
        raise CredentialsError(f'{WORKSPACE_ID} is not a workspace id (a letter or digit, then up to 127 letters, '
                               'digits, "_" or "-").')
    return Credentials(api_key=values[API_KEY], workspace_id=workspace)


class _Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason  # missing | symlink | not_regular | shared_permissions | too_large | unreadable


def _read_regular_file(path, max_bytes: int) -> bytes:
    """A regular file that is not a symlink and is readable by its owner only, refused over ``max_bytes``. O_NONBLOCK
    keeps a FIFO from blocking the open; it is then refused as not regular."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise _Refused('missing') from None
    except OSError as exc:
        raise _Refused('symlink' if exc.errno == errno.ELOOP else 'unreadable') from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise _Refused('not_regular')
        if info.st_mode & 0o077:
            raise _Refused('shared_permissions')
        chunks, size = [], 0  # bounded by the read itself, so a file growing after fstat is still caught
        while True:
            chunk = os.read(fd, max_bytes + 1 - size)
            if not chunk:
                return b''.join(chunks)
            size += len(chunk)
            if size > max_bytes:
                raise _Refused('too_large')
            chunks.append(chunk)
    except OSError:
        raise _Refused('unreadable') from None
    finally:
        os.close(fd)


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(text.split('\n'), start=1):
        line = line.removesuffix('\r').strip()
        if not line or line.startswith('#'):
            continue
        match = _ASSIGNMENT.fullmatch(line)
        if not match:
            raise CredentialsError(f'Line {number} of the Anthropic credentials file is not a KEY=VALUE assignment.')
        key, value = match.groups()
        if key not in KEYS:
            raise CredentialsError(f'Line {number} of the Anthropic credentials file sets a key other than '
                                   f'{" or ".join(KEYS)}.')
        if key in values:
            raise CredentialsError(f'{key} is set more than once in the Anthropic credentials file.')
        values[key] = _value(value, number)
    return values


def _value(value: str, number: int) -> str:
    if not value or value[0] not in '"\'':
        return _INLINE_COMMENT.sub('', value).rstrip()
    quoted = _QUOTED.fullmatch(value)
    if not quoted:
        raise CredentialsError(f'Line {number} of the Anthropic credentials file has an unterminated or malformed '
                               'quoted value.')
    content = quoted.group(1) if quoted.group(1) is not None else quoted.group(2)
    if '\\' in content:
        raise CredentialsError(f'Line {number} of the Anthropic credentials file uses an escape sequence; escapes are '
                               'not supported.')
    return content


# The name the installer's offline credentials check calls (ops/install.py CODER['loader']).
load_anthropic_credentials = load
