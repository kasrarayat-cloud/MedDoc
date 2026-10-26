"""Immutable original-file store.

Each upload is written exactly once under ``ORIGINALS_DIR/<workspace>/`` with
a random name, mode 0600, exclusive create (never overwrites), and its sha256
is verified by reading the stored bytes back. Reads verify the hash again, so
a modified original is detected rather than served.
"""
import hashlib
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_SUFFIXES = {'.pdf': 'application/pdf',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.txt': 'text/plain'}


class OriginalCorrupted(Exception):
    pass


def _root() -> Path:
    root = Path(settings.ORIGINALS_DIR)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def media_type_for(filename: str, head: bytes) -> str:
    """Accept only PDF, DOCX and TXT, by extension AND content signature."""
    suffix = Path(filename or '').suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationError('Upload a PDF, DOCX or TXT file.')
    if suffix == '.pdf' and not head.startswith(b'%PDF-'):
        raise ValidationError('The file is named .pdf but is not a PDF document.')
    if suffix == '.docx' and not head.startswith(b'PK\x03\x04'):
        raise ValidationError('The file is named .docx but is not a Word (DOCX) document.')
    if suffix == '.txt' and b'\x00' in head:
        raise ValidationError('The file is named .txt but contains binary data.')
    return ALLOWED_SUFFIXES[suffix]


def store_original(workspace_id, data: bytes, filename: str):
    """Write ``data`` once; return (storage_name, sha256, size)."""
    if len(data) == 0:
        raise ValidationError('The file is empty.')
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise ValidationError(f'The file is larger than {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
    suffix = Path(filename or '').suffix.lower()
    digest = hashlib.sha256(data).hexdigest()
    folder = _root() / str(workspace_id)
    folder.mkdir(mode=0o700, exist_ok=True)
    name = f'{secrets.token_hex(24)}{suffix}'
    path = folder / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise OriginalCorrupted('Stored original does not match the uploaded bytes.')
    return f'{workspace_id}/{name}', digest, len(data)


def read_original(source_file) -> bytes:
    root = _root().resolve()
    path = (root / source_file.storage_name).resolve()
    if root not in path.parents:
        raise OriginalCorrupted('Original path escapes the original store.')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != source_file.sha256:
        raise OriginalCorrupted('Stored original no longer matches its recorded sha256.')
    return data
