"""Immutable original-file store.

Each upload is written exactly once under ``ORIGINALS_DIR/<workspace>/`` with
a random name, mode 0600, exclusive create (never overwrites), and its sha256
is verified by reading the stored bytes back. Reads verify the hash again, so
a modified original is detected rather than served.

A read takes only a name of the exact shape store_original writes (STORAGE_NAME_RE), never through a symbolic link and
never outside its folder; a reader acting for one practice reads only that practice's own files (own_path, the one test
every such reader and the disposal apply; release 1). What that protects against: a crafted or corrupted ROW naming
another practice's file, and symbolic links. What it does not: a hard link, or a copy, made by someone who can write to
the store - a residual, recorded (refutation round 3). No link-count check is made, deliberately: a hard-link snapshot
backup on the same filesystem would then refuse every read, and whoever can write to the store can copy the bytes
anyway.

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
import re
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


# The exact shape of a name store_original writes: '<the practice's id>/<48 lowercase hex characters><suffix>', the
# suffix one of ALLOWED_SUFFIXES (intake checks an upload's; a converted PDF's is '.pdf') or none. So one separator, and
# no '.', '..' or empty segment, no backslash and no capital letter.
STORAGE_NAME_RE = re.compile(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/([0-9a-f]{48}(?:'
                             + '|'.join(re.escape(suffix) for suffix in sorted(ALLOWED_SUFFIXES)) + r')?)')


def _named(storage_name):
    """The match of ``storage_name`` against STORAGE_NAME_RE (practice id, file name); StoreRefused for any other name."""
    match = STORAGE_NAME_RE.fullmatch(storage_name) if isinstance(storage_name, str) else None
    if match is None:
        raise StoreRefused('not a name the store writes')
    return match


def _checked_path(match) -> Path:
    """The path of a matched name: neither its folder nor the file a symbolic link (lstat), the folder directly in the
    store, and the file's resolved path inside the folder's resolved path; StoreRefused otherwise. A path that does not
    exist passes (reading it then fails as a missing file). A hard link is a regular file to these checks: it passes
    (the module docstring says why, and what that leaves)."""
    root = root_path()
    folder = root / match.group(1)
    path = folder / match.group(2)
    for part in (folder, path):
        try:
            mode = os.lstat(part).st_mode
        except FileNotFoundError:
            break  # nothing exists below a part that does not
        if stat.S_ISLNK(mode):
            raise StoreRefused('a symbolic link')
    own = folder.resolve()
    if own.parent != root or not path.resolve().is_relative_to(own):
        raise StoreRefused('outside its folder')
    return path


def own_path(workspace_id, storage_name) -> Path:
    """The path of ``storage_name`` when it is one of practice ``workspace_id``'s own stored files: the one test every
    reader and destroyer acting for one practice applies (release 1; refutation finding 6 and round 2's first): a name of
    the exact shape store_original writes (STORAGE_NAME_RE) whose folder is this practice's id, then _checked_path - no
    symbolic link, and the resolved path inside the practice's own resolved folder. StoreRefused otherwise, before
    anything of another practice is touched; OSError when the folder cannot be looked at. A row of one practice that
    names any other file is a corrupted or crafted row: nothing outside the practice's folder is reached through it. It
    protects against such a row and against symbolic links - not against a hard link or a copy put in the folder by
    someone who can write to the store (the module docstring: a residual)."""
    try:
        practice = str(uuid.UUID(str(workspace_id)))
    except (TypeError, ValueError, AttributeError):
        raise StoreRefused('not a practice id') from None
    match = _named(storage_name)
    if match.group(1) != practice:
        raise StoreRefused('not a file of this practice')
    return _checked_path(match)


def in_practice_folder(workspace_id, storage_name) -> bool:
    """Whether ``storage_name`` is one of practice ``workspace_id``'s own stored files (own_path); False too when that
    cannot be told (an OSError): a name that cannot be checked is never taken for the practice's own."""
    try:
        own_path(workspace_id, storage_name)
    except (StoreRefused, OSError):
        return False
    return True


def _read_bytes(path: Path) -> bytes:
    """Every byte of the stored file at ``path``, opened through its folder without following a symbolic link at either
    step (one put there after the checks is refused, ELOOP). The store's one read of a stored file: the tests count it."""
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | nofollow)
    try:
        fd = os.open(path.name, os.O_RDONLY | nofollow, dir_fd=folder)
    finally:
        os.close(folder)
    with os.fdopen(fd, 'rb') as handle:
        return handle.read()


def _verified(path: Path, sha256) -> bytes:
    data = _read_bytes(path)
    if hashlib.sha256(data).hexdigest() != sha256:
        raise OriginalCorrupted('Stored original no longer matches its recorded sha256.')
    return data


def read_original(source_file) -> bytes:
    """The bytes of a stored file - a SourceFile, or anything with ``storage_name`` and ``sha256`` - checked against its
    sha256. OriginalCorrupted, before any byte is read, for a name that is not one the store writes or leads through a
    symbolic link or out of its folder (_checked_path), and when the bytes no longer match; OSError when the file is
    missing or cannot be read. It reads any practice's file: a reader acting for one practice uses read_own_original."""
    try:
        path = _checked_path(_named(source_file.storage_name))
    except StoreRefused:
        raise OriginalCorrupted('Original path escapes the original store.') from None
    return _verified(path, source_file.sha256)


def read_own_original(workspace_id, source_file) -> bytes:
    """read_original for a reader acting for one practice: OriginalCorrupted, before any byte is read, unless
    ``source_file``'s storage name is one of the practice's own stored files (own_path)."""
    try:
        path = own_path(workspace_id, getattr(source_file, 'storage_name', None))
    except StoreRefused:
        raise OriginalCorrupted('A stored file lies outside its practice\'s folder.') from None
    return _verified(path, source_file.sha256)


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
