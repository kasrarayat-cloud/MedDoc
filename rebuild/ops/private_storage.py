"""Read-only operator access to the dedicated application's private state.

The operator does not join the application group. A nonroot, capability-free,
networkless helper reads one explicitly approved read-only bind. Its root must
match the device/inode recorded by the root-owned installation procedure.
Neither file contents nor container stderr are included in errors or logs.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat
import subprocess

from dotenv import dotenv_values

STATE_DIR = Path('/var/lib/quillmd')
APP_ACCOUNT = 'quillmd-app'
IDENTITY_FILE = Path('/opt/meddoc-pro/rebuild/.runtime/state-identity.json')
APPROVED_ROOTS = frozenset(STATE_DIR / name for name in ('files', 'mail', 'proofs'))
MAX_OBJECT_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 10000
MAX_PATH_BYTES = 4096
MAX_DEPTH = 32


def _require(condition, message='Private storage validation failed.'):
    if not condition:
        raise RuntimeError(message)


def _relative(value):
    _require(isinstance(value, str) and value and '\\' not in value and '\x00' not in value)
    p = PurePosixPath(value)
    _require(p.parts and not p.is_absolute() and str(p) == value and '..' not in p.parts
             and len(p.parts) <= MAX_DEPTH and len(value.encode()) <= MAX_PATH_BYTES)
    return p.parts


def _checked_stat(value, expected, directory=False):
    _require((stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode))
             and value.st_uid == expected['uid'] and value.st_gid == expected['gid']
             and stat.S_IMODE(value.st_mode) == (0o700 if directory else 0o600))
    if not directory:
        _require(value.st_nlink == 1 and value.st_size <= MAX_OBJECT_BYTES)


def _directory(parent, name, expected):
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    _checked_stat(before, expected, directory=True)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        current = os.fstat(fd)
        _checked_stat(current, expected, directory=True)
        _require((before.st_dev, before.st_ino) == (current.st_dev, current.st_ino))
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_at(parent, name, expected, include_bytes):
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    _checked_stat(before, expected)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        start = os.fstat(fd)
        _checked_stat(start, expected)
        _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                  before.st_ctime_ns) == (start.st_dev, start.st_ino, start.st_size,
                                          start.st_mtime_ns, start.st_ctime_ns))
        content, length, digest = [], 0, hashlib.sha256()
        while True:
            piece = os.read(fd, 65536)
            if not piece:
                break
            length += len(piece)
            _require(length <= MAX_OBJECT_BYTES)
            digest.update(piece)
            if include_bytes:
                content.append(piece)
        end = os.fstat(fd)
        _require((start.st_dev, start.st_ino, start.st_size, start.st_mtime_ns,
                  start.st_ctime_ns) == (end.st_dev, end.st_ino, end.st_size,
                                        end.st_mtime_ns, end.st_ctime_ns)
                 and length == start.st_size)
        result = {'sha256': digest.hexdigest(), 'size': length, 'mode': 0o600}
        return result, b''.join(content) if include_bytes else None
    finally:
        os.close(fd)


def _collect(root, expected, action, relative=None):
    """Helper implementation, also exercised on local synthetic fixtures."""
    _require(action in ('read', 'inventory'))
    _require(set(expected) == {'uid', 'gid', 'device', 'inode'}
             and all(type(v) is int and v >= 0 for v in expected.values())
             and expected['uid'] > 0 and expected['gid'] > 0 and expected['inode'] > 0)
    root_stat = os.stat(root, follow_symlinks=False)
    _checked_stat(root_stat, expected, directory=True)
    _require((root_stat.st_dev, root_stat.st_ino) == (expected['device'], expected['inode']))
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(root_fd)
        _checked_stat(opened, expected, directory=True)
        _require((opened.st_dev, opened.st_ino) == (expected['device'], expected['inode']))
        if action == 'read':
            parts = _relative(relative)
            current = os.dup(root_fd)
            try:
                for part in parts[:-1]:
                    nested = _directory(current, part, expected)
                    os.close(current)
                    current = nested
                return _read_at(current, parts[-1], expected, True)
            finally:
                os.close(current)
        _require(relative is None)
        results, count = {}, [0]

        def visit(fd, parts):
            _require(len(parts) <= MAX_DEPTH)
            before = os.fstat(fd)
            with os.scandir(fd) as entries:
                for entry in entries:
                    count[0] += 1
                    _require(count[0] <= MAX_ENTRIES)
                    relative_path = '/'.join((*parts, entry.name))
                    _relative(relative_path)
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        nested = _directory(fd, entry.name, expected)
                        try:
                            visit(nested, (*parts, entry.name))
                        finally:
                            os.close(nested)
                    else:
                        results[relative_path] = _read_at(fd, entry.name, expected, False)[0]
            after = os.fstat(fd)
            _require((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
                     == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns))

        visit(root_fd, ())
        return results
    finally:
        os.close(root_fd)


def _helper_main():
    import sys
    try:
        raw = sys.stdin.buffer.read(16385)
        _require(len(raw) <= 16384)
        request = json.loads(raw)
        _require(type(request) is dict and set(request) == {'action', 'relative', 'expected'})
        expected = request['expected']
        _require(os.getuid() == expected['uid'] and os.getgid() == expected['gid']
                 and not (set(os.getgroups()) - {expected['gid']}))
        result = _collect('/data', expected, request['action'], request['relative'])
        if request['action'] == 'read':
            metadata, data = result
            sys.stdout.buffer.write(json.dumps(metadata, separators=(',', ':')).encode() + b'\n')
            sys.stdout.buffer.write(data)
        else:
            sys.stdout.buffer.write(json.dumps(result, separators=(',', ':')).encode())
        sys.stdout.buffer.flush()
    except BaseException:
        # Suppress tracebacks, paths, exception values, and document contents.
        os._exit(1)


def _no_symlink_components(path):
    _require(path.is_absolute() and '..' not in path.parts)
    current = Path('/')
    for component in path.parts[1:]:
        current /= component
        _require(not stat.S_ISLNK(current.lstat().st_mode))


def state_root(source):
    """Resolve explicit fresh state configuration without inheriting shell env."""
    source = Path(source).absolute()
    _no_symlink_components(source)
    value = dotenv_values(source / '.env').get('QUILLMD_STATE_DIR')
    if not value:
        return source / '.runtime'
    _require(value == str(STATE_DIR), 'Unexpected application state directory.')
    return STATE_DIR


def _installation(root):
    root = Path(root)
    _require(root in APPROVED_ROOTS, 'Unapproved private storage root.')
    for directory in (Path('/'), Path('/var'), Path('/var/lib'), STATE_DIR):
        info = directory.lstat()
        _require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                 and not (stat.S_IMODE(info.st_mode) & 0o022),
                 'Private storage ancestor ownership differs.')
    account = pwd.getpwnam(APP_ACCOUNT)
    _require(account.pw_uid > 0 and account.pw_gid > 0
             and set(os.getgrouplist(APP_ACCOUNT, account.pw_gid)) <= {account.pw_gid},
             'Application account privileges differ.')
    _require(STATE_DIR.lstat().st_gid == account.pw_gid
             and stat.S_IMODE(STATE_DIR.lstat().st_mode) == 0o710,
             'Private storage parent permissions differ.')
    _no_symlink_components(IDENTITY_FILE)
    before = IDENTITY_FILE.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
             and stat.S_IMODE(before.st_mode) == 0o600 and before.st_size <= 16384,
             'Private storage identity artifact is invalid.')
    fd = os.open(IDENTITY_FILE, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        current = os.fstat(fd)
        _require((before.st_dev, before.st_ino, before.st_uid, before.st_mode,
                  before.st_size) == (current.st_dev, current.st_ino, current.st_uid,
                                      current.st_mode, current.st_size))
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            document = json.loads(stream.read(16385))
    finally:
        os.close(fd)
    _require(type(document) is dict and document.get('version') == 1
             and document.get('account') == {'name': APP_ACCOUNT, 'uid': account.pw_uid,
                                             'gid': account.pw_gid}
             and type(document.get('roots')) is dict
             and set(document['roots']) == {str(p) for p in APPROVED_ROOTS},
             'Private storage installation identity differs.')
    identity = document['roots'][str(root)]
    _require(type(identity) is dict and set(identity) == {'device', 'inode'}
             and type(identity['device']) is int and identity['device'] >= 0
             and type(identity['inode']) is int and identity['inode'] > 0,
             'Private storage directory identity is invalid.')
    return dict(identity, uid=account.pw_uid, gid=account.pw_gid)


def _helper_source():
    functions = (_require, _relative, _checked_stat, _directory, _read_at, _collect, _helper_main)
    constants = ('MAX_OBJECT_BYTES', 'MAX_ENTRIES', 'MAX_PATH_BYTES', 'MAX_DEPTH')
    return ('import hashlib,json,os,stat\nfrom pathlib import PurePosixPath\n'
            + '\n'.join(f'{name}={globals()[name]}' for name in constants) + '\n'
            + '\n'.join(inspect.getsource(function) for function in functions)
            + '\n_helper_main()\n')


def _execute(root, action, relative=None):
    try:
        root = Path(root)
        expected = _installation(root)
        if action == 'read':
            _relative(relative)
        request = json.dumps({'action': action, 'relative': relative, 'expected': expected}).encode()
        args = ['docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                '--pids-limit=32', '--memory=1g', '--cpus=1',
                '--user', f"{expected['uid']}:{expected['gid']}",
                '--mount', f'type=bind,src={root},dst=/data,readonly',
                'python:3-slim', 'python', '-B', '-c', _helper_source()]
        result = subprocess.run(args, input=request, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=300, check=False)
        _require(result.returncode == 0)
        return result.stdout
    except Exception:
        raise RuntimeError('Private storage helper failed; protected output was suppressed.') from None


def _metadata(value):
    _require(type(value) is dict and set(value) == {'sha256', 'size', 'mode'}
             and type(value['size']) is int and 0 <= value['size'] <= MAX_OBJECT_BYTES
             and type(value['mode']) is int and value['mode'] == 0o600
             and isinstance(value['sha256'], str)
             and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None)


def read_file(root, relative):
    """Return a complete verified file; never grants host filesystem access."""
    try:
        output = _execute(root, 'read', relative)
        header, separator, data = output.partition(b'\n')
        _require(separator and len(header) <= 256)
        metadata = json.loads(header)
        _metadata(metadata)
        _require(len(data) == metadata['size']
                 and hashlib.sha256(data).hexdigest() == metadata['sha256'])
        return data
    except Exception:
        raise RuntimeError('Private storage file read failed; protected output was suppressed.') from None


def inventory(root):
    """Map approved-root relative file paths to SHA-256, byte size, and mode."""
    try:
        output = _execute(root, 'inventory')
        _require(len(output) <= MAX_ENTRIES * (MAX_PATH_BYTES + 256))
        # Duplicate JSON members must not silently overwrite paths or metadata.
        def unique(pairs):
            value = {}
            for key, item in pairs:
                _require(key not in value)
                value[key] = item
            return value
        result = json.loads(output, object_pairs_hook=unique)
        _require(type(result) is dict and len(result) <= MAX_ENTRIES)
        for relative, metadata in result.items():
            _relative(relative)
            _metadata(metadata)
        return result
    except Exception:
        raise RuntimeError('Private storage inventory failed; protected output was suppressed.') from None
