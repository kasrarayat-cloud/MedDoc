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
import sys
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / '.runtime'
LOCK_PATH = RUNTIME / '.activation-publication.lock'
DEFERRALS = RUNTIME / 'publication-deferrals.jsonl'
#: ⚠️ A `finally` DOES NOT RUN AFTER SIGKILL OR A HOST FAILURE. An activation that pauses the
#: publisher timer and is then killed would leave publication stopped indefinitely — which is the
#: "permanently disabled timer" outcome arriving by accident rather than by decision. The prior
#: state is therefore written DURABLY before the pause, and two independent paths restore it:
#:
#:   process kill  `quillmd-fresh-backup-alerts.timer` runs `ops/backup_alerts.py check` every
#:                 five minutes on its OWN timer and keeps running while the publisher is paused.
#:                 It calls `recover_publication()`, which restores and clears the marker.
#:   host failure  the publisher timer is ENABLED via `timers.target.wants` (verified, not
#:                 assumed), so a reboot re-arms it regardless of this marker.
#:
#: And the pause stays VISIBLE meanwhile: the ServiceHealth row keeps its own staleness check, so
#: a publisher that is not running reads as stale rather than as a green.
TIMER_STATE = RUNTIME / 'publication-timer-pause.json'
PUBLISHER_COMMAND = 'publish_operations_status'
PUBLISHER_TIMER = 'quillmd-fresh-operations-publisher.timer'
HELPER_PIN = RUNTIME / 'word-beta-recovery-20260917-final.json'
#: Recovery never interrupts a LIVE act: it acts only when exclusion is free, and only after this
#: grace period, so it cannot race an activation's own `finally`.
RECOVERY_GRACE_SECONDS = 60
#: A bounded wait. An activation that cannot drain publication in this long should refuse rather
#: than proceed unprotected — a silent unbounded wait is its own outage.
DRAIN_TIMEOUT_SECONDS = 120


def bind_runtime(runtime_dir):
    """Point every path at ONE runtime, explicitly.

    ⚠️ INSTALLED-STATE PATHS MUST NEVER FOLLOW THIS MODULE'S OWN LOCATION. On a first install the
    adapter imports this module from the TARGET WORKTREE, because the installed tree does not
    carry it yet. A `__file__`-relative runtime then puts the lock, the pause marker and the
    deferral records under the worktree, while the installed publisher looks in the installed
    runtime — two different locks, no exclusion, and an activation that LOOKS coordinated while
    coordinating nothing. That failure is silent: every check passes and the race is untouched.

    Normal in-process use needs no call: imported from the installed tree, the default is already
    correct. It is the cross-tree case that must be explicit.
    """
    global RUNTIME, LOCK_PATH, DEFERRALS, TIMER_STATE
    RUNTIME = Path(runtime_dir).resolve()
    LOCK_PATH = RUNTIME / '.activation-publication.lock'
    DEFERRALS = RUNTIME / 'publication-deferrals.jsonl'
    TIMER_STATE = RUNTIME / 'publication-timer-pause.json'
    return {'runtime': str(RUNTIME), 'lock': str(LOCK_PATH),
            'deferrals': str(DEFERRALS), 'timer_state': str(TIMER_STATE)}


def bound_runtime():
    return {'runtime': str(RUNTIME), 'lock': str(LOCK_PATH),
            'deferrals': str(DEFERRALS), 'timer_state': str(TIMER_STATE)}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _open_lock():
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    return os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)


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


def _own_process_tree(pid=None):
    """Self and every ancestor. ⚠️ A substring probe over `ps` matches the shell running it — the
    self-match that made a `pgrep` check lie earlier and then made a lock guard refuse itself."""
    pid = pid or os.getpid()
    seen = []
    while pid and pid > 1 and pid not in seen:
        seen.append(pid)
        try:
            pid = int(Path('/proc/%d/stat' % pid).read_text().split(') ', 1)[1].split()[1])
        except Exception:
            break
    return set(seen)


def publisher_processes(command=PUBLISHER_COMMAND):
    """Live publisher runs, excluding this process tree."""
    import subprocess
    mine = _own_process_tree()
    listing = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout
    found = []
    for line in listing.splitlines()[1:]:
        pid_text, _, args = line.strip().partition(' ')
        if pid_text.isdigit() and int(pid_text) not in mine and command in args:
            found.append(int(pid_text))
    return found


def drain_publisher(timeout=DRAIN_TIMEOUT_SECONDS, command=PUBLISHER_COMMAND):
    """Wait for an in-flight publication to finish, BEFORE the baseline snapshot.

    ⚠️ THIS IS WHY PAUSING THE TIMER IS NOT ENOUGH, AND WHY THE LOCK IS NOT ENOUGH EITHER. Pausing
    a timer does not stop a run already executing, and on a FIRST installation the running
    publisher predates the lock and never takes it — so acquiring the lock cannot drain what does
    not participate in it. Only waiting for the actual process to exit drains that case.
    """
    deadline = time.monotonic() + timeout
    while True:
        live = publisher_processes(command)
        if not live:
            return True
        if time.monotonic() >= deadline:
            raise TimeoutError('A publication was still in flight after %ds (pids %s); refusing '
                               'to snapshot a moving target.' % (timeout, live))
        time.sleep(0.2)


