"""Linux boundary for the separately qualified self-contained Word SDK.

The generic Python document sandbox is separate. Landlock and the first
seccomp filter precede CLR startup; the managed gate synchronizes exec denial before opening a document.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import pwd
import resource
import stat
import sys


READ_FILE, READ_DIR, EXECUTE = 1 << 2, 1 << 3, 1
FS_RIGHTS = (1 << 15) - 1  # Landlock ABI3, including truncate.
CLONE_REQUIRED = 0x100 | 0x800 | 0x10000  # VM | SIGHAND | THREAD.
CLONE_ALLOWED = CLONE_REQUIRED | 0x200 | 0x400 | 0x40000 | 0x80000 | 0x100000 | 0x200000 | 0x1000000
CAP_AS = 8 * 1024 * 1024 * 1024  # CLR reserves address space; managed heap is separately bounded.
MAX_RUNTIME_BYTES = 384 * 1024 * 1024


def require(value, message):
    if not value:
        raise RuntimeError(message)


def clone_allowed(flags):
    return flags & CLONE_REQUIRED == CLONE_REQUIRED and flags & ~CLONE_ALLOWED == 0


def verified_runtime(root, manifest_path, expected_manifest_sha, *, qualification=False):
    root, manifest_path = Path(root).absolute(), Path(manifest_path).absolute()
    require(root.resolve() == root and root.is_dir() and manifest_path.resolve() == manifest_path,
            'Runtime paths must not contain symlinks.')
    require(not root.stat().st_mode & 0o022, 'Runtime root cannot be group/world writable.')
    require(manifest_path.is_file() and manifest_path.stat().st_size <= 1024 * 1024
            and not manifest_path.is_relative_to(root), 'Runtime manifest must be separate and bounded.')
    trusted_owners = {0}
    try:
        trusted_owners.add(pwd.getpwnam('claude').pw_uid)
    except KeyError:
        pass
    def immutable_for_app(path):
        info = path.lstat()
        require(info.st_uid in trusted_owners and info.st_uid != os.getuid()
                and not info.st_mode & 0o022 and not os.access(path, os.W_OK),
                'Application must not own or modify its runtime or manifest.')
    if not qualification:
        require(os.getuid() != 0, 'Document processing must not run as root.')
        immutable_for_app(root)
        immutable_for_app(manifest_path)
        # An immutable child can still be replaced through a writable ancestor.
        for ancestor in {*root.parents, *manifest_path.parents}:
            require(not os.access(ancestor, os.W_OK), 'Application can replace a runtime ancestor.')
    raw = manifest_path.read_bytes()
    require(len(expected_manifest_sha) == 64 and hashlib.sha256(raw).hexdigest() == expected_manifest_sha,
            'Runtime manifest does not match the trusted pin.')
    manifest = json.loads(raw)
    require(set(manifest) == {'format', 'runtime', 'executable', 'files'} and manifest['format'] == 1
            and manifest['runtime'] == 'dotnet8-self-contained-linux-x64'
            and manifest['executable'] in ('ProbeHost', 'WordHost')
            and isinstance(manifest['files'], dict) and 1 <= len(manifest['files']) <= 1000,
            'Unqualified runtime manifest.')
    actual, total = {}, 0
    for item in root.rglob('*'):
        info = item.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'Runtime contains a symlink.')
        if not qualification:
            immutable_for_app(item)
        if stat.S_ISDIR(info.st_mode):
            require(not info.st_mode & 0o022, 'Runtime directories cannot be group/world writable.')
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o022,
                'Runtime files must be regular and not group/world writable.')
        total += info.st_size
        require(total <= MAX_RUNTIME_BYTES, 'Runtime size exceeds qualification.')
        actual[str(item.relative_to(root))] = hashlib.sha256(item.read_bytes()).hexdigest()
    require(actual == manifest['files'], 'Published runtime bytes differ from the trusted manifest.')
    executable = root / manifest['executable']
    require(executable.is_file() and os.access(executable, os.X_OK), 'Pinned SDK entry point is not executable.')
    require(all((root / name).is_file() for name in ('libcoreclr.so', 'System.Private.CoreLib.dll')),
            'Require a self-contained runtime, not the shared full SDK.')
    return executable


def clean_environment(workspace):
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC', 'TMPDIR': str(workspace),
            'DOTNET_EnableDiagnostics': '0', 'COMPlus_EnableDiagnostics': '0',
            'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT': '1', 'DOTNET_GCHeapHardLimit': '10000000',
            'DOTNET_GCHeapCount': '1', 'DOTNET_gcServer': '0', 'DOTNET_PROCESSOR_COUNT': '2',
            'DOTNET_TieredCompilation': '0', 'DOTNET_CLI_TELEMETRY_OPTOUT': '1'}


def isolate(workspace, runtime_root):
    require(sys.platform == 'linux' and platform.machine() == 'x86_64', 'Only qualified Linux x86-64 is supported.')
    require(len(os.listdir('/proc/self/task')) == 1, 'Apply native boundary before any CLR or other thread starts.')
    workspace, runtime_root = Path(workspace).absolute(), Path(runtime_root).absolute()
    for path in (workspace, runtime_root):
        require(path.resolve() == path and path.is_dir(), 'Boundary roots must be real directories.')
    require(not workspace.is_relative_to(runtime_root) and not runtime_root.is_relative_to(workspace),
            'Runtime and untrusted workspace must be separate trees.')
    info = workspace.stat()
    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, 'Workspace must be private and owned.')
    resource.setrlimit(resource.RLIMIT_AS, (CAP_AS, CAP_AS))
    # Qualified independently with the real CLR probe. This bounds ordinary
    # native data allocations without rejecting its ~3.68 GiB VA reservations.
    resource.setrlimit(resource.RLIMIT_DATA, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (96, 96))
    resource.setrlimit(resource.RLIMIT_STACK, (8 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    seccomp = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    require(libc.prctl(38, 1, 0, 0, 0) == 0, 'No-new-privileges setup failed.')
    require(libc.syscall(444, 0, 0, 1) >= 3, 'Landlock ABI3 or newer is required.')

    class Ruleset(ctypes.Structure):
        _fields_ = [('handled_access_fs', ctypes.c_uint64)]

    class PathBeneath(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int)]

    ruleset = Ruleset(FS_RIGHTS)
    descriptor = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    require(descriptor >= 0, 'Landlock ruleset setup failed.')
    # No application tree, home, broad /etc, /proc tree or full .NET SDK grant.
    grants = [(workspace, FS_RIGHTS & ~EXECUTE), (runtime_root, READ_FILE | READ_DIR | EXECUTE)]
    for candidate in ('/usr/lib/x86_64-linux-gnu', '/lib/x86_64-linux-gnu'):
        path = Path(candidate).resolve()
        if path.is_dir() and all(path != old for old, _ in grants):
            grants.append((path, READ_FILE | READ_DIR))
    # The ELF interpreter itself requires execute; native libraries require read.
    interpreter = Path('/lib64/ld-linux-x86-64.so.2').resolve()
    grants.append((interpreter, READ_FILE | EXECUTE))
    metadata = ('/etc/ld.so.cache', '/etc/os-release', '/etc/localtime', '/dev/urandom', '/dev/null',
                '/proc/self/status', '/proc/self/stat', '/proc/self/maps', '/proc/self/cgroup', '/proc/meminfo',
                '/sys/devices/system/cpu/online', '/sys/devices/system/cpu/possible',
                '/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.high')
    for name in metadata:
        path = Path(name)
        if path.exists() and path.is_file():
            grants.append((path.resolve(), READ_FILE))
    try:
        for path, rights in grants:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathBeneath(rights, fd)
                require(libc.syscall(445, descriptor, 1, ctypes.byref(rule), 0) == 0,
                        'Landlock path setup failed.')
            finally:
                os.close(fd)
        require(libc.syscall(446, descriptor, 0) == 0, 'Landlock enforcement failed.')
    finally:
        os.close(descriptor)
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                              ctypes.c_uint, ctypes.c_void_p]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]

    class Compare(ctypes.Structure):
        _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_uint), ('a', ctypes.c_uint64), ('b', ctypes.c_uint64)]

    context = seccomp.seccomp_init(0x7FFF0000)
    require(bool(context), 'Seccomp context setup failed.')
    def rule(name, error=errno.EPERM, comparison=None):
        number = seccomp.seccomp_syscall_resolve_name(name.encode())
        require(number >= 0, 'Required syscall identity unavailable.')
        result = seccomp.seccomp_rule_add_array(context, 0x00050000 | error, number,
                                               0 if comparison is None else 1,
                                               None if comparison is None else ctypes.byref(comparison))
        require(result == 0, 'Seccomp rule setup failed.')
    try:
        for name in ('socket', 'socketpair', 'connect', 'bind', 'listen', 'accept', 'accept4',
                     'sendto', 'sendmsg', 'recvfrom', 'recvmsg', 'fork', 'vfork', 'ptrace',
                     'process_vm_readv', 'process_vm_writev', 'mount', 'umount2', 'unshare', 'setns',
                     'bpf', 'io_uring_setup', 'io_uring_enter', 'io_uring_register', 'open_by_handle_at',
                     'name_to_handle_at', 'userfaultfd', 'keyctl', 'add_key', 'request_key', 'kill', 'tkill',
                     'pidfd_open', 'pidfd_getfd', 'pidfd_send_signal', 'personality',
                     'shmget', 'shmat', 'shmctl', 'semget', 'semop', 'semtimedop', 'semctl',
                     'msgget', 'msgsnd', 'msgrcv', 'msgctl', 'mq_open', 'mq_timedsend', 'mq_timedreceive'):
            rule(name)
        rule('clone3', errno.ENOSYS)  # libc may safely fall back to qualified clone.
        for bit in range(64):
            value = 1 << bit
            if value & CLONE_REQUIRED:
                rule('clone', comparison=Compare(0, 7, value, 0))
            elif not value & CLONE_ALLOWED:
                rule('clone', comparison=Compare(0, 7, value, value))
        # CLR suspension signals may target only this process's own threads.
        for name in ('tgkill', 'rt_tgsigqueueinfo'):
            rule(name, comparison=Compare(0, 1, os.getpid(), 0))
        rule('rt_sigqueueinfo')
        rule('prlimit64', comparison=Compare(0, 1, 0, 0))  # Current-process pid0 only.
        require(seccomp.seccomp_load(context) == 0, 'Seccomp enforcement failed.')
    finally:
        seccomp.seccomp_release(context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--qualification', action='store_true', help='Explicit operator fixture mode; managed services refuse it.')
    parser.add_argument('--outside-canary', help='Existing synthetic qualification control outside workspace.')
    parser.add_argument('--canary-sha')
    args = parser.parse_args()
    workspace, runtime = Path(args.workspace).absolute(), Path(args.runtime).absolute()
    require(not args.qualification or (os.getenv('QUILLMD_WORD_QUALIFICATION') == '1'
            and os.getenv('QUILLMD_ENV_MANAGED') != '1'), 'Managed service cannot use operator qualification mode.')
    executable = verified_runtime(runtime, args.manifest, args.manifest_sha, qualification=args.qualification)
    arguments = [str(executable), str(workspace)]
    if executable.name == 'ProbeHost':
        require(args.qualification and args.outside_canary and args.canary_sha,
                'Probe host requires explicit qualification and a synthetic outside control.')
        canary = Path(args.outside_canary).absolute()
        require(canary.resolve() == canary and canary.is_file()
                and not canary.is_relative_to(workspace)
                and not canary.is_relative_to(runtime) and canary.stat().st_size <= 4096
                and hashlib.sha256(canary.read_bytes()).hexdigest() == args.canary_sha,
                'Outside synthetic control must positively verify before isolation.')
        arguments.append(str(canary))
    else:
        require(executable.name == 'WordHost' and args.outside_canary is None and args.canary_sha is None,
                'Unexpected document host arguments.')
    environment = clean_environment(workspace)
    os.chdir(workspace)
    isolate(workspace, runtime)
    os.execve(executable, arguments, environment)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('SDK boundary refused or failed; no unsafe fallback or sensitive output.')
