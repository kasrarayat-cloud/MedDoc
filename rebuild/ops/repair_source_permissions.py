"""One pinned, reversible installed-source mode repair; default is a no-op.

Only Git-tracked rebuild source bytes and their pinned public parents are admitted.
This operator never starts services, changes contents, or qualifies availability.
"""
import argparse
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[2]
INSTALLED = '4d46a71520275d76a36aa83ddff1a85939711a04'
BASE = 'c227031634f2c416b1cc972ab9dbde74a8c3caf1'
SELF = 'rebuild/ops/repair_source_permissions.py'
TEST = 'rebuild/ops/test_repair_source_permissions.py'
ENTRY = 'scripts/repair-quillmd-source-permissions.py'
DECL = 'docs/foundation/mutations/20261007-quillmd-source-permissions-repair.md'
ALLOWED = frozenset({SELF, TEST, ENTRY, DECL,
    'rebuild/ops/private_availability_recovery.py',
    'docs/foundation/mutations/20261007-quillmd-private-availability-recovery.md'})
OUTPUT = ROOT / 'rebuild/.runtime/source-permissions-repair-20261007'
ATTEMPT = ROOT / 'rebuild/.runtime/owner-demo-20261006/source-permissions-repair-attempt-20261007.json'
DIRECTORY = 'rebuild/static/fonts'
MODES = frozenset({0o600, 0o644, 0o664, 0o700, 0o755, 0o775})
UNITS = tuple('quillmd-fresh-' + name + '.service' for name in
              ('doctor', 'admin', 'worker', 'backup', 'offsite', 'backup-alerts', 'operations-publisher'))
LOCKS = ('legacy-model-activation.lock', 'backup-monitor/capture.lock',
         'automatic-offsite/execution.lock', 'backup-alerts/monitor.lock')
FIELDS = ('dev', 'ino', 'uid', 'gid', 'mode', 'nlink', 'size')
PATH_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C', 'GIT_OPTIONAL_LOCKS': '0'}
NATIVE_CLI_ENV = ('HOME', 'XDG_CONFIG_HOME', 'GH_CONFIG_DIR', 'GH_TOKEN', 'GITHUB_TOKEN')


class Refusal(RuntimeError):
    """Fixed nonsecret label, never arbitrary exception details."""


def require(value, label):
    if not value:
        raise Refusal('source_permissions_' + label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def command(argv, cwd=None, pass_fds=()):
    # Retain the existing native session's GitHub authentication for citation;
    # do not let shell bootstrap or Git redirection change the approved target.
    child_env = {key: os.environ[key] for key in NATIVE_CLI_ENV if key in os.environ}
    child_env.update(PATH_ENV)
    result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=60, env=child_env, pass_fds=pass_fds)
    require(result.returncode == 0 and len(result.stdout) <= 16 * 1024 * 1024, 'command_failed')
    return result.stdout


def git(tree, *args):
    return command(['/usr/bin/git', '-C', str(tree), *args])


def metadata(info):
    return dict(zip(FIELDS, (info.st_dev, info.st_ino, info.st_uid, info.st_gid,
                           stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size)))


def stable(info):
    return (*metadata(info).values(), info.st_mtime_ns, info.st_ctime_ns)


def relative_path(value):
    require(isinstance(value, str) and value == str(PurePosixPath(value))
            and not value.startswith('/') and '..' not in PurePosixPath(value).parts,
            'relative_path')
    return value


def source_path(value):
    relative_path(value)
    parts = PurePosixPath(value).parts
    require(parts[0] == 'rebuild' and all(part not in
            {'.env', '.runtime', '.venv', 'node_modules', '.git'} for part in parts), 'public_source_path')
    return value


@contextmanager
def open_root(path):
    """Every absolute parent is opened without following links."""
    require(path.is_absolute() and path == Path(os.path.normpath(path)), 'root_path')
    with ExitStack() as stack:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        for name in path.parts[1:]:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, fd)
        yield fd


def open_relative(root_fd, relative, directory=False):
    relative_path(relative)
    if relative == '.':
        return os.dup(root_fd)
    with ExitStack() as stack:
        parent = root_fd
        parts = PurePosixPath(relative).parts
        for name in parts[:-1]:
            parent = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, parent)
        flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else os.O_NONBLOCK)
        return os.open(parts[-1], flags, dir_fd=parent)


