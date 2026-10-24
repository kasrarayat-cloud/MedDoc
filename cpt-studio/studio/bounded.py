"""Pure, CPU-bound stage work under a wall-clock and a memory limit (round 4).

Routing and context extraction are pure functions of the document text, and on adversarial input below the documented
limits they could hold the single worker for minutes or grow past its container memory (refutation round 4: 72-113 s
routes, a 1.5 GiB peak on a 20 KB paste). JOB_DEADLINE_SECONDS was configured and read nowhere.

``run_bounded`` forks, runs the function in the child (which inherits the already imported modules, so the cost is a
fork, not an interpreter start), and returns its pickled result. The parent kills the child at the deadline, and the
child's address space may grow only by ``memory_bytes`` beyond what it inherited. The child never touches the database:
only Django-free functions may be passed, and it leaves with ``os._exit`` so no parent cleanup (an inherited database
socket, atexit handlers) runs in it.
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


class Overrun(Exception):
    """The work did not finish within its limits; nothing it computed is used. ``reason`` is 'time' or 'memory'."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _address_space_bytes():
    """The current virtual size of this process (the first field of /proc/self/statm, in pages)."""
    with open('/proc/self/statm', 'rb') as handle:
        return int(handle.read().split()[0]) * os.sysconf('SC_PAGE_SIZE')


def _child(write_fd, fn, args, memory_bytes):
    status = 0
    try:
        limit = _address_space_bytes() + memory_bytes
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        try:
            payload = pickle.dumps(('ok', fn(*args)), protocol=pickle.HIGHEST_PROTOCOL)
        except MemoryError:
            payload = pickle.dumps(('memory', None))
        except BaseException:  # noqa: BLE001 — reported to the parent, which logs it
            payload = pickle.dumps(('error', traceback.format_exc()))
        view = memoryview(payload)
        while view:
            view = view[os.write(write_fd, view):]
    except BaseException:  # noqa: BLE001 — the parent reads a short or empty pipe as a crash
        status = 1
    finally:
        os._exit(status)


def run_bounded(fn, *args, seconds, memory_bytes):
    """``fn(*args)`` in a forked child; raises Overrun past ``seconds`` or past ``memory_bytes`` of growth."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        _child(write_fd, fn, args, memory_bytes)
    os.close(write_fd)
    deadline = time.monotonic() + seconds
    chunks, finished = [], False
    try:
        while not finished:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Overrun('time')
            ready, _, _ = select.select([read_fd], [], [], remaining)
            if ready:
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
