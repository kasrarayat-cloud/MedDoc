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
SELF = 'scripts/activate-recovery-hook-install.py'
DECL = 'docs/foundation/mutations/20260922-quillmd-recovery-hook-install.md'
DECL_SHA256 = 'a4da88d1101741b4871e0394cf05359fa0679346209522895aad128c99746d27'
#: The tree commit and the configured release AGREE here, which is the normal case and is
#: asserted rather than assumed: the 2026-09-22 repair exists because they once did not.
BASELINE = '411d57bd338e85daa9547a3f2c8689412179e111'
RUNNING_RELEASE = '411d57bd338e85daa9547a3f2c8689412179e111'
EVIDENCE = ROOT / 'rebuild/.runtime/recovery-hook-install-20260922'
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
STATIC_RECEIPT = APP / '.runtime/publication-install-20260922/publication-install-411d57bd338e.json'
STATIC_RECEIPT_SHA256 = 'eb974256188f89790f29322d9bdbc7f7dd7047fc238bfb2301eb04fc87c27a48'
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
RENAMED_PATTERN = r'recovery-hook-install-[a-zA-Z0-9_-]+\.json'
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
REQUIRED = {SELF, DECL, 'rebuild/ops/backup_alerts.py'}
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


def recovery_ledger_state():
    """⚠️ THE EVIDENCE THIS ACT IS JUDGED ON. Before the release the hook recorded a
    ModuleNotFoundError on EVERY tick; after it, ticks must add none."""
    path = APP / '.runtime/backup-alerts/recovery-failures.jsonl'
    if not path.exists():
        return {'exists': False, 'records': 0, 'last': None}
    lines = [x for x in path.read_text().splitlines() if x.strip()]
    return {'exists': True, 'records': len(lines),
            'last': json.loads(lines[-1]) if lines else None}


if __name__ == '__main__':
    if '--execute' not in sys.argv:
        driver.main()
    else:
        EVIDENCE.mkdir(mode=0o700, exist_ok=True)
        sys.path.insert(0, str(SOURCE / 'rebuild'))
        from ops import activation_exclusion as exclusion
        from ops import install_operations_publisher as publisher
        publisher.scope()
        bound = exclusion.bind_runtime(APP / '.runtime')
        require(bound['lock'].startswith(str(APP / '.runtime')), 'Exclusion bound outside the installed runtime.')
        require(bound['helper_pin'].startswith(str(APP / '.runtime')), 'Helper pin bound outside the installed runtime.')
        target = sys.argv[sys.argv.index('--target') + 1]
        require(re.fullmatch('[a-f0-9]{40}', target), 'Full reviewed target commit required.')
        owner = 'activation:' + target[:12]
        outcome = {'adapter': SELF, 'declaration': DECL, 'declaration_sha256': DECL_SHA256,
                   'baseline': BASELINE, 'running_release_before': RUNNING_RELEASE, 'target': target,
                   'started_at': datetime.now(timezone.utc).isoformat(), 'provider_calls': 0,
                   'fresh_backup_or_restore_performed': False, 'units_installed': 0, 'complete': False,
                   'driver_receipt': sys.argv[sys.argv.index('--result') + 1]
                   if '--result' in sys.argv else None}
        receipt = EVIDENCE / ('recovery-hook-install-outcome-' + target[:12] + '.json')

        def write_receipt():
            with contextlib.suppress(Exception):
                fd = os.open(receipt, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(outcome, stream, indent=1, sort_keys=True, default=str)

        try:
            outcome['recovery_ledger_before'] = recovery_ledger_state()
            outcome['units_before'] = {u: sha((SYSTEMD / u).read_bytes()) for u in AMENDED_UNITS}
            before_row = publisher.published_row()
            outcome['published_row_before'] = before_row
            watchdog = exclusion.spawn_bootstrap_watchdog(owner, SOURCE / 'rebuild', APP / '.runtime')
            exclusion.note_timer_paused(owner, prior_active=True)
            systemctl('stop', PUBLISHER_TIMER)
            try:
                exclusion.drain_publisher()
                exclusion.record('publication_drained', owner=owner)
                #: ⚠️ ONE LOCK, NOT TWO. The publication install moved every participant onto the
                #: granted directory, so the installed code and the code being installed lock the
                #: SAME path. The dual hold that act needed would be theatre here.
                with exclusion.hold(owner):
                    driver.main()
            finally:
                systemctl('start', PUBLISHER_TIMER)
                exclusion.clear_timer_pause(owner)
                with contextlib.suppress(Exception):
                    watchdog.wait(timeout=20)
            outcome['units_after'] = {u: sha((SYSTEMD / u).read_bytes()) for u in AMENDED_UNITS}
            require(outcome['units_after'] == outcome['units_before'],
                    'This release installs no unit; a unit changed anyway.')
            before_invocation = invocation_of(PUBLISHER_SERVICE)
            outcome['proof_through_the_unit'] = prove_through_the_unit(
                publisher, before_row, before_invocation)
            outcome['scheduled_tick'] = await_scheduled_tick(
                publisher, outcome['proof_through_the_unit']['row'],
                outcome['proof_through_the_unit']['unit'])
            outcome['timer_state'] = unit_state(
                PUBLISHER_TIMER, ('ActiveState', 'UnitFileState', 'NextElapseUSecRealtime'))
            require(outcome['timer_state'].get('ActiveState') == 'active'
                    and outcome['timer_state'].get('UnitFileState') == 'enabled',
                    'The publisher timer is not active and enabled after the act.')
            outcome['recovery_debt'] = exclusion.pause_owed()
            require(not outcome['recovery_debt'], 'A pause debt survived the act.')
            outcome['recovery_ledger_after'] = recovery_ledger_state()
            outcome['complete'] = bool(outcome['scheduled_tick'].get('observed'))
            outcome['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_receipt()
            require(outcome['complete'],
                    'No scheduled invocation was observed inside the bound; the timer claim is withheld.')
            print(json.dumps({'complete': True, 'target': target, 'receipt': str(receipt),
                              'scheduled_tick_observed': True,
                              'recovery_failures_before': outcome['recovery_ledger_before']['records'],
                              'recovery_failures_after': outcome['recovery_ledger_after']['records']},
                             sort_keys=True))
        except BaseException as error:
            outcome['failed_with'] = type(error).__name__
            outcome['failure_detail'] = str(error)[:400]
            outcome['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_receipt()
            raise