def bytes_at(fd, maximum=32 * 1024 * 1024):
    before = os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, 'regular_file_size')
    os.lseek(fd, 0, os.SEEK_SET)
    raw = bytearray()
    while len(raw) <= maximum:
        piece = os.read(fd, min(65536, maximum + 1 - len(raw)))
        if not piece:
            break
        raw.extend(piece)
    require(len(raw) == before.st_size and stable(before) == stable(os.fstat(fd)), 'read_race')
    return bytes(raw)


def protected(path):
    with open_root(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000
                    and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600, 'protected_identity')
            return bytes_at(fd)
        finally:
            os.close(fd)


def write_new(path, raw):
    with open_root(path.parent) as parent:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def operator_bytes(relative, mode=0o644, root_fd=None):
    """Authenticate public metadata before reading; never follow a source link."""
    if root_fd is None:
        with open_root(SOURCE) as opened:
            return operator_bytes(relative, mode, opened)
    fd = open_relative(root_fd, relative)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 1000
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == mode
                and mode in (0o644, 0o755) and not os.listxattr(fd), 'operator_file_identity')
        raw = bytes_at(fd)
        current = open_relative(root_fd, relative)
        try:
            require(stable(before) == stable(os.fstat(fd)) == stable(os.fstat(current)), 'operator_path_race')
        finally:
            os.close(current)
        return raw
    finally:
        os.close(fd)


def sealed_citation(top, library, target):
    """Execute the checked citation predicates and library without reopening paths."""
    assignment = b'_RA_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/runs-api.sh"'
    require(top.count(assignment) == 1, 'citation_library_assignment')
    with ExitStack() as stack:
        def sealed(raw):
            fd = os.memfd_create('quillmd-reviewed-citation', os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
            stack.callback(os.close, fd)
            require(os.write(fd, raw) == len(raw), 'citation_buffer_write')
            seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
            fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
            require(fcntl.fcntl(fd, fcntl.F_GET_SEALS) == seals, 'citation_buffer_seals')
            return fd
        library_fd = sealed(library)
        adapted = top.replace(assignment, ('_RA_LIB="/proc/self/fd/' + str(library_fd) + '"').encode())
        top_fd = sealed(adapted)
        command(['/bin/bash', '/proc/self/fd/' + str(top_fd), target], cwd=SOURCE,
                pass_fds=(top_fd, library_fd))


def native_identity():
    with open_root(ROOT) as root_fd:
        root = metadata(os.fstat(root_fd))
    return {'uid': os.getuid(), 'gid': os.getgid(),
            'machine_id_sha256': sha(Path('/etc/machine-id').read_bytes()),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'namespaces': {name: os.readlink('/proc/self/ns/' + name) for name in ('mnt', 'pid', 'user')},
            'root': root}


def load_contract():
    raw = operator_bytes(DECL)
    marker = b'<!-- source-permissions-contract -->\n```json\n'
    require(raw.count(marker) == 1 and b'\n```' in raw.split(marker, 1)[1], 'declaration_contract')
    value = json.loads(raw.split(marker, 1)[1].split(b'\n```', 1)[0])
    require(value.get('format') == 1 and value.get('installed_commit') == INSTALLED
            and value.get('root') == str(ROOT) and value.get('output') == str(OUTPUT)
            and value.get('attempt') == str(ATTEMPT) and value.get('provider_calls') == 0
            and value.get('service_actions') == 0 and value.get('content_changes') == 0
            and value.get('automatic_retries') is False, 'prospective_scope')
    return value


def source_gate(target):
    require(re.fullmatch('[a-f0-9]{40}', target or '') and SOURCE.is_relative_to(ROOT / '.worktrees')
            and SOURCE.resolve(strict=True) == SOURCE, 'operator_source')
    require(git(SOURCE, 'rev-parse', 'HEAD').strip().decode() == target
            and not git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(), 'operator_clean')
    git(SOURCE, 'merge-base', '--is-ancestor', BASE, target)
    changes = set(git(SOURCE, 'diff', '--name-only', BASE, target).decode().splitlines())
    require(changes <= ALLOWED and {SELF, TEST, ENTRY, DECL} <= changes, 'operator_scope')
    require(git(ROOT, 'branch', '--show-current').strip() == b'main'
            and git(ROOT, 'rev-parse', 'HEAD').strip().decode() == INSTALLED
            and not git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'installed_clean')
    require(git(ROOT, 'rev-parse', 'origin/main').strip().decode() == target, 'merged_operator')
    # The worktree contents, including the executing operator, must be Git bytes.
    buffers = {}
    with open_root(SOURCE) as root_fd:
        for line in git(SOURCE, 'ls-files', '--stage', '-z').decode().split('\0')[:-1]:
            identity, relative = line.split('\t', 1)
            mode, _, stage = identity.split()
            require(stage == '0' and mode in ('100644', '100755'), 'operator_index_type')
            raw = operator_bytes(relative, 0o644 if mode == '100644' else 0o755, root_fd)
            require(raw == git(SOURCE, 'show', target + ':' + relative), 'operator_byte_identity')
            if relative in ('scripts/check-citation.sh', 'scripts/lib/runs-api.sh'):
                buffers[relative] = raw
    require(len(buffers) == 2, 'citation_source_population')
    sealed_citation(buffers['scripts/check-citation.sh'], buffers['scripts/lib/runs-api.sh'], target)
    return {'operator_commit': target, 'installed_commit': INSTALLED, 'changed_paths': sorted(changes)}


def installed_index():
    indexed = {}
    for line in git(ROOT, 'ls-files', '--stage', '-z', 'rebuild').decode().split('\0')[:-1]:
        identity, relative = line.split('\t', 1)
        mode, _, stage = identity.split()
        require(stage == '0' and mode in ('100644', '100755'), 'index_type')
        indexed[source_path(relative)] = 0o644 if mode == '100644' else 0o755
    return indexed


def load_manifest(contract):
    path = Path(contract['manifest_path'])
    require(path.is_relative_to(ROOT / 'rebuild/.runtime/owner-demo-20261006')
            and re.fullmatch('[a-f0-9]{64}', contract.get('manifest_sha256', '')), 'manifest_path')
    raw = protected(path)
    require(sha(raw) == contract['manifest_sha256'], 'manifest_pin')
    value = json.loads(raw)
    require(value.get('format') == 1 and value.get('installed_commit') == INSTALLED
            and value.get('root') == str(ROOT), 'manifest_scope')
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000
            and value.get('native_identity') == native_identity(), 'native_identity')
    return value, raw


