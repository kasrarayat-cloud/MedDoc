"""Processing copies and old rows cleaned up (release 1, D3; FLOW-3 code part, AUTH-6, AUTH-9, SCALE-11).

    sweep_orphan_files(delete=False)   files under ORIGINALS_DIR that no row names and that are older than an hour:
                                       counted (a dry run), or removed with ``delete``. Only SourceFile.storage_name and
                                       CodingRound.view_pdf_storage_name name files (the converted PDF a Word document's
                                       viewer shows is a named file and always kept). Counts only, never a name.
    run_daily()                        the daily maintenance: the session store's links whose session is gone or expired
                                       removed (studio.session_store; refutation round 1, avail-0: the links the revision
                                       before release 1 or the installer leave when they delete sessions), expired
                                       sessions cleared (clearsessions), RateWindow rows
                                       older than a day removed, sign-in names that match no account replaced by their
                                       keyed hash after 30 days (B1; the row stays), the orphan sweep (deleting), stale
                                       conversion folders removed, and LoginAttempt rows older than the retention
                                       removed (OWNER DECISION D25: six years, so in practice none). One SecurityEvent
                                       maintenance.daily holds the counts, and the names of any step that failed: the
                                       links and the expired sessions - sign-in state, not records - go first, each
                                       step committed on its own (refutation round 3: a sign-in never waits for the
                                       run); the other rows go in one transaction with the record, and the files once
                                       it has committed, so a record that cannot be written leaves every record in
                                       place (refutation round 2); one more, maintenance.daily_files_removed, then
                                       holds what the files' removal did.
    verify_originals()                 the integrity check (164.312(c)(1)): a sample of stored originals and converted
                                       PDFs read again and their sha256 checked; each mismatch, missing or unreadable
                                       file writes a SecurityEvent storage.original_mismatch (ids only), and the run one
                                       maintenance.originals_verified with its counts. Alerting is new-server work.
    tick(state)                        what the worker's main thread runs on its sweep (studio.jobs.work): every hour,
                                       stale conversion folders; then, under a Postgres advisory lock so one process
                                       does it, the daily maintenance once a day and verify_originals once a week (each
                                       due when its SecurityEvent is older than its period, so a restart does not run it
                                       again); a due run that failed is tried again DUE_RETRY_SECONDS later.

Every value below is a constant of the release, like the settings' own figures (cptstudio/settings.py is the
foundation lane's file, so D3's figures live here). Ids, counts and fixed words only in every record (studio/audit.py).
"""
from __future__ import annotations

import logging
import math
import time
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import connection, transaction
from django.db.models import Exists, F, OuterRef
from django.utils import timezone

from . import jobs, models, rate, security_events, session_store, storage

log = logging.getLogger(__name__)

ORPHAN_MIN_AGE_SECONDS = 60 * 60  # a file no row names is an orphan only once it is this old (its upload has ended)
RATE_WINDOW_MAX_AGE = timedelta(days=1)
SIGNIN_NAME_HASH_AFTER = timedelta(days=30)  # B1 item 7 (AUTH-9)
SIGNIN_NAMES_PER_RUN = 10_000  # distinct names hashed in one run, so one run stays bounded after a flood
LOGIN_ATTEMPT_RETENTION = timedelta(days=6 * 365 + 2)  # OWNER DECISION D25, recommended answer: kept six years
STALE_WORK_DIR_SECONDS = 60 * 60  # far above a conversion's own limit (fable.document.CONVERT_SECONDS)
HOURLY_SECONDS = 60 * 60
DUE_RETRY_SECONDS = 60 * 60  # a due run that failed (its record could not be written) waits this long, not one tick
DAILY_EVERY = timedelta(days=1)
WEEKLY_EVERY = timedelta(days=7)
VERIFY_SAMPLE = 200  # stored originals read again per weekly check, and as many converted PDFs
# 'CPTMNT': one session lock for the maintenance, apart from jobs.PROVIDER_LOCK_KEY's slots (0x435054535455 + n)
LOCK_KEY = 0x4350544D4E54
HASHED_NAME_PREFIX = 'hash:'  # no username can hold ':' (Django's username validator), so a hashed name is never one
DAILY_EVENT = 'maintenance.daily'
REMOVED_EVENT = 'maintenance.daily_files_removed'  # what the daily run removed once its record committed (run_daily)
VERIFIED_EVENT = 'maintenance.originals_verified'
MISMATCH_EVENT = 'storage.original_mismatch'
SWEPT_EVENT = 'maintenance.orphans_swept'
SWEEP_REMOVED_EVENT = 'maintenance.orphans_removed'  # what the sweep command removed once its record committed
MISMATCH, MISSING, UNREADABLE = 'mismatch', 'missing', 'unreadable'


