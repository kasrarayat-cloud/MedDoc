"""One worker per database, enforced by a session-level PostgreSQL advisory lock (blockers.txt item 3).

The settlement path's safety argument assumes ONE worker process runs `mark_stale` and `run_one` one after the other
(docs/rebuild/v1/residuals-assessment-20260929.md, "Remaining limits"). Nothing enforced it. A second worker (for example a
rebuilt host whose units started before the old instance stopped) swept a job the first worker was still sending to the
provider; the first worker then settled it anyway, or charged nothing under an administrator's "no provider cost
evidenced" (the two-worker probe). `manage.py worker` now takes this lock before it processes anything and keeps it for its
whole life; a second worker against the same database refuses to start.

WORKER_LOCK_KEY is one fixed bigint: the ASCII bytes of 'QUILLWK1' read big-endian. It is distinct from every other
advisory key the application takes (core.retention.LOCK_KEY and the bootstrap, role and terminology keys), which
core.tests.test_settlement_single_worker pins, and it is released by nothing but its own session.

The lock lives on a DEDICATED connection the worker opens for itself, never on Django's own connection: the worker recycles
that one (core.jobs.usable_connection closes it when it is unusable or older than CONN_MAX_AGE, and the RS-1 detection
depends on Django dropping it), and a session lock on it would be released silently. PostgreSQL releases a session-level
advisory lock when its session ends, so a worker that dies — killed, crashed, its connection cut — frees the lock with no
cleanup. The worker re-reads the lock before every pass of its loop and stops (non-zero) the moment it no longer holds it.

Limits, stated rather than solved:
- A host that disappears without closing its TCP connection keeps its session, and the lock, until the server notices the
  dead peer (TCP keepalive; the production server's settings are not established here). Stop the old host's units first.
- A session the server ends while the worker is inside a provider request frees the lock before the worker can notice; a
  second worker could then sweep that job. settle() refuses a job that is no longer running and the late receipt is held
  for an administrator (core.billing.SETTLEABLE_STATES, core.jobs.hold_late_receipt), so that race charges nothing and loses
  nothing.
- idle_session_timeout ends an idle session, and the lock session is idle while a provider request runs;
  idle_in_transaction_session_timeout ends a session idle inside a transaction, and the worker's own session is exactly
  that while an adoption runs in Python under the encounter's row lock (core.jobs.run_one), so a paid-for generation would
  be lost. The worker refuses to start while any of these (or lock_timeout, statement_timeout) is non-zero for its role
  (session_timeout_problems). It checks at start only: a login default changed later reaches the worker's next new
  session unchecked.
- An absent lock shows that no worker HOLDS it, not that no worker process runs: a worker whose lock session ended is
  still inside its request until its next pass, and a worker built before this lock never takes it. The status wording
  says only the first (status_rows); stopping the old units is what ends the second.
"""
import re

from django.db import DatabaseError, InterfaceError, connection, connections

WORKER_LOCK_KEY = int.from_bytes(b'QUILLWK1', 'big')
# pg_locks shows a bigint advisory key as classid (high 32 bits), objid (low 32 bits), objsubid 1.
_CLASSID, _OBJID = WORKER_LOCK_KEY >> 32, WORKER_LOCK_KEY & 0xFFFFFFFF
HOLDERS = ("SELECT pid FROM pg_locks WHERE locktype='advisory' AND granted AND objsubid=1 AND classid=%s AND objid=%s "
           "AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) ORDER BY pid")

#: Must be 0 for the worker's role. lock_timeout and statement_timeout turn an ordinary lock wait into a DatabaseError on the
#: settlement path (residuals-assessment, "Remaining limits"); idle_session_timeout ends the idle lock session;
#: idle_in_transaction_session_timeout ends the worker's session in the middle of an adoption, which holds its transaction
#: open while Python adopts the output (core.jobs.run_one).
TIMEOUT_SETTINGS = ('lock_timeout', 'statement_timeout', 'idle_session_timeout', 'idle_in_transaction_session_timeout')
_ZERO = re.compile(r"'?\s*0+(?:\.0*)?\s*(?:us|ms|s|min|h|d)?\s*'?", re.IGNORECASE)


