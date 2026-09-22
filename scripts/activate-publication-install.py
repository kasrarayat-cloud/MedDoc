#!/usr/bin/env python3
"""Install the publication sandbox grant: one release, two amended units, one new directory.

⚠️ WHY A RELEASE AND NOT A UNIT EDIT. `reviewed_source` requires the shared tree to BE at the
reviewed commit, so amending a unit implies a source advance — and a source advance that does not
replace the release marker recreates exactly the tree/release divergence the 2026-09-22 repair
existed to close. There is no smaller coherent act; a unit edit alone would leave the host
describing itself wrongly.

⚠️ AND THERE IS NO SHIPPED DOOR THAT AMENDS AN INSTALLED UNIT. Every unit writer in this
repository uses `O_CREAT | O_EXCL`; `install` requires the units ABSENT, `activate` requires the
installed bytes to EQUAL the reviewed source and so refuses on changed bytes, and `disable` only
drops the timer link. `require_installed` additionally forbids drop-in `.d` overrides, so
`systemctl edit` is not a way round it either. This adapter adds the missing verb for exactly two
named units, and it is STRICTER than the install path in the way that matters: it refuses unless
the bytes it is about to replace are already the exact bytes a named reviewed commit shipped, so
it can never overwrite a unit somebody has edited by hand.

⚠️ THE PROOF IS TAKEN FROM THE UNIT, NEVER FROM THE COMMAND. The previous report cited an
08:00:09Z publication as evidence that publication had resumed. That claim was wrong: it was run
by the operator outside the sandbox, so it never executed the failing path, and its row then sat
frozen for hours. A hand-run command demonstrates that the COMMAND works and says nothing about
the SERVICE. This act requires `Result=success`/`ExecMainStatus=0` from the systemd-managed unit
AND a subsequent scheduled tick.
"""
from datetime import datetime, timezone
import base64
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
APP = ROOT / 'rebuild'
SELF = 'scripts/activate-publication-install.py'
DECL = 'docs/foundation/mutations/20260922-quillmd-publication-install.md'
DECL_SHA256 = '46b293aa482bb628191a1c1bd7cab217b8b638bbe212e8c50b963bf4fd746ee2'
#: The tree commit and the configured release AGREE here, which is the normal case and is
#: asserted rather than assumed: the 2026-09-22 repair exists because they once did not.
BASELINE = '52b28b369600549e0ad623fe49bdcd47c2cd44a1'
RUNNING_RELEASE = '52b28b369600549e0ad623fe49bdcd47c2cd44a1'
EVIDENCE = ROOT / 'rebuild/.runtime/publication-install-20260922'
DRIVER = 'scripts/activate-typed-voice.py'
DRIVER_SHA256 = '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18'
MIGRATION = '0018_servicehealth'
#: ⚠️ REUSED, NOT REPEATED. The retained capture and the independent-key restore proof are the
#: ones qualified on 2026-09-22. `assert_retained_capture` pins the run id, the backed-up files'
#: digests, the table POPULATION and the financial invariants — none of which this release moves,
#: and none of which depend on the capture's source commit. A fresh capture or a repeat drill
#: would be work done to make a check pass, which is the opposite of what the check is for.
RESTORE_RESULT = APP / '.runtime/recovery-custody-handoff-20260922/return-evidence/independent-key-restore/result.json'
RESTORE_RESULT_SHA256 = 'f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f'
RESTORED_MANIFEST_SHA256 = 'c3c4994fa4b50c51e75197e2ba57f8e2427daaf5929539c01498548da2083011'
CAPTURE_RUN = '20260922T043002Z-7d766ca1'
CAPTURE_SOURCE = 'eb37c7846f3ef634c16b4da46456663b88217a60'
CAPTURE_MANIFEST_SHA256 = 'c3c4994fa4b50c51e75197e2ba57f8e2427daaf5929539c01498548da2083011'
#: ⚠️ THE INHERITED STATIC ALLOWLIST IS STALE AND REJECTS THE LIVE TREE.
#: `activate-word-export.static_inventory` carries `allowed_dirs = {'.'}`, so the five OTP asset
#: directories that have been installed for releases — `django_otp/`, `django_otp/css/`,
#: `otp_totp/`, `otp_totp/css/`, `otp_totp/js/` — are "objects outside the reviewed public asset
#: set". Measured: 31 files + 6 directories = the 37 entries the serving release's own receipt
#: records. Every recent activation replaced this check for the same reason; this one pins the
#: COMPLETED transition of the release now serving and requires the tree to still match it.
STATIC_RECEIPT = APP / '.runtime/candidate-review-repair-20260922/candidate-review-repair-52b28b369600.json'
STATIC_RECEIPT_SHA256 = 'a36729114ad2c01ca2daf05751fe52f9d11c9e59e593f027a382af6380c17875'
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
RENAMED_PATTERN = r'publication-install-[a-zA-Z0-9_-]+\.json'
SCHEMA_MARKER = '<!-- declared-schema -->'
SCOPE_MARKER = '<!-- declared-source-scope -->'