# --- the orphan sweep -----------------------------------------------------------------------------------------------------

def named_files() -> set:
    """Every storage name a row names: the originals (SourceFile.storage_name) and the converted PDFs a Word document's
    viewer shows (CodingRound.view_pdf_storage_name)."""
    names = set(models.SourceFile.objects.values_list('storage_name', flat=True))
    names.update(models.CodingRound.objects.filter(view_pdf_storage_name__isnull=False)
                 .exclude(view_pdf_storage_name='').values_list('view_pdf_storage_name', flat=True))
    return names


def _is_uuid(text) -> bool:
    return storage._is_uuid(text)


def sweep_orphan_files(*, delete=False, now=None, min_age_seconds=ORPHAN_MIN_AGE_SECONDS) -> dict:
    """Count - or with ``delete`` remove - the files under ORIGINALS_DIR that no row names and that were last changed at
    least ``min_age_seconds`` ago. A young file is kept (its upload's transaction may still be open). Anything that is not
    a regular file in a practice's folder is counted as unexpected and never touched. Counts only."""
    counts, orphans = scan_orphan_files(now=now, min_age_seconds=min_age_seconds)
    if delete:
        counts.update(remove_orphan_files(orphans))
    return counts


def scan_orphan_files(*, now=None, min_age_seconds=ORPHAN_MIN_AGE_SECONDS):
    """The orphan sweep's dry run: (its counts, the storage names of the orphans it found - never logged or recorded)."""
    counts = {'folders': 0, 'files': 0, 'named': 0, 'orphans': 0, 'young': 0, 'deleted': 0, 'unexpected': 0,
              'failed': 0}
    cutoff = (now or timezone.now()).timestamp() - min_age_seconds
    named = named_files()  # read before the folders are listed: a file named after this read is a young one
    root, orphans = storage.root_path(), []
    for folder_name, kind in storage.folder_entries(root):
        if kind != storage.FOLDER or not _is_uuid(folder_name):
            counts['unexpected'] += 1
            continue
        counts['folders'] += 1
        folder = root / folder_name
        for name, entry_kind in storage.folder_entries(folder):
            if entry_kind != storage.FILE:
                counts['unexpected'] += 1
                continue
            counts['files'] += 1
            storage_name = f'{folder_name}/{name}'
            if storage_name in named:
                counts['named'] += 1
                continue
            try:
                changed = (folder / name).lstat().st_mtime
            except FileNotFoundError:
                continue
            if changed > cutoff:
                counts['young'] += 1
                continue
            counts['orphans'] += 1
            orphans.append(storage_name)
    return counts, orphans


def remove_orphan_files(orphans) -> dict:
    """Remove the orphans a scan found (scan_orphan_files), each folder synced once a file of it went; one that no
    longer is an orphan - a row names it now - is kept. {'deleted', 'failed'}."""
    counts, named, removed = {'deleted': 0, 'failed': 0}, named_files(), set()
    for storage_name in orphans:
        if storage_name in named:
            continue
        try:
            if storage.delete_stored(storage_name):
                counts['deleted'] += 1
                removed.add(storage_name.split('/', 1)[0])
        except (OSError, storage.StoreRefused) as exc:
            counts['failed'] += 1
            log.error('an orphan file could not be removed (%s)', type(exc).__name__)
    root = storage.root_path()
    for folder_name in sorted(removed):
        storage.sync_folder(root / folder_name)
    return counts