class WorkerRefused(Exception):
    """Why the worker will not run. The message is fixed text plus database identifiers; it never carries a secret."""


class WorkerLockHeld(WorkerRefused):
    pass


class WorkerLockLost(WorkerRefused):
    pass


def lock_holders(cursor):
    cursor.execute(HOLDERS, [_CLASSID, _OBJID])
    return [pid for (pid,) in cursor.fetchall()]


class WorkerLock:
    """The held lock: its own connection, its backend pid and database. verify() before every pass; release() at exit."""

    def __init__(self, wrapper, pid, database):
        self.wrapper, self.pid, self.database = wrapper, pid, database

    def verify(self):
        try:
            with self.wrapper.cursor() as cursor:
                cursor.execute(HOLDERS.replace('ORDER BY pid', 'AND pid=pg_backend_pid()'), [_CLASSID, _OBJID])
                held = cursor.fetchone() is not None
        except (DatabaseError, InterfaceError):
            held = False
        if not held:
            raise WorkerLockLost(
                f'This worker no longer holds the single-worker lock on database {self.database!r} (its lock session '
                f'{self.pid} ended). It stops before processing anything more, so that at most one worker runs.')

    def release(self):
        try:
            with self.wrapper.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [WORKER_LOCK_KEY])
        except (DatabaseError, InterfaceError):
            pass  # A session that is gone holds nothing.
        finally:
            self.wrapper.close()


def acquire(alias='default'):
    """Take the lock on a new connection of `alias`, or raise WorkerLockHeld naming the session that holds it."""
    wrapper = connections.create_connection(alias)
    try:
        with wrapper.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s), pg_backend_pid(), current_database()', [WORKER_LOCK_KEY])
            taken, pid, database = cursor.fetchone()
            holders = [] if taken else lock_holders(cursor)
    except BaseException:
        wrapper.close()
        raise
    if not taken:
        wrapper.close()
        held_by = ', '.join(str(holder) for holder in holders) or 'a session that ended a moment ago'
        raise WorkerLockHeld(
            f'Another QuillMD worker holds the single-worker lock on database {database!r} (PostgreSQL advisory lock '
            f'{WORKER_LOCK_KEY}, held by database session {held_by}). Only one worker may run against a database, so this '
            'one stops without processing anything. Stop the other worker first (on a rebuilt host: the old instance\'s '
            'units).')
    return WorkerLock(wrapper, pid, database)


def _nonzero(value):
    return _ZERO.fullmatch(str(value).strip()) is None


def session_timeouts(cursor=None):
    """{setting: {'current': value or None, 'default': value or None}} for this connection's role and database.

    'current' is what this session runs with (pg_settings, in the setting's base unit); 'default' is the login default a NEW
    session of this role on this database would receive from ALTER ROLE / ALTER DATABASE (pg_db_role_setting, highest
    precedence first: role and database, role, database, all), which a long-lived session does not see. None: not set, or
    (for 'current') not a setting this server has.
    """
    def read(cursor):
        cursor.execute('SELECT name, setting FROM pg_settings WHERE name = ANY(%s)', [list(TIMEOUT_SETTINGS)])
        current = dict(cursor.fetchall())
        cursor.execute(
            "SELECT split_part(setting, '=', 1), substr(setting, strpos(setting, '=') + 1) FROM pg_db_role_setting s "
            "CROSS JOIN LATERAL unnest(s.setconfig) AS setting "
            "WHERE s.setdatabase IN (0, (SELECT oid FROM pg_database WHERE datname = current_database())) "
            "AND s.setrole IN (0, (SELECT oid FROM pg_roles WHERE rolname = session_user), "
            "(SELECT oid FROM pg_roles WHERE rolname = current_user)) "
            "AND split_part(setting, '=', 1) = ANY(%s) "
            "ORDER BY (s.setrole <> 0) DESC, (s.setdatabase <> 0) DESC", [list(TIMEOUT_SETTINGS)])
        defaults = {}
        for name, value in cursor.fetchall():
            defaults.setdefault(name, value)
        return {name: {'current': current.get(name), 'default': defaults.get(name)} for name in TIMEOUT_SETTINGS}
    if cursor is not None:
        return read(cursor)
    with connection.cursor() as own:
        return read(own)