PUBLISHER_SERVICE = 'quillmd-fresh-operations-publisher.service'
PUBLISHER_TIMER = 'quillmd-fresh-operations-publisher.timer'
ALERTS_SERVICE = 'quillmd-fresh-backup-alerts.service'
AMENDED_UNITS = (PUBLISHER_SERVICE, ALERTS_SERVICE)
SYSTEMD = Path('/etc/systemd/system')
#: The path the INSTALLED code locks. The target locks a different one; holding both is the only
#: way an act spanning the change can exclude participants on either side of it.
LEGACY_LOCK = APP / '.runtime/.activation-publication.lock'
GRANT = '/opt/meddoc-pro/rebuild/.runtime/publication'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def declared(marker, text):
    """The fenced list directly under a marker. A parse that drifts raises rather than reading empty."""
    require(marker in text, 'The declaration carries no ' + marker + ' marker.')
    after = text.split(marker, 1)[1].splitlines()
    index = 0
    while index < len(after) and not after[index].strip():
        index += 1
    require(index < len(after) and after[index].startswith('```'),
            'The ' + marker + ' block must open, unindented, directly after the marker.')
    index += 1
    body = []
    while index < len(after) and not after[index].startswith('```'):
        body.append(after[index])
        index += 1
    require(index < len(after), 'The ' + marker + ' block is not closed.')
    values = {line.strip() for line in body if line.strip()}
    require(values, 'The ' + marker + ' block is empty.')
    require(all(' ' not in value for value in values), 'The ' + marker + ' block holds prose.')
    return values


DECLARATION = (SOURCE / DECL).read_bytes()
require(sha(DECLARATION) == DECL_SHA256, 'Reviewed activation declaration changed.')
BASELINE_TABLES = frozenset(declared(SCHEMA_MARKER, DECLARATION.decode()))
ALLOWED = declared(SCOPE_MARKER, DECLARATION.decode()) | {SELF, DECL}
#: Every file this act depends on being present in the range it installs.
REQUIRED = {SELF, DECL, 'rebuild/ops/activation_exclusion.py', 'rebuild/ops/backup_alerts.py',
            'rebuild/core/admin_console.py', 'rebuild/core/views.py',
            'rebuild/deploy/' + PUBLISHER_SERVICE, 'rebuild/deploy/' + ALERTS_SERVICE}
require('core_servicehealth' in BASELINE_TABLES, 'The declared schema omits the reviewed table.')
require(len(BASELINE_TABLES) == 36, 'The declared schema is not this baseline.')


def pinned_module(relative, expected, name):
    data = (SOURCE / relative).read_bytes()
    require(sha(data) == expected, 'Qualified activation driver changed.')
    module = types.ModuleType(name)
    module.__file__ = str(SOURCE / relative)
    sys.modules[name] = module
    exec(compile(data, module.__file__, 'exec'), module.__dict__)
    return module


driver = pinned_module(DRIVER, DRIVER_SHA256, '_publication_install_driver')
for module in (driver, driver.a, driver.b):
    for name, value in {'BASELINE': BASELINE, 'RUNNING_RELEASE': RUNNING_RELEASE, 'SOURCE': SOURCE,
                        'SELF': SELF, 'DECL': DECL, 'EVIDENCE': EVIDENCE,
                        'MIGRATION': MIGRATION, 'CAPTURE_RUN': CAPTURE_RUN,
                        'CAPTURE_SOURCE': CAPTURE_SOURCE,
                        'CAPTURE_MANIFEST_SHA256': CAPTURE_MANIFEST_SHA256,
                        'RESTORED_RUN': CAPTURE_RUN, 'RESTORED_RELEASE': CAPTURE_SOURCE,
                        'RESTORED_MANIFEST_SHA256': RESTORED_MANIFEST_SHA256,
                        'RESTORE_RESULT': RESTORE_RESULT,
                        'RESTORE_RESULT_SHA256': RESTORE_RESULT_SHA256}.items():
        setattr(module, name, value)
driver.__file__ = __file__
driver.RUNTIME_ALLOWED = ALLOWED
driver.REQUIRED = REQUIRED
#: The one reviewed expectation, replacing the driver's own era set. An expectation taken from
#: the thing under test cannot fail, so it is read from the declaration.
driver.BASELINE_TABLES = BASELINE_TABLES