def _helper_systemctl(action, unit):
    """Exactly one unit, exactly two verbs, through the locally pinned helper image."""
    import json as _json
    import re
    import subprocess
    if action not in ('start', 'stop'):
        raise ValueError('Only start/stop is permitted.')
    if unit != PUBLISHER_TIMER:
        raise ValueError('Only the publisher timer may be coordinated here.')
    helper = _json.loads(HELPER_PIN.read_text())['helper_image']
    if not re.fullmatch('sha256:[a-f0-9]{64}', helper):
        raise ValueError('Helper image must be locally pinned.')
    code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\n"
    code += 'subprocess.run(' + repr(['systemctl', action, unit]) + ',check=True)\n'
    done = subprocess.run(['docker', 'run', '--rm', '-i', '--pull=never', '--network=none',
                           '--pid=host', '--mount', 'type=bind,src=/,dst=/host,readonly',
                           helper, 'python', '-B', '-'],
                          input=code, text=True, capture_output=True, timeout=200)
    if done.returncode != 0:
        raise RuntimeError('Publisher timer %s failed; helper stderr withheld.' % action)


def note_timer_paused(owner, prior_active):
    """Durable, written BEFORE the pause. Its existence is the debt; clearing it is the payment."""
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    state = {'owner': owner, 'unit': PUBLISHER_TIMER, 'prior_active': bool(prior_active),
             'paused_at': _now(), 'pid': os.getpid(), 'must_restore': True}
    tmp = TIMER_STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, sort_keys=True))
    os.chmod(tmp, 0o600)
    os.replace(tmp, TIMER_STATE)          # atomic: a torn marker is worse than none
    record('publisher_timer_paused', **state)
    return state


def clear_timer_pause(owner):
    with contextlib.suppress(FileNotFoundError):
        TIMER_STATE.unlink()
    record('publisher_timer_restored', owner=owner, unit=PUBLISHER_TIMER)


def pause_owed():
    """The durable debt, if any."""
    try:
        return json.loads(TIMER_STATE.read_text())
    except (OSError, ValueError):
        return None


def recover_publication(grace_seconds=RECOVERY_GRACE_SECONDS):
    """Restore publication after an activation died without running its `finally`.

    Safe to call on every tick of an unrelated timer: it is a no-op unless a pause is actually
    owed, and it refuses while an activation still holds exclusion so it can never interrupt a
    live act.
    """
    owed = pause_owed()
    if not owed or not owed.get('must_restore'):
        return {'recovered': False, 'reason': 'no_pause_owed'}
    descriptor = _open_lock()
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except BlockingIOError:
            return {'recovered': False, 'reason': 'activation_still_holds_exclusion'}
    finally:
        os.close(descriptor)
    age = time.time() - TIMER_STATE.stat().st_mtime
    if age < grace_seconds:
        return {'recovered': False, 'reason': 'within_grace', 'age_seconds': round(age, 1)}
    _helper_systemctl('start', PUBLISHER_TIMER)
    record('publication_recovered_after_interruption', owner=owed.get('owner'),
           unit=PUBLISHER_TIMER, paused_at=owed.get('paused_at'),
           age_seconds=round(age, 1), recovered_by='recover_publication')
    with contextlib.suppress(FileNotFoundError):
        TIMER_STATE.unlink()
    return {'recovered': True, 'owner': owed.get('owner'), 'age_seconds': round(age, 1)}


if __name__ == '__main__':
    print(json.dumps(recover_publication(), sort_keys=True))


#: ⚠️ THE BOOTSTRAP RECOVERY GAP, AND IT IS NOT THE SAME AS THE ORDINARY ONE.
#: `recover_publication()` is reached from `ops/backup_alerts.py`, which runs on its own timer —
#: but on a FIRST INSTALL the INSTALLED `backup_alerts.py` has no such call, because this act is
#: what installs it. So during first installation the ordinary recovery path DOES NOT EXIST: an
#: act that pauses the timer and is then killed would leave publication stopped with nothing
#: positioned to notice. Testing recovery with the future installed version proves nothing about
#: that window.
#:
#: A detached watchdog closes it. It is spawned from the TARGET source BEFORE the pause, survives
#: the parent (own session), refuses while exclusion is held, and exits as soon as the debt is
#: cleared or its bounded lifetime ends. A reboot remains the independent backstop for host
#: failure, since the timer is enabled.
WATCHDOG_TTL_SECONDS = 1800


def spawn_bootstrap_watchdog(owner, source_root, runtime_dir, ttl=WATCHDOG_TTL_SECONDS,
                             grace=RECOVERY_GRACE_SECONDS):
    import subprocess
    code = (
        'import sys, time\n'
        'sys.path.insert(0, %r)\n'
        'from ops import activation_exclusion as x\n'
        'x.bind_runtime(%r)\n'
        'deadline = time.time() + %d\n'
        'while time.time() < deadline:\n'
        '    if not x.pause_owed():\n'
        '        break\n'
        '    r = x.recover_publication(grace_seconds=%d)\n'
        '    if r.get("recovered"):\n'
        '        x.record("publication_recovered_by_bootstrap_watchdog", owner=%r)\n'
        '        break\n'
        '    time.sleep(5)\n'
    ) % (str(source_root), str(runtime_dir), int(ttl), int(grace), owner)
    process = subprocess.Popen([sys.executable, '-c', code], start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    record('bootstrap_watchdog_started', owner=owner, pid=process.pid, ttl_seconds=int(ttl),
           reason='the installed backup_alerts cannot recover a pause it does not know about')
    return process