def session_timeout_problems(timeouts=None):
    """Every non-zero timeout, as 'name=value (where)'. Empty when the role may run the worker."""
    timeouts = session_timeouts() if timeouts is None else timeouts
    problems = []
    for name in TIMEOUT_SETTINGS:
        row = timeouts[name]
        if row['current'] is not None and _nonzero(row['current']):
            problems.append(f"{name}={row['current']} (this session)")
        if row['default'] is not None and _nonzero(row['default']):
            problems.append(f"{name}={row['default']} (login default for this role or database)")
    return problems


def refusal(problems, role, database):
    """The WorkerRefused for non-zero timeouts: the worker's refusal and configuration_status's exit, one text."""
    names = ', '.join(TIMEOUT_SETTINGS[:-1]) + ' and ' + TIMEOUT_SETTINGS[-1]
    return WorkerRefused(
        f'{names} must be 0 for role {role!r} on database {database!r}; found {", ".join(problems)}. A lock or statement '
        'timeout turns an ordinary wait on the settlement path into an error, an idle-session timeout ends the '
        'single-worker lock session, and an idle-in-transaction timeout ends the worker\'s session in the middle of an '
        'adoption. The worker does not start.')


def refuse_nonzero_timeouts():
    problems = session_timeout_problems()
    if problems:
        with connection.cursor() as cursor:
            cursor.execute('SELECT session_user, current_database()')
            role, database = cursor.fetchone()
        raise refusal(problems, role, database)


def status_rows():
    """The worker section of `manage.py configuration_status` and of the services page, as data (one implementation)."""
    return worker_status()[0]


def worker_status():
    """(rows, refusal): the worker section's rows and the WorkerRefused its timeouts call for (None when all are 0), from
    ONE read of the database. A database that cannot be read gives an UNKNOWN row for the lock and for every timeout, and no
    refusal: the report degrades, as its other sections do, instead of ending in a traceback (L2:R2-2). The worker itself
    never starts on an unreadable database: its own check (refuse_nonzero_timeouts) raises."""
    try:
        with connection.cursor() as cursor:
            holders = lock_holders(cursor)
            cursor.execute('SELECT session_user, current_database()')
            role, database = cursor.fetchone()
            timeouts = session_timeouts(cursor)
    except (DatabaseError, InterfaceError) as exc:
        unknown = f'UNKNOWN: the database could not be read ({type(exc).__name__})'
        return ([{'name': 'single-worker lock', 'value': unknown, 'severity': 'error'}]
                + [{'name': name, 'value': unknown, 'severity': 'error'} for name in TIMEOUT_SETTINGS]), None
    rows = []
    # 'not held' says that no worker HOLDS the lock, never that no worker process runs (the module's limits).
    rows.append({'name': f'single-worker lock (advisory key {WORKER_LOCK_KEY})',
                 'value': (f'held by database session {", ".join(map(str, holders))}' if holders
                           else 'not held: no lock-holding worker'),
                 'severity': 'success' if len(holders) == 1 else 'warning'})
    for name in TIMEOUT_SETTINGS:
        row = timeouts[name]
        problems = session_timeout_problems({**{other: {'current': None, 'default': None} for other in TIMEOUT_SETTINGS},
                                             name: row})
        if row['current'] is None and row['default'] is None:
            value = 'not a setting of this server'
        else:
            value = f"{row['current'] if row['current'] is not None else '(none)'} for this session"
            value += f"; login default {row['default']}" if row['default'] is not None else '; no login default'
            value += f' (role {role})'
        rows.append({'name': name, 'value': ('NON-ZERO, the worker refuses to start: ' + value) if problems else value,
                     'severity': 'error' if problems else 'success'})
    problems = session_timeout_problems(timeouts)
    return rows, (refusal(problems, role, database) if problems else None)