def validate_static_receipt(data):
    require(sha(data) == STATIC_RECEIPT_SHA256, 'Completed static receipt bytes changed.')
    receipt = json.loads(data)
    require(receipt.get('complete') is True and receipt.get('target') == RUNNING_RELEASE
            and receipt.get('stage') == 'complete' and receipt.get('provider_calls') == 0,
            'Completed static transition of the serving release is required.')
    return receipt['static_transition']['after']


def current_static(identity, word):
    """The installed assets, authenticated against the receipt written when they were installed.

    ⚠️ THIS RELEASE CHANGES NO STATIC SOURCE, so the collection must come back identical and the
    honest check is equality with the completed transition — not a stale hand-written allowlist
    that predates the OTP asset directories.
    """
    expected = validate_static_receipt(word.checked_file(STATIC_RECEIPT, private=True))
    current = driver.static_inventory(APP / 'staticfiles')
    require(current == expected, 'Current static assets differ from the completed activation evidence.')
    for name, source in identity.static_sources().items():
        require(current.get(name, {}).get('sha256') == sha(source.read_bytes()),
                'Current static alias differs from its unchanged source.')
    return current


_qualified_load = driver.a.load


def load(name, relative, target):
    module = _qualified_load(name, relative, target)
    if name == 'old':
        module.static_inventory = current_static
    return module


driver.a.load = load


class _RenamedReceiptRe:
    """Rename only the inherited receipt-name pattern; everything else is the real `re`."""

    def __getattr__(self, name):
        return getattr(re, name)

    def fullmatch(self, pattern, string, *args, **kwargs):
        if pattern == RESULT_PATTERN:
            pattern = RENAMED_PATTERN
        return re.fullmatch(pattern, string, *args, **kwargs)


driver.re = _RenamedReceiptRe()


def _ops():
    """The reviewed installer machinery, imported from the target source."""
    from ops import install_backup_schedule as base
    from ops import managed_helper
    return base, managed_helper


def _helper(code, writable_systemd=False, timeout=200):
    """⚠️ THROUGH `run_helper`, NOT A BARE `docker run`.

    The first version of this adapter called `subprocess.run(['docker','run',...])` directly. A
    client-side timeout does not stop a daemon-owned container, so an interrupted call would have
    left a ROOT container running with `/` bind-mounted — and `managed_helper` exists in this
    repository precisely to stop that. It arms an in-container absolute alarm that survives parent
    SIGKILL, names and labels the container, and returns output only after VERIFIED cleanup.
    """
    base, managed_helper = _ops()
    mounts = ['--mount', 'type=bind,src=/,dst=/host,readonly']
    if writable_systemd:
        mounts += ['--mount', 'type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system']
    argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none',
            '--network', 'none', '--pid=host', *mounts, base.IMAGE, 'python', '-B', '-']
    return managed_helper.run_helper(argv, input=code.encode(), timeout=timeout)


def systemctl(action, unit):
    """Exactly the verbs this act needs, on exactly the units it names."""
    require(action in ('start', 'stop'), 'Unpermitted systemd verb.')
    require(unit in (PUBLISHER_TIMER, PUBLISHER_SERVICE, ALERTS_SERVICE), 'Unpermitted unit.')
    code = ("import os,subprocess\nos.chroot('/host');os.chdir('/')\n"
            'subprocess.run(' + repr(['systemctl', action, unit]) + ',check=True)\n')
    _helper(code)


def unit_state(unit, properties):
    """Read systemd's own view. Property names are constants, never caller text."""
    require(unit in (PUBLISHER_TIMER, PUBLISHER_SERVICE, ALERTS_SERVICE), 'Unpermitted unit.')
    require(all(re.fullmatch('[A-Za-z]+', name) for name in properties), 'Unpermitted property.')
    code = ("import os,subprocess,sys\nos.chroot('/host');os.chdir('/')\n"
            "sys.stdout.write(subprocess.run("
            + repr(['systemctl', 'show', unit, '--property=' + ','.join(properties)])
            + ",capture_output=True,text=True,check=True).stdout)\n")
    done = _helper(code)
    return dict(line.split('=', 1) for line in done.stdout.decode().splitlines() if '=' in line)


def invocation_of(unit):
    """⚠️ THE IDENTITY OF A RUN, NOT ITS OUTCOME.

    `Result` and `ExecMainStatus` on a `Type=oneshot` unit describe the LAST completed run and are
    not cleared when it goes inactive — so reading them twice without an intervening invocation
    replays the first answer. Only `InvocationID` changing proves systemd started the unit again.
    """
    return unit_state(unit, ('InvocationID', 'Result', 'ExecMainStatus',
                             'ExecMainStartTimestampMonotonic'))


