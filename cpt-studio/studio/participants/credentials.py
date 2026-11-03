"""OpenAI and Anthropic credentials for the participants, from protected dotenv-style files parsed strictly as data
(HARNESS.md 8), exactly as Corti's are (studio/providers/credentials.py).

A file is never sourced, interpolated or escape-decoded. It must be a regular file, not a symlink, readable by its owner
only and at most 32,000 bytes. Each holds its one required key and, optionally, one more; any other key, or a key set
twice, refuses the whole file. No error message, repr or exception chain carries a value, a file line or the file's
path: errors name keys and line numbers only.

Every value goes into an HTTP header, so it must be visible ASCII with no space: a value the HTTP library would refuse
while preparing the request is refused here, before anything is sent, never after (an exception raised inside the POST
would read as an unknown outcome).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from studio.providers.base import FileRefused, read_regular_file
from studio.providers.credentials import CredentialsError

MAX_FILE_BYTES = 32_000
OPENAI_KEYS = ('OPENAI_API_KEY', 'OPENAI_PROJECT')
ANTHROPIC_KEYS = ('ANTHROPIC_API_KEY', 'ANTHROPIC_WORKSPACE_ID')
_HEADER_VALUE = re.compile(r'[\x21-\x7e]+')  # visible ASCII, no space or control character
_PROJECT = re.compile(r'proj_[A-Za-z0-9_-]{1,128}')
_WORKSPACE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')
_ASSIGNMENT = re.compile(r'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*)')
_QUOTED = re.compile(r'''(?:"([^"]*)"|'([^']*)')[ \t]*(?:#.*)?''')
_INLINE_COMMENT = re.compile(r'[ \t]#.*')

__all__ = ['AnthropicCredentials', 'CredentialsError', 'OpenAICredentials', 'load_anthropic_credentials',
           'load_openai_credentials']


@dataclass(frozen=True, repr=False)
class OpenAICredentials:
    api_key: str
    project: Optional[str] = None  # OpenAI-Project, when the key is used for a project it is not scoped to

    def __repr__(self):
        return f'OpenAICredentials(api_key=<redacted>, project={_configured(self.project)})'

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class AnthropicCredentials:
    api_key: str
    workspace_id: Optional[str] = None  # anthropic-workspace-id, needed only by a key not scoped to a workspace

    def __repr__(self):
        return f'AnthropicCredentials(api_key=<redacted>, workspace_id={_configured(self.workspace_id)})'

    __str__ = __repr__


def _configured(value: Optional[str]) -> str:
    return '<not configured>' if value is None else '<configured>'


def load_openai_credentials(path) -> OpenAICredentials:
    values = _load(path, 'OpenAI', OPENAI_KEYS)
    project = values.get('OPENAI_PROJECT')
    if project is not None and not _PROJECT.fullmatch(project):
        raise CredentialsError('OPENAI_PROJECT is not an OpenAI project id ("proj_" and then letters, digits, "_" '
                               'or "-").')
    return OpenAICredentials(api_key=values['OPENAI_API_KEY'], project=project)


def load_anthropic_credentials(path) -> AnthropicCredentials:
    values = _load(path, 'Anthropic', ANTHROPIC_KEYS)
    workspace = values.get('ANTHROPIC_WORKSPACE_ID')
    if workspace is not None and not _WORKSPACE.fullmatch(workspace):
        raise CredentialsError('ANTHROPIC_WORKSPACE_ID is not a workspace id (a letter or digit, then up to 127 '
                               'letters, digits, "_" or "-").')
    return AnthropicCredentials(api_key=values['ANTHROPIC_API_KEY'], workspace_id=workspace)


def _load(path, vendor: str, keys: tuple[str, str]) -> dict[str, str]:
    """The file's values: ``keys[0]`` required, ``keys[1]`` optional, nothing else."""
    if not path:
        raise CredentialsError(f'No {vendor} credentials file is configured.')
    try:
        raw = read_regular_file(path, MAX_FILE_BYTES, owner_only=True)
    except FileRefused as exc:
        raise CredentialsError(_file_error(vendor, exc.reason)) from None
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise CredentialsError(f'The {vendor} credentials file is not valid UTF-8.') from None
    values = _parse(text, vendor, keys)
    if keys[0] not in values:
        raise CredentialsError(f'{keys[0]} is missing from the {vendor} credentials file.')
    if not _HEADER_VALUE.fullmatch(values[keys[0]]):
        raise CredentialsError(f'{keys[0]} is empty or contains a space, a control character or a character that is '
                               'not ASCII.')
    return values


def _file_error(vendor: str, reason: str) -> str:
    return {
        'missing': f'The {vendor} credentials file does not exist.',
        'symlink': f'The {vendor} credentials file is a symbolic link; it was refused.',
        'not_regular': f'The {vendor} credentials file is not a regular file.',
        'shared_permissions': f'The {vendor} credentials file is accessible to group or other users; '
                              'it must be readable by its owner only (mode 600 or stricter).',
        'too_large': f'The {vendor} credentials file is larger than {MAX_FILE_BYTES:,} bytes.',
    }.get(reason, f'The {vendor} credentials file cannot be read.')


def _parse(text: str, vendor: str, keys: tuple[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(text.split('\n'), start=1):
        line = line.removesuffix('\r').strip()
        if not line or line.startswith('#'):
            continue
        match = _ASSIGNMENT.fullmatch(line)
        if not match:
            raise CredentialsError(f'Line {number} of the {vendor} credentials file is not a KEY=VALUE assignment.')
        key, value = match.groups()
        if key not in keys:
            raise CredentialsError(f'Line {number} of the {vendor} credentials file sets a key other than '
                                   f'{" or ".join(keys)}.')
        if key in values:
            raise CredentialsError(f'{key} is set more than once in the {vendor} credentials file.')
        values[key] = _value(value, number, vendor)
    return values


def _value(value: str, number: int, vendor: str) -> str:
    if not value or value[0] not in '"\'':
        return _INLINE_COMMENT.sub('', value).rstrip()
    quoted = _QUOTED.fullmatch(value)
    if not quoted:
        raise CredentialsError(f'Line {number} of the {vendor} credentials file has an unterminated or '
                               'malformed quoted value.')
    content = quoted.group(1) if quoted.group(1) is not None else quoted.group(2)
    if '\\' in content:
        raise CredentialsError(f'Line {number} of the {vendor} credentials file uses an escape sequence; '
                               'escapes are not supported.')
    return content
