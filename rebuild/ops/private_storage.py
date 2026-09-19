"""Read-only operator access to the dedicated application's private state.

The operator does not join the application group. A nonroot, capability-free,
networkless helper reads one explicitly approved read-only bind. Its root must
match the device/inode recorded by the root-owned installation procedure.
Neither file contents nor container stderr are included in errors or logs.

⚠️ AND THE CONTAINER'S OWN STDOUT IS A LOGGED CHANNEL UNLESS IT IS TOLD NOT TO BE. Measured on this host:
`docker info` reports the `json-file` driver, and an ATTACHED `docker run --rm` whose stdout the client is
already capturing on a pipe is STILL recorded by the daemon — `docker logs` returned a canary from a
running container and `docker inspect --format '{{.LogPath}}'` named a real file under
`/var/lib/docker/containers/<id>/`. `--rm` deletes that file when the container exits; it does not prevent
the recording, and an earlier report of this module called the arrangement harmless on exactly that
mistaken reading. Every invocation now passes `--log-driver=none`, measured to leave `LogPath` empty and
`docker logs` refusing, while the client pipe still receives the data.
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
# Version 2 identities live on the encrypted volume. A device-mapper minor is assigned
# when the volume opens, so the device number is resolved from this node at check time.
DEVICE_SOURCE = '/dev/mapper/quillmd-fresh-encrypted'
APP_ACCOUNT = 'quillmd-app'
IDENTITY_FILE = Path('/opt/meddoc-pro/rebuild/.runtime/state-identity.json')
APPROVED_ROOTS = frozenset(STATE_DIR / name for name in ('files', 'mail', 'proofs'))
MAX_OBJECT_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 10000
MAX_PATH_BYTES = 4096
MAX_DEPTH = 32
# Django's file email backend writes each message then a line of 79 dashes. A single outbox file routinely
# holds SEVERAL messages for SEVERAL recipients, because the filename carries one second of entropy and the
# application opens it O_APPEND — so a whole file is never the unit of anything.
RECORD_SEPARATOR = b'\n' + b'-' * 79 + b'\n'
SYNTHETIC_DOMAIN = '@synthetic.quillmd.invalid'
MAX_RECORDS = 256
MAX_SELECT_NAMES = 8
MAX_ROUTE_BYTES = 1024


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


def _records(blob):
    """The messages one outbox file holds. Runs INSIDE the helper; nothing here leaves the boundary."""
    chunks = [chunk for chunk in blob.split(RECORD_SEPARATOR) if chunk.strip()]
    _require(len(chunks) <= MAX_RECORDS)
    return chunks


def _recipients(chunk):
    """One record's To: addresses, lowercased. Never raises with content attached."""
    import email
    from email.utils import getaddresses
    try:
        parsed = email.message_from_bytes(chunk)
        return [found.lower() for _, found in getaddresses(parsed.get_all('To') or []) if found]
    except Exception:
        return []


def _selected(blobs, criteria):
    """⚠️ THE WHOLE POINT OF THIS FUNCTION IS WHAT IT DOES NOT RETURN.

    It runs inside the confined helper, over bytes that never leave it, and hands back ONE matched route
    plus counts. Unrelated records — another account's invitation, a message for a real address — are
    counted and dropped here, on the service side of the boundary. The previous arrangement exported the
    entire file to the operator process and rejected the unrelated records afterwards, which is a rejection
    that happens one address space too late.

    Four things must agree before anything is returned: the run's files, the exact recipient, the message
    purpose, and the record binding. A failure in any of them returns a reason, never a candidate.
    """
    import re
    address = criteria['address']
    pattern = re.compile(criteria['pattern'].encode())
    mine, foreign, outside = [], 0, 0
    for blob in blobs:
        for chunk in _records(blob):
            found = _recipients(chunk)
            if address in found:
                mine.append(chunk)
                continue
            foreign += 1
            if not found or any(not one.endswith(SYNTHETIC_DOMAIN) for one in found):
                outside += 1
    counts = {'records_for_this_run': len(mine), 'records_for_others': foreign,
              'records_outside_synthetic': outside}
    if outside:
        return dict(counts, found=False, reason='outside_synthetic', route='')
    if not mine:
        return dict(counts, found=False, reason='no_record_for_this_run', route='')
    if len(mine) > 1:
        return dict(counts, found=False, reason='more_than_one_record', route='')
    match = pattern.search(mine[0])
    if not match:
        return dict(counts, found=False, reason='no_link_of_this_purpose', route='')
    token = match.group('token')
    digest = hashlib.sha256(token).hexdigest()
    if criteria.get('expect_sha256') and digest != criteria['expect_sha256']:
        # The token is real and belongs to a DIFFERENT record. It is discarded here, inside the boundary.
        return dict(counts, found=False, reason='token_not_bound', route='')
    prefix = criteria.get('expect_prefix')
    if prefix and not token.startswith(prefix.encode() + b'/'):
        return dict(counts, found=False, reason='token_not_bound', route='')
    route = ('/%s/' % criteria['purpose']).encode() + token + b'/'
    _require(len(route) <= MAX_ROUTE_BYTES)
    return dict(counts, found=True, reason='', route=route.decode('ascii'))