def remove_swept_orphans(orphans, *, swept) -> dict:
    """The sweep command's removal (sweep_orphan_files --delete), once its SWEPT_EVENT record ``swept`` - what the scan
    found, recorded first, so a record the database refuses removes nothing (refutation round 2, records-2) - committed:
    the orphans removed (remove_orphan_files), then what that did in one more SecurityEvent, SWEEP_REMOVED_EVENT, naming
    the sweep's record (swept: its id) - sweep_deleted and sweep_failed, and in failed the removal's name when it raised
    (logged by type, and raised again once recorded) - as run_daily writes REMOVED_EVENT (refutation round 3,
    disposal-3): after the removal, outside the first record's transaction; one that cannot be written is logged by
    type and never raised, and undoes nothing. Counts only. {'deleted', 'failed'}."""
    removed, failed, error = {}, [], None
    try:
        removed = remove_orphan_files(orphans)
    except Exception as exc:  # noqa: BLE001 - recorded below, then raised again
        log.error("the orphan sweep's removal failed (%s)", type(exc).__name__)
        failed, error = ['orphan_sweep'], exc
    try:
        security_events.record(SWEEP_REMOVED_EVENT, swept=swept.pk,
                               **{f'sweep_{key}': value for key, value in removed.items()}, failed=failed)
    except Exception as exc:  # noqa: BLE001 - the sweep's record stands, and what went stays gone (see above)
        log.error("the record of the orphan sweep's removed files could not be written (%s)", type(exc).__name__)
    if error is not None:
        raise error
    return removed


# --- old rows ---------------------------------------------------------------------------------------------------------

def hashed_signin_name(username) -> str:
    """A sign-in name as kept once it is replaced: HASHED_NAME_PREFIX and its keyed hash - the key B1's throttle counts the
    name by (rate.key_hash of 'signin-user:' and the casefolded name) - so the row stays countable and never holds the
    name."""
    return HASHED_NAME_PREFIX + rate.key_hash('signin-user:' + str(username).casefold())


def hash_unmatched_signin_names(now=None, *, limit=SIGNIN_NAMES_PER_RUN) -> int:
    """Replace, on sign-in rows older than SIGNIN_NAME_HASH_AFTER, every typed name that matches no account (ignoring
    case) by its keyed hash (B1 item 7; AUTH-9): what someone typed into the wrong box - an e-mail address, a password - is
    not kept. The rows stay. A name that matches an account is kept. The number of rows changed."""
    cutoff = (now or timezone.now()) - SIGNIN_NAME_HASH_AFTER
    names = list(models.LoginAttempt.objects.filter(created_at__lt=cutoff)
                 .exclude(username__startswith=HASHED_NAME_PREFIX)
                 .annotate(known=Exists(models.User.objects.filter(username__iexact=OuterRef('username'))))
                 .filter(known=False).order_by().values_list('username', flat=True).distinct()[:limit])
    changed = 0
    for name in names:
        changed += models.LoginAttempt.objects.filter(username=name, created_at__lt=cutoff).update(
            username=hashed_signin_name(name))
    return changed


def prune_rate_windows(now=None) -> int:
    """Remove the RateWindow counters whose window started more than RATE_WINDOW_MAX_AGE ago (every limit's window is
    an hour at most)."""
    return models.RateWindow.objects.filter(window_start__lt=(now or timezone.now()) - RATE_WINDOW_MAX_AGE).delete()[0]


def prune_login_attempts(now=None) -> int:
    """Remove the sign-in rows older than LOGIN_ATTEMPT_RETENTION (OWNER DECISION D25; recommended six years)."""
    return models.LoginAttempt.objects.filter(created_at__lt=(now or timezone.now()) - LOGIN_ATTEMPT_RETENTION).delete()[0]


def clear_expired_sessions(now=None) -> int:
    """Django's clearsessions; the number of expired sessions it found."""
    expired = Session.objects.filter(expire_date__lt=now or timezone.now()).count()
    call_command('clearsessions')
    return expired


# --- the daily run and the weekly check -----------------------------------------------------------------------------------