def verify_fd(fd, row, mode=None):
    info = os.fstat(fd)
    expected = {field: row[field] for field in FIELDS}
    if mode is not None:
        expected['mode'] = mode
    require(metadata(info) == expected and info.st_uid == info.st_gid == 1000
            and stat.S_IMODE(info.st_mode) in MODES, 'inventory_metadata')
    require(not os.listxattr(fd), 'inventory_xattrs')
    if row['kind'] == 'file':
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and sha(bytes_at(fd)) == row['sha256'], 'inventory_content')
    else:
        require(row['kind'] == 'directory' and stat.S_ISDIR(info.st_mode), 'inventory_type')


@contextmanager
def inventory(manifest):
    indexed = installed_index()
    required = set(indexed)
    for relative in indexed:
        required.update(str(parent) for parent in PurePosixPath(relative).parents)
    rows = manifest['inventory']
    require(isinstance(rows, list) and len(rows) == len(required)
            and {row['path'] for row in rows} == required, 'inventory_population')
    candidates = manifest['candidates']
    require(isinstance(candidates, list) and candidates and len(candidates) == len({row['path'] for row in candidates}),
            'candidate_population')
    expected_candidates = []
    with ExitStack() as stack:
        root_fd = stack.enter_context(open_root(ROOT))
        handles = {}
        for row in rows:
            relative = row['path']
            relative_path(relative)
            require(set(row) == set(FIELDS) | {'path', 'kind', 'target_mode'} | ({'sha256'} if relative in indexed else set()),
                    'inventory_schema')
            is_file = relative in indexed
            require(row['kind'] == ('file' if is_file else 'directory'), 'inventory_type')
            fd = open_relative(root_fd, relative, directory=not is_file)
            stack.callback(os.close, fd)
            verify_fd(fd, row)
            handles[relative] = (fd, row)
            if is_file:
                require(sha(git(ROOT, 'show', INSTALLED + ':' + relative)) == row['sha256'], 'installed_byte_identity')
                target = indexed[relative]
                require(row['target_mode'] == target, 'index_mode')
                if row['mode'] != target:
                    expected_candidates.append(row)
            elif not row['mode'] & 0o001:
                require(relative == DIRECTORY and row['mode'] == 0o700 and row['target_mode'] == 0o755, 'directory_scope')
                expected_candidates.append(row)
            else:
                require(row['target_mode'] == row['mode'], 'directory_mode')
        require(sorted(candidates, key=lambda row: row['path']) == sorted(expected_candidates, key=lambda row: row['path']),
                'candidate_scope')
        yield root_fd, handles, candidates


