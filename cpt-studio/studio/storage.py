"""Immutable original-file store.

Each upload is written exactly once under ``ORIGINALS_DIR/<workspace>/`` with
a random name, mode 0600, exclusive create (never overwrites), and its sha256
is verified by reading the stored bytes back. Reads verify the hash again, so
a modified original is detected rather than served.

A file whose write or read-back check fails is removed at once (release 1, D3): a failed store never leaves a file that
no row names. The deletion helpers below are the store's only other way to remove a file, and every caller is one of
release 1's ruled clean-ups: a practice's disposal (studio.disposal, D1), an upload whose transaction failed
(studio.intake, D3) and the orphan sweep (studio.maintenance, D3). Every path they take is resolved inside the store, so
nothing outside ORIGINALS_DIR is ever touched.

Encryption of stored files (F1's wiring into store_original and read_original) is release 1b: nothing here seals or
opens a file (studio.file_crypto stays unused in release 1).
"""
import hashlib
import os
import secrets
import stat
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_SUFFIXES = {'.pdf': 'application/pdf',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.txt': 'text/plain'}
READ_CHUNK = 1024 * 1024


class OriginalCorrupted(Exception):
    pass


class StoreRefused(Exception):
    """A storage name or folder entry the deletion helpers will not act on: outside the store, or not a stored file."""


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


def _read_back(path: Path) -> bytes:
    """The stored bytes as the read-back check reads them (a seam the tests use to make the check fail)."""
    return path.read_bytes()


def store_original(workspace_id, data: bytes, filename: str):
    """Write ``data`` once; return (storage_name, sha256, size). A write or a read-back check that fails removes the
    file it wrote before raising (D3), so a failed store leaves nothing behind."""
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
    try:
        stored = _read_back(path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if hashlib.sha256(stored).hexdigest() != digest:
        path.unlink(missing_ok=True)
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


def in_practice_folder(workspace_id, storage_name) -> bool:
    """Whether ``storage_name`` lies in the practice's own folder: its first part is the practice's id."""
    try:
        folder = str(uuid.UUID(str(workspace_id)))
    except (TypeError, ValueError, AttributeError):
        return False
    return isinstance(storage_name, str) and storage_name.split('/', 1)[0] == folder


def read_own_original(workspace_id, source_file) -> bytes:
    """read_original for a reader acting for one practice (release 1; refutation finding 6): OriginalCorrupted, before
    any byte is read, when ``source_file``'s storage name - a SourceFile, or anything with ``storage_name`` and
    ``sha256``, such as a round's converted PDF - lies outside the practice's own folder (<workspace_id>/). A row of one
    practice that names another practice's file is a corrupted or crafted row: that file is never read for it."""
    if not in_practice_folder(workspace_id, getattr(source_file, 'storage_name', None)):
        raise OriginalCorrupted('A stored file lies outside its practice\'s folder.')
    return read_original(source_file)


# --- release 1: finding and removing stored files (D1 disposal, D3 clean-up) ------------------------------------------

def root_path() -> Path:
    """The store's root (ORIGINALS_DIR), resolved."""
    return _root().resolve()


def stored_path(storage_name) -> Path:
    """The path of ``storage_name`` ('<workspace>/<name>'), resolved inside the store and never followed through a
    symbolic link; StoreRefused for a name that is not of that form or leaves the store."""
    if not isinstance(storage_name, str) or not storage_name or '\x00' in storage_name:
        raise StoreRefused('not a storage name')
    parts = storage_name.split('/')
    if len(parts) != 2 or any(part in ('', '.', '..') for part in parts) or not _is_uuid(parts[0]):
        raise StoreRefused('a storage name is <workspace>/<file>')
    root = root_path()
    folder = root / parts[0]
    if folder.is_symlink() or (folder.exists() and folder.resolve().parent != root):
        raise StoreRefused('the folder leaves the store')
    return folder / parts[1]


def _is_uuid(text) -> bool:
    try:
        return str(uuid.UUID(text)) == text
    except (TypeError, ValueError, AttributeError):
        return False


def workspace_folder(workspace_id) -> Path:
    """The folder a practice's files are stored in (it may not exist)."""
    return root_path() / str(uuid.UUID(str(workspace_id)))


def file_digest(path: Path):
    """(size, sha256) of the regular file at ``path``, read in chunks; OSError when it cannot be read."""
    digest, size = hashlib.sha256(), 0
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK), b''):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


FILE, FOLDER, OTHER = 'file', 'folder', 'other'


def _kind(entry) -> str:
    if entry.is_symlink():
        return OTHER
    if entry.is_file(follow_symlinks=False):
        return FILE
    if entry.is_dir(follow_symlinks=False):
        return FOLDER
    return OTHER


def folder_entries(folder: Path):
    """Every entry directly in ``folder``: (name, FILE | FOLDER | OTHER), sorted by name. A symbolic link is OTHER
    whatever it points at, and so is anything that is neither a regular file nor a real folder: such an entry is never
    acted on. [] when the folder does not exist."""
    try:
        with os.scandir(folder) as found:
            entries = [(entry.name, _kind(entry)) for entry in found]
    except FileNotFoundError:
        return []
    return sorted(entries)


def delete_stored(storage_name) -> bool:
    """Remove the stored file ``storage_name``: True when a file was removed, False when none was there. A name outside
    the store, or an entry that is not a regular file, is refused (StoreRefused) and left as it is."""
    path = stored_path(storage_name)
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise StoreRefused('not a stored file')
        os.unlink(path)
    except FileNotFoundError:
        return False
    return True


def sync_folder(folder: Path) -> None:
    """fsync ``folder`` itself, so the removal of its entries is on the disk (a folder that is gone is skipped)."""
    try:
        fd = os.open(folder, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    except FileNotFoundError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def remove_empty_folder(folder: Path) -> bool:
    """Remove a practice's folder once nothing is left in it, then sync the store's root: True when it was removed.
    A folder that still holds anything stays (OSError is never swallowed for that case)."""
    try:
        folder.rmdir()
    except FileNotFoundError:
        return False
    sync_folder(folder.parent)
    return True