def _collect(root, expected, action, relative=None, criteria=None):
    """Helper implementation, also exercised on local synthetic fixtures."""
    _require(action in ('read', 'inventory', 'select'))
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
        def read_one(name):
            parts = _relative(name)
            current = os.dup(root_fd)
            try:
                for part in parts[:-1]:
                    nested = _directory(current, part, expected)
                    os.close(current)
                    current = nested
                return _read_at(current, parts[-1], expected, True)
            finally:
                os.close(current)
        if action == 'read':
            return read_one(relative)
        if action == 'select':
            # Same verified read as 'read' — same ownership, mode and stat re-checks — but the bytes stay
            # here and only the matched route is returned.
            _require(relative is None and type(criteria) is dict)
            _require(set(criteria) <= {'names', 'address', 'pattern', 'purpose', 'expect_sha256', 'expect_prefix'})
            _require({'names', 'address', 'pattern', 'purpose'} <= set(criteria))
            names = criteria['names']
            _require(type(names) is list and 0 < len(names) <= MAX_SELECT_NAMES)
            _require(isinstance(criteria['address'], str)
                     and criteria['address'].endswith(SYNTHETIC_DOMAIN)
                     and criteria['address'] == criteria['address'].lower())
            return _selected([read_one(name)[1] for name in names], criteria)
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
        _require(type(request) is dict
                 and set(request) == {'action', 'relative', 'expected', 'criteria'})
        expected = request['expected']
        _require(os.getuid() == expected['uid'] and os.getgid() == expected['gid']
                 and not (set(os.getgroups()) - {expected['gid']}))
        result = _collect('/data', expected, request['action'], request['relative'], request['criteria'])
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
    _require(type(document) is dict and document.get('version') in (1, 2)
             and document.get('account') == {'name': APP_ACCOUNT, 'uid': account.pw_uid,
                                             'gid': account.pw_gid}
             and type(document.get('roots')) is dict
             and set(document['roots']) == {str(p) for p in APPROVED_ROOTS},
             'Private storage installation identity differs.')
    identity = document['roots'][str(root)]
    if document['version'] == 1:
        _require(set(document) == {'version', 'account', 'roots'}
                 and type(identity) is dict and set(identity) == {'device', 'inode'}
                 and type(identity['device']) is int and identity['device'] >= 0
                 and type(identity['inode']) is int and identity['inode'] > 0,
                 'Private storage directory identity is invalid.')
        return dict(identity, uid=account.pw_uid, gid=account.pw_gid)
    _require(set(document) == {'version', 'account', 'roots', 'device_source'}
             and document['device_source'] == DEVICE_SOURCE
             and type(identity) is dict and set(identity) == {'inode'}
             and type(identity['inode']) is int and identity['inode'] > 0,
             'Private storage directory identity is invalid.')
    return {'device': _encrypted_device(), 'inode': identity['inode'],
            'uid': account.pw_uid, 'gid': account.pw_gid}


def _encrypted_device():
    """Current device number of the open encrypted volume; refuses when it is closed."""
    _require(Path(DEVICE_SOURCE).parent == Path('/dev/mapper'), 'Unexpected encrypted device source.')
    try:
        info = os.stat(DEVICE_SOURCE)
    except OSError:
        raise RuntimeError('The encrypted volume is not open.') from None
    _require(stat.S_ISBLK(info.st_mode) and info.st_rdev > 0, 'The encrypted volume is not open.')
    return info.st_rdev