def run_daily(now=None) -> dict:
    """The daily maintenance (module docstring): every step runs even when another failed; one SecurityEvent
    maintenance.daily holds every count and the names of the steps that failed (their errors are logged by type).

    Sign-in state first (refutation round 3, disposal-2, regression-0 and locks-2): the session store's dead links and
    the expired sessions - sign-in state, not records (studio.sessions) - are removed before the recorded transaction
    begins, each step in a short transaction of its own, so no link or session it removes stays locked while the
    recorded steps run (a sign-in's cap and the end of an account's sessions delete the same rows: they waited for the
    whole run's commit). Their counts, or their names when they failed, go in the run's record; a record that cannot be
    written leaves them removed.

    What it deletes of the records and its record commit together, or neither does (refutation round 2, records-2): the
    rows it removes or rewrites - and the orphan sweep's dry run - in one transaction with that SecurityEvent, each step
    in a savepoint of its own, so a failing step rolls back alone; a record that cannot be written rolls every one of
    them back. What cannot be rolled back waits for that commit: the orphans the scan counted (sweep_orphans) are removed
    once the record has committed, and so are the stale conversion folders (which the worker's tick removes every hour
    besides). What they removed and what failed - sweep_deleted, sweep_failed, work_dirs_removed and the steps' names -
    then go in one more SecurityEvent, REMOVED_EVENT, naming the run's record (daily: its id), and in the answer. That
    record is written after the commit: one that cannot be written is logged by type and never raised, so it neither
    undoes the committed run nor makes the next tick run it again (the run is not due for a day)."""
    now = now or timezone.now()
    counts, failed, orphans, removed, removal_failed = {}, [], [], {}, []
    sign_in_state = (('session_links_pruned', lambda: session_store.prune_session_links(now)),
                     ('sessions_cleared', lambda: clear_expired_sessions(now)))
    for name, step in sign_in_state:
        try:
            with transaction.atomic():  # its own: committed before the next step, and before the recorded steps
                result = step()
        except Exception as exc:  # noqa: BLE001 - one step's failure never stops the others; logged by type
            log.error('the daily maintenance step %s failed (%s)', name, type(exc).__name__)
            failed.append(name)
            continue
        counts[name] = result  # once its transaction committed
    steps = (('rate_windows_pruned', lambda: prune_rate_windows(now)),
             ('signin_names_hashed', lambda: hash_unmatched_signin_names(now)),
             ('login_attempts_pruned', lambda: prune_login_attempts(now)),
             ('orphan_sweep', lambda: scan_orphan_files(now=now)))
    with transaction.atomic():
        for name, step in steps:
            try:
                with transaction.atomic():
                    result = step()
            except Exception as exc:  # noqa: BLE001 - one step's failure never stops the others; logged by type
                log.error('the daily maintenance step %s failed (%s)', name, type(exc).__name__)
                failed.append(name)
                continue
            if name == 'orphan_sweep':
                scanned, orphans = result
                counts.update({f'sweep_{key}': value for key, value in scanned.items()
                               if key not in ('deleted', 'failed')})
            else:
                counts[name] = result
        daily = security_events.record(DAILY_EVENT, **counts, failed=list(failed))
    later = (('orphan_sweep', lambda: {f'sweep_{key}': value for key, value in remove_orphan_files(orphans).items()}),
             ('work_dirs_removed', lambda: {'work_dirs_removed': jobs.remove_stale_work_dirs(
                 older_than=STALE_WORK_DIR_SECONDS)}))
    for name, step in later:
        try:
            removed.update(step())
        except Exception as exc:  # noqa: BLE001 - after the record: logged by type, named in the next one
            log.error('the daily maintenance step %s failed (%s)', name, type(exc).__name__)
            removal_failed.append(name)
    try:
        security_events.record(REMOVED_EVENT, daily=daily.pk, **removed, failed=removal_failed)
    except Exception as exc:  # noqa: BLE001 - the run is committed: logged by type, never raised (see above)
        log.error("the record of the daily maintenance's removed files could not be written (%s)", type(exc).__name__)
    return {**counts, **removed, 'failed': failed + removal_failed}


def _check(item, counts, kind):
    """Read one stored file again (storage.read_original checks its sha256); a problem writes its SecurityEvent."""
    counts['checked'] += 1
    try:
        storage.read_original(SimpleNamespace(storage_name=item['storage_name'], sha256=item['sha256']))
    except storage.OriginalCorrupted:
        problem = MISMATCH
    except FileNotFoundError:
        problem = MISSING
    except OSError:
        problem = UNREADABLE
    else:
        counts['ok'] += 1
        return
    counts[problem] += 1
    security_events.record(MISMATCH_EVENT, workspace_id=item['workspace_id'], problem=problem, kind=kind,
                           encounter=item['encounter_id'], record=item['pk'])