def check_inventory(root_fd, handles, modes):
    for relative, (fd, row) in handles.items():
        mode = modes.get(relative, row['mode'])
        verify_fd(fd, row, mode)
        current = open_relative(root_fd, relative, directory=row['kind'] == 'directory')
        try:
            verify_fd(current, row, mode)
        finally:
            os.close(current)


def directory_children(fd, row, handles):
    """Opening public traversal must not expose an untracked child."""
    expected = {PurePosixPath(path).name: child for path, (_, child) in handles.items()
                if str(PurePosixPath(path).parent) == row['path']}
    require(expected and len(expected) <= 4096, 'directory_children_population')
    found = set()
    with os.scandir(fd) as children:
        for child in children:
            require(child.name in expected and child.name not in found, 'directory_unknown_child')
            found.add(child.name)
            info = child.stat(follow_symlinks=False)
            pinned = expected[child.name]
            require(metadata(info) == {field: pinned[field] for field in FIELDS}
                    and not stat.S_ISLNK(info.st_mode), 'directory_child_identity')
    require(found == set(expected), 'directory_children_population')


def check_path(root_fd, fd, row, mode, handles, modes):
    for relative in map(str, PurePosixPath(row['path']).parents):
        parent_row = handles[relative][1]
        parent = open_relative(root_fd, relative, directory=True)
        try:
            verify_fd(parent, parent_row, modes.get(relative, parent_row['mode']))
        finally:
            os.close(parent)
    verify_fd(fd, row, mode)
    current = open_relative(root_fd, row['path'], directory=row['kind'] == 'directory')
    try:
        verify_fd(current, row, mode)
    finally:
            os.close(current)
    if row['kind'] == 'directory':
        # Children repaired earlier keep their admitted canonical modes.
        admitted = {path: (handle, {**child, 'mode': modes.get(path, child['mode'])})
                    for path, (handle, child) in handles.items()}
        directory_children(fd, row, admitted)


def rollback_identity(fd, row, mode):
    if row['kind'] == 'file':
        # Restore only our mode on the original admitted inode. A concurrent
        # writer's bytes, size or attributes must not leave that inode public;
        # neither read nor restore those unrelated changes during rollback.
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_dev == row['dev'] and info.st_ino == row['ino']
                and info.st_uid == row['uid'] == 1000 and info.st_gid == row['gid'] == 1000
                and stat.S_IMODE(info.st_mode) == mode,
                'rollback_file_identity')
        return
    # An unknown child can change directory size/link count while traversal is
    # public. Restore this very same owned directory's private mode promptly.
    info = os.fstat(fd)
    require(stat.S_ISDIR(info.st_mode) and info.st_dev == row['dev'] and info.st_ino == row['ino']
            and info.st_uid == info.st_gid == 1000 and stat.S_IMODE(info.st_mode) == mode,
            'rollback_directory_identity')


def stopped_state():
    state = {}
    properties = ('ActiveState,SubState,MainPID,InvocationID,ActiveEnterTimestampMonotonic,'
                  'InactiveEnterTimestampMonotonic,ExecMainStartTimestampMonotonic')
    for unit in UNITS:
        raw = command(['/usr/bin/systemctl', 'show', unit, '--property=' + properties]).decode()
        row = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        require(set(row) == set(properties.split(',')) and row['MainPID'] == '0'
                and row['ActiveState'] in ('inactive', 'failed'), 'services_not_stopped')
        state[unit] = row
    return state