def _helper_source():
    functions = (_require, _relative, _checked_stat, _directory, _read_at,
                 _records, _recipients, _selected, _collect, _helper_main)
    constants = ('MAX_OBJECT_BYTES', 'MAX_ENTRIES', 'MAX_PATH_BYTES', 'MAX_DEPTH',
                 'RECORD_SEPARATOR', 'SYNTHETIC_DOMAIN', 'MAX_RECORDS', 'MAX_SELECT_NAMES',
                 'MAX_ROUTE_BYTES')
    return ('import hashlib,json,os,stat\nfrom pathlib import PurePosixPath\n'
            + '\n'.join(f'{name}={globals()[name]!r}' for name in constants) + '\n'
            + '\n'.join(inspect.getsource(function) for function in functions)
            + '\n_helper_main()\n')


def _execute(root, action, relative=None, criteria=None):
    try:
        root = Path(root)
        expected = _installation(root)
        if action == 'read':
            _relative(relative)
        request = json.dumps({'action': action, 'relative': relative,
                              'expected': expected, 'criteria': criteria}).encode()
        # ⚠️ `--log-driver=none` IS LOad-BEARING AND IS NOT A TIDINESS FLAG. Without it the daemon records
        # this container's stdout — which for a 'read' is the file itself — into
        # /var/lib/docker/containers/<id>/<id>-json.log for the container's lifetime. Measured: with the
        # default driver a canary was readable via `docker logs` from a RUNNING attached `--rm` container
        # and `LogPath` named a real file; with this flag `LogPath` is empty and `docker logs` refuses,
        # while the client pipe below is unaffected. Nothing about the shared daemon is changed.
        args = ['docker', 'run', '--rm', '-i', '--log-driver=none',
                '--pull=never', '--network=none', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                '--pids-limit=32', '--memory=1g', '--cpus=1',
                '--user', f"{expected['uid']}:{expected['gid']}",
                '--mount', f'type=bind,src={root},dst=/data,readonly',
                'python:3-slim', 'python', '-B', '-c', _helper_source()]
        result = subprocess.run(args, input=request, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=300, check=False)
        del request
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


def select_message(root, names, address, purpose, pattern, expect_sha256='', expect_prefix=''):
    """Return ONE matched route from this run's own message, or a reason. Unrelated records never leave.

    ⚠️ THIS EXISTS SO THAT `read_file` IS NOT THE MAIL PATH. `read_file` is all-or-nothing by construction
    — no predicate, no partial read — so using it to find one message means exporting every message that
    shares the file into the operator process and rejecting the unrelated ones afterwards. That rejection
    is correct and it is one address space too late: under the append-collision this module's callers exist
    to handle, the exported file can hold somebody else's live token. Here the selection, the purpose match
    and the record binding all happen inside the helper, and the only thing that crosses the boundary is
    the route the caller is entitled to.

    The returned route IS a secret — it contains the token. Navigate to it; never log or store it.
    """
    try:
        criteria = {'names': list(names), 'address': address, 'purpose': purpose, 'pattern': pattern}
        if expect_sha256:
            criteria['expect_sha256'] = expect_sha256
        if expect_prefix:
            criteria['expect_prefix'] = expect_prefix
        output = _execute(root, 'select', criteria=criteria)
        _require(len(output) <= MAX_ROUTE_BYTES + 512)
        result = json.loads(output)
        _require(type(result) is dict
                 and set(result) == {'found', 'reason', 'route', 'records_for_this_run',
                                     'records_for_others', 'records_outside_synthetic'})
        _require(type(result['found']) is bool and isinstance(result['route'], str)
                 and isinstance(result['reason'], str) and len(result['reason']) <= 64
                 and all(type(result[k]) is int and result[k] >= 0 for k in
                         ('records_for_this_run', 'records_for_others', 'records_outside_synthetic')))
        _require(bool(result['route']) == result['found'])
        return result
    except Exception:
        raise RuntimeError('Private storage selection failed; protected output was suppressed.') from None


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
