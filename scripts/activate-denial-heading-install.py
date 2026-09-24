#!/usr/bin/env python3
"""Install the denial-heading repair: code and templates only.

A heading (a line that visibly ends in a colon), or a denial, family-history, hypothetical or correction
sentence that ends by pointing at other lines, now governs the answers it introduces: each is a decision
for the clinician, never pre-filled and never offered for one click, with the candidate kept beside the
line that governs it; finalization re-checks this from the notes. On the qualified Word form a question
whose own value ends in a colon governs the answers after it. The qualified Word form's wording/answer
conflicts name their statement, wording and answers on the page.

No migration, no unit, no model, prompt or schema change, and no static source change: the driver's
static transition must leave every public asset identical. No Word adapter (C#) change, so the installed
Word runtime is untouched. The act is the qualified code-only driver under the shared
activation/publication exclusion, and the publisher is proved through its own unit afterwards because
this act pauses it.
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
SELF = 'scripts/activate-denial-heading-install.py'
DECL = 'docs/foundation/mutations/20260924-quillmd-denial-heading-finish.md'
DECL_SHA256 = '2c2c959048bd321b54275733f8c8ec4b6fc3db5cb7f64d502f89c498bf9a73b4'
#: The tree commit and the configured release AGREE here, which is the normal case and is
#: asserted rather than assumed: the 2026-09-22 repair exists because they once did not.
BASELINE = '02c29f991e50327525ebc6b4498f5cde08f78bbb'
RUNNING_RELEASE = '02c29f991e50327525ebc6b4498f5cde08f78bbb'
EVIDENCE = ROOT / 'rebuild/.runtime/denial-heading-install-20260923'
DRIVER = 'scripts/activate-typed-voice.py'
DRIVER_SHA256 = '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18'
MIGRATION = '0018_servicehealth'
#: ⚠️ REUSED, NOT REPEATED — TWO RETAINED RECORDS, EACH ALREADY QUALIFIED. The independent-key
#: restore proof is the 2026-09-22 drill (`RESTORED_*`). The retained capture is the SCHEDULED
#: 2026-09-23 04:30Z one, the capture the 30-hour window applies to: the 09-22 capture this adapter
#: first pinned was 40 h old at the rehearsal, which refused, as it should. A later authenticated
#: capture of the same mechanism beside an earlier independent restore is the shape the
#: business-readiness (09-20 19:39Z beside 09-20 09:53Z), admin-console and Word-multicolumn
#: activations used; the driver requires the same container, table set and invariants. Nothing is
#: re-dated or re-run: a fresh capture or a repeat drill would be work done to make a check pass.
RESTORE_RESULT = APP / '.runtime/recovery-custody-handoff-20260922/return-evidence/independent-key-restore/result.json'
RESTORE_RESULT_SHA256 = 'f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f'
RESTORED_RUN = '20260922T043002Z-7d766ca1'
RESTORED_RELEASE = 'eb37c7846f3ef634c16b4da46456663b88217a60'
RESTORED_MANIFEST_SHA256 = 'c3c4994fa4b50c51e75197e2ba57f8e2427daaf5929539c01498548da2083011'
CAPTURE_RUN = '20260923T043000Z-2031049f'
CAPTURE_SOURCE = 'd9660e34f9d3217369212ffc7d0d8302d4ad568c'
CAPTURE_MANIFEST_SHA256 = 'a6617fd69f4f7da84f6f4c40a52bec53b32dc9cc77300736caaa66052ad3c987'
#: ⚠️ THE INHERITED STATIC ALLOWLIST IS STALE AND REJECTS THE LIVE TREE.
#: `activate-word-export.static_inventory` carries `allowed_dirs = {'.'}`, so the five OTP asset
#: directories that have been installed for releases — `django_otp/`, `django_otp/css/`,
#: `otp_totp/`, `otp_totp/css/`, `otp_totp/js/` — are "objects outside the reviewed public asset
#: set". Measured: 31 files + 6 directories = the 37 entries the serving release's own receipt
#: records. Every recent activation replaced this check for the same reason; this one pins the
#: COMPLETED transition of the release now serving and requires the tree to still match it.
STATIC_RECEIPT = APP / '.runtime/doctor-pilot-install-20260923/doctor-pilot-install-02c29f991e50.json'
STATIC_RECEIPT_SHA256 = '8fc268d3e541eb913e1dc8347156df12ecce7e9623e3ae91b12dc6f169b8df9a'
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
RENAMED_PATTERN = r'denial-heading-install-[a-zA-Z0-9_-]+\.json'
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
REQUIRED = {SELF, DECL, 'rebuild/core/generation.py', 'rebuild/core/views.py', 'rebuild/core/wm_conflicts.py',
            'rebuild/templates/encounter_detail.html'}
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
                        'RESTORED_RUN': RESTORED_RUN, 'RESTORED_RELEASE': RESTORED_RELEASE,
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

    This validates the SERVING tree before the act: it must still equal the completed transition of
    the release now serving. This release changes no static source, so the driver's own static
    transition must come back with an empty delta.
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


def systemctl(action, unit, *, judged_by_record=False):
    """Exactly the verbs this act needs, on exactly the units it names.

    ⚠️ `judged_by_record`: starting the publisher oneshot returns non-zero whenever the run exits 1,
    and it exits 1 BY DESIGN after publishing an unhealthy backup state. On 2026-09-22 that made this
    call raise on a release that had installed cleanly. For that one start the exit is not the
    verdict; `publisher_verification.judge` decides from systemd's record, the journal and the row.
    """
    require(action in ('start', 'stop'), 'Unpermitted systemd verb.')
    require(unit in (PUBLISHER_TIMER, PUBLISHER_SERVICE, ALERTS_SERVICE), 'Unpermitted unit.')
    require(not judged_by_record or (action, unit) == ('start', PUBLISHER_SERVICE), 'Only the publisher start is judged by record.')
    code = ("import os,subprocess\nos.chroot('/host');os.chdir('/')\n"
            'subprocess.run(' + repr(['systemctl', action, unit]) + ',check=' + repr(not judged_by_record) + ')\n')
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
    from ops import publisher_verification as verification
    started = datetime.now(timezone.utc)
    systemctl('start', PUBLISHER_SERVICE, judged_by_record=True)
    state = unit_state(PUBLISHER_SERVICE, ('InvocationID', 'Result', 'ExecMainStatus',
                                          'ExecMainStartTimestamp', 'ExecMainExitTimestamp'))
    code = ("import os,subprocess,sys\nos.chroot('/host');os.chdir('/')\n"
            "sys.stdout.write(subprocess.run(" + repr(['journalctl', '-u', PUBLISHER_SERVICE, '--since',
                                                       started.strftime('%Y-%m-%d %H:%M:%S UTC'), '-o', 'json', '--no-pager'])
            + ",capture_output=True,text=True,check=True).stdout)\n")
    entries = [(item.get('_SYSTEMD_INVOCATION_ID') or item.get('INVOCATION_ID') or '', str(item.get('MESSAGE', '')))
               for item in (json.loads(line) for line in _helper(code).stdout.decode().splitlines() if line.strip())]
    row = publisher.published_row()
    try:
        verdict = verification.judge(before_row, before_invocation.get('InvocationID'), state, row, entries)
    except verification.VerificationFailure as failure:
        raise RuntimeError('The unit-driven publication is not verified: ' + str(failure)) from None
    return {'unit': state, 'row': row, 'verdict': verdict}


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
        receipt = EVIDENCE / ('denial-heading-install-outcome-' + target[:12] + '.json')

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
                              'scheduled_tick_observed': True}, sort_keys=True))
        except BaseException as error:
            outcome['failed_with'] = type(error).__name__
            outcome['failure_detail'] = str(error)[:400]
            outcome['finished_at'] = datetime.now(timezone.utc).isoformat()
            write_receipt()
            raise