def verify_originals(*, sample=VERIFY_SAMPLE, every_file=False) -> dict:
    """Read again ``sample`` stored originals and as many converted PDFs, chosen at random (all of them with
    ``every_file``), and check each against its recorded sha256 (module docstring). One SecurityEvent per problem, and
    maintenance.originals_verified with the counts."""
    counts = {'checked': 0, 'ok': 0, MISMATCH: 0, MISSING: 0, UNREADABLE: 0}
    originals = models.SourceFile.objects.values('pk', 'storage_name', 'sha256', 'encounter_id',
                                                 workspace_id=F('encounter__workspace_id'))
    views = (models.CodingRound.objects.filter(view_pdf_storage_name__isnull=False).exclude(view_pdf_storage_name='')
             .values('pk', 'encounter_id', storage_name=F('view_pdf_storage_name'),
                     sha256=F('view_pdf_sha256'),
                     workspace_id=F('encounter__workspace_id')))
    if not every_file:
        originals, views = originals.order_by('?')[:sample], views.order_by('?')[:sample]
    for item in originals:
        _check(item, counts, 'original')
    seen = set()
    for item in views:  # several rounds can name one converted PDF: each file is read once
        if item['storage_name'] in seen:
            continue
        seen.add(item['storage_name'])
        _check(item, counts, 'converted')
    security_events.record(VERIFIED_EVENT, **counts)
    return counts


# --- the worker's tick ----------------------------------------------------------------------------------------------------

@contextmanager
def advisory_lock(key=LOCK_KEY):
    """The maintenance's session lock on this thread's database connection, taken without waiting: yields whether it
    is held (another process doing the maintenance holds it otherwise), and is released on the way out."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [key])
        held = bool(cursor.fetchone()[0])
    try:
        yield held
    finally:
        if held:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [key])


def _due(event, every, now) -> bool:
    return not models.SecurityEvent.objects.filter(event=event, created_at__gt=now - every).exists()


def run_due(now=None) -> dict:
    """The daily maintenance and the weekly check when each is due (its SecurityEvent is older than its period), under
    the advisory lock, which one process holds at a time; due-ness is read again inside the lock. What ran:
    {'daily': counts or None, 'verified': counts or None, 'locked': whether the lock was held}."""
    now = now or timezone.now()
    ran = {'daily': None, 'verified': None, 'locked': False}
    if not (_due(DAILY_EVENT, DAILY_EVERY, now) or _due(VERIFIED_EVENT, WEEKLY_EVERY, now)):
        return ran
    with advisory_lock() as held:
        ran['locked'] = held
        if not held:
            return ran
        if _due(DAILY_EVENT, DAILY_EVERY, now):
            ran['daily'] = run_daily(now)
        if _due(VERIFIED_EVENT, WEEKLY_EVERY, now):
            ran['verified'] = verify_originals()
    return ran


def tick(state, *, clock=time.monotonic, now=None) -> dict:
    """One maintenance tick of the worker's main thread (jobs.work, every jobs.STALE_SWEEP_SECONDS): once an hour (by
    ``state``, the worker's own memory) the stale conversion folders, then whatever run_due finds due. When run_due
    fails - a daily run whose record cannot be written rolled back and raised - it waits DUE_RETRY_SECONDS in this
    worker before it is tried again, never at every tick (refutation round 2, records-2: _due reads that very record);
    the failure is raised as before, and logged by jobs._maintain."""
    removed, moment = None, clock()
    if moment - state.get('hourly_at', -math.inf) >= HOURLY_SECONDS:
        removed = jobs.remove_stale_work_dirs(older_than=STALE_WORK_DIR_SECONDS)
        state['hourly_at'] = clock()
    if moment - state.get('due_failed_at', -math.inf) < DUE_RETRY_SECONDS:
        return {'work_dirs_removed': removed, 'daily': None, 'verified': None, 'locked': False}
    try:
        return {'work_dirs_removed': removed, **run_due(now)}
    except Exception:
        state['due_failed_at'] = clock()
        raise
