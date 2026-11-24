"""Encryption of stored files and report PDFs (release 1, F1; RELEASE-1-SPEC 3.3), built and switched off
(settings.FILES_ENCRYPTION, OWNER DECISION D16). The storage (Lane 4) and the reports (Lane 3) call it.

    seal(workspace_id, data, aad)          ``data`` sealed with the practice's own data key (AES-256-GCM)
    open_sealed(workspace_id, blob, aad)   the data back; NotAuthentic for a changed byte, another practice or another
                                           ``aad``; KeyUnavailable when no key can open it
    is_sealed(blob)                        whether ``blob`` is in the sealed format (reads accept plain and sealed data)
    enabled()                              whether files are sealed now (FILES_ENCRYPTION is 'on')

The format: b'CPTF1', the key version (4 bytes, big-endian), a 12-byte random nonce, then the ciphertext and its 16-byte
tag. The associated data authenticates that header, the practice's id and the caller's ``aad`` - the kind plus the
storage name (a file) or the export id (a report) - so a sealed blob opens only on the record it was sealed for.

Keys. Each practice has one data key (FileKey: 32 random bytes, made at its first seal), kept only wrapped: AES-256-GCM
under the key-encryption key, with the practice's id and the key version as associated data. The key-encryption key is
CPT_STUDIO_FILES_KEK, 32 bytes in base64, read when it is needed: from the protected environment file that
settings.FILES_KEK_FILE names (its line CPT_STUDIO_FILES_KEK=...), or from the process environment when no file is
named. Both at once is refused as ambiguous. It is never read from or written to the database, and no message here ever
holds it. A destroyed data key (destroyed_at: D1's crypto-erase) seals and opens nothing.

Turned on, the key is required: check_files_key, a Django system check (studio.apps), refuses `manage.py check` and the
worker's start without a usable key-encryption key.
"""
from __future__ import annotations

import base64
import binascii
import os
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core import checks

from .models import FileKey

MAGIC = b'CPTF1'
WRAP_MAGIC = b'CPTK1'  # what a wrapped data key's associated data starts with: never confused with a file's
VERSION_BYTES, NONCE_BYTES, TAG_BYTES, KEY_BYTES = 4, 12, 16, 32
HEADER_BYTES = len(MAGIC) + VERSION_BYTES + NONCE_BYTES
KEK_NAME = 'CPT_STUDIO_FILES_KEK'


class FileCryptoError(Exception):
    """A sealed file could not be sealed or opened (a fixed sentence: never key material or content)."""


class KeyUnavailable(FileCryptoError):
    """No usable key: no key-encryption key, an unreadable or malformed one, or the practice's data key missing,
    destroyed or wrapped under another key-encryption key."""


class NotAuthentic(FileCryptoError):
    """The blob is not in the sealed format, was changed, or was sealed for another record or practice."""


def enabled() -> bool:
    return settings.FILES_ENCRYPTION == 'on'


def is_sealed(blob) -> bool:
    """Whether ``blob`` has the sealed format: the magic and room for a header and a tag. It reads the format only."""
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        return False
    return len(blob) >= HEADER_BYTES + TAG_BYTES and bytes(blob[:len(MAGIC)]) == MAGIC


def _bytes(value, label) -> bytes:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    raise ValueError(f'{label} must be bytes.')


def _aad(value) -> bytes:
    if isinstance(value, str):
        value = value.encode('utf-8')
    value = _bytes(value, 'aad')
    if not value:
        raise ValueError('aad names the record a blob is sealed for (the kind plus a storage name or an export id).')
    return value


def _workspace(workspace_id) -> uuid.UUID:
    value = getattr(workspace_id, 'pk', workspace_id)
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValueError('workspace_id is a practice or its id.') from None


def _decode_kek(value) -> bytes:
    try:
        key = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise KeyUnavailable(f'{KEK_NAME} is not base64.') from None
    if len(key) != KEY_BYTES:
        raise KeyUnavailable(f'{KEK_NAME} is not {KEY_BYTES} bytes.')
    return key


def _from_file(path) -> str:
    """The one CPT_STUDIO_FILES_KEK line's value in the protected environment file at ``path``."""
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        raise KeyUnavailable('The file FILES_KEK_FILE names cannot be read.') from None
    values = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        name, separator, value = line.partition('=')
        if not separator:
            raise KeyUnavailable('The file FILES_KEK_FILE names holds a line that is not NAME=value.')
        if name == KEK_NAME:
            values.append(value)
    if len(values) != 1:
        raise KeyUnavailable(f'The file FILES_KEK_FILE names must hold exactly one {KEK_NAME} line.')
    return values[0]