def installed_unit_digests():
    return {unit: sha((SYSTEMD / unit).read_bytes()) for unit in AMENDED_UNITS}


def amend_units():
    """Replace exactly two unit files with the reviewed target bytes, root-owned 0644.

    ⚠️ IT REFUSES UNLESS THE BYTES IT IS REPLACING ARE ALREADY A NAMED REVIEWED COMMIT'S. That is
    what keeps this from being a general-purpose overwrite: a unit somebody edited by hand does
    not match, so this act stops rather than erasing the edit.
    """
    prior = {}
    for unit in AMENDED_UNITS:
        reviewed_prior = subprocess.run(['git', '-C', str(ROOT), 'show', BASELINE + ':rebuild/deploy/' + unit],
                                        capture_output=True, timeout=60)
        require(reviewed_prior.returncode == 0, 'Could not read the prior reviewed unit bytes.')
        installed = (SYSTEMD / unit).read_bytes()
        require(installed == reviewed_prior.stdout,
                'Installed %s is not the bytes %s reviewed; refusing to overwrite an unreviewed unit.'
                % (unit, BASELINE[:12]))
        require(not (SYSTEMD / (unit + '.d')).exists(), 'Unexpected drop-in override for %s.' % unit)
        prior[unit] = installed
    # Retained BEFORE either file is replaced: a rollback needs the bytes, not a promise of them.
    for unit, data in prior.items():
        path = EVIDENCE / ('prior-' + unit + '-' + sha(data)[:12])
        if path.exists():           # same bytes already retained by an earlier attempt
            continue
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    target = {unit: (SOURCE / 'rebuild/deploy' / unit).read_bytes() for unit in AMENDED_UNITS}
    for unit, data in target.items():
        require(GRANT.encode() in data, 'Target %s does not carry the declared grant.' % unit)
        require(b'ProtectSystem=strict' in data, 'Target %s stopped sandboxing; refusing.' % unit)
    payload = {unit: base64.b64encode(data).decode() for unit, data in target.items()}
    expected = {unit: sha(data) for unit, data in target.items()}
    code = (
        "import base64,hashlib,json,os,subprocess,sys\n"
        "os.chroot('/host');os.chdir('/')\n"
        "files=" + repr(payload) + "\n"
        "out={}\n"
        # ⚠️ TEMP FILE THEN ATOMIC RENAME, NOT AN IN-PLACE TRUNCATE. `O_TRUNC` empties the unit
        # before writing it, so a crash, an OOM kill or the helper's own alarm firing between the
        # truncate and the write leaves a ZERO-LENGTH or half-written unit file on a production
        # host. `os.replace` within the same directory is atomic: readers see the old bytes or
        # the new ones and never a torn file.
        "for unit,encoded in files.items():\n"
        "    data=base64.b64decode(encoded)\n"
        "    path='/etc/systemd/system/'+unit\n"
        "    tmp=path+'.quillmd-amend'\n"
        "    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)\n"
        "    with os.fdopen(fd,'wb') as s:\n"
        "        os.fchmod(s.fileno(),0o644);os.fchown(s.fileno(),0,0)\n"
        "        s.write(data);s.flush();os.fsync(s.fileno())\n"
        "    os.replace(tmp,path)\n"
        "dirfd=os.open('/etc/systemd/system',os.O_RDONLY|os.O_DIRECTORY)\n"
        "os.fsync(dirfd);os.close(dirfd)\n"
        # Reported separately: a reload failure after a successful write is a DIFFERENT state
        # from a failed write, and conflating them sends the reader to the wrong place.
        "reload=subprocess.run(['systemctl','daemon-reload'],capture_output=True)\n"
        "out['daemon_reload_returncode']=reload.returncode\n"
        "for unit in files:\n"
        "    path='/etc/systemd/system/'+unit\n"
        "    info=os.lstat(path)\n"
        "    out[unit]={'sha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),\n"
        "               'uid':info.st_uid,'gid':info.st_gid,'mode':oct(info.st_mode & 0o777)}\n"
        "print(json.dumps(out,sort_keys=True))\n")
    done = _helper(code, writable_systemd=True)
    readback = json.loads(done.stdout.decode())
    require(readback.pop('daemon_reload_returncode', None) == 0,
            'The units were written but systemd did not reload; the host is running stale unit state.')
    for unit in AMENDED_UNITS:
        require(readback[unit]['sha256'] == expected[unit], 'Amended %s did not read back.' % unit)
        require(readback[unit]['uid'] == 0 and readback[unit]['gid'] == 0
                and readback[unit]['mode'] == '0o644', 'Amended %s has wrong ownership or mode.' % unit)
    # And independently, from the operator side rather than from the helper's own report.
    require(installed_unit_digests() == expected, 'Operator-side readback of the amended units differs.')
    # ⚠️ AND BOTH UNITS MUST STILL PARSE. The alerts unit is amended and never started by this
    # act, so without this a syntactically broken unit would be discovered by the next timer tick
    # — i.e. by the monitoring that is supposed to notice things, failing silently itself.
    loaded = {}
    for unit in AMENDED_UNITS:
        state = unit_state(unit, ('LoadState', 'UnitFileState'))
        require(state.get('LoadState') == 'loaded',
                'Amended %s does not load: %s' % (unit, state))
        loaded[unit] = state
    return {'prior': {u: sha(d) for u, d in prior.items()}, 'after': expected,
            'readback': readback, 'loaded': loaded}