@contextmanager
def operation_locks():
    with ExitStack() as stack:
        for relative in LOCKS:
            path = ROOT / 'rebuild/.runtime' / relative
            parent = stack.enter_context(open_root(path.parent))
            fd = os.open(path.name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000
                    and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600, 'lock_identity')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def repair(manifest, raw, source, *, execute=False):
    require(not os.path.lexists(OUTPUT) and not os.path.lexists(ATTEMPT), 'attempt_consumed')
    with operation_locks(), inventory(manifest) as (root_fd, handles, candidates):
        before = stopped_state()
        require(manifest['native_identity'] == native_identity(), 'native_identity_race')
        check_inventory(root_fd, handles, {})
        for row in candidates:
            if row['kind'] == 'directory':
                directory_children(handles[row['path']][0], row, handles)
        require(stopped_state() == before, 'service_race')
        if not execute:
            return {'complete': True, 'readonly': True, 'candidate_count': len(candidates), **source}
        with open_root(OUTPUT.parent) as parent:
            os.mkdir(OUTPUT.name, 0o700, dir_fd=parent)
        write_new(OUTPUT / 'original-inventory.json', raw)
        write_new(ATTEMPT, encode({'format': 1, 'manifest_sha256': sha(raw), **source}))
        changed, modes = [], {}
        try:
            for row in candidates:
                require(manifest['native_identity'] == native_identity(), 'native_identity_race')
                require(stopped_state() == before, 'service_race')
                fd = handles[row['path']][0]
                check_path(root_fd, fd, row, row['mode'], handles, modes)
                # Register first: a failure immediately after fchmod still rolls back.
                changed.append(row)
                os.fchmod(fd, row['target_mode'])
                modes[row['path']] = row['target_mode']
                check_path(root_fd, fd, row, row['target_mode'], handles, modes)
            check_inventory(root_fd, handles, modes)
            for row in candidates:
                if row['kind'] == 'directory':
                    check_path(root_fd, handles[row['path']][0], row, row['target_mode'], handles, modes)
            require(stopped_state() == before and manifest['native_identity'] == native_identity(), 'final_boundary')
            result = {'complete': True, 'manifest_sha256': sha(raw), 'changed_paths': sorted(modes),
                      'service_actions': 0, 'content_changes': 0, 'provider_calls': 0, 'automatic_retries': False, **source}
            write_new(OUTPUT / 'complete.json', encode(result))
            return result
        except BaseException as error:
            rollback = {}
            for row in reversed(changed):
                try:
                    fd = handles[row['path']][0]
                    current_mode = stat.S_IMODE(os.fstat(fd).st_mode)
                    require(current_mode in (row['mode'], row['target_mode']), 'rollback_mode')
                    rollback_identity(fd, row, current_mode)
                    os.fchmod(fd, row['mode'])
                    rollback_identity(fd, row, row['mode'])
                    rollback[row['path']] = True
                except BaseException:
                    rollback[row['path']] = False
            label = safe_failure_label(error)
            try:
                stopped_after = stopped_state() == before
            except BaseException:
                stopped_after = False
            write_new(OUTPUT / 'failed.json', encode({'complete': False, 'refusal_label': label,
                'rollback': rollback, 'attempt_consumed': True, 'service_actions': 0, 'provider_calls': 0,
                'services_stopped_after': stopped_after, 'automatic_retries': False,
                'preservation_verified': False, 'external_drift_adjudicated': False,
                'rollback_scope': 'original_admitted_inode_modes_only',
                'manifest_sha256': sha(raw), **source}))
            raise Refusal(label) from None


def safe_failure_label(error):
    return str(error) if isinstance(error, Refusal) and re.fullmatch('source_permissions_[a-z_]+', str(error)) \
        else 'source_permissions_operation_failed'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--operator-commit')
    args = parser.parse_args(argv)
    if not (args.preflight or args.execute):
        print(json.dumps({'action': 'none', 'scope': 'pinned installed Git-tracked public source modes only',
                          'service_actions': 0, 'provider_calls': 0, 'automatic_retries': False}))
        return 0
    require(os.environ.get('RULED_MUTATION_DECLARATION') == DECL, 'normal_ruled_door')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(re.fullmatch('[a-f0-9]{40}', commit)
            and git(SOURCE, 'log', '-1', '--format=%H', '--', DECL).strip().decode() == commit
            and git(SOURCE, 'show', commit + ':' + DECL) == operator_bytes(DECL), 'committed_declaration')
    contract = load_contract()
    require(not args.execute or contract.get('execution_qualified') is True, 'execution_unqualified')
    source = source_gate(args.operator_commit)
    manifest, raw = load_manifest(contract)
    result = repair(manifest, raw, source, execute=args.execute)
    print(json.dumps(result, sort_keys=True))
    return 0
