"""One exclusion mechanism shared by activation and every publisher write path.

⚠️ WHY THIS EXISTS. The 2026-09-21 activation of `5b2576c5` stopped partway because
`quillmd-fresh-operations-publisher.timer` recomputed and published `core_servicehealth` at
05:23:08.077Z, inside the act's window 05:22:32Z–05:23:15Z. The `unchanged()` invariant refused,
correctly: it cannot distinguish a routine publish from corruption, and it must not try to.

⚠️ AND TIMING IS NOT A FIX. Starting just after an observed publish only shortens the window; it
does not exclude anything. Two writers with no shared mechanism race for as long as they both
exist, and a race you lose rarely is still a race you lose on the night it matters.

THE MECHANISM IS `flock`, deliberately:

  - it is held by the KERNEL against an open descriptor, so a holder that dies releases it. There
    is no stale-lock class here, which is exactly the failure the activation's own
    `.private-readiness-activation.lock` had to be reasoned about after the stopped act (its pid
    was dead and the file remained).
  - the activation takes it BLOCKING with a bounded wait, which IS the drain: acquisition cannot
    complete until an in-flight publication has finished and released.
  - the publisher takes it NON-BLOCKING, so it never wedges an act by waiting.

⚠️ AND A DEFERRAL IS RECORDED, NOT SWALLOWED. A publisher that quietly skipped its write would
make monitoring lie by omission: the row would age with no explanation. Every deferral appends a
record, the ServiceHealth row is left strictly alone so its own freshness check keeps working, and
NO health is asserted on a deferred tick. The truthful signal is "deferred at T because an
activation held exclusion", not a manufactured green.
"""
import contextlib
import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / '.runtime'
LOCK_PATH = RUNTIME / '.activation-publication.lock'
DEFERRALS = RUNTIME / 'publication-deferrals.jsonl'
#: A bounded wait. An activation that cannot drain publication in this long should refuse rather
#: than proceed unprotected — a silent unbounded wait is its own outage.
DRAIN_TIMEOUT_SECONDS = 120


def _now():
    return datetime.now(timezone.utc).isoformat()


def _open_lock():
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    return descriptor


def record(event, **fields):
    """Append a truthful, non-clinical record. Monitoring reads this; it must never be silent."""
    line = json.dumps({'at_utc': _now(), 'event': event, **fields}, sort_keys=True)
    with open(DEFERRALS, 'a', encoding='utf-8') as stream:
        stream.write(line + '\n')
    with contextlib.suppress(OSError):
        os.chmod(DEFERRALS, 0o600)
    return line


@contextlib.contextmanager
def hold(owner, timeout=DRAIN_TIMEOUT_SECONDS):
    """Activation side. Blocks until in-flight publication drains, then holds exclusively.

    Released in a finally, so a FAILED activation frees it exactly as a successful one does. That
    is not incidental: the stopped act left its own advisory lock file behind with a dead pid, and
    a repair mechanism that could do the same would be a worse bug than the one it fixes.
    """
    descriptor = _open_lock()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        'Publication did not drain within %ds; refusing to proceed unprotected.'
                        % timeout)
                time.sleep(0.2)
        os.ftruncate(descriptor, 0)
        os.write(descriptor, json.dumps({'owner': owner, 'pid': os.getpid(),
                                         'held_since': _now()}, sort_keys=True).encode())
        os.fsync(descriptor)
        record('exclusion_held', owner=owner, pid=os.getpid())
        yield
    finally:
        if acquired:
            record('exclusion_released', owner=owner, pid=os.getpid())
            with contextlib.suppress(OSError):
                os.ftruncate(descriptor, 0)
            with contextlib.suppress(OSError):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextlib.contextmanager
def attempt(owner):
    """Publisher side. Yields True when exclusion was taken, False when an activation holds it.

    ⚠️ THE CALLER MUST COMPUTE ITS OBSERVATIONS INSIDE THIS BLOCK. Collecting first and writing
    afterwards would publish a picture of the host from BEFORE the activation, which is a stale
    reading wearing a current timestamp — worse than no reading at all.
    """
    descriptor = _open_lock()
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            acquired = False
        yield acquired
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def holder():
    """Who holds it, for evidence. Absent or empty means nobody."""
    try:
        data = LOCK_PATH.read_bytes()
    except OSError:
        return None
    if not data.strip():
        return None
    with contextlib.suppress(ValueError):
        return json.loads(data)
    return None
