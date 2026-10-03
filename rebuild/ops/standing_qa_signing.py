"""Prospective QA signing identity; no clinical evidence is resigned or rewritten.

The secret stays in its protected file and the request environment. Append-only
preflight, run and attempt records carry only the file identity and SHA-256.
"""
import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path

try:
    from . import provider_campaign as pc
except ImportError:
    import provider_campaign as pc

CONTRACT = 'prospective-qa-signing-key-v1'
KEY_NAME = 'qa-signing-key'
RECORD_NAME = 'qa-signing-key.json'
FIELD = 'qa_signing_key'


def declared_file(text, seen, root):
    mentions = re.findall(r'(?<![A-Za-z0-9_])qa_signing_key_file(?![A-Za-z0-9_])[^\w\n]*:', seen, re.I)
    if not mentions:
        return None
    pc.require(len(mentions) == 1, 'qa_signing_key_file must occur exactly once as a plain line.')
    value = pc._one(text, r'^qa_signing_key_file:[ \t]*(/\S+)[ \t]*$', 'qa_signing_key_file:')
    pc.refuse_env_path(value)
    pc.require(value == str(Path(root) / 'access' / KEY_NAME),
               'qa_signing_key_file must be this campaign root/access/qa-signing-key.')
    return value


def _access(declaration, root):
    root = Path(root)
    pc.require(str(root) == declaration.root and root.is_absolute(),
               'The signing identity belongs to the declared campaign root.')
    pc.require(declaration.qa_signing_key_file == str(root / 'access' / KEY_NAME),
               'The signing key path is not the declared campaign access path.')
    pc.refuse_env_path(root)
    parent_fd = pc._open_without_links(str(root.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        info = os.fstat(parent_fd)
        pc.require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                   'The signing campaign parent must be owned by this account and mode 0700.')
    finally:
        os.close(parent_fd)
    root_fd = pc._open_without_links(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        info = os.fstat(root_fd)
        pc.require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                   'The signing campaign root must be owned by this account and mode 0700.')
        fd = os.open('access', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root_fd)
    finally:
        os.close(root_fd)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        os.close(fd)
        raise pc.Refused('The signing access directory must be owned by this account and mode 0700.')
    return fd


def _read(directory, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        pc.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                   and stat.S_IMODE(info.st_mode) == 0o600 and 0 < info.st_size <= limit,
                   'The signing file must be bounded, regular, singly linked, owned by this account and mode 0600.')
        return os.read(fd, limit + 1)
    finally:
        os.close(fd)


def _write(directory, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(directory)


def _prior_activity(root):
    # A key may be recovered after an interrupted first preparation, but never
    # introduced after any provider preflight, clinical state, run or attempt.
    for name in ('ledger', 'runs', 'preflight', 'qa-state'):
        directory = Path(root) / name
        if os.path.lexists(directory):
            pc.require(not directory.is_symlink(), 'A signing history directory cannot be a link.')
            if any(item.name != pc.LOCK_FILE for item in directory.iterdir()):
                return True
    return False


def load(declaration, root, *, create=False):
    """Return the key and nonsecret binding; optional absence reads no key file.

    Creation is called only while the campaign ledger lock is held. Existing
    identity files are never overwritten; every subsequent reader checks them.
    """
    if not declaration.qa_signing_key_file:
        return None, None
    try:
        directory = _access(declaration, root)
    except OSError as error:
        raise pc.Refused(f'The QA signing directory cannot be opened ({type(error).__name__}).') from None
    try:
        names = os.listdir(directory)
        if RECORD_NAME not in names:
            pc.require(create and not _prior_activity(root),
                       'A persistent signing identity can be prepared only before this campaign has any activity.')
            if KEY_NAME not in names:
                _write(directory, KEY_NAME, secrets.token_urlsafe(48).encode('ascii'))
        data = _read(directory, KEY_NAME, 256)
        pc.require(re.fullmatch(rb'[A-Za-z0-9_-]{64}', data) is not None,
                   'The QA signing key must be a generated 64-character secret.')
        record = {'contract': CONTRACT, 'campaign': declaration.campaign,
                  'authority_id': declaration.authority_id, 'database': declaration.qa_database,
                  'file': declaration.qa_signing_key_file, 'sha256': hashlib.sha256(data).hexdigest()}
        if RECORD_NAME not in names:
            _write(directory, RECORD_NAME, (json.dumps(record, sort_keys=True) + '\n').encode())
        try:
            saved = json.loads(_read(directory, RECORD_NAME, 4096))
        except (ValueError, UnicodeDecodeError):
            raise pc.Refused('The QA signing identity record cannot be read.') from None
        pc.require(saved == record, 'The QA signing key or its campaign identity has changed.')
        return data.decode('ascii'), record
    except OSError as error:
        raise pc.Refused(f'The QA signing identity cannot be opened ({type(error).__name__}).') from None
    finally:
        os.close(directory)


def require_history(record, records):
    """Mutable files alone cannot replace the first append-only identity pin."""
    pc.require(all(value.get(FIELD) == record for value in records),
               'The QA signing identity differs from an earlier preflight, run or attempt; no request is sent.')
