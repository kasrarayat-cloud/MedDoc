"""Linux Landlock + seccomp, applied before opening the untrusted document.

No fallback: unsupported kernels/configurations fail closed. There is no cloud
upload, network access, process creation, or visibility of application secrets.
"""

import ctypes
import errno
import os
from pathlib import Path
import resource
import sys


def isolate(workspace):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_FSIZE, (30 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise RuntimeError("no_new_privs unavailable")
    # All filesystem operations through ABI 3, plus truncate (ABI 3).
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError("Landlock ABI 3 or newer is required")
    rights = (1 << 15) - 1

    class Ruleset(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class PathBeneath(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]

    ruleset = Ruleset(rights)
    ruleset_fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if ruleset_fd < 0:
        raise RuntimeError("Landlock ruleset unavailable")
    try:
        # Imports are trusted code. Read access is confined to Python runtime/library
        # trees; the application tree and environment files are not visible.
        readonly = {Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}"}
        readonly.add(Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}")
        grants = [(Path(workspace), rights)] + [(p.resolve(), (1 << 2) | (1 << 3)) for p in readonly if p.exists()]
        for path, access in grants:
            descriptor = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathBeneath(access, descriptor)
                if libc.syscall(445, ruleset_fd, 1, ctypes.byref(rule), 0) != 0:
                    raise RuntimeError("Landlock path restriction failed")
            finally:
                os.close(descriptor)
        if libc.syscall(446, ruleset_fd, 0) != 0:
            raise RuntimeError("Landlock enforcement failed")
    finally:
        os.close(ruleset_fd)
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("seccomp initialization failed")
    try:
        denied = (
            "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
            "sendto", "sendmsg", "recvfrom", "recvmsg", "execve", "execveat",
            "fork", "vfork", "clone", "clone3", "ptrace", "process_vm_readv",
            "process_vm_writev", "mount", "umount2", "unshare", "setns", "bpf",
            "io_uring_setup", "io_uring_enter", "io_uring_register", "open_by_handle_at",
            "name_to_handle_at", "userfaultfd", "keyctl", "add_key", "request_key",
            "kill", "tkill", "tgkill", "pidfd_open", "pidfd_getfd", "pidfd_send_signal",
        )
        for name in denied:
            number = seccomp.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and seccomp.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0:
                raise RuntimeError("seccomp rule failed")
        if seccomp.seccomp_load(context) != 0:
            raise RuntimeError("seccomp enforcement failed")
    finally:
        seccomp.seccomp_release(context)