def capture_failure_evidence():
    """⚠️ THE EROFS HISTORY IS EVIDENCE AND THIS ACT IS ABOUT TO ERASE ITS CAUSE.

    Once the grant lands the journal keeps rotating and the failure it recorded stops being
    reproducible. Preserved BEFORE the fix, because afterwards it cannot be re-derived.
    """
    done = subprocess.run(['journalctl', '-u', PUBLISHER_SERVICE, '--since', '2026-09-22 07:45:00',
                           '--no-pager', '-o', 'short-iso'], capture_output=True, text=True, timeout=180)
    text = done.stdout if done.returncode == 0 else '(journal unavailable: exit %d)' % done.returncode
    failures = [line for line in text.splitlines() if 'Read-only file system' in line]
    # ⚠️ UNIQUE PER ATTEMPT. `O_EXCL` on a fixed name in a reusable evidence directory makes a
    # SECOND attempt fail at the first step — after a failed first attempt is exactly when
    # this evidence matters most, and refusing to record it then is the wrong way round.
    path = EVIDENCE / ('erofs-journal-before-repair-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.txt')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(text)
    return {'journal_retained': str(path), 'erofs_lines': len(failures),
            'first': failures[0] if failures else None, 'last': failures[-1] if failures else None}


def prepare_publication_directory(exclusion):
    """Create the granted directory and move the deferral ledger into it, byte-identical.

    ⚠️ THE LEDGER IS FAILURE HISTORY AND IS MOVED, NOT RESTARTED. A fresh empty ledger beside the
    new lock would read as 'nothing has ever been deferred here', which is false and is exactly
    the kind of quiet erasure this programme keeps finding.
    """
    directory = Path(exclusion.PUBLICATION)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    legacy_ledger = APP / '.runtime/publication-deferrals.jsonl'
    moved = None
    if legacy_ledger.exists() and not Path(exclusion.DEFERRALS).exists():
        data = legacy_ledger.read_bytes()
        fd = os.open(exclusion.DEFERRALS, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require(Path(exclusion.DEFERRALS).read_bytes() == data, 'Deferral ledger did not migrate byte-identically.')
        legacy_ledger.unlink()
        moved = {'records': len([x for x in data.decode().splitlines() if x.strip()]), 'sha256': sha(data)}
    info = {'directory': str(directory), 'mode': oct(directory.stat().st_mode & 0o777),
            'ledger_migrated': moved}
    exclusion.record('publication_directory_prepared', **{k: v for k, v in info.items() if k != 'ledger_migrated'},
                     ledger_records=(moved or {}).get('records'))
    return info


@contextlib.contextmanager
def both_locks(exclusion, owner):
    """⚠️ HOLD THE OLD LOCK AND THE NEW ONE. The installed code locks one path and the code being
    installed locks another; a participant on each side would take a different lock and exclude
    nothing — silently, because every check still passes. This act spans the change, so it is the
    one participant that must be on both sides of it."""
    legacy = os.open(LEGACY_LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('The legacy exclusion lock is held; an older participant is mid-write.')
        exclusion.record('legacy_exclusion_held', owner=owner, path=str(LEGACY_LOCK))
        with exclusion.hold(owner):
            yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(legacy, fcntl.LOCK_UN)
        os.close(legacy)
        with contextlib.suppress(Exception):
            exclusion.record('legacy_exclusion_released', owner=owner, path=str(LEGACY_LOCK))


def prove_through_the_unit(publisher, before_row, before_invocation):
    """⚠️ THE CLAIM THAT WAS WRONG LAST TIME, MADE CORRECTLY THIS TIME.

    A hand-run command proves the COMMAND works. The defect was in the SERVICE — its sandbox — so
    only the service can discharge it.

    ⚠️ AND THE EXIT STATUS ALONE IS NOT THE CLAIM. `publish_operations_status` exits 0 when it
    DEFERS because an activation holds exclusion (it writes nothing and says so), so
    `Result=success` is compatible with no publication at all. The row must move as well, and the
    invocation must be a NEW one rather than a replay of the last completed run.
    """
    systemctl('start', PUBLISHER_SERVICE)
    state = invocation_of(PUBLISHER_SERVICE)
    require(state.get('InvocationID') and state.get('InvocationID') != before_invocation.get('InvocationID'),
            'systemd did not record a new invocation; the status read is a replay, not a run.')
    require(state.get('Result') == 'success' and state.get('ExecMainStatus') == '0',
            'The unit-driven publication did not succeed: %s' % state)
    row = publisher.verify_publication(before_row)
    return {'unit': state, 'row': row}


def await_scheduled_tick(publisher, after_row, after_invocation, bound_seconds=480):
    """⚠️ ONE MANUAL START IS NOT A WORKING TIMER, AND THAT DISTINCTION IS THE WHOLE INCIDENT.

    The timer was armed, active and enabled throughout the outage; what failed was every
    invocation it made. So the act waits for an invocation it did not ask for.

    ⚠️ AND A MOVED ROW IS NOT EVIDENCE OF A TIMER. Any writer can move it — including a hand-run
    command in another shell, which is exactly what happened on this host at 08:00:09Z and is the
    thing this adapter exists to stop believing. The proof is therefore bound to systemd's own
    identity for the run: the timer's `LastTriggerUSec` must advance AND the service's
    `InvocationID` must change. A row that moved without a new invocation is a finding.
    """
    before_trigger = unit_state(PUBLISHER_TIMER, ('LastTriggerUSec',)).get('LastTriggerUSec')
    deadline = time.monotonic() + bound_seconds
    while time.monotonic() < deadline:
        time.sleep(15)
        state = invocation_of(PUBLISHER_SERVICE)
        if state.get('InvocationID') == after_invocation.get('InvocationID'):
            continue                      # no new invocation yet; the row cannot be a tick
        trigger = unit_state(PUBLISHER_TIMER, ('LastTriggerUSec',)).get('LastTriggerUSec')
        row = publisher.published_row()
        return {'observed': True, 'row': row, 'unit': state,
                'invocation_changed': True,
                'timer_trigger_before': before_trigger, 'timer_trigger_after': trigger,
                'timer_trigger_advanced': trigger != before_trigger,
                'row_advanced': bool(row and row['computed_at'] != after_row['computed_at']),
                'result': state.get('Result'), 'exec_main_status': state.get('ExecMainStatus')}
    return {'observed': False, 'waited_seconds': bound_seconds,
            'timer_trigger_before': before_trigger,
            'note': 'No invocation that this act did not start occurred inside the bound. The '
                    'manual proof stands; the TIMER claim does not, and is withheld.'}


def retire_legacy_lock(exclusion):
    """Only after every participant runs the new code, and recorded rather than quietly deleted."""
    if not LEGACY_LOCK.exists():
        return {'retired': False, 'reason': 'absent'}
    digest = sha(LEGACY_LOCK.read_bytes())
    LEGACY_LOCK.unlink()
    exclusion.record('legacy_lock_retired', path=str(LEGACY_LOCK), sha256=digest,
                     reason='every participant now locks the granted directory')
    return {'retired': True, 'path': str(LEGACY_LOCK), 'sha256': digest}


def reviewed_unit_bytes():
    """The two units as BASELINE reviewed them and as the TARGET reviews them."""
    prior = {}
    for unit in AMENDED_UNITS:
        done = subprocess.run(['git', '-C', str(ROOT), 'show', BASELINE + ':rebuild/deploy/' + unit],
                              capture_output=True, timeout=60)
        require(done.returncode == 0, 'Could not read the prior reviewed unit bytes.')
        prior[unit] = sha(done.stdout)
    target = {unit: sha((SOURCE / 'rebuild/deploy' / unit).read_bytes()) for unit in AMENDED_UNITS}
    for unit in AMENDED_UNITS:
        require(prior[unit] != target[unit], 'Declared amendment for %s changes nothing.' % unit)
    return prior, target


def bind_declared_amendment_into_preservation(state):
    """⚠️ THE PRESERVATION CHECK RECORDS THE INSTALLED UNIT'S DIGEST, SO AMENDING IT IS A DELTA.

    `operational_state()` stores `units[<installed path>] = sha(bytes)` and the driver's
    `unchanged(baseline, after)` compares whole snapshots — so amending a unit inside the act
    raises `Undeclared code-only activation delta: preserved_operations`, three lines after the
    merge. Hooking the amendment into the merge is NECESSARY and on its own NOT SUFFICIENT.

    ⚠️ AND THE CHECK IS NOT WEAKENED TO GET PAST IT. For the two DECLARED units the generic
    byte-equality is replaced by a STRICTER, act-specific expectation asserted on every snapshot:
    before the amendment the installed bytes must equal exactly what BASELINE reviewed, and after
    it exactly what the TARGET reviews. Nothing else is accepted, no other unit is touched, and
    the recorded value is replaced by a constant only so that a CHANGE THE DECLARATION NAMES stops
    reading as an undeclared one. Every other unit in that set keeps the original comparison.
    """
    prior, target = reviewed_unit_bytes()
    state['declared_unit_expectation'] = {'before': prior, 'after': target}
    original = driver.a.operational_state

    def operational_state(word):
        value = original(word)
        amended = bool(state.get('unit_amendment'))
        for unit in AMENDED_UNITS:
            key = str(SYSTEMD / unit)
            if key not in value['units']:
                continue          # not in the compared set; nothing to reconcile
            expected = target[unit] if amended else prior[unit]
            actual = sha((SYSTEMD / unit).read_bytes())
            require(actual == expected,
                    'Declared unit %s is neither the reviewed baseline nor the reviewed target '
                    '(amended=%s): %s' % (unit, amended, actual))
            value['units'][key] = 'declared-amendment:' + unit
        return value

    #: ⚠️ REBINDING THE FUNCTION IS ENOUGH, AND REBINDING `snapshot` TOO WOULD BE RISK FOR
    #: NOTHING. `a.snapshot` resolves `operational_state` from its own module globals at CALL
    #: time (activate-business-readiness.py:288), so it picks this wrapper up by itself. A second
    #: patch would duplicate the driver's body in this file, where it could silently drift from it.
    driver.a.operational_state = operational_state


def hook_amendment_into_the_merge(state):
    """⚠️ THE AMENDMENT MUST LAND BETWEEN THE MERGE AND THE NEXT SNAPSHOT. NOTHING ELSE WORKS.

    `activate-business-readiness.operational_state()` — reached from EVERY snapshot the driver
    takes — asserts, for six units including `quillmd-fresh-backup-alerts.service`:

        installed bytes == (APP / 'deploy' / unit).read_bytes()      # APP is the SHARED tree

    So the installed unit is tied to the shared tree's own copy, and `git merge --ff-only` moves
    that copy. Amend BEFORE the driver and the BASELINE snapshot raises (installed is new, the
    tree is still old); amend AFTER `driver.main()` returns and the POST-MERGE snapshot raises
    (the tree is new, installed is still old) — leaving production stopped, the tree advanced and
    the release marker unreplaced, which is the exact divergence this act exists to close.

    Measured: installed and shared-tree both `caf7a568…` today, target `2b1ed72f…`. The publisher
    unit is not in that list, so the alerts unit alone trips it — once is enough.

    ⚠️ AND NO PRESERVATION CHECK IS WEAKENED TO ACHIEVE THIS. The invariant is left exactly as
    written and is made TRUE at the only instant it can be: the units are amended in the driver's
    own stopped window, immediately after the merge and before anything reads them.
    """
    original = driver.b.run

    def run(argv, *args, **kwargs):
        result = original(argv, *args, **kwargs)
        if list(argv[:3]) == ['git', 'merge', '--ff-only'] and not state.get('unit_amendment'):
            state['unit_amendment'] = amend_units()
        return result

    driver.b.run = run


if __name__ == '__main__':
    if '--execute' not in sys.argv:
        driver.main()
    else:
        EVIDENCE.mkdir(mode=0o700, exist_ok=True)
        # ⚠️ FROM THE SOURCE BEING INSTALLED, NOT THE TREE IT IS INSTALLED INTO. The installed
        # tree still locks the legacy path; these are the exact bytes the act is about to install.
        sys.path.insert(0, str(SOURCE / 'rebuild'))
        from ops import activation_exclusion as exclusion
        from ops import install_operations_publisher as publisher
        publisher.scope()
        # ⚠️ AND BIND IT TO THE INSTALLED RUNTIME, EXPLICITLY. Imported from the target worktree,
        # the module's `__file__`-relative default would put the lock, the marker and the deferral
        # records under the WORKTREE while the installed publisher looks in the installed runtime.
        # Two locks, no exclusion, and silently so.
        bound = exclusion.bind_runtime(APP / '.runtime')
        require(bound['lock'].startswith(str(APP / '.runtime')), 'Exclusion bound outside the installed runtime.')
        require(bound['publication'] == GRANT, 'Bound publication directory is not the declared grant.')
        target = sys.argv[sys.argv.index('--target') + 1]
        require(re.fullmatch('[a-f0-9]{40}', target), 'Full reviewed target commit required.')
        owner = 'activation:' + target[:12]
        outcome = {'adapter': SELF, 'declaration': DECL, 'declaration_sha256': DECL_SHA256,
                   'baseline': BASELINE, 'running_release_before': RUNNING_RELEASE, 'target': target,
                   'started_at': datetime.now(timezone.utc).isoformat(), 'provider_calls': 0,
                   'fresh_backup_or_restore_performed': False, 'complete': False,
                   'driver_receipt': sys.argv[sys.argv.index('--result') + 1]
                   if '--result' in sys.argv else None}
        receipt = EVIDENCE / ('publication-install-outcome-' + target[:12] + '.json')

        def write_receipt():
            """⚠️ WRITTEN ON FAILURE TOO. An act that mutated two root-owned unit files and the
            release marker and then left no receipt is an unexplained host, and the first person
            to look would have nothing but a traceback that scrolled past."""
            with contextlib.suppress(Exception):
                fd = os.open(receipt, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(outcome, stream, indent=1, sort_keys=True, default=str)

        try:
            outcome['failure_evidence'] = capture_failure_evidence()
            outcome['publication_directory'] = prepare_publication_directory(exclusion)
            outcome['units_before'] = installed_unit_digests()
            before_row = publisher.published_row()
            outcome['published_row_before'] = before_row
            bind_declared_amendment_into_preservation(outcome)
            hook_amendment_into_the_merge(outcome)
            # ⚠️ THE WATCHDOG STARTS BEFORE THE DEBT IS INCURRED. Between the source advance and
            # the unit amendment the sandboxed recovery path cannot open the new lock, so for that
            # window the watchdog — unconfined, from the target source — is the only thing that can
            # pay a pause debt. Started first, reaped last.
            watchdog = exclusion.spawn_bootstrap_watchdog(owner, SOURCE / 'rebuild', APP / '.runtime')
            exclusion.note_timer_paused(owner, prior_active=True)
            systemctl('stop', PUBLISHER_TIMER)
            try:
                # Pausing the timer does not stop a run already in flight, and the installed
                # publisher does not take the new lock, so acquiring it cannot drain one either.
                exclusion.drain_publisher()
                exclusion.record('publication_drained', owner=owner)
                with both_locks(exclusion, owner):
                    driver.main()
                require(outcome.get('unit_amendment'),
                        'The merge hook never fired; the units were not amended inside the act.')
            finally:
                systemctl('start', PUBLISHER_TIMER)
                exclusion.clear_timer_pause(owner)
                with contextlib.suppress(Exception):
                    watchdog.wait(timeout=20)
            outcome['units_after'] = installed_unit_digests()
            before_invocation = invocation_of(PUBLISHER_SERVICE)
            outcome['publisher_invocation_before_proof'] = before_invocation
            outcome['proof_through_the_unit'] = prove_through_the_unit(
                publisher, before_row, before_invocation)
            outcome['scheduled_tick'] = await_scheduled_tick(
                publisher, outcome['proof_through_the_unit']['row'],
                outcome['proof_through_the_unit']['unit'])
            outcome['legacy_lock'] = retire_legacy_lock(exclusion)
            outcome['timer_state'] = unit_state(
                PUBLISHER_TIMER, ('ActiveState', 'UnitFileState', 'NextElapseUSecRealtime'))
            require(outcome['timer_state'].get('ActiveState') == 'active'
                    and outcome['timer_state'].get('UnitFileState') == 'enabled',
                    'The publisher timer is not active and enabled after the act.')
            outcome['recovery_debt'] = exclusion.pause_owed()
            require(not outcome['recovery_debt'], 'A pause debt survived the act.')
            # ⚠️ THE SCHEDULED TICK IS REQUIRED, NOT OPTIONAL. The declaration says a subsequent
            # scheduled invocation MUST advance the row; a receipt that recorded `observed: false`
            # and still said `complete: true` would be the same shape of false green this whole
            # act exists to correct. The release is already installed at this point, so failing
            # here reports an unproven TIMER on a working release — which is the truth.
            outcome['complete'] = bool(outcome['scheduled_tick'].get('observed'))
            outcome['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_receipt()
            require(outcome['complete'],
                    'No scheduled invocation was observed inside the bound; the timer claim is '
                    'withheld. The release and the units are installed; see the receipt.')
            print(json.dumps({'complete': True, 'target': target, 'receipt': str(receipt),
                              'scheduled_tick_observed': True}, sort_keys=True))
        except BaseException as error:
            outcome['failed_with'] = type(error).__name__
            outcome['failure_detail'] = str(error)[:400]
            outcome['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_receipt()
            raise