def key_encryption_key() -> bytes:
    """The key-encryption key (see the module), or KeyUnavailable."""
    path, environment = settings.FILES_KEK_FILE, os.environ.get(KEK_NAME)
    if path and environment is not None:
        raise KeyUnavailable(f'Both FILES_KEK_FILE and {KEK_NAME} in the environment are set; name one source only.')
    if path:
        return _decode_kek(_from_file(path))
    if environment is not None:
        return _decode_kek(environment)
    raise KeyUnavailable('No key-encryption key is configured.')


def _wrap_aad(workspace: uuid.UUID, version: int) -> bytes:
    return WRAP_MAGIC + workspace.bytes + version.to_bytes(VERSION_BYTES, 'big')


def _data_key(workspace: uuid.UUID, *, create: bool):
    """(key version, data key) of the practice, made and stored wrapped at its first seal when ``create``."""
    kek = key_encryption_key()
    row = FileKey.objects.filter(workspace_id=workspace).first()
    if row is None:
        if not create:
            raise KeyUnavailable('This practice has no file key.')
        nonce = os.urandom(NONCE_BYTES)
        wrapped = nonce + AESGCM(kek).encrypt(nonce, os.urandom(KEY_BYTES), _wrap_aad(workspace, 1))
        # two first seals at once: the second finds the first's row and unwraps it (its own key is never used)
        row, _ = FileKey.objects.get_or_create(workspace_id=workspace,
                                               defaults={'key_version': 1, 'wrapped_key': wrapped})
    if row.destroyed_at is not None:
        raise KeyUnavailable('This practice\'s file key was destroyed.')
    wrapped = bytes(row.wrapped_key)
    try:
        key = AESGCM(kek).decrypt(wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:], _wrap_aad(workspace, row.key_version))
    except (InvalidTag, ValueError):
        raise KeyUnavailable('This practice\'s file key does not open with the key-encryption key.') from None
    return row.key_version, key


def seal(workspace_id, data, aad) -> bytes:
    """``data`` sealed for the practice ``workspace_id`` and the record ``aad`` names (see the module)."""
    workspace, data, aad = _workspace(workspace_id), _bytes(data, 'data'), _aad(aad)
    version, key = _data_key(workspace, create=True)
    header = MAGIC + version.to_bytes(VERSION_BYTES, 'big')
    nonce = os.urandom(NONCE_BYTES)
    return header + nonce + AESGCM(key).encrypt(nonce, data, header + workspace.bytes + aad)


def open_sealed(workspace_id, blob, aad) -> bytes:
    """The data ``blob`` holds, opened for the practice ``workspace_id`` and the record ``aad`` names; NotAuthentic for
    a blob changed in any byte or sealed for another practice or record."""
    workspace, blob, aad = _workspace(workspace_id), _bytes(blob, 'blob'), _aad(aad)
    if not is_sealed(blob):
        raise NotAuthentic('The blob is not a sealed file.')
    header, nonce = blob[:len(MAGIC) + VERSION_BYTES], blob[len(MAGIC) + VERSION_BYTES:HEADER_BYTES]
    version, key = _data_key(workspace, create=False)
    if int.from_bytes(header[len(MAGIC):], 'big') != version:
        raise NotAuthentic('The blob was sealed with another key version.')
    try:
        return AESGCM(key).decrypt(nonce, blob[HEADER_BYTES:], header + workspace.bytes + aad)
    except InvalidTag:
        raise NotAuthentic('The blob was changed, or sealed for another record.') from None


def check_files_key(app_configs=None, **kwargs):
    """The system check: with FILES_ENCRYPTION on, a usable key-encryption key is required (studio.E101)."""
    if not enabled():
        return []
    try:
        key_encryption_key()
    except KeyUnavailable as exc:
        return [checks.Error(f'Stored files are sealed (FILES_ENCRYPTION is on) with no usable key: {exc}',
                             hint=f'Provide {KEK_NAME} (32 bytes, base64) in the protected environment file that '
                                  'CPT_STUDIO_FILES_KEK_FILE names, or turn FILES_ENCRYPTION off.',
                             id='studio.E101')]
    return []
