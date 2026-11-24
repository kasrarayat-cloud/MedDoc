"""Pure, CPU-bound stage work under a wall-clock and a memory limit (round 4).

Routing and context extraction are pure functions of the document text, and on adversarial input below the documented
limits they could hold the single worker for minutes or grow past its container memory (refutation round 4: 72-113 s
routes, a 1.5 GiB peak on a 20 KB paste). JOB_DEADLINE_SECONDS was configured and read nowhere.

``run_bounded`` forks, runs the function in the child (which inherits the already imported modules, so the cost is a
fork, not an interpreter start), and returns its pickled result. The parent kills the child at the deadline, and the
child's address space may grow only by ``memory_bytes`` beyond what it inherited. The child never touches the database:
only Django-free functions may be passed, and it leaves with ``os._exit`` so no parent cleanup (an inherited database
socket, atexit handlers) runs in it.

A child's work may start processes in sessions of their own - LibreOffice, for a Word conversion (release 1, E1) -
which killing the child does not kill. The work tells the parent each such process group on a second pipe before it
waits on it (``report_group``), and that it killed one itself (``group_ended``). The parent's ``finally`` kills the
child, reads every report the child wrote, then kills each group reported and not ended, timeout or not, and waits
briefly for it to be gone.
"""
import logging
import os
import pickle
import resource
import select
import signal
import time
import traceback

log = logging.getLogger(__name__)
READ_CHUNK = 1 << 20
# Built before any limit is set: the child's MemoryError handler runs while the failed call's frames still hold the
# address space, so pickling the answer there failed too and the child exited without one (round 7 bounded:6: the
# stage then said it "failed unexpectedly" instead of naming the memory limit).
MEMORY_PAYLOAD = pickle.dumps(('memory', None))
GROUP_GONE_SECONDS = 2  # how long the parent waits for a killed process group to be gone before it moves on
_GROUPS_FD = None  # in a bounded child only: the write end of the pipe of process-group reports


class Overrun(Exception):
    """The work did not finish within its limits; nothing it computed is used. ``reason`` is 'time' or 'memory'."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def report_group(pgid):
    """In a bounded child: process group ``pgid`` (a session the work started) is running. Call it before waiting on
    the group: the parent then kills it after the child, whatever the child does next. A no-op outside a child."""
    _tell(b'+', pgid)


def group_ended(pgid):
    """In a bounded child: the work killed process group ``pgid`` itself, so the parent need not (a no-op outside)."""
    _tell(b'-', pgid)


def _tell(sign, pgid):
    if _GROUPS_FD is not None:
        os.write(_GROUPS_FD, sign + str(int(pgid)).encode('ascii') + b'\n')


def _address_space_bytes():
    """The current virtual size of this process (the first field of /proc/self/statm, in pages)."""
    with open('/proc/self/statm', 'rb') as handle:
        return int(handle.read().split()[0]) * os.sysconf('SC_PAGE_SIZE')


def _child(write_fd, groups_fd, fn, args, memory_bytes):
    global _GROUPS_FD
    status = 0
    try:
        _GROUPS_FD = groups_fd
        limit = _address_space_bytes() + memory_bytes
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        try:
            payload = pickle.dumps(('ok', fn(*args)), protocol=pickle.HIGHEST_PROTOCOL)
        except MemoryError:
            payload = MEMORY_PAYLOAD  # nothing is allocated here; what the call held is released after the handler
        except BaseException:  # noqa: BLE001 — reported to the parent, which logs it
            try:
                payload = pickle.dumps(('error', traceback.format_exc()))
            except MemoryError:  # describing the failure needed the memory the failure left
                payload = MEMORY_PAYLOAD
        view = memoryview(payload)
        while view:
            view = view[os.write(write_fd, view):]
    except BaseException:  # noqa: BLE001 — the parent reads a short or empty pipe as a crash
        status = 1
    finally:
        os._exit(status)


def run_bounded(fn, *args, seconds, memory_bytes):
    """``fn(*args)`` in a forked child; raises Overrun past ``seconds`` or past ``memory_bytes`` of growth. Every
    process group the child reported (report_group) and did not end is killed before this returns or raises."""
    read_fd, write_fd = os.pipe()
    groups_read, groups_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        os.close(groups_read)
        _child(write_fd, groups_write, fn, args, memory_bytes)
    os.close(write_fd)
    os.close(groups_write)
    deadline = time.monotonic() + seconds
    chunks, reports, finished = [], bytearray(), False
    watched = [read_fd, groups_read]
    try:
        while not finished:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Overrun('time')
            ready, _, _ = select.select(watched, [], [], remaining)
            if groups_read in ready:
                report = os.read(groups_read, READ_CHUNK)
                reports += report
                if not report:
                    watched.remove(groups_read)
            if read_fd in ready:
                chunk = os.read(read_fd, READ_CHUNK)
                chunks.append(chunk)
                finished = not chunk
    finally:
        os.close(read_fd)
        try:
            os.kill(pid, signal.SIGKILL)  # a no-op on a child that already exited (not yet reaped)
        except ProcessLookupError:
            pass
        os.waitpid(pid, 0)
        reports += _drained(groups_read)  # the child is gone: everything it reported is in the pipe now
        os.close(groups_read)
        _kill_groups(reports)
    data = b''.join(chunks)
    if not data:
        raise RuntimeError('The bounded child exited without a result.')
    kind, value = pickle.loads(data)
    if kind == 'memory':
        raise Overrun('memory')
    if kind == 'error':
        log.error('bounded child failed:\n%s', value)
        raise RuntimeError('The bounded child failed; the error was logged.')
    return value


def _drained(fd) -> bytes:
    """What is left to read on ``fd``, without waiting (a process the child started could still hold its write end)."""
    os.set_blocking(fd, False)
    found = bytearray()
    try:
        while True:
            chunk = os.read(fd, READ_CHUNK)
            if not chunk:
                break
            found += chunk
    except BlockingIOError:
        pass
    return bytes(found)


def _kill_groups(reports):
    """Kills (SIGKILL) every process group ``reports`` names as started and not as ended, then waits up to
    GROUP_GONE_SECONDS for each to be gone. Never this process's own group, nor 0 or 1."""
    started, ended = [], set()
    for line in bytes(reports).split(b'\n'):
        if len(line) > 1 and line[:1] in (b'+', b'-') and line[1:].isdigit():
            (started.append if line[:1] == b'+' else ended.add)(int(line[1:]))
    own = os.getpgrp()
    for pgid in dict.fromkeys(started):
        if pgid in ended or pgid <= 1 or pgid == own:
            continue
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue
        gone_by = time.monotonic() + GROUP_GONE_SECONDS
        while time.monotonic() < gone_by:
            try:
                os.killpg(pgid, 0)
            except (ProcessLookupError, PermissionError):
                break
            time.sleep(0.01)
